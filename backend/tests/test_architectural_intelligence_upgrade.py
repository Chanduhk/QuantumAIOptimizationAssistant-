"""Comprehensive Test Suite for HELIOX AI Architectural Intelligence Upgrade.

Validates:
1. Goal Intelligence: duration-weighted progress, feasibility modeling, velocity, health analytics.
2. Dependencies Intelligence: graph topology, downstream slack hours, critical path, cycle prevention.
3. Dynamic Multi-Criteria Prioritization (MCDA): 6-pillar scoring, blocker gating, explainable breakdown.
4. Actionable Recommendations: structured proposals generation & execution via API.
5. Cognitive Budgeting: deep work tracking, fatigue risk assessment, workload integration.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.db import get_db
from backend.app.engines.deadline_risk_engine import DeadlineRiskEngine
from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine
from backend.app.engines.prioritization_engine import MultiCriteriaPrioritizer
from backend.app.models.base import Base
from backend.app.models.goal import Goal
from backend.app.models.task import Task
from backend.app.recommendation.recommendation_engine import RecommendationEngine
from backend.app.services.goal_service import GoalService
from backend.app.services.task_lifecycle_service import TaskLifecycleService
from backend.main import app


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    from backend.app.services.auth_service import enforce_authenticated_request

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[enforce_authenticated_request] = lambda: None
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# =========================================================================
# 1. GOAL INTELLIGENCE TESTS
# =========================================================================

def test_goal_duration_weighted_progress(db_session: Session):
    service = GoalService(db_session)
    goal = service.create_goal(user_id=1, title="Master Quantum ML", priority=5)

    # Add 2 tasks: 1 completed (30m, P1) and 1 uncompleted (120m, P5)
    t1 = Task(
        user_id=1,
        title="Intro lecture",
        task_type="study",
        priority=1,
        estimated_duration=30.0,
        actual_duration=30.0,
        goal_id=goal.id,
        completed=True,
    )
    t2 = Task(
        user_id=1,
        title="Implement QAOA",
        task_type="coding",
        priority=5,
        estimated_duration=120.0,
        goal_id=goal.id,
        completed=False,
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # Weight T1: 30 * 1 = 30. Weight T2: 120 * 5 = 600. Total = 630. Completed ratio: 30 / 630 = 4.76%
    progress = service.calculate_progress(goal.id, user_id=1)
    assert 4.0 <= progress <= 5.5, f"Expected ~4.76% weighted progress, got {progress}%"


def test_goal_feasibility_and_health_scoring(db_session: Session):
    service = GoalService(db_session)
    now = datetime.now(timezone.utc)

    # Goal target date is 10 days in the future
    target_dt = now + timedelta(days=10)
    goal = service.create_goal(
        user_id=2,
        title="Release Beta Platform",
        priority=4,
        target_date=target_dt.replace(tzinfo=None),
    )

    # Add 3 pending tasks totaling 360 mins (6h). At default velocity of 180m/day, days needed = 2.
    # 10 days available vs 2 needed -> feasibility ratio = 5.0 -> 'on_track'
    for i in range(3):
        t = Task(
            user_id=2,
            title=f"Beta Task {i}",
            task_type="engineering",
            priority=3,
            estimated_duration=120.0,
            goal_id=goal.id,
            completed=False,
        )
        db_session.add(t)
    db_session.commit()

    analytics = service.get_goal_analytics(goal.id, user_id=2)
    assert analytics["health_status"] == "on_track"
    assert analytics["target_date_feasible"] is True
    assert analytics["days_needed"] == 2
    assert analytics["task_count"] == 3
    assert analytics["pending_task_count"] == 3


def test_goal_behind_health_status(db_session: Session):
    service = GoalService(db_session)
    now = datetime.now(timezone.utc)

    # Target date is only 1 day in the future
    target_dt = now + timedelta(days=1)
    goal = service.create_goal(
        user_id=3,
        title="Urgent Thesis Submission",
        priority=5,
        target_date=target_dt.replace(tzinfo=None),
    )

    # Add 10 pending tasks totaling 1200 mins (20h). Days needed = 7.
    # 1 day available vs 7 needed -> feasibility ratio < 0.8 -> 'behind'
    for i in range(10):
        t = Task(
            user_id=3,
            title=f"Chapter {i}",
            task_type="writing",
            priority=4,
            estimated_duration=120.0,
            goal_id=goal.id,
            completed=False,
        )
        db_session.add(t)
    db_session.commit()

    analytics = service.get_goal_analytics(goal.id, user_id=3)
    assert analytics["health_status"] in ("behind", "critical")
    assert analytics["target_date_feasible"] is False


# =========================================================================
# 2. DEPENDENCIES INTELLIGENCE TESTS
# =========================================================================

def test_dependency_slack_computation():
    engine = DependencyIntelligenceEngine()
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Task 1 (Prerequisite, duration 2h) -> Task 2 (Dependent, duration 3h, deadline Nov 20, 20:00)
    # Task 2 earliest deadline is 20:00. It needs 3h, so it must start by 17:00.
    # Therefore Task 1 must finish by 17:00. Task 1 earliest finish from 10:00 is 12:00.
    # Slack for Task 1: 17:00 - 12:00 = 5.0 hours!
    tasks = [
        {
            "id": "1",
            "title": "Setup Pipeline",
            "estimated_duration": 120.0,
            "deadline": None,
            "dependencies": [],
            "completed": False,
        },
        {
            "id": "2",
            "title": "Train Model",
            "estimated_duration": 180.0,
            "deadline": "2026-11-20T20:00:00Z",
            "dependencies": ["1"],
            "completed": False,
        },
    ]

    slack_map = engine.compute_downstream_slack_hours(tasks, now=now)
    assert slack_map["1"] == 5.0, f"Expected 5.0h slack for Task 1, got {slack_map['1']}"
    assert slack_map["2"] == 7.0, f"Expected 7.0h slack for Task 2 (20:00 - 13:00), got {slack_map['2']}"


def test_dependency_topology_and_bottlenecks():
    engine = DependencyIntelligenceEngine()
    tasks = [
        {"id": "A", "title": "Database Schema", "estimated_duration": 60.0, "dependencies": [], "completed": False},
        {"id": "B", "title": "API Layer", "estimated_duration": 60.0, "dependencies": ["A"], "completed": False},
        {"id": "C", "title": "Frontend App", "estimated_duration": 60.0, "dependencies": ["A"], "completed": False},
        {"id": "D", "title": "Integration Tests", "estimated_duration": 60.0, "dependencies": ["B", "C"], "completed": False},
    ]

    topology = engine.get_dependency_graph_topology(tasks)
    assert topology["summary"]["total_nodes"] == 4
    assert topology["summary"]["total_edges"] == 4
    assert len(topology["critical_path"]) >= 3

    # Task A blocks 3 downstream tasks (B, C, D)
    bottlenecks = topology["bottlenecks"]
    assert len(bottlenecks) > 0
    top_b = bottlenecks[0]
    assert top_b["task_id"] == "A"
    assert top_b["downstream_dependents"] == 3


def test_task_lifecycle_cycle_prevention(db_session: Session):
    svc = TaskLifecycleService(db_session)
    t1 = svc.create_task(user_id=4, title="Task 1", task_type="coding", priority=3, estimated_duration=60.0)
    t2 = svc.create_task(user_id=4, title="Task 2", task_type="coding", priority=3, estimated_duration=60.0, dependencies=[t1.id])

    # Attempting to make t1 depend on t2 must raise ValueError for cycle
    with pytest.raises(ValueError, match="cycle"):
        svc.update_task(task_id=t1.id, user_id=4, dependencies=[t2.id])


# =========================================================================
# 3. DYNAMIC MULTI-CRITERIA PRIORITIZATION (MCDA) TESTS
# =========================================================================

def test_mcda_blocker_gating_and_ranking():
    prioritizer = MultiCriteriaPrioritizer()
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    tasks = [
        {
            "id": "10",
            "title": "Prerequisite Task",
            "priority": 3,
            "task_type": "coding",
            "dependencies": [],
            "completed": False,
        },
        {
            "id": "11",
            "title": "Blocked High-Priority Task",
            "priority": 5,
            "task_type": "coding",
            "dependencies": ["10"],  # Blocked by 10
            "completed": False,
        },
    ]

    ranked = prioritizer.prioritize_workload(tasks=tasks, now=now)
    # Even though Task 11 has base priority 5 and Task 10 has base priority 3,
    # Task 10 MUST be ranked higher because Task 11 is blocked and Task 10 unblocks it!
    assert ranked[0]["id"] == "10", "Unblocked prerequisite task must rank higher than blocked dependent."
    assert ranked[0]["blocking_count"] == 1
    assert ranked[1]["is_blocked"] is True
    assert ranked[1]["priority_breakdown"]["blocker_penalty"] == -50.0


def test_mcda_reschedule_starvation_boost():
    prioritizer = MultiCriteriaPrioritizer()
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    t_deferred = {
        "id": "21",
        "title": "Deferred Bug Fix",
        "priority": 2,
        "task_type": "maintenance",
        "dependencies": [],
        "reschedule_count": 3,
        "completed": False,
    }
    t_normal = {
        "id": "22",
        "title": "New Chore",
        "priority": 2,
        "task_type": "maintenance",
        "dependencies": [],
        "reschedule_count": 0,
        "completed": False,
    }

    ranked = prioritizer.prioritize_workload(tasks=[t_deferred, t_normal], now=now)
    assert ranked[0]["id"] == "21", "Task deferred 3 times should receive starvation boost over fresh task."
    assert ranked[0]["priority_breakdown"]["starvation_score"] >= 70.0


# =========================================================================
# 4. ACTIONABLE RECOMMENDATIONS & EXECUTION TESTS
# =========================================================================

def test_actionable_proposals_generation_and_execution(db_session: Session):
    svc = TaskLifecycleService(db_session)
    t_blocker = svc.create_task(user_id=5, title="Create DB Schema", task_type="architecture", priority=2, estimated_duration=60.0)
    t_dep = svc.create_task(user_id=5, title="Build Auth Endpoints", task_type="coding", priority=4, estimated_duration=90.0, dependencies=[t_blocker.id])

    rec_engine = RecommendationEngine(session=db_session)
    # Test proposal execution directly
    res = rec_engine.apply_proposal(
        user_id=5,
        proposal_id="test-unblock",
        action_type="prioritize_task",
        payload={"task_id": t_blocker.id, "priority": 5},
    )

    assert res["applied"] is True
    updated = svc.get_task(task_id=t_blocker.id, user_id=5)
    assert updated.priority == 5, "Blocker priority should be elevated to 5."


def test_boost_goal_tasks_execution(db_session: Session):
    goal_svc = GoalService(db_session)
    goal = goal_svc.create_goal(user_id=6, title="Major Milestone", priority=5)

    svc = TaskLifecycleService(db_session)
    t1 = svc.create_task(user_id=6, title="Goal Task 1", task_type="coding", priority=2, estimated_duration=60.0, goal_id=goal.id)
    t2 = svc.create_task(user_id=6, title="Goal Task 2", task_type="coding", priority=1, estimated_duration=60.0, goal_id=goal.id)

    rec_engine = RecommendationEngine(session=db_session)
    res = rec_engine.apply_proposal(
        user_id=6,
        proposal_id="test-goal-boost",
        action_type="boost_goal_tasks",
        payload={"goal_id": goal.id, "boost_priority": 4},
    )

    assert res["applied"] is True
    assert res["boosted_tasks_count"] == 2

    # Verify database state
    refreshed_t1 = svc.get_task(task_id=t1.id, user_id=6)
    refreshed_t2 = svc.get_task(task_id=t2.id, user_id=6)
    assert refreshed_t1.priority == 4
    assert refreshed_t2.priority == 4


# =========================================================================
# 5. COGNITIVE ENERGY & WORKLOAD INTEGRATION TESTS
# =========================================================================

def test_daily_workload_cognitive_budget():
    engine = DeadlineRiskEngine()
    now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)

    # 4 deep work tasks totaling 360 mins (6h). Sustainable limit is 240 mins (4h).
    tasks = [
        {
            "id": 101,
            "title": "Quantum Circuit Synthesis",
            "task_type": "coding",
            "estimated_duration": 90.0,
            "scheduled_start_time": "2026-11-20T10:00:00Z",
            "completed": False,
        },
        {
            "id": 102,
            "title": "Hamiltonian Mapping",
            "task_type": "research",
            "estimated_duration": 90.0,
            "scheduled_start_time": "2026-11-20T12:00:00Z",
            "completed": False,
        },
        {
            "id": 103,
            "title": "VQE Optimization Loop",
            "task_type": "deep_work",
            "estimated_duration": 90.0,
            "scheduled_start_time": "2026-11-20T14:00:00Z",
            "completed": False,
        },
        {
            "id": 104,
            "title": "State Tomography Benchmark",
            "task_type": "engineering",
            "estimated_duration": 90.0,
            "scheduled_start_time": "2026-11-20T16:00:00Z",
            "completed": False,
        },
    ]

    workload = engine.compute_daily_workload(user_id=7, tasks=tasks, target_date=now)
    assert "cognitive_budget" in workload
    cb = workload["cognitive_budget"]
    assert cb["deep_work_hours"] == 6.0
    assert cb["sustainable_limit_hours"] == 4.0
    assert cb["cognitive_utilization_pct"] == 150.0
    assert cb["fatigue_risk"] == "high"


# =========================================================================
# 6. END-TO-END REST API TESTS
# =========================================================================

def test_rest_api_goals_analytics_and_summary(client: TestClient, db_session: Session):
    goal_svc = GoalService(db_session)
    goal = goal_svc.create_goal(user_id=10, title="API Launch Goal", priority=4)

    # 1. Test Goal Analytics Endpoint
    resp = client.get(f"/api/v1/goals/{goal.id}/analytics?user_id=10")
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["goal_id"] == goal.id
    assert "health_status" in data
    assert "target_date_feasible" in data

    # 2. Test Goals Health Summary Endpoint
    resp_summary = client.get("/api/v1/goals/summary/health?user_id=10")
    assert resp_summary.status_code == 200
    sum_data = resp_summary.json()["result"]
    assert sum_data["total_active_goals"] == 1
    assert "portfolio_health_score" in sum_data


def test_rest_api_dependencies_and_prioritized(client: TestClient, db_session: Session):
    svc = TaskLifecycleService(db_session)
    t1 = svc.create_task(user_id=11, title="Root Step", task_type="architecture", priority=3, estimated_duration=60.0)
    t2 = svc.create_task(user_id=11, title="Leaf Step", task_type="coding", priority=5, estimated_duration=60.0, dependencies=[t1.id])

    # 1. Dependency Graph Endpoint
    resp_graph = client.get("/api/v1/tasks/dependencies/graph?user_id=11")
    assert resp_graph.status_code == 200
    graph_data = resp_graph.json()["result"]
    assert graph_data["summary"]["total_nodes"] == 2
    assert graph_data["summary"]["total_edges"] == 1

    # 2. Prioritized Tasks Endpoint
    resp_prio = client.get("/api/v1/tasks/prioritized?user_id=11")
    assert resp_prio.status_code == 200
    prio_data = resp_prio.json()["tasks"]
    assert len(prio_data) == 2
    assert "dynamic_priority" in prio_data[0]
    assert "priority_breakdown" in prio_data[0]
    assert "recommended_action" in prio_data[0]


def test_rest_api_apply_recommendation(client: TestClient, db_session: Session):
    svc = TaskLifecycleService(db_session)
    task = svc.create_task(user_id=12, title="Recommendation Test Task", task_type="coding", priority=2, estimated_duration=60.0)

    payload = {
        "user_id": 12,
        "proposal_id": "test-prop-1",
        "action_type": "prioritize_task",
        "payload": {"task_id": task.id, "priority": 5},
    }
    resp = client.post("/api/v1/ai/recommendations/apply", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()["result"]
    assert res_data["applied"] is True

    # Check updated task in db
    updated = svc.get_task(task_id=task.id, user_id=12)
    assert updated.priority == 5
