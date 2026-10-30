import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as main
from backend.app.database.db import get_db
from backend.app.memory.vector_memory import VectorMemorySystem
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.auth_service import CSRF_COOKIE
from backend.app.services.task_lifecycle_service import TaskLifecycleService


@pytest.fixture
def f14_client(monkeypatch):
    monkeypatch.setattr(VectorMemorySystem, "_load_model", lambda self: None)
    monkeypatch.setattr(VectorMemorySystem, "preload_model_async", lambda model_name="all-MiniLM-L6-v2": None)
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

    main.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(main.app)
    try:
        yield client, session_factory
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def register_user(client: TestClient, email: str = "f14_user@example.com") -> int:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure f14 test password 123"},
    )
    assert response.status_code == 201
    return response.json()["user"]["id"]


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token
    return {"X-CSRF-Token": token}


def test_assistant_creates_real_task(f14_client):
    client, session_factory = f14_client
    user_id = register_user(client, "creator@example.com")

    response = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "Create task Write release documentation with priority 4 and duration 90 minutes",
            "days_back": 90,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "create_task"
    result = data["result"]
    assert result["action"] == "task_created"
    task = result["task"]
    assert task["title"] == "Write release documentation"
    assert task["priority"] == 4
    assert task["estimated_duration"] == 90.0
    assert task["estimated_duration_unit"] == "minutes"
    assert task["estimated_duration_source"] == "conversational_input"
    assert task["completed"] is False

    # Verify task exists in the database
    with session_factory() as session:
        db_task = session.query(Task).filter(Task.id == task["id"]).one_or_none()
        assert db_task is not None
        assert db_task.user_id == user_id
        assert db_task.title == "Write release documentation"


def test_assistant_lists_and_prioritizes_active_tasks(f14_client):
    client, session_factory = f14_client
    user_id = register_user(client, "list_prio@example.com")

    with session_factory() as session:
        service = TaskLifecycleService(session)
        service.create_task(
            user_id=user_id,
            title="Low priority bug",
            task_type="coding",
            priority=2,
            estimated_duration=30.0,
            estimated_duration_unit="minutes",
            estimated_duration_source="task_api",
        )
        service.create_task(
            user_id=user_id,
            title="Critical security patch",
            task_type="coding",
            priority=5,
            estimated_duration=60.0,
            estimated_duration_unit="minutes",
            estimated_duration_source="task_api",
        )

    # 1. List tasks
    list_resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={"user_id": user_id, "command": "List my pending tasks", "days_back": 90},
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["intent"] == "list_tasks"
    assert list_data["result"]["total_pending"] == 2

    # 2. Prioritize tasks
    prio_resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={"user_id": user_id, "command": "Which tasks should I complete first?", "days_back": 90},
    )
    assert prio_resp.status_code == 200
    prio_data = prio_resp.json()
    assert prio_data["intent"] == "prioritize_tasks"
    prioritized = prio_data["result"]["prioritized_tasks"]
    assert len(prioritized) == 2
    # Critical security patch (priority 5) must be ranked first
    assert prioritized[0]["title"] == "Critical security patch"


def test_natural_language_planning_with_user_tasks_and_feasible_schedule(f14_client):
    client, session_factory = f14_client
    user_id = register_user(client, "planner@example.com")

    with session_factory() as session:
        service = TaskLifecycleService(session)
        service.create_task(
            user_id=user_id,
            title="Database indexing optimization",
            task_type="analysis",
            priority=5,
            estimated_duration=60.0,
            estimated_duration_unit="minutes",
            estimated_duration_source="task_api",
        )
        service.create_task(
            user_id=user_id,
            title="API endpoint refactoring",
            task_type="coding",
            priority=4,
            estimated_duration=120.0,
            estimated_duration_unit="minutes",
            estimated_duration_source="task_api",
        )
        service.create_task(
            user_id=user_id,
            title="Frontend telemetry review",
            task_type="review",
            priority=3,
            estimated_duration=60.0,
            estimated_duration_unit="minutes",
            estimated_duration_source="task_api",
        )

    response = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "Plan my day around my three most important tasks",
            "days_back": 90,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "plan_day"
    res = data["result"]
    assert res["success"] is True

    schedule = res["schedule"]
    assert len(schedule) == 3

    # Multi-hour interval non-overlap validation
    for i in range(len(schedule) - 1):
        curr_task = schedule[i]
        next_task = schedule[i + 1]
        assert float(curr_task["scheduled_end_hour"]) <= float(next_task["scheduled_hour"])

    # Feasibility and provenance
    assert res["feasibility_status"] == "FEASIBLE"
    assert res["behavioral_provenance"] == "DETERMINISTIC_FALLBACK"
    assert "quantum_suitability" in res
    assert res["quantum_status"] in ("CLASSICAL_ONLY", "QUANTUM_CONSIDERED_BUT_REJECTED", "SIMULATED_LOCAL")


def test_overloaded_workload_detects_infeasibility_and_reports_unfitted_tasks(f14_client):
    client, session_factory = f14_client
    user_id = register_user(client, "overload@example.com")

    # Create 3 tasks of 2 hours each (total 6 hours)
    with session_factory() as session:
        service = TaskLifecycleService(session)
        for i in range(1, 4):
            service.create_task(
                user_id=user_id,
                title=f"Heavy task {i}",
                task_type="coding",
                priority=4,
                estimated_duration=120.0,
                estimated_duration_unit="minutes",
                estimated_duration_source="task_api",
            )

    # User asks to plan within 3 available hours
    response = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "I have 3 hours available today. Arrange my pending work.",
            "days_back": 90,
        },
    )
    assert response.status_code == 200
    data = response.json()
    res = data["result"]

    assert res["available_hours"] == 3.0
    assert res["total_demanded_hours"] == 6.0
    assert res["feasibility_status"] == "INFEASIBLE_OVERLOAD"
    assert len(res["infeasible_tasks"]) >= 1

    # Infeasible tasks must be explicitly flagged and not silently dropped
    all_scheduled = res["schedule"]
    assert len(all_scheduled) == 3
    for infeasible in res["infeasible_tasks"]:
        assert infeasible["fits_in_horizon"] is False
        assert infeasible["capacity_warning"] is not None


def test_plan_acceptance_persists_schedule_to_database(f14_client):
    client, session_factory = f14_client
    user_id = register_user(client, "acceptor@example.com")

    task_id = None
    with session_factory() as session:
        service = TaskLifecycleService(session)
        t = service.create_task(
            user_id=user_id,
            title="Task to be scheduled",
            task_type="coding",
            priority=4,
            estimated_duration=60.0,
            estimated_duration_unit="minutes",
            estimated_duration_source="task_api",
        )
        task_id = t.id
        assert t.start_time is None
        assert t.end_time is None

    # Call /api/v1/ai/plan/accept
    schedule_payload = [
        {
            "task_id": task_id,
            "title": "Task to be scheduled",
            "scheduled_hour": 10.0,
            "scheduled_end_hour": 11.0,
            "estimated_duration": 1.0,
        }
    ]

    accept_resp = client.post(
        "/api/v1/ai/plan/accept",
        headers=csrf_headers(client),
        json={"user_id": user_id, "schedule": schedule_payload},
    )
    assert accept_resp.status_code == 200
    accept_data = accept_resp.json()
    assert accept_data["result"]["action"] == "plan_accepted"
    assert task_id in accept_data["result"]["persisted_task_ids"]

    # Verify task in DB has updated start_time and end_time
    with session_factory() as session:
        updated_task = session.query(Task).filter(Task.id == task_id).one()
        assert updated_task.start_time is not None
        assert updated_task.end_time is not None
        assert updated_task.start_time.hour == 10
        assert updated_task.end_time.hour == 11


def test_user_isolation_blocks_cross_user_access(f14_client):
    client, _ = f14_client
    user_a_id = register_user(client, "user_a@example.com")
    other_user_id = user_a_id + 9999

    # Attempt to run command specifying another user's ID
    forbidden_resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={"user_id": other_user_id, "command": "Plan my day", "days_back": 90},
    )
    assert forbidden_resp.status_code == 403
    detail_resp = forbidden_resp.json()["detail"]
    assert "User isolation violation" in detail_resp or "does not match requested user" in detail_resp

    # Attempt to accept plan for another user's ID
    forbidden_accept = client.post(
        "/api/v1/ai/plan/accept",
        headers=csrf_headers(client),
        json={"user_id": other_user_id, "schedule": [{"task_id": 1, "scheduled_hour": 9}]},
    )
    assert forbidden_accept.status_code == 403
    detail_accept = forbidden_accept.json()["detail"]
    assert "User isolation violation" in detail_accept or "does not match requested user" in detail_accept
