from __future__ import annotations

import math

import pytest

from backend.app.domain.dependency_model import TaskDependency
from backend.app.domain.goal_model import Goal
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine
from backend.app.engines.goal_intelligence_engine import GoalIntelligenceEngine
from backend.app.knowledge.dependency_graph import DependencyGraph
from backend.app.knowledge.goal_graph import GoalGraph
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_task_dependency_model_validation_and_normalization() -> None:
    dependency = TaskDependency(
        dependency_id=" d1 ",
        task_id=" b ",
        depends_on_task_id=" a ",
        dependency_type="SOFT",
    )

    assert dependency.dependency_id == "d1"
    assert dependency.task_id == "b"
    assert dependency.depends_on_task_id == "a"
    assert dependency.dependency_type == "soft"

    with pytest.raises(ValueError, match="dependency_type"):
        TaskDependency("d2", "b", "a", "invalid")

    with pytest.raises(ValueError, match="itself"):
        TaskDependency("d3", "a", "a")


def test_dependency_graph_creation_removal_and_lookup() -> None:
    graph = DependencyGraph()
    graph.add_dependency(TaskDependency("d1", "b", "a", "hard"))

    assert graph.get_dependencies("b")[0].depends_on_task_id == "a"
    assert graph.get_dependents("a")[0].task_id == "b"
    assert graph.remove_dependency("d1") is True
    assert graph.get_dependencies("b") == []
    assert graph.remove_dependency("d1") is False


def test_hard_dependencies_block_until_prerequisite_completed() -> None:
    graph = DependencyGraph()
    graph.add_dependency(TaskDependency("d1", "b", "a", "hard"))

    assert graph.is_blocked("b", completed_task_ids=[]) is True
    assert graph.is_blocked("b", completed_task_ids=["a"]) is False


def test_soft_and_recommended_dependencies_do_not_block() -> None:
    graph = DependencyGraph()
    graph.add_dependency(TaskDependency("d1", "b", "a", "soft"))
    graph.add_dependency(TaskDependency("d2", "c", "a", "recommended"))

    assert graph.is_blocked("b", completed_task_ids=[]) is False
    assert graph.is_blocked("c", completed_task_ids=[]) is False


def test_cycle_detection_and_cycle_safe_ordering() -> None:
    graph = DependencyGraph()
    graph.add_dependency(TaskDependency("d1", "b", "a"))
    graph.add_dependency(TaskDependency("d2", "a", "b"))

    assert graph.detect_cycles() == [["a", "b", "a"]]
    assert graph.topological_sort() == []
    assert graph.get_critical_path() == []


def test_topological_sort_and_critical_path_are_deterministic() -> None:
    graph = DependencyGraph()
    graph.add_dependency(TaskDependency("d1", "b", "a"))
    graph.add_dependency(TaskDependency("d2", "c", "b"))
    graph.add_dependency(TaskDependency("d3", "d", "a"))

    assert graph.topological_sort() == ["a", "b", "c", "d"]
    assert graph.get_critical_path() == ["a", "b", "c"]
    assert graph.get_critical_path() == graph.get_critical_path()


def test_dependency_engine_enriches_blocked_and_critical_path_tasks() -> None:
    graph = DependencyGraph()
    graph.add_dependency(TaskDependency("d1", "b", "a"))
    graph.add_dependency(TaskDependency("d2", "c", "b"))
    engine = DependencyIntelligenceEngine(graph)
    tasks = [
        {"id": "a", "completed": False, "estimated_duration": 1},
        {"id": "b", "completed": False, "estimated_duration": 1},
        {"id": "c", "completed": False, "estimated_duration": 1},
    ]

    enriched = engine.enrich_tasks_with_dependencies(tasks)

    assert enriched[0]["id"] == "a"
    assert enriched[0]["blocked"] is False
    assert enriched[1]["blocked"] is True
    assert enriched[2]["blocked"] is True
    assert enriched[0]["dependency_impact_score"] > enriched[2]["dependency_impact_score"]
    assert enriched[0]["critical_path_priority"] > 0


def test_dependency_engine_filters_blocked_tasks() -> None:
    engine = DependencyIntelligenceEngine()
    tasks = [
        {"id": "a", "completed": False},
        {"id": "b", "completed": False, "depends_on_task_ids": ["a"]},
    ]

    blocked = engine.detect_blocked_tasks(tasks)

    assert [task["id"] for task in blocked] == ["b"]


def test_bottleneck_analysis_scores_downstream_dependents() -> None:
    graph = DependencyGraph()
    graph.add_dependency(TaskDependency("d1", "b", "a"))
    graph.add_dependency(TaskDependency("d2", "c", "a"))
    graph.add_dependency(TaskDependency("d3", "d", "b"))
    engine = DependencyIntelligenceEngine(graph)

    bottlenecks = engine.detect_bottlenecks()

    assert bottlenecks[0]["task_id"] == "a"
    assert bottlenecks[0]["downstream_dependents"] == 3
    assert bottlenecks[0]["dependency_impact_score"] == 60.0


def test_dependency_analysis_schema_and_execution_order() -> None:
    engine = DependencyIntelligenceEngine()
    tasks = [
        {"id": "a", "completed": True},
        {"id": "b", "completed": False, "depends_on_task_ids": ["a"]},
        {"id": "c", "completed": False, "depends_on_task_ids": ["b"]},
    ]

    analysis = engine.analyze_dependencies(tasks)

    assert analysis["blocked_tasks"] == ["c"]
    assert analysis["critical_path"] == ["a", "b", "c"]
    assert analysis["critical_path_length"] == 3
    assert analysis["execution_order"] == ["a", "b", "c"]
    assert analysis["cycles"] == []


def test_dependency_engine_rejects_malformed_inputs() -> None:
    engine = DependencyIntelligenceEngine()

    with pytest.raises(ValueError, match="tasks"):
        engine.enrich_tasks_with_dependencies({"id": "bad"})

    with pytest.raises(ValueError, match="Each task"):
        engine.enrich_tasks_with_dependencies([None])

    with pytest.raises(ValueError, match="id"):
        engine.enrich_tasks_with_dependencies([{"title": "Missing id"}])

    with pytest.raises(ValueError, match="unique"):
        engine.enrich_tasks_with_dependencies([{"id": "a"}, {"id": "a"}])

    with pytest.raises(ValueError, match="finite"):
        engine.enrich_tasks_with_dependencies([{"id": "a", "estimated_duration": math.inf}])

    with pytest.raises(ValueError, match="depends_on_task_ids"):
        engine.enrich_tasks_with_dependencies([{"id": "a", "depends_on_task_ids": [None]}])


def test_goal_health_can_include_dependency_risk() -> None:
    goal_graph = GoalGraph()
    goal_graph.add_goal(Goal(goal_id="g1", title="Goal", progress=95))
    goal_graph.link_task_to_goal({"id": "a", "completed": False}, "g1")
    goal_graph.link_task_to_goal({"id": "b", "completed": False, "depends_on_task_ids": ["a"]}, "g1")
    dependency_engine = DependencyIntelligenceEngine()
    goal_engine = GoalIntelligenceEngine(goal_graph, dependency_engine=dependency_engine)

    health = goal_engine.analyze_goal_health("g1")

    assert health["blocked_task_count"] == 1
    assert health["dependency_risk_score"] >= 20.0
    assert health["health_status"] == "at_risk"


def test_decision_engine_uses_dependency_signals_when_present() -> None:
    tasks = [
        {"id": "blocked", "priority": 10, "estimated_duration": 1, "blocked": True},
        {"id": "available", "priority": 1, "estimated_duration": 1, "dependency_score": 50},
    ]

    result = DecisionEngine().prioritize_tasks(tasks, [], {})

    assert result[0]["id"] == "available"
    assert result[1]["decision_breakdown"]["blocked_penalty"] == -1000.0
    assert result[0]["decision_breakdown"]["dependency_score"] == 15.0


def test_orchestrator_dependency_enrichment_is_optional_and_additive() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.dependency_intelligence_engine = DependencyIntelligenceEngine()

    normalized = orchestrator._normalize_tasks(
        [
            {"id": "a", "title": "A", "duration": 1, "priority": 1},
            {"id": "b", "title": "B", "duration": 1, "priority": 1, "depends_on_task_ids": ["a"]},
        ]
    )
    enriched = orchestrator._enrich_tasks_with_dependencies(normalized)

    assert enriched[0]["id"] == "input-1"
    assert enriched[1]["depends_on_task_ids"] == ["input-1"]
    assert enriched[1]["blocked"] is True
    assert enriched[1]["dependency_score"] < 0


def test_orchestrator_without_dependency_data_leaves_tasks_unchanged() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.dependency_intelligence_engine = DependencyIntelligenceEngine()
    tasks = [{"id": "a", "title": "A"}]

    assert orchestrator._enrich_tasks_with_dependencies(tasks) == tasks


def test_dependency_enrichment_is_deterministic() -> None:
    engine = DependencyIntelligenceEngine()
    tasks = [
        {"id": "a", "completed": False},
        {"id": "b", "completed": False, "depends_on_task_ids": ["a"]},
    ]

    first = engine.enrich_tasks_with_dependencies(tasks)
    second = engine.enrich_tasks_with_dependencies(tasks)

    assert first == second
