from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from backend.app.domain.executive_execution_model import (
    ExecutionCheckpoint,
    ExecutionDeviation,
    ExecutionTimeline,
    ExecutiveAlert,
    PlanExecutionState,
    RecoveryRecommendation,
)
from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
from backend.app.orchestrator.executive_execution import ExecutiveExecutionEngine


BASE_TIME = datetime(2026, 1, 1, 9, 0, 0)


def checkpoint(**overrides):
    payload = {
        "checkpoint_id": "checkpoint-1",
        "timestamp": BASE_TIME,
        "selected_strategy": "Use optimized plan",
        "planned_progress": 50.0,
        "actual_progress": 40.0,
        "confidence": 75.0,
        "status": "on_track",
        "metadata": {"affected_goals": ["goal-1"]},
    }
    payload.update(overrides)
    return ExecutionCheckpoint(**payload)


def test_execution_domain_validation_and_immutability():
    item = checkpoint()

    assert item.actual_progress == 40.0
    with pytest.raises(FrozenInstanceError):
        item.actual_progress = 50.0
    with pytest.raises(ValueError, match="timestamp must be a datetime"):
        checkpoint(timestamp="bad")
    with pytest.raises(ValueError, match="actual_progress must be between"):
        checkpoint(actual_progress=-1.0)
    with pytest.raises(ValueError, match="confidence must be finite"):
        checkpoint(confidence=float("nan"))
    with pytest.raises(ValueError, match="status must be a valid"):
        checkpoint(status="running")


def test_execution_state_deviation_alert_recovery_and_timeline_validation():
    state = PlanExecutionState(
        state_id="state-1",
        timestamp=BASE_TIME,
        selected_strategy="Use optimized plan",
        progress=50.0,
        execution_health=70.0,
        execution_confidence=75.0,
        execution_stability=80.0,
        execution_momentum=65.0,
        execution_risk=20.0,
        schedule_reliability=85.0,
        goal_progress=50.0,
        recovery_readiness=75.0,
        status="on_track",
    )
    deviation = ExecutionDeviation(
        deviation_id="deviation-1",
        deviation_type="schedule_drift",
        severity="medium",
        severity_score=35.0,
        detected_at=BASE_TIME,
        affected_goals=["goal-1"],
        description="Behind schedule.",
        recommended_recovery="Reorder tasks.",
    )
    alert = ExecutiveAlert(
        alert_id="alert-1",
        alert_type="schedule_drift",
        severity="medium",
        message="Behind schedule.",
        timestamp=BASE_TIME,
        recommended_action="Reorder tasks.",
    )
    recovery = RecoveryRecommendation(
        recovery_id="recovery-1",
        action="reorder tasks",
        priority=1,
        expected_impact=75.0,
        rationale="Schedule drift detected.",
        created_at=BASE_TIME,
    )
    timeline = ExecutionTimeline("timeline-1", [checkpoint()], [deviation], [alert], BASE_TIME)

    assert state.execution_health == 70.0
    assert recovery.action == "reorder tasks"
    assert timeline.deviations[0].deviation_type == "schedule_drift"
    with pytest.raises(ValueError, match="deviation_type must be valid"):
        ExecutionDeviation("bad", "bad_type", "low", 10.0, BASE_TIME, [], "Bad.", "Recover.")
    with pytest.raises(ValueError, match="timeline checkpoints must have unique IDs"):
        ExecutionTimeline("timeline-2", [checkpoint(), checkpoint()], [], [], BASE_TIME)


def test_checkpoint_recording_duplicate_ids_and_bounded_history():
    engine = ExecutiveExecutionEngine(max_history=2)
    first = engine.record_execution_checkpoint(checkpoint(checkpoint_id="a"))
    second = engine.record_execution_checkpoint(checkpoint(checkpoint_id="b", timestamp=BASE_TIME + timedelta(minutes=1)))

    with pytest.raises(ValueError, match="checkpoint_id must be unique"):
        engine.record_execution_checkpoint(checkpoint(checkpoint_id="b", timestamp=BASE_TIME + timedelta(minutes=2)))

    third = engine.record_execution_checkpoint(checkpoint(checkpoint_id="c", timestamp=BASE_TIME + timedelta(minutes=3)))
    timeline = engine.execution_timeline()

    assert first.checkpoint_id == "a"
    assert [item.checkpoint_id for item in timeline.checkpoints] == [second.checkpoint_id, third.checkpoint_id]


def test_zero_and_full_progress_boundaries():
    engine = ExecutiveExecutionEngine()
    zero = checkpoint(checkpoint_id="zero", planned_progress=0.0, actual_progress=0.0, status="not_started")
    full = checkpoint(checkpoint_id="full", planned_progress=100.0, actual_progress=100.0, status="completed")

    zero_state = engine.estimate_execution_health(zero, [])
    full_state = engine.estimate_execution_health(full, [])

    assert zero_state.progress == 0.0
    assert full_state.status == "completed"
    assert full_state.execution_confidence >= zero_state.execution_confidence


def test_deviation_detection_schedule_goal_dependency_capacity_and_context():
    engine = ExecutiveExecutionEngine()
    late = checkpoint(planned_progress=80.0, actual_progress=30.0)
    context = {
        "goal_progress": 20.0,
        "blocked_tasks": ["task-1"],
        "capacity_utilization": 140.0,
        "context_mismatch": True,
        "priority_inversion": True,
        "affected_goals": ["goal-1"],
    }

    deviations = engine.detect_execution_deviation(
        late,
        executive_context=context,
        executive_reasoning={"recommended_action": "Use optimized plan"},
        risk_summary={"risk_level": "high"},
    )
    types = {item.deviation_type for item in deviations}

    assert "schedule_drift" in types
    assert "goal_drift" in types
    assert "blocked_dependency" in types
    assert "capacity_overload" in types
    assert "context_mismatch" in types
    assert "priority_inversion" in types
    assert "confidence_degradation" in types


def test_confidence_degradation_detection():
    engine = ExecutiveExecutionEngine()
    engine.record_execution_checkpoint(checkpoint(checkpoint_id="first", confidence=90.0))
    second = engine.record_execution_checkpoint(checkpoint(checkpoint_id="second", confidence=60.0, timestamp=BASE_TIME + timedelta(minutes=1)))

    deviations = engine.detect_execution_deviation(second)

    assert any(item.deviation_type == "falling_confidence" for item in deviations)


def test_health_confidence_recovery_alerts_dashboard_and_summary():
    engine = ExecutiveExecutionEngine()
    late = checkpoint(planned_progress=80.0, actual_progress=30.0)
    deviations = engine.detect_schedule_slippage(late)
    state = engine.estimate_execution_health(late, deviations)
    recovery = engine.generate_recovery_plan(deviations, state)
    alerts = engine.generate_execution_alerts(deviations, state)
    engine.record_execution_checkpoint(late)
    timeline = engine.execution_timeline(deviations, alerts)
    dashboard = engine.generate_executive_dashboard(state, deviations, alerts, recovery, timeline)

    assert engine.estimate_completion_probability(late, deviations) < 80.0
    assert engine.estimate_schedule_confidence(late, deviations) < 60.0
    assert recovery[0].action == "reorder tasks"
    assert alerts
    assert dashboard["current_execution_status"] in {"at_risk", "blocked", "on_track"}
    assert dashboard["executive_summary"]
    assert "deviations" in engine.generate_execution_explanation(state, deviations)


def test_track_execution_progress_generates_all_outputs():
    engine = ExecutiveExecutionEngine()
    outputs = engine.track_execution_progress(
        selected_strategy="Use optimized plan",
        checkpoint=checkpoint(planned_progress=60.0, actual_progress=20.0),
        executive_context={"affected_goals": ["goal-1"]},
        executive_reasoning={"recommended_action": "Use optimized plan", "confidence": 70.0},
        risk_summary={"risk_level": "medium"},
    )

    assert set(outputs) == {
        "execution_state",
        "execution_health",
        "execution_dashboard",
        "execution_alerts",
        "execution_deviations",
        "execution_recovery",
        "execution_summary",
        "execution_timeline",
        "execution_confidence",
        "next_execution_checkpoint",
    }
    assert outputs["execution_deviations"]
    assert outputs["execution_recovery"]


def test_execution_outputs_are_deterministic():
    first = ExecutiveExecutionEngine()
    second = ExecutiveExecutionEngine()

    first_output = first.track_execution_progress(
        selected_strategy="Use optimized plan",
        checkpoint=checkpoint(planned_progress=60.0, actual_progress=20.0),
    )
    second_output = second.track_execution_progress(
        selected_strategy="Use optimized plan",
        checkpoint=checkpoint(planned_progress=60.0, actual_progress=20.0),
    )

    assert first_output == second_output


def test_malformed_inputs_nan_infinity_and_empty_recovery_plan():
    engine = ExecutiveExecutionEngine()

    with pytest.raises(ValueError, match="max_history must be a positive integer"):
        ExecutiveExecutionEngine(max_history=0)
    with pytest.raises(ValueError, match="planned_progress must be finite"):
        checkpoint(planned_progress=float("inf"))
    with pytest.raises(ValueError, match="checkpoint_id must be a non-empty string"):
        checkpoint(checkpoint_id="")
    with pytest.raises(ValueError, match="priority must be a positive integer"):
        RecoveryRecommendation("r", "recover", 0, 50.0, "bad", BASE_TIME)
    with pytest.raises(ValueError, match="checkpoint must be a dictionary"):
        engine.record_execution_checkpoint(["bad"])


def test_large_history_remains_bounded_and_deterministic():
    engine = ExecutiveExecutionEngine(max_history=25)
    for index in range(100):
        engine.record_execution_checkpoint(
            checkpoint(
                checkpoint_id=f"checkpoint-{index}",
                timestamp=BASE_TIME + timedelta(minutes=index),
                planned_progress=min(100.0, index),
                actual_progress=min(100.0, index / 2),
            )
        )

    timeline = engine.execution_timeline()

    assert len(timeline.checkpoints) == 25
    assert timeline.checkpoints[0].checkpoint_id == "checkpoint-75"
    assert timeline == engine.execution_timeline()


def test_executive_brain_integration_and_backward_compatibility():
    result = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])
    required_existing = {
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
        "executive_reasoning",
        "executive_experience",
    }

    assert required_existing <= set(result)
    assert result["execution_state"]["selected_strategy"] == result["executive_reasoning"]["recommended_action"]
    assert 0.0 <= result["execution_health"]["execution_health"] <= 100.0
    assert isinstance(result["execution_alerts"], list)
    assert isinstance(result["execution_deviations"], list)
    assert isinstance(result["execution_recovery"], list)
    assert result["execution_summary"]["summary"]
    assert result["next_execution_checkpoint"]["checkpoint_id"]


def test_executive_brain_execution_outputs_are_deterministic():
    first = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])
    second = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])

    for key in (
        "execution_state",
        "execution_health",
        "execution_dashboard",
        "execution_alerts",
        "execution_deviations",
        "execution_recovery",
        "execution_summary",
        "execution_timeline",
        "execution_confidence",
        "next_execution_checkpoint",
    ):
        assert first[key] == second[key]
