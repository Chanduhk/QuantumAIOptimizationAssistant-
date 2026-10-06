from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as main
from backend.app.database.db import get_db
from backend.app.models.base import Base
from backend.app.services.auth_service import CSRF_COOKIE


@pytest.fixture
def authenticated_environment():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = main.app
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_account(client: TestClient, email: str) -> int:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure test password 123"},
    )
    assert response.status_code == 201
    return response.json()["user"]["id"]


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token
    return {"X-CSRF-Token": token}


def test_authenticated_task_lifecycle_and_user_isolation(authenticated_environment):
    client = authenticated_environment
    user_id = create_account(client, "f3-owner@example.com")
    now = datetime.now(timezone.utc)
    created = client.post(
        "/api/v1/tasks",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "title": "F3 task",
            "task_type": "focus",
            "priority": 4,
            "estimated_duration": 45,
            "estimated_duration_unit": "minutes",
            "created_at": (now - timedelta(hours=2)).isoformat(),
        },
    )
    assert created.status_code == 200
    task = created.json()["result"]["task"]
    task_id = task["id"]
    assert task["estimated_duration_unit"] == "minutes"
    assert task["estimated_duration_source"] == "task_api"

    assert client.get(f"/api/v1/tasks?user_id={user_id}").json()["tasks"][0]["id"] == task_id
    assert client.get(f"/api/v1/tasks/{task_id}?user_id={user_id}").status_code == 200

    started = client.post(
        f"/api/v1/tasks/{task_id}/start",
        headers=csrf_headers(client),
        json={"user_id": user_id, "started_at": (now - timedelta(hours=1)).isoformat()},
    )
    assert started.status_code == 200
    completed = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=csrf_headers(client),
        json={"user_id": user_id, "completed_at": now.isoformat()},
    )
    assert completed.status_code == 200
    assert completed.json()["result"]["task"]["actual_duration"] == pytest.approx(60.0)
    assert completed.json()["result"]["task"]["lifecycle_state"] == "completed"

    second_client = TestClient(main.app)
    second_user_id = create_account(second_client, "f3-other@example.com")
    assert second_client.get(f"/api/v1/tasks?user_id={second_user_id}").json()["tasks"] == []
    assert second_client.get(f"/api/v1/tasks/{task_id}?user_id={second_user_id}").status_code == 404
    assert second_client.get(f"/api/v1/tasks?user_id={user_id}").status_code == 403


def test_task_and_planning_routes_reject_unauthenticated_requests(authenticated_environment):
    client = authenticated_environment
    assert client.get("/api/v1/tasks?user_id=1").status_code == 401
    assert client.post(
        "/api/v1/ai/run-decision-pipeline",
        json={"user_id": 1, "goal": "plan my day", "days_back": 90},
    ).status_code == 401


def test_authenticated_planning_route_returns_backend_plan(authenticated_environment, monkeypatch):
    client = authenticated_environment
    user_id = create_account(client, "f3-planning@example.com")

    class StubPipeline:
        async def run_pipeline(self, *, goal_text: str, user_id: int):
            assert goal_text == "plan my day"
            assert user_id == client.get("/api/v1/auth/me").json()["id"]
            return {
                "tasks": [{"id": 5, "title": "Planning task", "estimated_duration": 30}],
                "schedule": [{"task_id": 5, "scheduled_hour": 9}],
                "predictions": [{"task_id": 5, "predicted_productivity": 0.7}],
            }

    monkeypatch.setattr(main, "_build_decision_pipeline", lambda db, days_back: StubPipeline())
    response = client.post(
        "/api/v1/ai/run-decision-pipeline",
        headers=csrf_headers(client),
        json={"user_id": user_id, "goal": "plan my day", "days_back": 90},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tasks"][0]["title"] == "Planning task"
    assert payload["schedule"][0]["scheduled_hour"] == 9
    assert payload["predictions"][0]["task_id"] == 5
