from __future__ import annotations

import concurrent.futures
import threading
import time
from datetime import datetime, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from backend.app.database.db import get_db, get_pool_status
from backend.app.models.auth import User
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.auth_service import CSRF_COOKIE, create_session, set_session_cookies
from backend.app.services.task_lifecycle_service import (
    TaskLifecycleService,
    _ENSURED_BINDS,
    ensure_task_lifecycle_schema_for_bind,
    is_schema_ensured,
    reset_schema_ensured_cache,
)
from backend.main import app


def test_schema_ensured_cache_prevents_per_request_ddl():
    """Verify that schema migration runs at most once per bind and avoids per-request DDL."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=test_engine)
    reset_schema_ensured_cache()

    SessionMaker = sessionmaker(bind=test_engine, future=True, expire_on_commit=False)
    session = SessionMaker()

    assert not is_schema_ensured(test_engine)

    # First instantiation should register the bind
    svc1 = TaskLifecycleService(session)
    assert is_schema_ensured(test_engine)

    # Second instantiation should recognize cached bind and do zero DDL
    bind_id = id(test_engine)
    assert bind_id in _ENSURED_BINDS
    svc2 = TaskLifecycleService(session)
    assert svc2 is not None

    session.close()
    test_engine.dispose()


def test_concurrent_authenticated_requests_do_not_exhaust_restricted_pool():
    """Verify that concurrent requests against a strict QueuePool(size=3, max_overflow=2)

    never suffer QueuePool exhaustion timeout errors.
    """
    import tempfile
    import os

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{db_path}"

    # Enforce a strictly restricted QueuePool: size 3, max_overflow 2, timeout 3s
    restricted_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "timeout": 15},
        poolclass=QueuePool,
        pool_size=3,
        max_overflow=2,
        pool_timeout=3.0,
        future=True,
    )
    Base.metadata.create_all(bind=restricted_engine)
    ensure_task_lifecycle_schema_for_bind(restricted_engine)

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=restricted_engine,
        future=True,
        expire_on_commit=False,
    )

    # Create a test user directly
    with TestSessionLocal() as init_sess:
        user = User(
            id=12345,
            email="pool_test@example.com",
            password_hash="test_hash",
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        init_sess.add(user)
        # Pre-seed 3 tasks
        for i in range(1, 4):
            task = Task(
                id=i,
                user_id=12345,
                title=f"Concurrent Task {i}",
                task_type="focus",
                priority=3,
                estimated_duration=30.0,
                completed=False,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                lifecycle_state="created",
            )
            init_sess.add(task)
        init_sess.commit()

        issued_session = create_session(init_sess, user)
        session_token = issued_session.session_token
        csrf_token = issued_session.csrf_token

    def override_get_db() -> Generator[Session, None, None]:
        sess = TestSessionLocal()
        try:
            yield sess
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        client.cookies.set("heliox_session", session_token)
        client.cookies.set("heliox_csrf", csrf_token)
        headers = {"X-CSRF-Token": csrf_token}

        # Concurrently fire 20 requests using 10 worker threads
        def make_request(req_id: int):
            c = TestClient(app)
            c.cookies.set("heliox_session", session_token)
            c.cookies.set("heliox_csrf", csrf_token)
            resp = c.get("/api/v1/tasks?user_id=12345", headers=headers)
            return resp.status_code, len(resp.json().get("tasks", []))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(20)]
            results = [f.result(timeout=10.0) for f in concurrent.futures.as_completed(futures)]

        for status, task_count in results:
            assert status == 200
            assert task_count == 3

    finally:
        app.dependency_overrides.clear()
        restricted_engine.dispose()
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_exception_paths_release_sessions_and_application_remains_usable():
    """Verify that simulated endpoint and middleware errors do not leak connections

    and that the application recovers cleanly.
    """
    import tempfile
    import os

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{db_path}"

    restricted_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "timeout": 15},
        poolclass=QueuePool,
        pool_size=2,
        max_overflow=1,
        pool_timeout=2.0,
        future=True,
    )
    Base.metadata.create_all(bind=restricted_engine)
    ensure_task_lifecycle_schema_for_bind(restricted_engine)

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=restricted_engine,
        future=True,
        expire_on_commit=False,
    )

    with TestSessionLocal() as init_sess:
        user = User(
            id=54321,
            email="exception_test@example.com",
            password_hash="test_hash",
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        init_sess.add(user)
        init_sess.commit()
        issued = create_session(init_sess, user)
        session_token = issued.session_token
        csrf_token = issued.csrf_token

    def override_get_db() -> Generator[Session, None, None]:
        sess = TestSessionLocal()
        try:
            yield sess
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        client.cookies.set("heliox_session", session_token)
        client.cookies.set("heliox_csrf", csrf_token)
        headers = {"X-CSRF-Token": csrf_token}

        # 1. Fire repeated 404 (non-existent task)
        for _ in range(5):
            res = client.get("/api/v1/tasks/999999?user_id=54321", headers=headers)
            assert res.status_code == 404

        # 2. Fire invalid auth request (no cookie)
        unauth_client = TestClient(app)
        for _ in range(5):
            res = unauth_client.get("/api/v1/tasks?user_id=54321")
            assert res.status_code == 401

        # 3. Fire invalid validation request
        for _ in range(5):
            res = client.post(
                "/api/v1/tasks",
                headers=headers,
                json={"user_id": 54321, "title": "", "task_type": "focus", "estimated_duration": -5},
            )
            assert res.status_code == 422

        # 4. Verify the application remains completely healthy and functional
        health_res = client.get("/api/v1/system/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "operational"
        assert health_res.json()["database_connected"] is True

        # 5. Create a real task after all exceptions
        create_res = client.post(
            "/api/v1/tasks",
            headers=headers,
            json={
                "user_id": 54321,
                "title": "Post Exception Task",
                "task_type": "writing",
                "priority": 3,
                "estimated_duration": 45.0,
            },
        )
        assert create_res.status_code == 200
        task_id = create_res.json()["result"]["task"]["id"]

        # 6. List tasks
        list_res = client.get("/api/v1/tasks?user_id=54321", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()["tasks"]) == 1

    finally:
        app.dependency_overrides.clear()
        restricted_engine.dispose()
        try:
            os.remove(db_path)
        except OSError:
            pass
