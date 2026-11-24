from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.engines.deadline_risk_engine import DeadlineRiskEngine
from backend.app.engines.scheduling_engine import SchedulingEngine
from backend.app.interface.ai_interaction import AIInteractionLayer
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.models.auth import User
from backend.app.services.task_lifecycle_service import (
    TaskLifecycleService,
    ensure_task_lifecycle_schema,
)


@pytest.fixture
def session_factory(tmp_path):
    db_file = tmp_path / "test_deadline.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"timeout": 30.0})
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()
    ensure_task_lifecycle_schema(session)

    # Seed test user
    now = datetime.now(timezone.utc)
    user = User(id=1, email="deadline_tester@example.com", password_hash="hash", is_active=True, created_at=now)
    session.add(user)
    session.commit()
    session.close()

    return SessionFactory


def test_task_creation_and_serialization_with_deadlines(session_factory):
    session = session_factory()
    service = TaskLifecycleService(session)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    deadline = now + timedelta(hours=3)
    sched_start = now + timedelta(hours=1)
    sched_end = now + timedelta(hours=2)

    task = service.create_task(
        user_id=1,
        title="Implement Auth Security",
        task_type="coding",
        priority=4,
        estimated_duration=60.0,
        estimated_duration_unit="minutes",
        estimated_duration_source="task_api",
        deadline=deadline,
        scheduled_start_time=sched_start,
        scheduled_end_time=sched_end,
        reschedule_count=1,
    )

    assert task.id is not None
    assert task.deadline == deadline
    assert task.scheduled_start_time == sched_start
    assert task.scheduled_end_time == sched_end
    assert task.reschedule_count == 1

    serialized = service.serialize_task(task)
    assert serialized["deadline"] is not None
    assert serialized["scheduled_start_time"] is not None
    assert serialized["scheduled_end_time"] is not None
    assert serialized["reschedule_count"] == 1
    assert "deadline_risk" in serialized
    assert serialized["deadline_risk"]["risk_level"] in ("low", "moderate", "high", "overdue")

    session.close()


def test_deadline_risk_engine_assessments():
    engine = DeadlineRiskEngine()
    now = datetime.now(timezone.utc)

    # 1. Overdue task
    overdue_task = {
        "id": 101,
        "title": "Overdue Feature",
        "priority": 4,
        "estimated_duration": 60.0,
        "deadline": (now - timedelta(hours=2)).isoformat(),
        "completed": False,
        "task_type": "coding",
    }
    risk_overdue = engine.assess_task_risk(overdue_task, now=now)
    assert risk_overdue["risk_level"] == "overdue"
    assert risk_overdue["is_overdue"] is True
    assert risk_overdue["risk_score"] == 1.0
    assert any("passed" in r.lower() or "overdue" in r.lower() for r in risk_overdue["reasons"])

    # 2. High risk task: estimated duration 120 mins but only 30 mins until deadline
    tight_task = {
        "id": 102,
        "title": "Tight Deadline Work",
        "priority": 5,
        "estimated_duration": 120.0,
        "deadline": (now + timedelta(minutes=30)).isoformat(),
        "completed": False,
        "task_type": "coding",
    }
    risk_tight = engine.assess_task_risk(tight_task, now=now)
    assert risk_tight["risk_level"] == "high"
    assert risk_tight["risk_score"] >= 0.75
    assert len(risk_tight["reasons"]) > 0

    # 3. Moderate risk task: estimated 60 mins with 90 mins remaining
    mod_task = {
        "id": 103,
        "title": "Moderate Deadline Work",
        "priority": 3,
        "estimated_duration": 60.0,
        "deadline": (now + timedelta(minutes=90)).isoformat(),
        "completed": False,
        "task_type": "general",
    }
    risk_mod = engine.assess_task_risk(mod_task, now=now)
    assert risk_mod["risk_level"] in ("moderate", "high")

    # 4. Low risk task: estimated 30 mins with 8 hours remaining
    safe_task = {
        "id": 104,
        "title": "Safe Task",
        "priority": 2,
        "estimated_duration": 30.0,
        "deadline": (now + timedelta(hours=8)).isoformat(),
        "completed": False,
        "task_type": "general",
    }
    risk_safe = engine.assess_task_risk(safe_task, now=now)
    assert risk_safe["risk_level"] == "low"
    assert risk_safe["risk_score"] < 0.4


def test_intelligent_scheduling_allocation_non_overlapping():
    scheduler = SchedulingEngine()
    now = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)

    tasks = [
        {
            "id": 1,
            "title": "Setup Core DB",
            "priority": 5,
            "estimated_duration": 60.0,
            "deadline": (now + timedelta(hours=5)).isoformat(),
            "dependencies": [],
        },
        {
            "id": 2,
            "title": "Build API on DB",
            "priority": 4,
            "estimated_duration": 90.0,
            "deadline": (now + timedelta(hours=6)).isoformat(),
            "dependencies": [1],  # Depends on Task 1
        },
        {
            "id": 3,
            "title": "Write Docs",
            "priority": 2,
            "estimated_duration": 45.0,
            "deadline": (now + timedelta(hours=7)).isoformat(),
            "dependencies": [],
        },
    ]

    allocation = scheduler.allocate_intelligent_schedule(
        tasks=tasks,
        day_start=9,
        day_end=18,
        now=now,
    )

    scheduled = allocation["scheduled_tasks"]
    assert len(scheduled) == 3

    # Check zero overlap between all scheduled tasks
    intervals = []
    for t in scheduled:
        sh = t["scheduled_start_hour"]
        eh = t["scheduled_end_hour"]
        assert eh > sh
        intervals.append((sh, eh, t["id"]))

    intervals.sort(key=lambda x: x[0])
    for i in range(len(intervals) - 1):
        cur_end = intervals[i][1]
        next_start = intervals[i + 1][0]
        assert next_start >= cur_end - 1e-6, f"Overlap detected between {intervals[i]} and {intervals[i+1]}"

    # Verify dependency order: Task 1 must finish before Task 2 starts
    t1_alloc = next(t for t in scheduled if t["id"] == 1)
    t2_alloc = next(t for t in scheduled if t["id"] == 2)
    assert t2_alloc["scheduled_start_hour"] >= t1_alloc["scheduled_end_hour"] - 1e-6


def test_intelligent_rescheduling_logic():
    scheduler = SchedulingEngine()
    now = datetime(2026, 11, 18, 10, 0, 0, tzinfo=timezone.utc)

    tasks = [
        {
            "id": 10,
            "title": "Already Finished Task",
            "priority": 4,
            "estimated_duration": 60.0,
            "completed": True,
            "scheduled_start_hour": 8.0,
            "scheduled_end_hour": 9.0,
        },
        {
            "id": 11,
            "title": "Delayed Feature",
            "priority": 5,
            "estimated_duration": 90.0,
            "completed": False,
            "deadline": (now + timedelta(hours=3)).isoformat(),
            "dependencies": [],
        },
        {
            "id": 12,
            "title": "Downstream Integration",
            "priority": 3,
            "estimated_duration": 60.0,
            "completed": False,
            "deadline": (now + timedelta(hours=5)).isoformat(),
            "dependencies": [11],
        },
    ]

    resched = scheduler.intelligent_reschedule(
        user_id=1,
        tasks=tasks,
        affected_task_id=11,
        reason="Developer encountered edge case in feature",
        now=now,
    )

    assert resched["success"] is True
    assert resched["action"] == "intelligent_reschedule_proposed"
    assert resched["preserved_completed_tasks_count"] == 1
    assert "11" in [str(x) for x in resched["affected_task_ids"]]
    assert "12" in [str(x) for x in resched["affected_task_ids"]]
    assert len(resched["revised_schedule"]) == 2  # Only pending tasks rescheduled
    assert "explanation" in resched
    assert "Rescheduling triggered" in resched["explanation"]


def test_daily_workload_aggregation():
    engine = DeadlineRiskEngine()
    now = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)

    tasks = [
        {
            "id": 1,
            "title": "Task A",
            "priority": 4,
            "estimated_duration": 120.0,  # 2.0 hrs
            "actual_duration": 120.0,
            "completed": True,
            "deadline": (now + timedelta(hours=1)).isoformat(),
        },
        {
            "id": 2,
            "title": "Task B",
            "priority": 3,
            "estimated_duration": 180.0,  # 3.0 hrs
            "completed": False,
            "deadline": (now + timedelta(hours=4)).isoformat(),
        },
        {
            "id": 3,
            "title": "Task C",
            "priority": 2,
            "estimated_duration": 60.0,  # 1.0 hr
            "completed": False,
            "deadline": (now - timedelta(hours=1)).isoformat(),  # Overdue
        },
    ]

    workload = engine.compute_daily_workload(user_id=1, tasks=tasks, target_date=now)

    assert workload["total_workload_hours"] == 6.0
    assert workload["completed_workload_hours"] == 2.0
    assert workload["remaining_workload_hours"] == 4.0
    assert workload["overdue_tasks_count"] == 1
    assert workload["capacity_hours"] == 8.0
    assert workload["capacity_utilization_pct"] == 50.0
    assert workload["workload_status"] == "balanced"


@pytest.mark.anyio
async def test_jam_assistant_intelligent_intents(session_factory):
    session = session_factory()
    service = TaskLifecycleService(session)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Create 3 tasks for user 1
    t1 = service.create_task(
        user_id=1,
        title="Critical Security Patch",
        task_type="coding",
        priority=5,
        estimated_duration=45.0,
        deadline=now + timedelta(hours=2),
    )
    t2 = service.create_task(
        user_id=1,
        title="Write Unit Tests",
        task_type="coding",
        priority=3,
        estimated_duration=60.0,
        deadline=now + timedelta(hours=6),
        dependencies=[t1.id],  # Blocked by t1
    )
    t3 = service.create_task(
        user_id=1,
        title="Overdue Documentation",
        task_type="writing",
        priority=4,
        estimated_duration=30.0,
        deadline=now - timedelta(hours=1),  # Overdue
    )

    from backend.app.interface.llm_provider import DeterministicFallbackProvider, HybridPlanningParser
    parser = HybridPlanningParser(llm_provider=DeterministicFallbackProvider())
    interaction = AIInteractionLayer(session, parser=parser)

    # 1. Intent: next_task
    intent_next = interaction.detect_intent("Which task should I complete next?")
    assert intent_next == "next_task"
    res_next = await interaction.process_command(1, "Which task should I complete next?")
    text_next = res_next["result"].get("executive_summary", "")
    assert "Critical Security Patch" in text_next or "Overdue" in text_next

    # 2. Intent: deadline_risks
    intent_risk = interaction.detect_intent("Which tasks are at risk of missing deadlines?")
    assert intent_risk == "deadline_risks"
    res_risk = await interaction.process_command(1, "Which tasks are at risk of missing deadlines?")
    text_risk = res_risk["result"].get("executive_summary", "")
    assert "Overdue" in text_risk

    # 3. Intent: workload_query
    intent_workload = interaction.detect_intent("How much work do I have today?")
    assert intent_workload == "workload_query"
    res_workload = await interaction.process_command(1, "How much work do I have today?")
    text_workload = res_workload["result"].get("executive_summary", "")
    assert "workload" in text_workload.lower()

    # 4. Intent: feasibility_query
    intent_feas = interaction.detect_intent("Can I finish all my tasks before their deadlines?")
    assert intent_feas == "feasibility_query"
    res_feas = await interaction.process_command(1, "Can I finish all my tasks before their deadlines?")
    text_feas = res_feas["result"].get("executive_summary", "")
    assert "feasibility" in text_feas.lower()

    # 5. Intent: blocking_tasks
    intent_block = interaction.detect_intent("Which tasks are blocking other tasks?")
    assert intent_block == "blocking_tasks"
    res_block = await interaction.process_command(1, "Which tasks are blocking other tasks?")
    text_block = res_block["result"].get("executive_summary", "")
    assert "Critical Security Patch" in text_block

    # 6. Intent: reschedule_tasks
    intent_resched = interaction.detect_intent("Reschedule my remaining tasks")
    assert intent_resched == "reschedule_tasks"
    res_resched = await interaction.process_command(1, "Reschedule my remaining tasks")
    text_resched = res_resched["result"].get("executive_summary", "")
    assert "schedule" in text_resched.lower()

    session.close()


def test_deadline_and_scheduling_api_endpoints(session_factory):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app.database.db import get_db
    from backend.app.services.auth_service import enforce_authenticated_request

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[enforce_authenticated_request] = lambda: None
    client = TestClient(app)

    # 1. Test GET /api/v1/tasks/workload/daily
    resp_workload = client.get("/api/v1/tasks/workload/daily?user_id=1")
    assert resp_workload.status_code == 200
    res_json = resp_workload.json()
    assert "result" in res_json
    assert "total_workload_hours" in res_json["result"]
    assert "capacity_utilization_pct" in res_json["result"]

    # 2. Test POST /api/v1/schedule/allocate
    resp_alloc = client.post("/api/v1/schedule/allocate", json={"user_id": 1, "day_start": 9, "day_end": 18, "apply": False})
    assert resp_alloc.status_code == 200
    alloc_json = resp_alloc.json()
    assert "result" in alloc_json
    assert "scheduled_tasks" in alloc_json["result"]

    # 3. Test POST /api/v1/schedule/reschedule
    resp_resched = client.post("/api/v1/schedule/reschedule", json={"user_id": 1, "reason": "Test adjustment", "auto_apply": False})
    assert resp_resched.status_code == 200
    resched_json = resp_resched.json()
    assert "result" in resched_json
    assert "proposal_id" in resched_json["result"]
    assert resched_json["result"]["proposal_status"] == "PROPOSED"

    app.dependency_overrides.clear()
