"""
F15 Comprehensive Test Suite: Intelligent Planning and Natural-Language Understanding
Tests multi-task extraction, relative/calendar deadline parsing, constraint-aware scheduling,
conversational refinement, safe persistence, duplicate prevention, and user isolation.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as main
from backend.app.database.db import get_db
from backend.app.interface.nl_extractor import (
    NaturalLanguageExtractor, 
    ExtractedPlanningContext, 
    ExtractedTaskSpec
)
from backend.app.memory.vector_memory import VectorMemorySystem
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.orchestrator.ai_brain_controller import AIBrainController
from backend.app.services.auth_service import CSRF_COOKIE
from backend.app.services.task_lifecycle_service import TaskLifecycleService


@pytest.fixture
def f15_client(monkeypatch):
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


def register_user(client: TestClient, email: str = "f15_user@example.com") -> int:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure f15 test password 123"},
    )
    assert response.status_code == 201
    return response.json()["user"]["id"]


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token
    return {"X-CSRF-Token": token}


# =========================================================================
# UNIT TESTS: NaturalLanguageExtractor with Injectable Clock
# =========================================================================

def test_nl_extractor_multi_task_and_relative_deadlines():
    # Fixed reference clock: Tuesday 2026-10-20 at 10:00:00 UTC
    fixed_now = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    extractor = NaturalLanguageExtractor(clock=lambda: fixed_now)

    text = (
        "I have an assignment due tomorrow, an exam in three days, and a project submission "
        "next week. I have four hours available today. Plan my schedule."
    )
    res: ExtractedPlanningContext = extractor.extract(text, user_tz="UTC")

    assert res.available_hours == 4.0
    assert len(res.extracted_tasks) == 3

    # Task 1: assignment
    t1 = res.extracted_tasks[0]
    assert "assignment" in t1.title.lower()
    assert t1.deadline_expression == "tomorrow"
    assert t1.deadline_dt is not None
    assert t1.deadline_dt.day == 21  # 2026-10-21
    assert t1.priority >= 3
    assert t1.estimated_duration_source in ("conversational_input", "deterministic_heuristic")

    # Task 2: exam
    t2 = res.extracted_tasks[1]
    assert "exam" in t2.title.lower()
    assert t2.deadline_expression == "in 3 days"
    assert t2.deadline_dt is not None
    assert t2.deadline_dt.day == 23  # 2026-10-23
    assert t2.priority >= 4  # exam gets elevated priority

    # Task 3: project submission
    t3 = res.extracted_tasks[2]
    assert "project" in t3.title.lower()
    assert t3.deadline_expression == "next week"
    assert t3.deadline_dt is not None
    assert t3.deadline_dt.day == 27  # 2026-10-27 (7 days)


def test_nl_extractor_calendar_dates_and_dependencies():
    fixed_now = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    extractor = NaturalLanguageExtractor(clock=lambda: fixed_now)

    text = "Complete literature review for 2 hours due 2026-10-25 with high priority. Then write thesis draft for 3 hours after literature review."
    res = extractor.extract(text, user_tz="UTC")

    assert len(res.extracted_tasks) == 2
    t1 = res.extracted_tasks[0]
    assert "literature review" in t1.title.lower()
    assert t1.estimated_duration == 2.0
    assert t1.deadline_dt is not None
    assert t1.deadline_dt.strftime("%Y-%m-%d") == "2026-10-25"
    assert t1.priority == 4

    t2 = res.extracted_tasks[1]
    assert "thesis draft" in t2.title.lower()
    assert t2.estimated_duration == 3.0
    assert len(t2.dependencies) == 1
    assert "literature review" in t2.dependencies[0]


def test_nl_extractor_refinement_instructions():
    extractor = NaturalLanguageExtractor()

    # Reorder instruction
    ref1 = extractor.parse_refinement("Move the assignment ahead of the exam preparation.")
    assert ref1 is not None
    assert ref1["action"] == "reorder"
    assert "assignment" in ref1["first_task"].lower()
    assert "exam" in ref1["second_task"].lower()

    # Buffer instruction
    ref2 = extractor.parse_refinement("Leave 30 minutes for revision.")
    assert ref2 is not None
    assert ref2["action"] == "add_buffer"
    assert ref2["buffer_minutes"] == 30.0

    # Afternoon instruction
    ref3 = extractor.parse_refinement("Start the project work after lunch.")
    assert ref3 is not None
    assert ref3["action"] == "set_start_hour"
    assert ref3["min_start_hour"] == 13.0
    assert "project" in ref3["task"].lower()

    # Duration reduction
    ref4 = extractor.parse_refinement("Keep the assignment first but reduce the project time today to 1 hour.")
    assert ref4 is not None
    assert ref4["action"] == "reduce_duration"
    assert "project" in ref4["task"].lower()
    assert ref4["new_duration_hours"] == 1.0


def test_nl_extractor_missing_information_triggers_clarification():
    extractor = NaturalLanguageExtractor()
    # Vague text with no tasks or horizon
    text = "Hello, can you help me plan something vague?"
    res = extractor.extract(text)
    assert len(res.extracted_tasks) == 0
    assert res.clarification_needed is True
    assert "could not detect" in res.clarification_question.lower()


# =========================================================================
# INTEGRATION TESTS: Multi-Task NL Planning via Brain Controller
# =========================================================================

def test_e2e_multi_task_planning_without_db_tasks(f15_client):
    """
    User requests schedule planning for three new tasks with deadlines in a 4-hour window.
    Tasks must NOT be persisted to the database upon proposal creation.
    Schedule must enforce non-overlapping intervals, prioritize earlier deadline, and identify overload.
    """
    client, session_factory = f15_client
    user_id = register_user(client, "multi_plan@example.com")

    # Command from requirements
    command_text = (
        "I have an assignment due tomorrow, an exam in three days, and a project submission "
        "next week. I have four hours available today. Plan my schedule."
    )

    resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": command_text,
            "days_back": 90,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "plan_day"
    result = data["result"]
    assert result["success"] is True

    schedule = result["schedule"]
    assert len(schedule) == 3

    # Verify all are proposed tasks, not existing
    for item in schedule:
        assert item["origin"] == "proposed"
        assert item["duration_source"] in ("conversational_input", "deterministic_heuristic")

    # Verify no tasks were written to DB on proposal!
    with session_factory() as session:
        db_tasks = session.query(Task).filter(Task.user_id == user_id).all()
        assert len(db_tasks) == 0

    # Verify Earliest Deadline First ordering:
    # Assignment (due tomorrow) must be scheduled before Exam (due in 3 days) and Project (due next week)
    titles = [s["title"].lower() for s in schedule]
    assert "assignment" in titles[0]

    # Verify non-overlapping intervals
    for i in range(len(schedule) - 1):
        assert schedule[i]["scheduled_end_hour"] <= schedule[i + 1]["scheduled_hour"] + 1e-4

    # Verify explainable prioritization reasons are provided
    assert len(result["reasons_for_prioritization"]) > 0
    assert len(result["trade_offs"]) > 0


def test_conversational_refinement_reorders_proposal_without_persistence(f15_client):
    """
    After generating a plan, the user asks follow-up refinement:
    'Move the exam preparation ahead of the assignment.'
    The schedule must reorder accordingly in the active proposal without persisting to DB.
    """
    client, session_factory = f15_client
    user_id = register_user(client, "refine_user@example.com")

    # 1. Initial multi-task plan
    client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "I have an assignment due tomorrow and an exam in three days. Available 4 hours.",
            "days_back": 90,
        },
    )

    # 2. Refinement command
    refine_resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "Move the exam ahead of the assignment",
            "days_back": 90,
        },
    )
    assert refine_resp.status_code == 200
    ref_data = refine_resp.json()
    assert ref_data["intent"] == "refine_plan"
    schedule = ref_data["result"]["schedule"]

    # Exam should now be first
    assert "exam" in schedule[0]["title"].lower()
    assert "assignment" in schedule[1]["title"].lower()

    # Verify still zero tasks persisted in database
    with session_factory() as session:
        db_tasks = session.query(Task).filter(Task.user_id == user_id).all()
        assert len(db_tasks) == 0


def test_conversational_refinement_add_buffer_and_after_lunch(f15_client):
    """
    User asks to 'Leave 30 minutes for revision' and 'Start after lunch'.
    The scheduler must enforce start_hour >= 13.0 and insert 30m buffers.
    """
    client, session_factory = f15_client
    user_id = register_user(client, "buffer_user@example.com")

    client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "I have an assignment and an exam today. Available 6 hours.",
            "days_back": 90,
        },
    )

    # Add buffer
    buf_resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "Leave 30 minutes for revision",
            "days_back": 90,
        },
    )
    buf_schedule = buf_resp.json()["result"]["schedule"]
    gap = buf_schedule[1]["scheduled_hour"] - buf_schedule[0]["scheduled_end_hour"]
    assert gap >= 0.49  # 30 minutes is 0.5 hours

    # Start after lunch
    lunch_resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "Start the assignment after lunch",
            "days_back": 90,
        },
    )
    lunch_schedule = lunch_resp.json()["result"]["schedule"]
    # First item scheduled at or after 13:00 (1:00 PM)
    for item in lunch_schedule:
        if "assignment" in item["title"].lower():
            assert item["scheduled_hour"] >= 13.0


def test_proposal_rejection_discards_cache_without_db_changes(f15_client):
    """
    User asks to reject the proposal.
    Cache is cleared and no database modifications occur.
    """
    client, session_factory = f15_client
    user_id = register_user(client, "reject_user@example.com")

    # Generate plan
    client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "I have an assignment due tomorrow. Available 2 hours.",
            "days_back": 90,
        },
    )

    # Reject plan
    rej_resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "Reject plan proposal",
            "days_back": 90,
        },
    )
    assert rej_resp.status_code == 200
    res = rej_resp.json()["result"]
    assert res["plan_rejected"] is True
    assert res["plan_accepted"] is False

    # Verify no tasks in DB
    with session_factory() as session:
        db_tasks = session.query(Task).filter(Task.user_id == user_id).all()
        assert len(db_tasks) == 0


def test_safe_acceptance_persists_proposed_tasks_and_updates_existing(f15_client):
    """
    Accepting a proposal creates proposed tasks in the DB and assigns scheduled times.
    Accepting again does NOT create duplicate tasks.
    """
    client, session_factory = f15_client
    user_id = register_user(client, "accept_user@example.com")

    # Seed 1 existing task in DB
    with session_factory() as session:
        service = TaskLifecycleService(session)
        existing_task = service.create_task(
            user_id=user_id,
            title="Pre-existing Code Review",
            task_type="coding",
            priority=3,
            estimated_duration=60.0,
            estimated_duration_unit="minutes",
            estimated_duration_source="task_api",
        )
        existing_task_id = existing_task.id

    # Plan with 1 new proposed task
    plan_resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": "I have an assignment due tomorrow. Available 4 hours.",
            "days_back": 90,
        },
    )
    schedule = plan_resp.json()["result"]["schedule"]

    # Call accept plan endpoint
    accept_resp = client.post(
        "/api/v1/ai/accept-plan",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "schedule": schedule,
        },
    )
    assert accept_resp.status_code == 200
    acc_data = accept_resp.json()
    assert acc_data["result"]["success"] is True

    with session_factory() as session:
        tasks = session.query(Task).filter(Task.user_id == user_id).all()
        # Should now have 2 tasks: the existing one + the newly accepted assignment
        assert len(tasks) == 2
        titles = [t.title for t in tasks]
        assert "Pre-existing Code Review" in titles
        assignment_task = next(t for t in tasks if "assignment" in t.title.lower())
        assert assignment_task.start_time is not None
        assert assignment_task.end_time is not None

    # Idempotent re-acceptance check (Duplicate Prevention)
    accept_resp2 = client.post(
        "/api/v1/ai/accept-plan",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "schedule": schedule,
        },
    )
    assert accept_resp2.status_code == 200
    with session_factory() as session:
        tasks_after = session.query(Task).filter(Task.user_id == user_id).all()
        # Still exactly 2 tasks; no duplicate created!
        assert len(tasks_after) == 2


def test_user_isolation_on_plan_acceptance(f15_client):
    """
    User B cannot accept or alter tasks belonging to User A.
    """
    client, session_factory = f15_client
    user_a = register_user(client, "user_a@example.com")
    user_b = register_user(client, "user_b@example.com")

    # Create task for User A
    with session_factory() as session:
        service = TaskLifecycleService(session)
        task_a = service.create_task(
            user_id=user_a,
            title="User A Private Strategy",
            task_type="planning",
            priority=5,
            estimated_duration=60.0,
            estimated_duration_unit="minutes",
            estimated_duration_source="task_api",
        )
        task_a_id = task_a.id

    # User B is currently authenticated (last registered user has active session cookies)
    # User B attempts to accept a plan modifying task_a_id
    tampered_schedule = [
        {
            "task_id": task_a_id,
            "title": "Hacked Task A",
            "origin": "existing",
            "scheduled_hour": 10.0,
            "scheduled_end_hour": 11.0,
        }
    ]

    # Attempt with user_id=user_a (mismatched with cookie auth for user_b)
    resp_mismatch = client.post(
        "/api/v1/ai/accept-plan",
        headers=csrf_headers(client),
        json={
            "user_id": user_a,
            "schedule": tampered_schedule,
        },
    )
    # Auth middleware rejects mismatched client-supplied user_id with 403
    assert resp_mismatch.status_code == 403

    # Attempt with user_id=user_b but targeting task_a_id
    resp_tamper = client.post(
        "/api/v1/ai/accept-plan",
        headers=csrf_headers(client),
        json={
            "user_id": user_b,
            "schedule": tampered_schedule,
        },
    )
    assert resp_tamper.status_code == 200
    # Task A in database should NOT have been modified
    with session_factory() as session:
        task_a_db = session.query(Task).filter(Task.id == task_a_id).one()
        assert task_a_db.user_id == user_a
        assert task_a_db.title == "User A Private Strategy"
        assert task_a_db.start_time is None


def test_overloaded_horizon_capacity_handling(f15_client):
    """
    Demanded tasks (6.0 hours total) exceed available window (3.0 hours).
    Scheduler marks INFEASIBLE_OVERLOAD, preserves tasks, marks fits_in_horizon=False,
    and returns trade-offs and alternative actions.
    """
    client, session_factory = f15_client
    user_id = register_user(client, "overload_user@example.com")

    # Command: 3 tasks each taking 2h = 6h demanded, but available 3h
    command_text = (
        "I have Task Alpha for 2 hours, Task Beta for 2 hours, and Task Gamma for 2 hours. "
        "I have 3 hours available today. Plan my schedule."
    )

    resp = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={
            "user_id": user_id,
            "command": command_text,
            "days_back": 90,
        },
    )
    assert resp.status_code == 200
    result = resp.json()["result"]

    assert result["feasibility_status"] == "INFEASIBLE_OVERLOAD"
    assert result["available_hours"] == 3.0
    assert result["total_demanded_hours"] >= 5.9

    # Unscheduled or over-horizon tasks must be identified
    assert len(result["infeasible_tasks"]) > 0
    # Alternatives offered
    assert len(result["alternative_actions"]) > 0
    assert any("horizon" in a.lower() or "defer" in a.lower() for a in result["alternative_actions"])
