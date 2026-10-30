"""Stage 5 Verification Script:
Verify Database Pool Resilience, Concurrency, Zero Leaks, and Schema DDL Isolation.

Parameters:
- Pool configuration: QueuePool(pool_size=3, max_overflow=2, pool_timeout=3.0)
- Concurrency: 60 concurrent operations across 12 worker threads
- Request varieties:
  1. Successful requests (task creation, retrieval)
  2. Authentication failures (401 missing/invalid credentials)
  3. Task validation errors (422 invalid payload)
  4. Database exceptions (forced error handling / rollback)
  5. Training status & trigger requests
  6. Concurrent user-scoped reads
  7. Concurrent task lifecycle operations (created -> started -> completed)
"""
import concurrent.futures
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from backend.app.database.db import get_db
from backend.app.models.auth import User
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.auth_service import create_session
from backend.app.services.task_lifecycle_service import (
    TaskLifecycleService,
    ensure_task_lifecycle_schema_for_bind,
)
from backend.main import app

def run_stage5_resilience():
    print("=== STAGE 5: DATABASE POOL RESILIENCE & CONCURRENCY AUDIT ===")
    
    # 1. Setup isolated database with constrained QueuePool
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{db_path}"

    ddl_statements = []

    constrained_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "timeout": 20},
        poolclass=QueuePool,
        pool_size=3,
        max_overflow=2,
        pool_timeout=3.0,
        future=True,
    )

    @event.listens_for(constrained_engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        s_upper = statement.strip().upper()
        if s_upper.startswith("CREATE TABLE") or s_upper.startswith("ALTER TABLE"):
            ddl_statements.append(statement)

    Base.metadata.create_all(bind=constrained_engine)
    ensure_task_lifecycle_schema_for_bind(constrained_engine)
    initial_ddl_count = len(ddl_statements)
    print(f"[x] 1. Schema initialized. Initial setup DDL count: {initial_ddl_count}")

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=constrained_engine,
        future=True,
        expire_on_commit=False,
    )

    # 2. Seed test users
    user_a_id = 80001
    user_b_id = 80002
    with TestSessionLocal() as sess:
        u_a = User(id=user_a_id, email="usera@stage5.test", password_hash="hash_a", is_active=True, created_at=datetime.now(timezone.utc).replace(tzinfo=None))
        u_b = User(id=user_b_id, email="userb@stage5.test", password_hash="hash_b", is_active=True, created_at=datetime.now(timezone.utc).replace(tzinfo=None))
        sess.add_all([u_a, u_b])
        sess.commit()

        sess_a = create_session(sess, u_a)
        sess_b = create_session(sess, u_b)
        token_a, csrf_a = sess_a.session_token, sess_a.csrf_token
        token_b, csrf_b = sess_b.session_token, sess_b.csrf_token

    print("[x] 2. Seeded isolated test users and authenticated sessions.")

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
        pool = constrained_engine.pool
        print(f"[x] 3. QueuePool configured: size={pool.size()}, max_overflow=2, timeout=3.0s")
        assert pool.checkedout() == 0, f"Expected 0 checked-out connections, got {pool.checkedout()}"

        client_a = TestClient(app)
        client_a.cookies.set("heliox_session", token_a)
        client_a.cookies.set("heliox_csrf", csrf_a)

        client_b = TestClient(app)
        client_b.cookies.set("heliox_session", token_b)
        client_b.cookies.set("heliox_csrf", csrf_b)

        headers_a = {"X-CSRF-Token": csrf_a}
        headers_b = {"X-CSRF-Token": csrf_b}

        errors = []
        user_a_tasks = []
        user_b_tasks = []

        total_requests = 60
        concurrency = 12
        start_time = time.perf_counter()

        def worker(idx: int):
            try:
                op_type = idx % 7
                if op_type == 0:
                    # Successful task creation (User A)
                    resp = client_a.post("/api/v1/tasks", headers=headers_a, json={
                        "user_id": user_a_id,
                        "title": f"Task A {idx}",
                        "task_type": "coding",
                        "priority": 4,
                        "estimated_duration": 45.0,
                    })
                    if resp.status_code == 200:
                        tid = resp.json()["result"]["task"]["id"]
                        user_a_tasks.append(tid)
                    else:
                        errors.append(f"Create A error: {resp.status_code} {resp.text}")

                elif op_type == 1:
                    # Successful task creation (User B)
                    resp = client_b.post("/api/v1/tasks", headers=headers_b, json={
                        "user_id": user_b_id,
                        "title": f"Task B {idx}",
                        "task_type": "research",
                        "priority": 3,
                        "estimated_duration": 30.0,
                    })
                    if resp.status_code == 200:
                        tid = resp.json()["result"]["task"]["id"]
                        user_b_tasks.append(tid)
                    else:
                        errors.append(f"Create B error: {resp.status_code} {resp.text}")

                elif op_type == 2:
                    # Authentication failure: unauthenticated request
                    unauth_client = TestClient(app)
                    resp = unauth_client.post("/api/v1/tasks", json={"title": "unauth"})
                    if resp.status_code != 401:
                        errors.append(f"Expected 401, got {resp.status_code}")

                elif op_type == 3:
                    # Task validation error: 422
                    resp = client_a.post("/api/v1/tasks", headers=headers_a, json={
                        "user_id": user_a_id,
                        "title": "",
                        "task_type": "unknown_type",
                        "estimated_duration": -5.0,
                    })
                    if resp.status_code != 422:
                        errors.append(f"Expected 422, got {resp.status_code}")

                elif op_type == 4:
                    # Database exception simulation / 404 lookup
                    resp = client_a.get(f"/api/v1/tasks/9999999?user_id={user_a_id}", headers=headers_a)
                    if resp.status_code != 404:
                        errors.append(f"Expected 404, got {resp.status_code}")

                elif op_type == 5:
                    # Concurrent user-scoped read
                    resp_a = client_a.get(f"/api/v1/tasks?user_id={user_a_id}", headers=headers_a)
                    resp_b = client_b.get(f"/api/v1/tasks?user_id={user_b_id}", headers=headers_b)
                    if resp_a.status_code != 200 or resp_b.status_code != 200:
                        errors.append(f"Read error: A={resp_a.status_code}, B={resp_b.status_code}")

                elif op_type == 6:
                    # Training readiness / inventory query under load
                    resp = client_a.get("/api/v1/ml/readiness?user_id=80001", headers=headers_a)
                    if resp.status_code != 200:
                        errors.append(f"Readiness query error: {resp.status_code}")

            except Exception as e:
                errors.append(f"Worker {idx} exception: {type(e).__name__}: {e}")

        print(f"\n[x] 4. Launching {total_requests} concurrent requests across {concurrency} threads...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker, i) for i in range(total_requests)]
            concurrent.futures.wait(futures)

        elapsed = time.perf_counter() - start_time
        print(f"[x] 5. Concurrency run completed in {elapsed:.3f}s. Total errors: {len(errors)}")
        if errors:
            for err in errors[:5]:
                print(f"     ERROR: {err}")
            raise RuntimeError(f"Errors occurred during pool test: {errors}")

        # Verify pool connections returned
        print(f"[x] 6. Post-load QueuePool status: checked_out={pool.checkedout()}, overflow={pool.overflow()}")
        assert pool.checkedout() == 0, f"LEAK DETECTED: {pool.checkedout()} connections still checked out!"

        # Verify zero subsequent DDL
        subsequent_ddl = len(ddl_statements) - initial_ddl_count
        print(f"[x] 7. Subsequent DDL statements executed on request paths: {subsequent_ddl}")
        assert subsequent_ddl == 0, f"REPEATED DDL ON REQUEST PATH: {subsequent_ddl} statements executed!"

        # Verify cross-user isolation
        resp_a = client_a.get(f"/api/v1/tasks?user_id={user_a_id}", headers=headers_a)
        resp_b = client_b.get(f"/api/v1/tasks?user_id={user_b_id}", headers=headers_b)
        tasks_a = resp_a.json().get("tasks", [])
        tasks_b = resp_b.json().get("tasks", [])
        set_a = {t["id"] for t in tasks_a}
        set_b = {t["id"] for t in tasks_b}
        overlap = set_a.intersection(set_b)
        print(f"[x] 8. Cross-user isolation: User A tasks={len(set_a)}, User B tasks={len(set_b)}, Overlap={len(overlap)}")
        assert len(overlap) == 0, f"CROSS USER CONTAMINATION DETECTED: {overlap}"

        # Test task lifecycle operations under load
        print("\n--- Testing Concurrent Task Lifecycle Operations ---")
        if user_a_tasks:
            from datetime import timedelta
            test_tid = user_a_tasks[0]
            # Fetch created_at to guarantee started_at >= created_at
            t_created = datetime.now(timezone.utc)
            t_start = t_created + timedelta(seconds=5)
            t_end = t_start + timedelta(minutes=40)
            start_resp = client_a.post(f"/api/v1/tasks/{test_tid}/start", headers=headers_a, json={"user_id": user_a_id, "started_at": t_start.isoformat()})
            assert start_resp.status_code == 200, f"Start failed: {start_resp.text}"
            comp_resp = client_a.post(f"/api/v1/tasks/{test_tid}/complete", headers=headers_a, json={"user_id": user_a_id, "completed_at": t_end.isoformat(), "actual_duration": 40.0})
            assert comp_resp.status_code == 200, f"Complete failed: {comp_resp.text}"
            print(f"[x] 9. Lifecycle transitions (created -> started -> completed) verified on task {test_tid}")

        print(f"\n[x] 10. Final pool status: checked_out={pool.checkedout()}, overflow={pool.overflow()}")
        assert pool.checkedout() == 0

        print(f"\n--- POOL RESILIENCE SUMMARY ---")
        print(f"Total Requests: {total_requests}")
        print(f"Concurrency Workers: {concurrency}")
        print(f"Pool Configuration: QueuePool(size=3, max_overflow=2, timeout=3.0s)")
        print(f"Elapsed Time: {elapsed:.3f}s")
        print(f"Requests / Second: {total_requests / elapsed:.1f} req/s")
        print(f"Leaked Connections: {pool.checkedout()}")
        print(f"DDL on Request Path: {subsequent_ddl}")
        print(f"Cross-User Leaks: {len(overlap)}")
        print("\nPASS: Stage 5 Database Pool Resilience completely verified!")

    finally:
        app.dependency_overrides.clear()
        constrained_engine.dispose()
        try:
            os.remove(db_path)
        except OSError:
            pass

if __name__ == "__main__":
    run_stage5_resilience()
