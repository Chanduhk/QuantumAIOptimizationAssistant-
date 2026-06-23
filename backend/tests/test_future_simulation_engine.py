from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timedelta

import pytest

from backend.app.domain.dependency_model import TaskDependency
from backend.app.domain.goal_model import Goal, Milestone
from backend.app.domain.simulation_model import SimulationResult, SimulationScenario
from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine
from backend.app.engines.future_simulation_engine import FutureSimulationEngine
from backend.app.engines.goal_intelligence_engine import GoalIntelligenceEngine
from backend.app.engines.strategic_planning_engine import StrategicPlanningEngine
from backend.app.knowledge.dependency_graph import DependencyGraph
from backend.app.knowledge.goal_graph import GoalGraph
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def build_engine() -> FutureSimulationEngine:
    goal_graph = GoalGraph()
    goal_graph.add_goal(
        Goal(
            goal_id="g1",
            title="Launch",
            priority=9,
            progress=35,
            created_at=datetime(2026, 1, 1) - timedelta(days=15),
        )
    )
    goal_graph.add_goal(Goal(goal_id="g2", title="Research", priority=5, progress=65))
    goal_graph.add_milestone(Milestone(milestone_id="m1", goal_id="g1", title="Prototype", progress=40))
    goal_graph.add_milestone(Milestone(milestone_id="m2", goal_id="g2", title="Review", progress=75))
    dependency_graph = DependencyGraph()
    dependency_graph.add_dependency(TaskDependency("d1", "b", "a"))
    dependency_engine = DependencyIntelligenceEngine(dependency_graph)
    goal_engine = GoalIntelligenceEngine(goal_graph, dependency_engine=dependency_engine)
    strategic_engine = StrategicPlanningEngine(goal_engine, dependency_engine)
    return FutureSimulationEngine(goal_engine, dependency_engine, strategic_engine)


def sample_tasks() -> list[dict]:
    return [
        {"id": "a", "goal_id": "g1", "estimated_duration": 2, "completed": False},
        {"id": "b", "goal_id": "g1", "estimated_duration": 2, "depends_on_task_ids": ["a"]},
        {"id": "c", "goal_id": "g2", "estimated_duration": 1},
    ]


def test_simulation_models_validate_and_bound_values() -> None:
    scenario = SimulationScenario(
        scenario_id="s1",
        scenario_name="Baseline",
        horizon_days=30,
        goal_ids=["g2", "g1", "g1"],
        task_ids=["b", "a"],
        assumptions={"scenario_type": "baseline"},
        created_at=datetime(2026, 1, 1),
    )
    result = SimulationResult(
        scenario_id="s1",
        success_probability=2,
        goal_completion_probability=-1,
        milestone_completion_probability=0.5,
        workload_score=150,
        risk_score=-10,
        confidence_score=200,
        projected_state={"state": "ok"},
        recommendations=["Maintain current execution strategy"],
    )

    assert scenario.goal_ids == ["g1", "g2"]
    assert scenario.task_ids == ["a", "b"]
    assert result.success_probability == 1.0
    assert result.goal_completion_probability == 0.0
    assert result.workload_score == 100.0
    assert result.risk_score == 0.0
    assert result.confidence_score == 100.0

    with pytest.raises(ValueError, match="horizon_days"):
        SimulationScenario("bad", "Bad", 0, [], [], {})

    with pytest.raises(ValueError, match="recommendations"):
        SimulationResult("s2", 0, 0, 0, 0, 0, 0, {}, [1])


def test_baseline_simulation_returns_expected_schema() -> None:
    engine = build_engine()

    result = engine.simulate_baseline(
        sample_tasks(),
        {"average_productivity": 75, "daily_capacity_hours": 4},
        horizon_days=30,
        now=datetime(2026, 1, 15),
    )

    assert result.scenario_id.startswith("simulation-baseline-30-20260115")
    assert 0.0 <= result.success_probability <= 1.0
    assert 0.0 <= result.goal_completion_probability <= 1.0
    assert 0.0 <= result.milestone_completion_probability <= 1.0
    assert result.projected_state["projected_completion_days"] > 0
    assert result.projected_state["projected_goal_state"] in {"on_track", "at_risk", "likely_delayed"}
    assert result.recommendations


def test_accelerated_simulation_improves_success_over_delayed() -> None:
    accelerated_engine = build_engine()
    delayed_engine = build_engine()
    now = datetime(2026, 1, 15)

    accelerated = accelerated_engine.simulate_accelerated(
        sample_tasks(),
        {"average_productivity": 75, "daily_capacity_hours": 4},
        now=now,
    )
    delayed = delayed_engine.simulate_delayed(
        sample_tasks(),
        {"average_productivity": 75, "daily_capacity_hours": 4},
        now=now,
    )

    assert accelerated.success_probability > delayed.success_probability
    assert accelerated.projected_state["projected_completion_days"] <= delayed.projected_state["projected_completion_days"]


def test_dependency_failure_simulation_increases_risk_and_blocked_count() -> None:
    baseline_engine = build_engine()
    failure_engine = build_engine()
    now = datetime(2026, 1, 15)

    baseline = baseline_engine.simulate_baseline(sample_tasks(), {"daily_capacity_hours": 4}, now=now)
    failure = failure_engine.simulate_dependency_failure(sample_tasks(), {"daily_capacity_hours": 4}, now=now)

    assert failure.risk_score > baseline.risk_score
    assert failure.projected_state["blocked_task_count"] >= 1
    assert "Recover or unblock critical dependencies" in failure.recommendations


def test_workload_expansion_adds_tasks_and_recommends_reduction() -> None:
    engine = build_engine()

    result = engine.simulate_workload_expansion(
        sample_tasks(),
        {"daily_capacity_hours": 1},
        additional_tasks=8,
        now=datetime(2026, 1, 15),
    )

    assert result.projected_state["task_count"] == len(sample_tasks()) + 8
    assert result.workload_score > 0
    assert "Defer low-alignment tasks before accepting expansion" in result.recommendations


def test_compare_scenarios_ranks_best_outcome_first() -> None:
    engine = build_engine()
    now = datetime(2026, 1, 15)
    scenarios = [
        engine.create_scenario("Delayed", 30, assumptions={"scenario_type": "delayed"}, created_at=now),
        engine.create_scenario("Accelerated", 30, assumptions={"scenario_type": "accelerated"}, created_at=now),
        engine.create_scenario("Baseline", 30, assumptions={"scenario_type": "baseline"}, created_at=now),
    ]

    ranked = engine.compare_scenarios(
        scenarios,
        sample_tasks(),
        {"average_productivity": 75, "daily_capacity_hours": 4},
        now=now,
    )

    assert [item["rank"] for item in ranked] == [1, 2, 3]
    assert ranked[0]["success_probability"] >= ranked[-1]["success_probability"]
    assert "accelerated" in ranked[0]["scenario_id"]


def test_goal_and_milestone_probabilities_use_forecasts() -> None:
    engine = build_engine()

    result = engine.simulate_baseline(
        sample_tasks(),
        {"average_productivity": 90, "daily_capacity_hours": 4},
        now=datetime(2026, 1, 15),
    )

    assert result.goal_completion_probability > 0
    assert result.milestone_completion_probability > 0
    assert result.confidence_score > 0


def test_empty_scenario_is_valid_and_deterministic() -> None:
    first_engine = FutureSimulationEngine()
    second_engine = FutureSimulationEngine()
    now = datetime(2026, 1, 15)

    first = first_engine.simulate_baseline([], {}, now=now)
    second = second_engine.simulate_baseline([], {}, now=now)

    assert asdict(first) == asdict(second)
    assert first.projected_state["task_count"] == 0
    assert first.projected_state["projected_completion_days"] == 0


def test_simulation_rejects_malformed_inputs() -> None:
    engine = build_engine()

    with pytest.raises(ValueError, match="tasks"):
        engine.simulate_baseline({"id": "bad"})

    with pytest.raises(ValueError, match="Each task"):
        engine.simulate_baseline([None])

    with pytest.raises(ValueError, match="duration"):
        engine.simulate_baseline([{"id": "a", "estimated_duration": 0}])

    with pytest.raises(ValueError, match="finite"):
        engine.simulate_baseline([{"id": "a", "estimated_duration": math.inf}])

    with pytest.raises(ValueError, match="behavior_patterns"):
        engine.simulate_baseline([], "bad")

    with pytest.raises(ValueError, match="scenario_type"):
        engine.create_scenario("Bad", 30, assumptions={"scenario_type": "unknown"})

    with pytest.raises(ValueError, match="non-negative"):
        engine.simulate_workload_expansion([], {}, additional_tasks=-1)


def test_future_projection_summary_is_optional() -> None:
    engine = build_engine()

    assert engine.summarize_future_projection() is None

    engine.simulate_baseline(sample_tasks(), {}, now=datetime(2026, 1, 15))
    summary = engine.summarize_future_projection()

    assert summary is not None
    assert summary["scenario_id"].startswith("simulation-baseline")
    assert summary["projected_completion_days"] > 0


def test_orchestrator_future_projection_summary_is_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.future_simulation_engine = build_engine()

    assert orchestrator._future_projection_summary() is None

    orchestrator.future_simulation_engine.simulate_baseline(sample_tasks(), {}, now=datetime(2026, 1, 15))
    summary = orchestrator._future_projection_summary()

    assert summary is not None
    assert summary["scenario_id"].startswith("simulation-baseline")


def test_orchestrator_rejects_malformed_future_projection_summary() -> None:
    class BadSimulationEngine:
        def summarize_future_projection(self):
            return {"risk_score": math.inf}

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.future_simulation_engine = BadSimulationEngine()

    with pytest.raises(ValueError, match="future_projection_summary"):
        orchestrator._future_projection_summary()


def test_simulation_outputs_are_deterministic_with_fixed_time() -> None:
    first_engine = build_engine()
    second_engine = build_engine()
    now = datetime(2026, 1, 15)

    first = first_engine.simulate_dependency_failure(
        sample_tasks(),
        {"average_productivity": 70, "daily_capacity_hours": 4},
        now=now,
    )
    second = second_engine.simulate_dependency_failure(
        sample_tasks(),
        {"average_productivity": 70, "daily_capacity_hours": 4},
        now=now,
    )

    assert asdict(first) == asdict(second)
