from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.app.domain.goal_model import Goal, Milestone
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.engines.goal_intelligence_engine import GoalIntelligenceEngine
from backend.app.knowledge.goal_graph import GoalGraph
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_goal_model_defaults_and_validation() -> None:
    goal = Goal(goal_id="g1", title="Build platform", progress=120)

    assert goal.goal_id == "g1"
    assert goal.status == "active"
    assert goal.progress == 100.0

    with pytest.raises(ValueError, match="goal_id"):
        Goal(goal_id="", title="Invalid")


def test_milestone_model_defaults_and_validation() -> None:
    milestone = Milestone(milestone_id="m1", goal_id="g1", title="Prototype", progress=-10)

    assert milestone.progress == 0.0

    with pytest.raises(ValueError, match="title"):
        Milestone(milestone_id="m2", goal_id="g1", title="")


def test_goal_graph_links_tasks_progress_and_dependencies() -> None:
    graph = GoalGraph()
    graph.add_goal(Goal(goal_id="g1", title="Launch", progress=20))
    graph.add_goal(Goal(goal_id="g2", title="Research", progress=50))
    graph.add_milestone(Milestone(milestone_id="m1", goal_id="g1", title="Alpha", progress=80))
    graph.add_dependency("g1", "g2")
    graph.link_task_to_goal({"id": "t1", "title": "Ship alpha"}, "g1")

    assert graph.get_goal_tasks("g1")[0]["goal_id"] == "g1"
    assert graph.get_goal_progress("g1") == 50.0
    assert graph.get_goal_dependencies("g1") == ["g2"]


def test_goal_graph_rejects_unknown_goal_links() -> None:
    graph = GoalGraph()

    with pytest.raises(ValueError, match="Unknown goal"):
        graph.link_task_to_goal({"id": "t1"}, "missing")


def test_goal_health_can_be_healthy_at_risk_or_critical() -> None:
    now = datetime(2026, 1, 1)
    graph = GoalGraph()
    graph.add_goal(Goal(goal_id="healthy", title="Healthy", progress=95, target_date=now + timedelta(days=90)))
    graph.add_goal(Goal(goal_id="risk", title="Risk", progress=70, target_date=now + timedelta(days=3)))
    graph.add_goal(Goal(goal_id="critical", title="Critical", progress=5, target_date=now - timedelta(days=1)))
    for index in range(5):
        graph.link_task_to_goal({"id": f"h{index}"}, "healthy", activity_at=now)
    for index in range(3):
        graph.link_task_to_goal({"id": f"r{index}"}, "risk", activity_at=now)

    engine = GoalIntelligenceEngine(graph)

    assert engine.analyze_goal_health("healthy", now=now)["health_status"] == "healthy"
    assert engine.analyze_goal_health("risk", now=now)["health_status"] == "at_risk"
    assert engine.analyze_goal_health("critical", now=now)["health_status"] == "critical"


def test_neglect_detection_flags_inactive_goals() -> None:
    now = datetime(2026, 1, 31)
    graph = GoalGraph()
    graph.add_goal(Goal(goal_id="g1", title="Neglected", created_at=now - timedelta(days=40)))

    result = GoalIntelligenceEngine(graph).detect_neglect("g1", now=now)

    assert result["neglected"] is True
    assert result["days_inactive"] == 40


def test_goal_prioritization_is_deterministic() -> None:
    graph = GoalGraph()
    graph.add_goal(Goal(goal_id="b", title="B", priority=3, progress=80))
    graph.add_goal(Goal(goal_id="a", title="A", priority=3, progress=20))
    engine = GoalIntelligenceEngine(graph)

    first = engine.prioritize_goals()
    second = engine.prioritize_goals()

    assert first == second
    assert first[0]["goal_id"] == "a"


def test_goal_engine_enriches_task_goal_alignment() -> None:
    graph = GoalGraph()
    graph.add_goal(Goal(goal_id="g1", title="Strategic Goal", priority=8, progress=10))
    engine = GoalIntelligenceEngine(graph)

    enriched = engine.enrich_tasks_with_goal_alignment([{"id": "t1", "goal_id": "g1"}])

    assert enriched[0]["goal_alignment_score"] > 0
    assert enriched[0]["goal_alignment_score"] <= 100


def test_next_best_action_uses_goal_alignment_and_decision_score() -> None:
    graph = GoalGraph()
    graph.add_goal(Goal(goal_id="g1", title="Important", priority=9, progress=5))
    graph.add_goal(Goal(goal_id="g2", title="Minor", priority=1, progress=80))
    engine = GoalIntelligenceEngine(graph)
    tasks = [
        {"id": "minor", "goal_id": "g2", "priority": 3, "estimated_duration": 1},
        {"id": "important", "goal_id": "g1", "priority": 3, "estimated_duration": 1},
    ]

    result = engine.recommend_next_best_action(tasks, {})

    assert result is not None
    assert result["id"] == "important"
    assert "decision_breakdown" in result


def test_decision_engine_consumes_goal_alignment_from_goal_layer() -> None:
    tasks = [
        {"id": "plain", "priority": 3, "estimated_duration": 1},
        {"id": "goal", "priority": 3, "estimated_duration": 1, "goal_alignment_score": 100},
    ]

    result = DecisionEngine().prioritize_tasks(tasks, [], {})

    assert result[0]["id"] == "goal"
    assert result[0]["decision_breakdown"]["goal_alignment_score"] == 20.0


def test_orchestrator_goal_enrichment_is_optional_and_additive() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    graph = GoalGraph()
    graph.add_goal(Goal(goal_id="g1", title="Goal", priority=8, progress=0))
    orchestrator.goal_intelligence_engine = GoalIntelligenceEngine(graph)

    normalized = orchestrator._normalize_tasks(
        [{"title": "Task", "duration": 1, "priority": 1, "goal_id": "g1"}]
    )
    enriched = orchestrator._enrich_tasks_with_goals(normalized)

    assert enriched[0]["goal_id"] == "g1"
    assert enriched[0]["goal_alignment_score"] > 0


def test_orchestrator_without_goals_leaves_tasks_unchanged() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)

    tasks = [{"id": "t1", "title": "Task"}]

    assert orchestrator._enrich_tasks_with_goals(tasks) == tasks


def test_goal_engine_rejects_malformed_tasks() -> None:
    engine = GoalIntelligenceEngine()

    with pytest.raises(ValueError, match="tasks"):
        engine.enrich_tasks_with_goal_alignment({"id": "bad"})

    with pytest.raises(ValueError, match="Each task"):
        engine.enrich_tasks_with_goal_alignment([None])
