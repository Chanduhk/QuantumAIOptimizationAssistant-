from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timedelta

import pytest

from backend.app.domain.dependency_model import TaskDependency
from backend.app.domain.goal_model import Goal, Milestone
from backend.app.domain.strategic_plan_model import RoadmapItem, StrategicPlan
from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine
from backend.app.engines.goal_intelligence_engine import GoalIntelligenceEngine
from backend.app.engines.strategic_planning_engine import StrategicPlanningEngine
from backend.app.knowledge.dependency_graph import DependencyGraph
from backend.app.knowledge.goal_graph import GoalGraph
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def build_engine() -> StrategicPlanningEngine:
    goal_graph = GoalGraph()
    goal_graph.add_goal(
        Goal(
            goal_id="g1",
            title="Launch product",
            priority=9,
            progress=20,
            created_at=datetime(2026, 1, 1) - timedelta(days=45),
        )
    )
    goal_graph.add_goal(Goal(goal_id="g2", title="Improve research", priority=4, progress=60))
    goal_graph.add_milestone(Milestone(milestone_id="m1", goal_id="g1", title="Prototype", progress=25))
    goal_graph.add_milestone(Milestone(milestone_id="m2", goal_id="g2", title="Review", progress=80))
    dependency_graph = DependencyGraph()
    dependency_graph.add_dependency(TaskDependency("d1", "b", "a"))
    dependency_engine = DependencyIntelligenceEngine(dependency_graph)
    goal_engine = GoalIntelligenceEngine(goal_graph, dependency_engine=dependency_engine)
    return StrategicPlanningEngine(goal_engine, dependency_engine)


def test_strategic_plan_and_roadmap_item_validation() -> None:
    item = RoadmapItem(
        sequence=1,
        goal_id="g1",
        milestone_id="m1",
        task_id="a",
        recommended_start_day=1,
        recommended_end_day=1,
        priority_score=120,
        risk_score=-5,
    )
    plan = StrategicPlan(
        plan_id="p1",
        horizon_days=7,
        goal_ids=["g2", "g1", "g1"],
        milestone_ids=["m1"],
        risk_score=10,
        confidence_score=90,
        roadmap_items=[asdict(item)],
    )

    assert item.priority_score == 100.0
    assert item.risk_score == 0.0
    assert plan.goal_ids == ["g1", "g2"]
    assert isinstance(plan.roadmap_items[0], RoadmapItem)

    with pytest.raises(ValueError, match="horizon_days"):
        StrategicPlan("bad", 0, [], [], 0, 0, [])


def test_generates_7_30_and_90_day_plans() -> None:
    engine = build_engine()
    tasks = [{"id": "a", "goal_id": "g1"}, {"id": "b", "goal_id": "g1", "depends_on_task_ids": ["a"]}]
    now = datetime(2026, 1, 15)

    seven = engine.generate_7_day_plan(tasks, {"daily_capacity_hours": 4}, now=now)
    thirty = engine.generate_30_day_plan(tasks, {"daily_capacity_hours": 4}, now=now)
    ninety = engine.generate_90_day_plan(tasks, {"daily_capacity_hours": 4}, now=now)

    assert seven.horizon_days == 7
    assert thirty.horizon_days == 30
    assert ninety.horizon_days == 90
    assert seven.plan_id.startswith("strategic-7-20260115")
    assert len(seven.roadmap_items) == 2


def test_roadmap_respects_dependency_order_and_blocked_risk() -> None:
    engine = build_engine()
    tasks = [
        {"id": "b", "goal_id": "g1", "estimated_duration": 1, "depends_on_task_ids": ["a"]},
        {"id": "a", "goal_id": "g1", "estimated_duration": 1},
    ]

    plan = engine.generate_7_day_plan(tasks, {"daily_capacity_hours": 2}, now=datetime(2026, 1, 15))

    assert [item.task_id for item in plan.roadmap_items] == ["a", "b"]
    assert plan.roadmap_items[1].risk_score >= 35.0


def test_goal_forecasting_returns_bounded_probabilities() -> None:
    engine = build_engine()

    forecasts = engine.forecast_goals({"average_productivity": 80}, now=datetime(2026, 1, 15))

    assert [forecast["goal_id"] for forecast in forecasts] == ["g1", "g2"]
    assert all(0.0 <= forecast["goal_completion_probability"] <= 1.0 for forecast in forecasts)
    assert all(forecast["risk_level"] in {"low", "medium", "high", "critical"} for forecast in forecasts)


def test_milestone_forecasting_returns_bounded_probabilities() -> None:
    engine = build_engine()

    forecasts = engine.forecast_milestones({"hourly_productivity": {9: 80, 10: 60}})

    assert [forecast["milestone_id"] for forecast in forecasts] == ["m1", "m2"]
    assert all(0.0 <= forecast["milestone_completion_probability"] <= 1.0 for forecast in forecasts)


def test_risk_assessment_detects_blocked_neglected_and_overloaded_horizons() -> None:
    engine = build_engine()
    tasks = [
        {"id": "a", "goal_id": "g1", "estimated_duration": 20},
        {"id": "b", "goal_id": "g1", "estimated_duration": 20, "depends_on_task_ids": ["a"]},
    ]

    risk = engine.assess_risk(
        horizon_days=1,
        tasks=tasks,
        behavior_patterns={"daily_capacity_hours": 2},
        now=datetime(2026, 1, 15),
    )

    assert risk["blocked_task_count"] == 1
    assert risk["neglected_goal_count"] >= 1
    assert risk["overload_ratio"] > 1
    assert risk["risk_level"] in {"high", "critical"}


def test_next_week_recommendations_use_plan_summary_shape() -> None:
    engine = build_engine()
    tasks = [{"id": "a", "goal_id": "g1"}, {"id": "b", "goal_id": "g1", "depends_on_task_ids": ["a"]}]

    recommendation = engine.recommend_next_week(tasks, {}, now=datetime(2026, 1, 15))

    assert recommendation["horizon_days"] == 7
    assert recommendation["recommended_items"][0]["task_id"] == "a"
    assert "confidence_score" in recommendation


def test_empty_plan_is_valid_and_low_risk() -> None:
    engine = StrategicPlanningEngine()

    plan = engine.generate_7_day_plan([], {}, now=datetime(2026, 1, 15))

    assert plan.goal_ids == []
    assert plan.milestone_ids == []
    assert plan.roadmap_items == []
    assert plan.risk_score == 0.0


def test_strategic_planning_rejects_malformed_inputs() -> None:
    engine = build_engine()

    with pytest.raises(ValueError, match="horizon_days"):
        engine.generate_plan(0)

    with pytest.raises(ValueError, match="behavior_patterns"):
        engine.generate_7_day_plan([], "bad")

    with pytest.raises(ValueError, match="tasks"):
        engine.generate_7_day_plan({"id": "bad"})

    with pytest.raises(ValueError, match="duration"):
        engine.generate_7_day_plan([{"id": "a", "estimated_duration": 0}])

    with pytest.raises(ValueError, match="finite"):
        engine.generate_7_day_plan([{"id": "a", "estimated_duration": math.inf}])


def test_strategic_plans_are_deterministic_with_fixed_time() -> None:
    first_engine = build_engine()
    second_engine = build_engine()
    tasks = [{"id": "a", "goal_id": "g1"}, {"id": "b", "goal_id": "g1", "depends_on_task_ids": ["a"]}]
    now = datetime(2026, 1, 15)

    first = first_engine.generate_30_day_plan(tasks, {"average_productivity": 75}, now=now)
    second = second_engine.generate_30_day_plan(tasks, {"average_productivity": 75}, now=now)

    assert asdict(first) == asdict(second)


def test_active_plan_summary_is_optional() -> None:
    engine = build_engine()

    assert engine.summarize_active_plans() is None

    engine.generate_7_day_plan([{"id": "a"}], {}, now=datetime(2026, 1, 15))
    summary = engine.summarize_active_plans()

    assert summary is not None
    assert summary["horizon_days"] == 7
    assert summary["roadmap_item_count"] == 1


def test_orchestrator_strategic_plan_summary_is_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.strategic_planning_engine = build_engine()

    assert orchestrator._strategic_plan_summary() is None

    orchestrator.strategic_planning_engine.generate_7_day_plan(
        [{"id": "a", "goal_id": "g1"}],
        {},
        now=datetime(2026, 1, 15),
    )
    summary = orchestrator._strategic_plan_summary()

    assert summary is not None
    assert summary["plan_id"].startswith("strategic-7")


def test_orchestrator_rejects_malformed_strategic_summary() -> None:
    class BadStrategicEngine:
        def summarize_active_plans(self):
            return {"risk_score": math.inf}

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.strategic_planning_engine = BadStrategicEngine()

    with pytest.raises(ValueError, match="strategic_plan_summary"):
        orchestrator._strategic_plan_summary()
