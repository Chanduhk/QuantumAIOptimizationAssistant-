import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app, OrchestratorTaskInput, ExecutivePlanRequest
from backend.app.database.db import get_db, SessionLocal
from backend.app.models.auth import User
from backend.app.models.task import Task
from backend.app.services.auth_service import CSRF_COOKIE
from backend.app.services.task_lifecycle_service import TaskLifecycleService
from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def register_user(client: TestClient, email: str = "dep_test@example.com") -> int:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure test password 123"},
    )
    if response.status_code == 201:
        return response.json()["user"]["id"]
    # If already registered, login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secure test password 123"},
    )
    assert login_resp.status_code == 200
    return login_resp.json()["user"]["id"]


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    if not token:
        # Get token from a GET endpoint
        client.get("/api/v1/system/health")
        token = client.cookies.get(CSRF_COOKIE)
    return {"X-CSRF-Token": token} if token else {}


def test_task_input_case_a_no_dependencies():
    """Case A: No dependencies -> Accepted with an empty dependency array."""
    task = OrchestratorTaskInput(
        id="1",
        title="Task A",
        type="general",
        priority=3,
        duration=30.0,
        depends_on_task_ids=[],
    )
    assert task.depends_on_task_ids == []
    assert task.dependencies == []

    # Also when omitted or None
    task_omitted = OrchestratorTaskInput(
        id="1",
        title="Task A",
        type="general",
        priority=3,
        duration=30.0,
    )
    assert task_omitted.depends_on_task_ids == []
    assert task_omitted.dependencies == []


def test_task_input_case_b_valid_dependency():
    """Case B: Valid dependency -> Accepted and string normalized."""
    task = OrchestratorTaskInput(
        id="2",
        title="Task B",
        type="general",
        priority=3,
        duration=30.0,
        depends_on_task_ids=["1"],
    )
    assert task.depends_on_task_ids == ["1"]


def test_task_input_case_c_multiple_dependencies():
    """Case C: Multiple dependencies -> All prerequisites preserved as strings."""
    task = OrchestratorTaskInput(
        id="3",
        title="Task C",
        type="general",
        priority=3,
        duration=30.0,
        depends_on_task_ids=["1", "2"],
    )
    assert task.depends_on_task_ids == ["1", "2"]


def test_task_input_case_d_empty_dependency_string_rejected():
    """Case D: Empty dependency entry -> Rejected with clear validation error."""
    with pytest.raises(ValueError, match="depends_on_task_ids must contain non-empty strings"):
        OrchestratorTaskInput(
            id="1",
            title="Task A",
            type="general",
            priority=3,
            duration=30.0,
            depends_on_task_ids=[""],
        )

    with pytest.raises(ValueError, match="depends_on_task_ids must contain non-empty strings"):
        OrchestratorTaskInput(
            id="1",
            title="Task A",
            type="general",
            priority=3,
            duration=30.0,
            depends_on_task_ids=["   "],
        )


def test_task_input_case_e_null_dependency_rejected():
    """Case E: Null dependency -> Rejected with clear validation error."""
    with pytest.raises(ValueError, match="depends_on_task_ids must contain non-empty strings"):
        OrchestratorTaskInput(
            id="1",
            title="Task A",
            type="general",
            priority=3,
            duration=30.0,
            depends_on_task_ids=[None],  # type: ignore
        )


def test_orchestrator_normalizes_numeric_dependencies():
    """Legacy or numeric dependency references from DB/API are safely stringified."""
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    normalized = orchestrator._normalize_tasks([
        {"id": 1, "title": "Prerequisite", "duration": 10.0, "priority": 1},
        {"id": 2, "title": "Dependent", "duration": 20.0, "priority": 2, "dependencies": [1]},
    ])
    assert normalized[0]["id"] == "1"
    assert normalized[1]["id"] == "2"
    assert normalized[1]["depends_on_task_ids"] == ["1"]


def test_endpoint_case_f_self_dependency_rejected(client):
    """Case F: Self-dependency -> HTTP 400 Bad Request."""
    uid = register_user(client, "dep_self@example.com")
    payload = {
        "user_id": uid,
        "tasks": [
            {
                "id": "100",
                "title": "Task 100",
                "type": "general",
                "priority": 3,
                "duration": 30.0,
                "depends_on_task_ids": ["100"],
            }
        ]
    }
    response = client.post("/api/v1/ai/executive-plan", json=payload, headers=csrf_headers(client))
    assert response.status_code == 400
    assert "cannot depend on itself" in response.json()["detail"]


def test_endpoint_case_g_circular_dependency_rejected(client):
    """Case G: Circular dependency -> HTTP 400 with cycle clearly reported."""
    uid = register_user(client, "dep_cycle@example.com")
    payload = {
        "user_id": uid,
        "tasks": [
            {
                "id": "101",
                "title": "Task 101",
                "type": "general",
                "priority": 3,
                "duration": 30.0,
                "depends_on_task_ids": ["102"],
            },
            {
                "id": "102",
                "title": "Task 102",
                "type": "general",
                "priority": 3,
                "duration": 30.0,
                "depends_on_task_ids": ["101"],
            }
        ]
    }
    response = client.post("/api/v1/ai/executive-plan", json=payload, headers=csrf_headers(client))
    assert response.status_code == 400
    assert "Circular dependency detected" in response.json()["detail"]


def test_endpoint_case_h_unauthorized_or_nonexistent_reference_rejected(client):
    """Case H: Dependency references a nonexistent or unauthorized task -> HTTP 400 without leaking data."""
    uid = register_user(client, "dep_unauth@example.com")
    payload = {
        "user_id": uid,
        "tasks": [
            {
                "id": "103",
                "title": "Task 103",
                "type": "general",
                "priority": 3,
                "duration": 30.0,
                "depends_on_task_ids": ["999999"],  # Nonexistent task ID
            }
        ]
    }
    response = client.post("/api/v1/ai/executive-plan", json=payload, headers=csrf_headers(client))
    assert response.status_code == 400
    assert "not found or unauthorized" in response.json()["detail"]


def test_endpoint_case_i_and_j_unselected_persisted_prerequisite(client, db_session: Session):
    """
    Case J: Selected task depends on a persisted task belonging to the user that is not selected.
    Case I: Completed prerequisite semantics.
    """
    uid = register_user(client, "dep_cases_ij@example.com")
    svc = TaskLifecycleService(db_session)

    # Create prerequisite task (open)
    prereq = svc.create_task(
        user_id=uid,
        title="Prereq Test Task",
        task_type="work",
        priority=3,
        estimated_duration=30.0,
        estimated_duration_unit="minutes",
    )
    prereq_id = str(prereq.id)

    # Request containing ONLY the dependent task, referencing prereq_id
    payload = {
        "user_id": uid,
        "tasks": [
            {
                "id": "99901",
                "title": "Dependent Task",
                "type": "work",
                "priority": 4,
                "duration": 45.0,
                "estimated_duration_unit": "minutes",
                "estimated_duration_source": "transient_request",
                "depends_on_task_ids": [prereq_id],
            }
        ]
    }

    try:
        response = client.post("/api/v1/ai/executive-plan", json=payload, headers=csrf_headers(client))
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # Prerequisite was open, so dependent task should be flagged as blocked
        dep_state = data["result"].get("executive_objectives", {}).get("dependency_state", {})
        assert "99901" in dep_state.get("blocked_tasks", [])

        # Case I: Now start and complete the prerequisite and verify it unblocks
        svc.start_task(task_id=prereq.id, user_id=uid)
        svc.complete_task(task_id=prereq.id, user_id=uid)
        response_completed = client.post("/api/v1/ai/executive-plan", json=payload, headers=csrf_headers(client))
        assert response_completed.status_code == 200
        dep_state_completed = response_completed.json()["result"].get("executive_objectives", {}).get("dependency_state", {})
        assert "99901" not in dep_state_completed.get("blocked_tasks", [])
    finally:
        # Cleanup test task
        try:
            svc.delete_task(task_id=prereq.id, user_id=uid)
        except Exception:
            pass
