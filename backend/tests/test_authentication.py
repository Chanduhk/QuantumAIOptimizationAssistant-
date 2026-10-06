import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.db import get_db
from backend.app.models.auth import AuthSession
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.models.auth import User
from backend.app.memory.vector_memory import VectorMemorySystem
from backend.main import app
from backend.app.services.auth_service import CSRF_COOKIE, SESSION_COOKIE, utc_now


@pytest.fixture
def auth_environment():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, session_factory
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def register(client: TestClient, email: str = "person@example.com", password: str = "correct horse battery"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def csrf_headers(client: TestClient) -> dict[str, str]:
    csrf = client.cookies.get(CSRF_COOKIE)
    return {"X-CSRF-Token": csrf} if csrf else {}


def test_register_creates_account_and_secure_session_cookie(auth_environment):
    client, _ = auth_environment
    response = register(client)
    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["email"] == "person@example.com"
    assert "password" not in payload
    assert client.cookies.get(SESSION_COOKIE)
    assert client.cookies.get(CSRF_COOKIE)
    assert "httponly" in response.headers.get("set-cookie", "").lower()


def test_password_is_hashed_and_registration_does_not_adopt_legacy_user_bucket(auth_environment):
    client, session_factory = auth_environment
    session = session_factory()
    session.add(Task(user_id=1, title="Legacy task", task_type="work", priority=2, completed=False))
    session.commit()
    session.close()

    response = register(client)
    assert response.status_code == 201
    new_user_id = response.json()["user"]["id"]
    assert new_user_id != 1
    session = session_factory()
    stored_user = session.query(User).filter(User.id == new_user_id).one()
    assert stored_user.password_hash.startswith("scrypt$")
    assert "correct horse battery" not in stored_user.password_hash
    session.close()


def test_duplicate_user_is_rejected(auth_environment):
    client, _ = auth_environment
    assert register(client).status_code == 201
    duplicate = client.post(
        "/api/v1/auth/register", json={"email": "PERSON@example.com", "password": "another safe password"}
    )
    assert duplicate.status_code == 409


def test_login_success_and_invalid_credentials(auth_environment):
    client, _ = auth_environment
    register(client)
    client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    success = client.post(
        "/api/v1/auth/login", json={"email": "PERSON@example.com", "password": "correct horse battery"}
    )
    assert success.status_code == 200
    assert success.json()["user"]["email"] == "person@example.com"
    invalid = client.post(
        "/api/v1/auth/login", json={"email": "person@example.com", "password": "wrong password!"}
    )
    assert invalid.status_code == 401


def test_current_user_and_protected_endpoint_require_authentication(auth_environment):
    client, _ = auth_environment
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/tasks?user_id=12").status_code == 401
    response = register(client)
    user_id = response.json()["user"]["id"]
    assert client.get("/api/v1/auth/me").json()["id"] == user_id
    assert client.get(f"/api/v1/tasks?user_id={user_id}").status_code == 200


def test_invalid_and_expired_sessions_are_rejected(auth_environment):
    client, session_factory = auth_environment
    client.cookies.set(SESSION_COOKIE, "invalid-token", path="/api/v1")
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    register(client)
    session = session_factory()
    record = session.query(AuthSession).one()
    record.expires_at = utc_now() - timedelta(seconds=1)
    session.commit()
    session.close()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_revokes_session(auth_environment):
    client, _ = auth_environment
    register(client)
    response = client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert response.status_code == 200
    assert response.json()["logged_out"] is True
    assert client.get("/api/v1/auth/me").status_code == 401


def test_task_access_is_scoped_to_authenticated_user(auth_environment):
    first, _ = auth_environment
    first_user = register(first, "one@example.com").json()["user"]["id"]
    second = TestClient(app)
    second_user = register(second, "two@example.com").json()["user"]["id"]

    created = first.post(
        "/api/v1/tasks",
        headers=csrf_headers(first),
        json={
            "user_id": first_user,
            "title": "Private task",
            "task_type": "work",
            "priority": 2,
            "estimated_duration": 30,
            "estimated_duration_unit": "minutes",
        },
    )
    assert created.status_code == 200
    task_id = created.json()["result"]["task"]["id"]
    assert second.get(f"/api/v1/tasks?user_id={second_user}").json()["tasks"] == []
    assert second.get(f"/api/v1/tasks/{task_id}?user_id={second_user}").status_code == 404
    assert second.get(f"/api/v1/tasks?user_id={first_user}").status_code == 403


def test_authenticated_writes_require_csrf_token(auth_environment):
    client, _ = auth_environment
    user_id = register(client).json()["user"]["id"]
    response = client.post(
        "/api/v1/tasks",
        json={"user_id": user_id, "title": "Task", "task_type": "work", "estimated_duration": 20},
    )
    assert response.status_code == 403


def test_user_id_body_without_content_type_is_rejected(auth_environment):
    client, session_factory = auth_environment
    register(client)
    response = client.post(
        "/api/v1/tasks",
        content=json.dumps({
            "user_id": 1,
            "title": "Forged owner",
            "task_type": "work",
            "priority": 2,
            "estimated_duration": 30,
            "estimated_duration_unit": "minutes",
        }),
        headers=csrf_headers(client),
    )
    assert response.status_code == 422
    session = session_factory()
    assert session.query(Task).filter(Task.user_id == 1).count() == 0
    session.close()


def test_user_id_body_scope_covers_json_suffix_media_types(auth_environment):
    client, session_factory = auth_environment
    register(client)
    response = client.post(
        "/api/v1/tasks",
        content=json.dumps({
            "user_id": 1,
            "title": "Forged JSON owner",
            "task_type": "work",
            "priority": 2,
            "estimated_duration": 30,
            "estimated_duration_unit": "minutes",
        }),
        headers={**csrf_headers(client), "Content-Type": "application/problem+json"},
    )
    assert response.status_code == 403
    session = session_factory()
    assert session.query(Task).filter(Task.user_id == 1).count() == 0
    session.close()


def test_user_id_body_scope_rejects_boolean_integer_coercion(auth_environment):
    client, session_factory = auth_environment
    register(client)
    response = client.post(
        "/api/v1/tasks",
        headers=csrf_headers(client),
        json={
            "user_id": True,
            "title": "Boolean owner",
            "task_type": "work",
            "priority": 2,
            "estimated_duration": 30,
            "estimated_duration_unit": "minutes",
        },
    )
    assert response.status_code == 403
    session = session_factory()
    assert session.query(Task).filter(Task.user_id == 1).count() == 0
    session.close()


def test_semantic_memory_search_filters_by_authenticated_owner(tmp_path):
    memory = VectorMemorySystem(storage_directory=str(tmp_path), model_name=None)
    memory.store_memory("private scheduling note", {"user_id": 101})
    memory.store_memory("private scheduling note", {"user_id": 202})
    results = memory.search_similar_tasks("private scheduling note", user_id=101)
    assert results
    assert all(item["metadata"]["user_id"] == 101 for item in results)
