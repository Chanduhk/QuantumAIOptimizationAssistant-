from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timedelta

import pytest

from backend.app.domain.behavior_learning_model import (
    BehaviorInsight,
    BehaviorObservation,
    BehaviorPattern,
    BehaviorTrend,
    LearningSnapshot,
)
from backend.app.engines.behavior_learning_engine import BehaviorLearningEngine
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_behavior_learning_domain_validation() -> None:
    observation = BehaviorObservation("o1", "Task_Completion", productivity_score=120, hour_of_day="9")
    pattern = BehaviorPattern("p1", "Focus", "Best hour", 2, 1)
    trend = BehaviorTrend("t1", "Productivity", "IMPROVING", 2, ["b", "a", "a"])
    insight = BehaviorInsight("i1", "Deep work works", 2, ["evidence"], "Protect mornings")
    snapshot = LearningSnapshot(
        "s1",
        "weekly",
        1,
        [asdict(pattern)],
        [asdict(trend)],
        [asdict(insight)],
        120,
        50,
        -10,
        2,
    )

    assert observation.productivity_score == 100.0
    assert observation.hour_of_day == 9
    assert pattern.confidence == 1.0
    assert trend.evidence == ["a", "b"]
    assert insight.confidence == 1.0
    assert snapshot.consistency_score == 100.0
    assert snapshot.behavior_volatility == 0.0
    assert snapshot.learning_confidence == 1.0

    with pytest.raises(ValueError, match="observation_id"):
        BehaviorObservation("", "task")

    with pytest.raises(ValueError, match="hour_of_day"):
        BehaviorObservation("o2", "task", hour_of_day=24)

    with pytest.raises(ValueError, match="direction"):
        BehaviorTrend("t2", "productivity", "bad", 0.5)

    with pytest.raises(ValueError, match="period"):
        LearningSnapshot("s2", "yearly", 0, [], [], [], 0, 0, 0, 0)


def test_observation_collection_and_bounded_history() -> None:
    engine = BehaviorLearningEngine(max_history_size=3)
    now = datetime(2026, 1, 1)

    engine.record_task_completion({"id": "t1", "task_type": "deep", "scheduled_hour": 9, "productivity_score": 90}, timestamp=now)
    engine.record_schedule_adherence({"scheduled_hour": 9, "actual_execution_hour": 11}, timestamp=now)
    engine.record_goal_progress({"goal_id": "g1", "progress": 30}, timestamp=now)
    engine.record_deferral({"id": "t2", "task_type": "admin", "scheduled_hour": 15}, timestamp=now)

    assert len(engine.observations) == 3
    assert engine.observations[-1].deferred is True
    assert engine.observations[0].observation_type == "schedule_adherence"


def test_pattern_discovery_detects_hours_task_types_delays_blockers_and_burnout() -> None:
    engine = BehaviorLearningEngine()
    base = datetime(2026, 1, 1)
    for index in range(3):
        engine.record_observation("task_completion", productivity_score=90, hour_of_day=9, task_type="deep", completed=True, timestamp=base + timedelta(days=index))
    for index in range(2):
        engine.record_observation("task_completion", productivity_score=30, hour_of_day=15, task_type="meeting", completed=True, metadata={"blocker": "calendar"}, timestamp=base + timedelta(days=3 + index))
        engine.record_deferral({"id": f"d{index}", "task_type": "meeting", "scheduled_hour": 15, "blocker": "calendar"}, timestamp=base + timedelta(days=5 + index))
    engine.record_observation("adaptive_signal", productivity_score=20, task_type="burnout", metadata={"burnout_signal": True}, timestamp=base + timedelta(days=8))

    patterns = engine.discover_patterns()
    pattern_ids = {pattern.pattern_id for pattern in patterns}

    assert "pattern-best-work-hour" in pattern_ids
    assert "pattern-worst-work-hour" in pattern_ids
    assert "pattern-most-productive-task-type" in pattern_ids
    assert "pattern-least-productive-task-type" in pattern_ids
    assert "pattern-recurring-delays" in pattern_ids
    assert "pattern-blocker-calendar" in pattern_ids
    assert "pattern-burnout-signals" in pattern_ids


def test_trend_analysis_identifies_productivity_and_consistency_changes() -> None:
    engine = BehaviorLearningEngine()
    base = datetime(2026, 1, 1)
    for index, score in enumerate([30, 35, 70, 75]):
        engine.record_observation("task_completion", productivity_score=score, task_type="deep", timestamp=base + timedelta(days=index))

    trends = {trend.trend_type: trend for trend in engine.analyze_trends()}

    assert trends["productivity"].direction == "improving"
    assert trends["productivity"].strength > 0
    assert trends["consistency"].direction in {"improving", "stable", "declining"}


def test_insight_generation_and_explainability() -> None:
    engine = BehaviorLearningEngine()
    base = datetime(2026, 1, 1)
    for index, score in enumerate([30, 35, 80, 85]):
        engine.record_observation("task_completion", productivity_score=score, hour_of_day=9, task_type="deep", completed=True, timestamp=base + timedelta(days=index))

    insights = engine.generate_insights()
    explanation = engine.explain_learning()

    assert insights
    assert any("Deep" in insight.title or "Best" in insight.title for insight in insights)
    assert explanation["pattern_reasoning"]
    assert explanation["trend_reasoning"]
    assert explanation["recommendation_reasoning"]


def test_habit_stability_and_predictive_tendencies() -> None:
    engine = BehaviorLearningEngine()
    for score in [80, 82, 81, 83]:
        engine.record_observation("task_completion", productivity_score=score, completed=True)
    engine.record_deferral({"id": "d1", "task_type": "admin"})
    engine.record_observation("adaptive_signal", productivity_score=20, metadata={"burnout_signal": True})

    stability = engine.calculate_habit_stability()
    tendencies = engine.predict_tendencies()

    assert 0.0 <= stability["consistency_score"] <= 100.0
    assert 0.0 <= stability["habit_strength"] <= 100.0
    assert tendencies["future_productivity_tendency"] in {"improving", "declining", "stable", "insufficient_data"}
    assert tendencies["future_risk_tendency"] in {"rising", "stable"}
    assert tendencies["future_burnout_tendency"] in {"rising", "stable"}
    assert tendencies["future_completion_tendency"] in {"strong", "moderate", "weak"}


def test_learning_snapshots_weekly_monthly_and_summary() -> None:
    engine = BehaviorLearningEngine()
    now = datetime(2026, 1, 31)
    engine.record_observation("task_completion", productivity_score=90, timestamp=now - timedelta(days=3), completed=True)
    engine.record_observation("task_completion", productivity_score=50, timestamp=now - timedelta(days=20), completed=True)

    weekly = engine.generate_learning_snapshot("weekly", created_at=now)
    monthly = engine.generate_learning_snapshot("monthly", created_at=now)
    summary = engine.summarize_behavior_learning()

    assert weekly.observation_count == 1
    assert monthly.observation_count == 2
    assert summary is not None
    assert set(summary) == {"behavior_learning_summary", "behavior_trends", "behavior_insights", "learning_snapshot"}


def test_empty_history_outputs() -> None:
    engine = BehaviorLearningEngine()

    assert engine.discover_patterns() == []
    assert [trend.direction for trend in engine.analyze_trends()] == ["insufficient_data", "insufficient_data"]
    assert engine.generate_insights() == []
    assert engine.predict_tendencies()["future_productivity_tendency"] == "insufficient_data"
    assert engine.summarize_behavior_learning() is None


def test_goal_reflection_and_adaptive_integrations() -> None:
    engine = BehaviorLearningEngine()

    goal_obs = engine.ingest_goal_update({"goal_id": "g1", "progress": 65})
    reflection_obs = engine.ingest_reflection({"engine_name": "DecisionEngine", "error_score": 20})
    adaptive_obs = engine.ingest_adaptive_signal({"signal_type": "burnout", "severity": "high"})

    assert goal_obs.observation_type == "goal_progress"
    assert reflection_obs.task_type == "decisionengine"
    assert adaptive_obs.metadata["burnout_signal"] is True


def test_malformed_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="max_history_size"):
        BehaviorLearningEngine(max_history_size=0)

    engine = BehaviorLearningEngine()

    with pytest.raises(ValueError, match="metadata"):
        engine.record_observation("task", metadata=[])

    with pytest.raises(ValueError, match="task"):
        engine.record_task_completion([])

    with pytest.raises(ValueError, match="period"):
        engine.generate_learning_snapshot("yearly")

    with pytest.raises(ValueError, match="reflection"):
        engine.ingest_reflection([])


def test_large_history_and_determinism() -> None:
    def build_summary() -> dict:
        engine = BehaviorLearningEngine(max_history_size=50)
        base = datetime(2026, 1, 1)
        for index in range(75):
            engine.record_observation(
                "task_completion",
                productivity_score=50 + (index % 20),
                hour_of_day=9 if index % 2 == 0 else 15,
                task_type="deep" if index % 2 == 0 else "admin",
                completed=index % 3 != 0,
                timestamp=base + timedelta(hours=index),
            )
        return engine.summarize_behavior_learning()

    first = build_summary()
    second = build_summary()

    assert first == second
    assert first["behavior_learning_summary"]["observation_count"] == 50


def test_orchestrator_behavior_learning_outputs_are_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.behavior_learning_engine = BehaviorLearningEngine()

    assert orchestrator._behavior_learning_outputs() is None

    orchestrator.behavior_learning_engine.record_observation("task_completion", productivity_score=90, completed=True)
    outputs = orchestrator._behavior_learning_outputs()

    assert outputs is not None
    assert "behavior_learning_summary" in outputs


def test_orchestrator_rejects_malformed_behavior_learning_outputs() -> None:
    class BadBehaviorLearningEngine:
        def summarize_behavior_learning(self):
            return {
                "behavior_learning_summary": {"bad": math.inf},
                "behavior_trends": [],
                "behavior_insights": [],
                "learning_snapshot": {},
            }

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.behavior_learning_engine = BadBehaviorLearningEngine()

    with pytest.raises(ValueError, match="finite"):
        orchestrator._behavior_learning_outputs()
