from __future__ import annotations

import math
from dataclasses import asdict

import pytest

from backend.app.domain.multi_objective_model import OptimizationObjective, OptimizationResult
from backend.app.domain.simulation_model import SimulationResult
from backend.app.engines.multi_objective_optimization_engine import MultiObjectiveOptimizationEngine
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def simulation(
    scenario_id: str,
    *,
    scenario_type: str,
    success: float,
    goal: float,
    milestone: float,
    workload: float,
    risk: float,
    confidence: float,
    blocked: int = 0,
    days: int = 20,
) -> SimulationResult:
    return SimulationResult(
        scenario_id=scenario_id,
        success_probability=success,
        goal_completion_probability=goal,
        milestone_completion_probability=milestone,
        workload_score=workload,
        risk_score=risk,
        confidence_score=confidence,
        projected_state={
            "scenario_type": scenario_type,
            "projected_goal_state": "on_track" if goal >= 0.75 else "at_risk",
            "blocked_task_count": blocked,
            "projected_completion_days": days,
        },
        recommendations=["scenario recommendation"],
    )


def test_objective_and_result_validation() -> None:
    objective = OptimizationObjective("Productivity", 200, "Desc", True)
    result = OptimizationResult(
        selected_scenario_id="s1",
        selected_scenario_name="Baseline",
        overall_score=120,
        objective_scores={"Productivity": 200},
        tradeoffs=["No major tradeoffs detected"],
        recommendations=["Select Baseline"],
        optimization_summary={"ranking": []},
    )

    assert objective.weight == 100.0
    assert result.overall_score == 100.0
    assert result.objective_scores["Productivity"] == 100.0

    with pytest.raises(ValueError, match="objective_name"):
        OptimizationObjective("", 1.0)

    with pytest.raises(ValueError, match="weight"):
        OptimizationObjective("Productivity", math.inf)

    with pytest.raises(ValueError, match="recommendations"):
        OptimizationResult("s1", "S", 1, {}, [], [1], {})


def test_scenario_ranking_selects_best_weighted_future() -> None:
    engine = MultiObjectiveOptimizationEngine()
    scenarios = [
        simulation("delayed", scenario_type="delayed", success=0.45, goal=0.45, milestone=0.4, workload=20, risk=20, confidence=55),
        simulation("accelerated", scenario_type="accelerated", success=0.82, goal=0.8, milestone=0.75, workload=30, risk=25, confidence=80),
        simulation("risky", scenario_type="dependency_failure", success=0.9, goal=0.85, milestone=0.8, workload=60, risk=80, confidence=70, blocked=2),
    ]

    result = engine.optimize(scenarios)

    assert result.selected_scenario_id == "accelerated"
    assert result.selected_scenario_name == "Accelerated"
    assert result.overall_score > 0
    assert result.optimization_summary["ranking"][0]["scenario_id"] == "accelerated"


def test_risk_heavy_scenario_is_rejected_despite_high_productivity() -> None:
    engine = MultiObjectiveOptimizationEngine()
    safe = simulation("safe", scenario_type="baseline", success=0.7, goal=0.7, milestone=0.7, workload=15, risk=10, confidence=75)
    risky = simulation("risky", scenario_type="dependency_failure", success=0.95, goal=0.95, milestone=0.9, workload=70, risk=90, confidence=65, blocked=3)

    result = engine.optimize([risky, safe])

    assert result.selected_scenario_id == "safe"
    assert result.optimization_summary["ranking"][-1]["scenario_id"] == "risky"


def test_goal_heavy_objective_selects_goal_best_scenario() -> None:
    objectives = [
        OptimizationObjective("Goal Completion", 10.0),
        OptimizationObjective("Risk Reduction", 0.5),
        OptimizationObjective("Productivity", 0.5),
    ]
    engine = MultiObjectiveOptimizationEngine(objectives)
    goal_heavy = simulation("goal", scenario_type="accelerated", success=0.65, goal=0.95, milestone=0.7, workload=40, risk=35, confidence=70)
    balanced = simulation("balanced", scenario_type="baseline", success=0.75, goal=0.7, milestone=0.75, workload=20, risk=15, confidence=80)

    result = engine.optimize([balanced, goal_heavy])

    assert result.selected_scenario_id == "goal"


def test_balanced_scenario_selection_with_default_objectives() -> None:
    engine = MultiObjectiveOptimizationEngine()
    balanced = simulation("balanced", scenario_type="baseline", success=0.78, goal=0.76, milestone=0.75, workload=20, risk=18, confidence=82)
    fast = simulation("fast", scenario_type="accelerated", success=0.9, goal=0.82, milestone=0.72, workload=70, risk=55, confidence=70)
    safe_slow = simulation("safe", scenario_type="delayed", success=0.5, goal=0.52, milestone=0.6, workload=5, risk=5, confidence=65, days=45)

    result = engine.optimize([fast, safe_slow, balanced])

    assert result.selected_scenario_id == "balanced"


def test_tradeoff_analysis_and_recommendations_are_generated() -> None:
    engine = MultiObjectiveOptimizationEngine()
    selected = simulation("selected", scenario_type="accelerated", success=0.85, goal=0.85, milestone=0.8, workload=40, risk=45, confidence=85)
    alternative = simulation("alternative", scenario_type="baseline", success=0.65, goal=0.6, milestone=0.6, workload=10, risk=15, confidence=70)

    result = engine.optimize([selected, alternative])

    assert "Higher productivity vs higher risk" in result.tradeoffs
    assert any("Select Accelerated" in recommendation for recommendation in result.recommendations)
    assert any("Review tradeoffs" in recommendation for recommendation in result.recommendations)


def test_rank_scenarios_returns_objective_breakdown() -> None:
    engine = MultiObjectiveOptimizationEngine()
    ranked = engine.rank_scenarios(
        [
            simulation("a", scenario_type="baseline", success=0.6, goal=0.6, milestone=0.6, workload=30, risk=30, confidence=70),
            simulation("b", scenario_type="accelerated", success=0.8, goal=0.8, milestone=0.75, workload=20, risk=20, confidence=80),
        ]
    )

    assert ranked[0]["simulation"].scenario_id == "b"
    assert "Productivity" in ranked[0]["objective_scores"]
    assert all(0.0 <= score <= 100.0 for score in ranked[0]["objective_scores"].values())


def test_optimizer_is_deterministic() -> None:
    first_engine = MultiObjectiveOptimizationEngine()
    second_engine = MultiObjectiveOptimizationEngine()
    scenarios = [
        simulation("a", scenario_type="baseline", success=0.7, goal=0.7, milestone=0.7, workload=20, risk=20, confidence=75),
        simulation("b", scenario_type="accelerated", success=0.8, goal=0.75, milestone=0.72, workload=30, risk=25, confidence=80),
    ]

    first = first_engine.optimize(scenarios)
    second = second_engine.optimize(scenarios)

    assert asdict(first) == asdict(second)


def test_optimizer_rejects_empty_and_malformed_inputs() -> None:
    engine = MultiObjectiveOptimizationEngine()

    with pytest.raises(ValueError, match="simulation_results"):
        engine.optimize("bad")

    with pytest.raises(ValueError, match="At least one"):
        engine.optimize([])

    with pytest.raises(ValueError, match="unique"):
        engine.optimize(
            [
                simulation("dup", scenario_type="baseline", success=0.5, goal=0.5, milestone=0.5, workload=1, risk=1, confidence=1),
                simulation("dup", scenario_type="baseline", success=0.6, goal=0.6, milestone=0.6, workload=1, risk=1, confidence=1),
            ]
        )

    with pytest.raises(ValueError, match="Unsupported objective"):
        engine.optimize(
            [simulation("a", scenario_type="baseline", success=0.5, goal=0.5, milestone=0.5, workload=1, risk=1, confidence=1)],
            objectives=[OptimizationObjective("Unknown", 1.0)],
        )


def test_optimizer_rejects_disabled_or_zero_weight_objectives() -> None:
    engine = MultiObjectiveOptimizationEngine()
    scenario = simulation("a", scenario_type="baseline", success=0.5, goal=0.5, milestone=0.5, workload=1, risk=1, confidence=1)

    with pytest.raises(ValueError, match="enabled"):
        engine.optimize([scenario], objectives=[OptimizationObjective("Productivity", 1.0, enabled=False)])

    with pytest.raises(ValueError, match="positive weight"):
        engine.optimize([scenario], objectives=[OptimizationObjective("Productivity", 0.0)])


def test_latest_optimization_summary_is_optional() -> None:
    engine = MultiObjectiveOptimizationEngine()

    assert engine.summarize_latest_optimization() is None

    engine.optimize(
        [simulation("a", scenario_type="baseline", success=0.7, goal=0.7, milestone=0.7, workload=10, risk=10, confidence=80)]
    )
    summary = engine.summarize_latest_optimization()

    assert summary is not None
    assert summary["selected_future"]["scenario_id"] == "a"
    assert summary["optimization_summary"]["ranking_count"] == 1


def test_orchestrator_optimization_summary_is_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.multi_objective_optimization_engine = MultiObjectiveOptimizationEngine()

    assert orchestrator._multi_objective_optimization_summary() is None

    orchestrator.multi_objective_optimization_engine.optimize(
        [simulation("a", scenario_type="baseline", success=0.7, goal=0.7, milestone=0.7, workload=10, risk=10, confidence=80)]
    )
    summary = orchestrator._multi_objective_optimization_summary()

    assert summary is not None
    assert summary["selected_future"]["scenario_id"] == "a"
    assert "optimization_summary" in summary


def test_orchestrator_rejects_malformed_optimization_summary() -> None:
    class BadOptimizationEngine:
        def summarize_latest_optimization(self):
            return {"selected_future": {"overall_score": math.inf}, "optimization_summary": {}}

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.multi_objective_optimization_engine = BadOptimizationEngine()

    with pytest.raises(ValueError, match="multi_objective_optimization"):
        orchestrator._multi_objective_optimization_summary()
