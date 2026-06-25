from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timedelta

import pytest

from backend.app.domain.context_awareness_model import (
    ContextConflict,
    ContextInsight,
    ContextShift,
    ContextSignal,
    ContextSnapshot,
)
from backend.app.engines.behavior_learning_engine import BehaviorLearningEngine
from backend.app.engines.context_awareness_engine import ContextAwarenessEngine
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_context_awareness_domain_validation() -> None:
    signal = ContextSignal("s1", "Focus", 120, 2, "test")
    snapshot = ContextSnapshot("snap1", "Focused", "healthy_load", "active", "positive", "LOW", "high", 2, [asdict(signal)])
    shift = ContextShift("sh1", "a", "b", "risk", "IMPROVING", 120, 2)
    conflict = ContextConflict("c1", "capacity", "HIGH", "Too much work", ["b", "a", "a"], 2)
    insight = ContextInsight("i1", "Risk elevated", 2, ["e"], "Reduce load")

    assert signal.value == 100.0
    assert signal.confidence == 1.0
    assert snapshot.momentum_state == "positive"
    assert snapshot.risk_state == "low"
    assert shift.magnitude == 100.0
    assert conflict.affected_items == ["a", "b"]
    assert insight.confidence == 1.0

    with pytest.raises(ValueError, match="signal_id"):
        ContextSignal("", "focus", 1, 1, "test")

    with pytest.raises(ValueError, match="momentum_state"):
        ContextSnapshot("s", "f", "w", "g", "bad", "low", "e", 1)

    with pytest.raises(ValueError, match="direction"):
        ContextShift("s", "a", "b", "risk", "bad", 1, 1)

    with pytest.raises(ValueError, match="severity"):
        ContextConflict("c", "risk", "bad", "desc")

    with pytest.raises(ValueError, match="confidence"):
        ContextInsight("i", "insight", math.inf, [], "rec")


def test_snapshot_generation_from_current_state() -> None:
    engine = ContextAwarenessEngine()
    snapshot = engine.generate_snapshot(
        current_context={"current_hour": 9, "behavior_patterns": {"best_focus_hours": [9], "average_energy_level": 80}},
        workload={"available_capacity": 4, "projected_workload": 3},
        goals=[{"goal_id": "g1", "progress": 70}],
        behavior_learning_summary={"consistency_score": 80, "habit_strength": 75},
        adaptive_life_summary={"burnout_probability": 0.1, "risk_count": 0},
        meta_cognitive_summary={"average_error": 5},
        timestamp=datetime(2026, 1, 1),
    )

    assert snapshot.focus_state == "focused"
    assert snapshot.workload_state == "healthy_load"
    assert snapshot.goal_state == "advancing"
    assert snapshot.momentum_state == "positive"
    assert snapshot.risk_state == "low"
    assert snapshot.energy_state == "high"
    assert len(snapshot.signals) == 5


def test_context_shifts_detect_improving_declining_stable_and_major_transitions() -> None:
    engine = ContextAwarenessEngine()
    engine.generate_snapshot(
        current_context={"current_hour": 15, "behavior_patterns": {"best_focus_hours": [9], "average_energy_level": 30}},
        workload={"capacity_utilization": 1.3},
        goals=[{"progress": 10}],
        behavior_learning_summary={"habit_strength": 20},
        adaptive_life_summary={"burnout_probability": 0.8, "risk_count": 3},
        timestamp=datetime(2026, 1, 1),
    )
    engine.generate_snapshot(
        current_context={"current_hour": 9, "behavior_patterns": {"best_focus_hours": [9], "average_energy_level": 80}},
        workload={"capacity_utilization": 0.8},
        goals=[{"progress": 80}],
        behavior_learning_summary={"habit_strength": 85, "consistency_score": 80},
        adaptive_life_summary={"burnout_probability": 0.1, "risk_count": 0},
        timestamp=datetime(2026, 1, 2),
    )

    shifts = engine.detect_context_shifts()
    directions = {shift.shift_type: shift.direction for shift in shifts}

    assert set(directions) == {"focus", "momentum", "risk"}
    assert "major_transition" in directions.values()


def test_context_conflicts_detect_all_required_conflict_types() -> None:
    engine = ContextAwarenessEngine()
    snapshot = engine.generate_snapshot(workload={"capacity_utilization": 1.4}, timestamp=datetime(2026, 1, 1))

    conflicts = engine.detect_context_conflicts(
        snapshot=snapshot,
        tasks=[
            {"id": "t1", "goal_id": "missing", "scheduled_hour": 9, "priority": 8, "blocked": True},
            {"id": "t2", "goal_id": "g1", "scheduled_hour": 9, "priority": 1},
        ],
        goals=[{"goal_id": "g1", "progress": 20}],
        dependency_state={"blocked_tasks": ["t1"]},
    )
    conflict_types = {conflict.conflict_type for conflict in conflicts}

    assert conflict_types == {"capacity", "dependency", "goal", "priority", "schedule"}


def test_momentum_and_recovery_analysis() -> None:
    engine = ContextAwarenessEngine()

    momentum = engine.analyze_momentum(
        goals=[{"progress": 80}],
        behavior_learning_summary={"habit_strength": 90},
        adaptive_life_summary={"risk_count": 0},
    )
    recovery = engine.analyze_recovery(
        behavior_learning_summary={"consistency_score": 80},
        adaptive_life_summary={"burnout_probability": 0.1, "load_status": "healthy_load"},
        meta_cognitive_summary={"average_error": 10},
    )

    assert momentum["momentum_state"] == "positive"
    assert recovery == {
        "burnout_recovery": True,
        "overload_recovery": True,
        "performance_recovery": True,
    }


def test_context_insights_and_explainability() -> None:
    engine = ContextAwarenessEngine()
    snapshot = engine.generate_snapshot(
        current_context={"behavior_patterns": {"average_energy_level": 20}},
        adaptive_life_summary={"burnout_probability": 0.9, "risk_count": 3},
        timestamp=datetime(2026, 1, 1),
    )
    conflicts = engine.detect_context_conflicts(snapshot=snapshot, tasks=[{"id": "t1", "scheduled_hour": 9}, {"id": "t2", "scheduled_hour": 9}])

    insights = engine.generate_context_insights(snapshot=snapshot, conflicts=conflicts)
    explanation = engine.explain_context()

    assert any("Risk state" in insight.insight for insight in insights)
    assert any("Energy is low" in insight.insight for insight in insights)
    assert explanation["context_reasoning"]
    assert explanation["conflict_reasoning"]
    assert explanation["recommendation_reasoning"]


def test_state_trajectory_empty_and_with_history() -> None:
    engine = ContextAwarenessEngine()

    assert engine.estimate_state_trajectory()["near_term_direction"] == "insufficient_data"

    engine.generate_snapshot(current_context={"behavior_patterns": {"average_energy_level": 30}}, adaptive_life_summary={"burnout_probability": 0.7}, timestamp=datetime(2026, 1, 1))
    engine.generate_snapshot(current_context={"behavior_patterns": {"average_energy_level": 80}}, adaptive_life_summary={"burnout_probability": 0.1}, timestamp=datetime(2026, 1, 2))
    trajectory = engine.estimate_state_trajectory()

    assert trajectory["near_term_direction"] in {"improving", "declining", "stable"}
    assert trajectory["stability"] in {"stable", "volatile"}
    assert trajectory["risk_tendency"] in {"improving", "declining", "stable", "major_transition"}


def test_behavior_learning_adaptive_and_meta_integration() -> None:
    behavior = BehaviorLearningEngine()
    behavior.record_observation("task_completion", productivity_score=90, completed=True, timestamp=datetime(2026, 1, 1))
    behavior_summary = behavior.summarize_behavior_learning()["behavior_learning_summary"]
    engine = ContextAwarenessEngine()

    snapshot = engine.generate_snapshot(
        behavior_learning_summary=behavior_summary,
        adaptive_life_summary={"burnout_probability": 0.2, "risk_count": 1, "load_status": "healthy_load"},
        meta_cognitive_summary={"average_error": 15},
        timestamp=datetime(2026, 1, 1),
    )

    assert snapshot.confidence > 0
    assert snapshot.risk_state in {"low", "medium", "high", "critical"}


def test_malformed_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="max_history_size"):
        ContextAwarenessEngine(max_history_size=0)

    engine = ContextAwarenessEngine()

    with pytest.raises(ValueError, match="current_context"):
        engine.generate_snapshot(current_context=[])

    with pytest.raises(ValueError, match="goals"):
        engine.generate_snapshot(goals={})

    with pytest.raises(ValueError, match="tasks"):
        engine.detect_context_conflicts(tasks={})

    with pytest.raises(ValueError, match="snapshot"):
        engine.generate_context_insights(snapshot=[])


def test_large_context_history_and_determinism() -> None:
    def build_summary() -> dict:
        engine = ContextAwarenessEngine(max_history_size=5)
        base = datetime(2026, 1, 1)
        for index in range(10):
            engine.generate_snapshot(
                current_context={"current_hour": 9, "behavior_patterns": {"best_focus_hours": [9], "average_energy_level": 60 + index}},
                workload={"capacity_utilization": 0.7},
                goals=[{"progress": 40 + index}],
                timestamp=base + timedelta(days=index),
            )
        return engine.summarize_context_awareness()

    first = build_summary()
    second = build_summary()

    assert first == second
    assert first["context_snapshot"]["snapshot_id"] == "context-snapshot-10"
    assert len(first["context_shifts"]) == 3


def test_empty_state_summary_is_optional() -> None:
    assert ContextAwarenessEngine().summarize_context_awareness() is None


def test_orchestrator_context_awareness_outputs_are_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.context_awareness_engine = ContextAwarenessEngine()

    assert orchestrator._context_awareness_outputs() is None

    orchestrator.context_awareness_engine.generate_snapshot(timestamp=datetime(2026, 1, 1))
    outputs = orchestrator._context_awareness_outputs()

    assert outputs is not None
    assert set(outputs) == {"context_snapshot", "context_shifts", "context_conflicts", "context_insights", "context_summary"}


def test_orchestrator_rejects_malformed_context_awareness_outputs() -> None:
    class BadContextAwarenessEngine:
        def summarize_context_awareness(self):
            return {
                "context_snapshot": {"bad": math.inf},
                "context_shifts": [],
                "context_conflicts": [],
                "context_insights": [],
                "context_summary": {},
            }

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.context_awareness_engine = BadContextAwarenessEngine()

    with pytest.raises(ValueError, match="finite"):
        orchestrator._context_awareness_outputs()
