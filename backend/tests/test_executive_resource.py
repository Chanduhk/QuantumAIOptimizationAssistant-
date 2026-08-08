from dataclasses import FrozenInstanceError

import pytest

from backend.app.domain.executive_resource_model import (
    AttentionAllocation,
    CapacityForecast,
    EnergyProfile,
    ExecutiveResourceSummary,
    ResourceAllocation,
    ResourceConflict,
    ResourceRecommendation,
    ResourceState,
)
from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
from backend.app.orchestrator.executive_resource import ExecutiveResourceEngine


def context(tasks=None):
    return {
        "context": {
            "current_tasks": tasks
            if tasks is not None
            else [
                {"id": "task-1", "task_type": "deep_work", "estimated_duration": 2.0},
                {"id": "task-2", "task_type": "meeting", "estimated_duration": 1.0},
            ],
            "behavior_patterns": {"average_energy_level": 70.0},
        },
        "adaptive_life": {"burnout_probability": 20.0},
        "behavior_learning": {"behavior_learning_summary": {"consistency_score": 70.0}},
        "context_snapshot": {"risk_state": "low"},
    }


def execution_outputs(**overrides):
    payload = {
        "execution_state": {"progress": 45.0, "execution_risk": 20.0},
        "execution_health": {"execution_health": 70.0},
        "execution_confidence": {"confidence": 75.0},
        "execution_deviations": [],
    }
    payload.update(overrides)
    return payload


def reasoning(**overrides):
    payload = {
        "recommended_action": "Use optimized plan",
        "confidence": 75.0,
        "reasoning_trace": {"conflicts_found": [], "tradeoffs": []},
    }
    payload.update(overrides)
    return payload


def resource_state(**overrides):
    payload = {
        "state_id": "state-1",
        "available_time": 75.0,
        "consumed_time": 50.0,
        "available_energy": 70.0,
        "consumed_energy": 35.0,
        "cognitive_load": 30.0,
        "attention_quality": 70.0,
        "strategic_capacity": 75.0,
        "operational_capacity": 70.0,
        "recovery_capacity": 75.0,
        "risk_budget": 80.0,
        "learning_capacity": 80.0,
        "decision_capacity": 75.0,
        "executive_reserve": 70.0,
    }
    payload.update(overrides)
    return ResourceState(**payload)


def test_resource_domain_validation_and_immutability():
    state = resource_state()

    assert state.executive_reserve == 70.0
    with pytest.raises(FrozenInstanceError):
        state.executive_reserve = 10.0
    with pytest.raises(ValueError, match="state_id must be a non-empty string"):
        resource_state(state_id="")
    with pytest.raises(ValueError, match="available_time must be finite"):
        resource_state(available_time=float("nan"))
    with pytest.raises(ValueError, match="consumed_time must be between"):
        resource_state(consumed_time=-1.0)


def test_resource_allocation_conflict_recommendation_validation():
    allocation = ResourceAllocation("alloc-1", "time", 60.0, 50.0, 83.0, 2, "Execution")
    conflict = ResourceConflict("conflict-1", "over_allocation", "high", "time", 70.0, "Too much work.", "Delay low-value work")
    recommendation = ResourceRecommendation("rec-1", "Delay low-value work", 1, 80.0, "Over allocation.", ["time"])

    assert allocation.resource_name == "time"
    assert conflict.severity == "high"
    assert recommendation.affected_resources == ["time"]
    with pytest.raises(ValueError, match="resource_name must be valid"):
        ResourceAllocation("bad", "invalid", 10.0, 10.0, 100.0, 1, "test")
    with pytest.raises(ValueError, match="conflict_type must be valid"):
        ResourceConflict("bad", "invalid", "low", "time", 10.0, "Bad.", "Recover.")
    with pytest.raises(ValueError, match="priority must be an integer"):
        ResourceRecommendation("bad", "Recover", 0, 10.0, "Bad.", ["time"])
    with pytest.raises(ValueError, match="affected_resources must be unique"):
        ResourceRecommendation("bad", "Recover", 1, 10.0, "Bad.", ["time", "time"])


def test_attention_energy_capacity_and_summary_validation():
    attention = AttentionAllocation("attention-1", 2, 10.0, 1, 80.0, 20.0)
    energy = EnergyProfile("energy-1", 75.0, 30.0, 80.0, 85.0)
    capacity = CapacityForecast("capacity-1", 7, 80.0, 60.0, 75.0, "low", 80.0)
    summary = ExecutiveResourceSummary("summary-1", 80.0, 75.0, 80.0, 80.0, 75.0, 85.0, 30.0, 80.0, 70.0, 78.0, "Healthy.")

    assert attention.deep_work_percent == 80.0
    assert energy.recovery_readiness == 85.0
    assert capacity.risk_level == "low"
    assert summary.executive_summary == "Healthy."
    with pytest.raises(ValueError, match="horizon_days must be a positive integer"):
        CapacityForecast("bad", 0, 80.0, 60.0, 75.0, "low", 80.0)
    with pytest.raises(ValueError, match="executive_summary must be a non-empty string"):
        ExecutiveResourceSummary("bad", 80.0, 75.0, 80.0, 80.0, 75.0, 85.0, 30.0, 80.0, 70.0, 78.0, "")


def test_evaluate_time_energy_attention_and_capacity_budgets():
    engine = ExecutiveResourceEngine()

    time = engine.evaluate_time_budget(context(), execution_outputs())
    energy = engine.evaluate_energy_budget(context(), {"learning_snapshot": {"behavior_volatility": 10.0}})
    attention = engine.evaluate_attention_budget(context())
    capacity = engine.evaluate_capacity_budget(context(), execution_outputs())

    assert time.resource_name == "time"
    assert 0.0 <= energy.energy_stability <= 100.0
    assert attention.context_switches == 1
    assert capacity.horizon_days == 7


def test_cognitive_load_increases_with_conflicts_and_deviations():
    engine = ExecutiveResourceEngine()
    load = engine.evaluate_cognitive_load(
        context(),
        reasoning(reasoning_trace={"conflicts_found": [{"id": "c1"}, {"id": "c2"}], "tradeoffs": []}),
        execution_outputs(execution_deviations=[{"id": "d1"}]),
    )

    assert load["cognitive_load"] > 20.0
    assert load["decision_fatigue"] >= 0.0


def test_resource_conflict_detection_covers_major_conflicts():
    engine = ExecutiveResourceEngine()
    state = resource_state(strategic_capacity=20.0, recovery_capacity=20.0, risk_budget=20.0, cognitive_load=90.0)
    attention = AttentionAllocation("attention-1", 1, 70.0, 8, 20.0, 80.0)
    energy = EnergyProfile("energy-1", 40.0, 90.0, 20.0, 20.0)
    capacity = CapacityForecast("capacity-1", 7, 40.0, 80.0, 200.0, "critical", 50.0)

    conflicts = engine.detect_resource_conflicts(state, attention, energy, capacity)
    types = {conflict.conflict_type for conflict in conflicts}

    assert "over_allocation" in types
    assert "attention_fragmentation" in types
    assert "context_switching" in types
    assert "energy_overload" in types
    assert "risk_saturation" in types
    assert "strategic_starvation" in types
    assert "recovery_deficit" in types
    assert "decision_fatigue" in types


def test_attention_fragmentation_and_context_switch_boundaries():
    engine = ExecutiveResourceEngine()
    calm = AttentionAllocation("calm", 3, 10.0, 1, 80.0, 20.0)
    fragmented = AttentionAllocation("frag", 1, 40.0, 7, 20.0, 70.0)

    assert engine.detect_attention_fragmentation(calm) == []
    assert engine.detect_context_switch_cost(calm) == []
    assert engine.detect_attention_fragmentation(fragmented)
    assert engine.detect_context_switch_cost(fragmented)


def test_efficiency_utilization_resilience_and_balance():
    engine = ExecutiveResourceEngine()
    state = resource_state()
    attention = AttentionAllocation("attention-1", 2, 10.0, 1, 80.0, 20.0)
    energy = EnergyProfile("energy-1", 75.0, 30.0, 80.0, 85.0)
    capacity = CapacityForecast("capacity-1", 7, 80.0, 60.0, 75.0, "low", 80.0)
    conflicts = engine.detect_resource_conflicts(state, attention, energy, capacity)
    summary = engine.evaluate_resource_balance(state, attention, energy, capacity, conflicts)

    assert 0.0 <= engine.estimate_resource_efficiency(state, conflicts) <= 100.0
    assert 0.0 <= engine.estimate_resource_utilization(state) <= 100.0
    assert 0.0 <= engine.estimate_resource_resilience(energy, capacity, conflicts) <= 100.0
    assert 0.0 <= summary.overall_resource_score <= 100.0


def test_recommendations_and_dashboard_generation():
    engine = ExecutiveResourceEngine()
    state = resource_state(strategic_capacity=20.0)
    attention = AttentionAllocation("attention-1", 1, 20.0, 1, 30.0, 20.0)
    energy = EnergyProfile("energy-1", 70.0, 30.0, 80.0, 80.0)
    capacity = CapacityForecast("capacity-1", 7, 70.0, 60.0, 85.0, "low", 80.0)
    conflicts = engine.detect_resource_conflicts(state, attention, energy, capacity)
    summary = engine.evaluate_resource_balance(state, attention, energy, capacity, conflicts)
    recommendations = engine.generate_resource_recommendations(conflicts, summary)
    dashboard = engine.generate_resource_dashboard(state, summary, conflicts, recommendations, attention, energy, capacity)

    assert recommendations
    assert dashboard["executive_summary"]
    assert dashboard["resource_conflicts"]


def test_generate_resource_summary_outputs_schema():
    engine = ExecutiveResourceEngine()
    outputs = engine.generate_resource_summary(
        executive_context=context(),
        executive_reasoning=reasoning(),
        executive_experience={"decision_count": 1},
        execution_outputs=execution_outputs(),
    )

    assert set(outputs) == {
        "resource_state",
        "resource_health",
        "resource_dashboard",
        "resource_conflicts",
        "resource_recommendations",
        "resource_summary",
        "resource_forecast",
        "resource_efficiency",
        "resource_utilization",
        "executive_resource_score",
    }
    assert isinstance(outputs["resource_conflicts"], list)
    assert outputs["resource_summary"]["executive_summary"]


def test_empty_state_and_zero_progress_are_supported():
    engine = ExecutiveResourceEngine()
    outputs = engine.generate_resource_summary(
        executive_context=context(tasks=[]),
        executive_reasoning=reasoning(confidence=0.0),
        execution_outputs=execution_outputs(execution_state={"progress": 0.0, "execution_risk": 0.0}, execution_confidence={"confidence": 0.0}),
    )

    assert outputs["resource_state"]["consumed_time"] == 0.0
    assert 0.0 <= outputs["executive_resource_score"]["score"] <= 100.0


def test_malformed_inputs_nan_infinity_and_invalid_containers():
    engine = ExecutiveResourceEngine()

    with pytest.raises(ValueError, match="max_history must be a positive integer"):
        ExecutiveResourceEngine(max_history=0)
    with pytest.raises(ValueError, match="executive_context must be a dictionary"):
        engine.evaluate_time_budget(["bad"])
    with pytest.raises(ValueError, match="current_tasks entries must be dictionaries"):
        engine.evaluate_attention_budget({"context": {"current_tasks": ["bad"]}})
    with pytest.raises(ValueError, match="finite"):
        engine.generate_resource_summary(executive_context=context([{"estimated_duration": float("inf")}]))
    with pytest.raises(ValueError, match="resource numeric inputs are out of range"):
        engine.evaluate_energy_budget({"context": {"behavior_patterns": {"average_energy_level": -1.0}}})


def test_bounded_history_after_large_dataset():
    engine = ExecutiveResourceEngine(max_history=3)
    for index in range(10):
        outputs = engine.generate_resource_summary(
            executive_context=context([{"id": f"task-{index}", "estimated_duration": 1.0}]),
            executive_reasoning=reasoning(confidence=60.0 + index),
            execution_outputs=execution_outputs(),
        )
        assert outputs["resource_summary"]["summary_id"] == "executive-resource-summary"

    assert len(engine._history) == 3


def test_resource_outputs_are_deterministic():
    first = ExecutiveResourceEngine().generate_resource_summary(
        executive_context=context(),
        executive_reasoning=reasoning(),
        executive_experience={"decision_count": 1},
        execution_outputs=execution_outputs(),
    )
    second = ExecutiveResourceEngine().generate_resource_summary(
        executive_context=context(),
        executive_reasoning=reasoning(),
        executive_experience={"decision_count": 1},
        execution_outputs=execution_outputs(),
    )

    assert first == second


def test_large_task_dataset_is_processed_deterministically():
    tasks = [{"id": f"task-{index}", "task_type": f"type-{index % 5}", "estimated_duration": 0.25} for index in range(200)]
    outputs = ExecutiveResourceEngine().generate_resource_summary(
        executive_context=context(tasks),
        executive_reasoning=reasoning(),
        execution_outputs=execution_outputs(),
    )

    assert outputs["resource_dashboard"]["attention_distribution"]["context_switches"] == 4
    assert 0.0 <= outputs["resource_utilization"]["utilization"] <= 100.0


def test_executive_brain_resource_integration_and_backward_compatibility():
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "task-1", "task_type": "deep_work", "estimated_duration": 2.0}],
        behavior_patterns={"average_energy_level": 75.0},
        goals=[],
    )

    existing_keys = {
        "executive_context",
        "executive_objectives",
        "candidate_plans",
        "recommended_plan",
        "future_analysis",
        "tradeoff_analysis",
        "risk_summary",
        "executive_summary",
        "explanations",
        "reflection",
        "execution_state",
    }
    resource_keys = {
        "resource_state",
        "resource_health",
        "resource_dashboard",
        "resource_conflicts",
        "resource_recommendations",
        "resource_summary",
        "resource_forecast",
        "resource_efficiency",
        "resource_utilization",
        "executive_resource_score",
    }

    assert existing_keys <= set(result)
    assert resource_keys <= set(result)
    assert 0.0 <= result["executive_resource_score"]["score"] <= 100.0
    assert result["resource_summary"]["executive_summary"]


def test_executive_brain_resource_outputs_are_deterministic():
    first = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])
    second = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])

    for key in (
        "resource_state",
        "resource_health",
        "resource_dashboard",
        "resource_conflicts",
        "resource_recommendations",
        "resource_summary",
        "resource_forecast",
        "resource_efficiency",
        "resource_utilization",
        "executive_resource_score",
    ):
        assert first[key] == second[key]
