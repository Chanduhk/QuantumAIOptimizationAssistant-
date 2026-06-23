from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timedelta

import pytest

from backend.app.domain.meta_cognitive_model import (
    PerformanceSummary,
    ReflectionRecord,
    StrategyRecommendation,
)
from backend.app.engines.meta_cognitive_engine import MetaCognitiveEngine
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_reflection_record_validation_and_bounding() -> None:
    record = ReflectionRecord(
        record_id=" r1 ",
        engine_name=" PredictionEngine ",
        prediction=80,
        actual_result=70,
        error_score=150,
        confidence=2,
        timestamp=datetime(2026, 1, 1),
        metadata={},
    )

    assert record.record_id == "r1"
    assert record.engine_name == "PredictionEngine"
    assert record.error_score == 100.0
    assert record.confidence == 1.0

    with pytest.raises(ValueError, match="record_id"):
        ReflectionRecord("", "Engine", 1, 1, 0, 0.5)

    with pytest.raises(ValueError, match="confidence"):
        ReflectionRecord("r2", "Engine", 1, 1, 0, math.inf)


def test_strategy_recommendation_validation() -> None:
    recommendation = StrategyRecommendation(
        recommendation_id="s1",
        engine_name="SchedulingEngine",
        problem_detected="High drift",
        root_cause="Overloaded periods",
        recommended_adjustment="Reduce scheduling preference for overloaded periods",
        confidence=2,
        priority=1,
    )

    assert recommendation.confidence == 1.0

    with pytest.raises(ValueError, match="recommended_adjustment"):
        StrategyRecommendation("s2", "Engine", "Problem", "Cause", "", 0.5, 1)

    with pytest.raises(ValueError, match="priority"):
        StrategyRecommendation("s3", "Engine", "Problem", "Cause", "Adjust", 0.5, 0)


def test_performance_summary_validation() -> None:
    summary = PerformanceSummary(
        engine_name="PredictionEngine",
        sample_count=2,
        average_error=10,
        average_accuracy=90,
        trend="stable",
        risk_level="low",
        recommendations=[
            {
                "recommendation_id": "s1",
                "engine_name": "PredictionEngine",
                "problem_detected": "Medium error",
                "root_cause": "Calibration",
                "recommended_adjustment": "Review calibration inputs for this engine",
                "confidence": 0.5,
                "priority": 2,
            }
        ],
    )

    assert isinstance(summary.recommendations[0], StrategyRecommendation)

    with pytest.raises(ValueError, match="trend"):
        PerformanceSummary("Engine", 1, 1, 99, "bad", "low", [])


def test_prediction_accuracy_analysis() -> None:
    result = MetaCognitiveEngine().analyze_prediction_accuracy(
        predicted_productivity=80,
        actual_productivity=65,
        confidence=0.8,
    )

    assert result["accuracy_score"] == 85.0
    assert result["error_score"] == 15.0
    assert result["confidence_band"] == "high"


def test_schedule_drift_analysis() -> None:
    result = MetaCognitiveEngine().analyze_schedule_drift(
        scheduled_hour="9",
        actual_execution_hour=12,
    )

    assert result["schedule_drift"] == 3
    assert result["drift_severity"] == "high"


def test_decision_quality_analysis() -> None:
    engine = MetaCognitiveEngine()

    exact = engine.analyze_decision_quality(
        recommended_task={"id": "a", "goal_id": "g1"},
        completed_task={"id": "a", "goal_id": "g1"},
    )
    aligned = engine.analyze_decision_quality(
        recommended_task={"id": "a", "goal_id": "g1"},
        completed_task={"id": "b", "goal_id": "g1"},
    )
    misaligned = engine.analyze_decision_quality(
        recommended_task={"id": "a", "goal_id": "g1"},
        completed_task={"id": "c", "goal_id": "g2"},
    )

    assert exact["decision_alignment"] == "exact"
    assert aligned["decision_alignment"] == "goal_aligned"
    assert misaligned["decision_alignment"] == "misaligned"
    assert exact["decision_quality_score"] > aligned["decision_quality_score"] > misaligned["decision_quality_score"]


def test_simulation_and_optimization_accuracy_analysis() -> None:
    engine = MetaCognitiveEngine()

    simulation = engine.analyze_simulation_accuracy(simulated_outcome=0.75, actual_outcome=0.55)
    optimization = engine.analyze_optimization_accuracy(projected_gain=40, actual_gain=25)

    assert simulation["simulation_accuracy"] == 99.8
    assert simulation["simulation_error"] == 0.2
    assert optimization["optimization_accuracy"] == 85.0
    assert optimization["optimization_error"] == 15.0


def test_record_reflection_and_history_limit() -> None:
    engine = MetaCognitiveEngine(max_history_size=2)

    engine.record_reflection(engine_name="PredictionEngine", prediction=90, actual_result=80, confidence=0.9)
    second = engine.record_reflection(engine_name="PredictionEngine", prediction=90, actual_result=60, confidence=0.7)
    third = engine.record_reflection(engine_name="SchedulingEngine", prediction=9, actual_result=12, confidence=0.6)

    assert len(engine.reflection_history) == 2
    assert engine.reflection_history[0].record_id == second.record_id
    assert engine.reflection_history[1].record_id == third.record_id


def test_trend_detection_for_improving_declining_and_stable() -> None:
    base = datetime(2026, 1, 1)
    improving = MetaCognitiveEngine()
    declining = MetaCognitiveEngine()
    stable = MetaCognitiveEngine()

    for index, error in enumerate([50, 40, 20, 10]):
        improving.record_reflection(
            engine_name="PredictionEngine",
            prediction=0,
            actual_result=0,
            error_score=error,
            timestamp=base + timedelta(days=index),
        )
    for index, error in enumerate([10, 20, 40, 50]):
        declining.record_reflection(
            engine_name="PredictionEngine",
            prediction=0,
            actual_result=0,
            error_score=error,
            timestamp=base + timedelta(days=index),
        )
    for index, error in enumerate([20, 22, 21, 23]):
        stable.record_reflection(
            engine_name="PredictionEngine",
            prediction=0,
            actual_result=0,
            error_score=error,
            timestamp=base + timedelta(days=index),
        )

    assert improving.generate_performance_summary("PredictionEngine").trend == "improving"
    assert declining.generate_performance_summary("PredictionEngine").trend == "declining"
    assert stable.generate_performance_summary("PredictionEngine").trend == "stable"


def test_strategy_recommendations_are_deterministic_and_engine_specific() -> None:
    engine = MetaCognitiveEngine()
    engine.record_reflection(
        engine_name="SchedulingEngine",
        prediction=9,
        actual_result=14,
        error_score=55,
        confidence=0.6,
        metadata={"error_type": "schedule_drift"},
    )
    engine.record_reflection(
        engine_name="SimulationEngine",
        prediction=80,
        actual_result=30,
        error_score=50,
        confidence=0.5,
        metadata={"error_type": "simulation_error"},
    )

    first = engine.generate_strategy_recommendations()
    second = engine.generate_strategy_recommendations()

    assert asdict(first[0]) == asdict(second[0])
    assert any(
        recommendation.recommended_adjustment == "Reduce scheduling preference for overloaded periods"
        for recommendation in first
    )
    assert any(
        recommendation.recommended_adjustment == "Increase dependency-risk consideration"
        for recommendation in first
    )


def test_performance_summary_and_reflection_report() -> None:
    engine = MetaCognitiveEngine()
    engine.record_reflection(
        engine_name="PredictionEngine",
        prediction=100,
        actual_result=60,
        error_score=40,
        confidence=0.7,
        metadata={"error_type": "prediction_miss"},
    )
    engine.record_reflection(
        engine_name="DecisionEngine",
        prediction=100,
        actual_result=95,
        error_score=5,
        confidence=0.9,
        metadata={"error_type": "decision_quality"},
    )

    summary = engine.generate_performance_summary("PredictionEngine")
    report = engine.generate_reflection_report()

    assert summary.sample_count == 1
    assert summary.average_error == 40.0
    assert summary.risk_level == "high"
    assert report["sample_count"] == 2
    assert report["least_accurate_engines"][0] == "PredictionEngine"
    assert report["risk_areas"] == ["PredictionEngine"]
    assert report["top_recurring_errors"][0]["count"] == 1


def test_empty_history_outputs() -> None:
    engine = MetaCognitiveEngine()

    assert engine.summarize_meta_cognition() is None
    assert engine.generate_strategy_recommendations() == []
    assert engine.generate_performance_summary("PredictionEngine").trend == "insufficient_data"
    assert engine.generate_reflection_report()["sample_count"] == 0


def test_malformed_inputs_are_rejected() -> None:
    engine = MetaCognitiveEngine()

    with pytest.raises(ValueError, match="max_history_size"):
        MetaCognitiveEngine(max_history_size=0)

    with pytest.raises(ValueError, match="engine_name"):
        engine.record_reflection(engine_name="", prediction=1, actual_result=1)

    with pytest.raises(ValueError, match="metadata"):
        engine.record_reflection(engine_name="Engine", prediction=1, actual_result=1, metadata="bad")

    with pytest.raises(ValueError, match="finite"):
        engine.analyze_prediction_accuracy(predicted_productivity=math.inf, actual_productivity=1)

    with pytest.raises(ValueError, match="scheduled_hour"):
        engine.analyze_schedule_drift(scheduled_hour=24, actual_execution_hour=1)

    with pytest.raises(ValueError, match="dictionaries"):
        engine.analyze_decision_quality(recommended_task=[], completed_task={})

    with pytest.raises(ValueError, match="numeric"):
        engine.analyze_simulation_accuracy(simulated_outcome="bad", actual_outcome=1)


def test_meta_cognition_summary_is_deterministic() -> None:
    first = MetaCognitiveEngine()
    second = MetaCognitiveEngine()
    for engine in (first, second):
        engine.record_reflection(
            engine_name="OptimizationEngine",
            prediction=50,
            actual_result=20,
            error_score=30,
            confidence=0.8,
            timestamp=datetime(2026, 1, 1),
        )

    assert first.summarize_meta_cognition() == second.summarize_meta_cognition()


def test_orchestrator_meta_cognitive_summary_is_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.meta_cognitive_engine = MetaCognitiveEngine()

    assert orchestrator._meta_cognitive_summary() is None

    orchestrator.meta_cognitive_engine.record_reflection(
        engine_name="PredictionEngine",
        prediction=90,
        actual_result=70,
        confidence=0.8,
    )
    summary = orchestrator._meta_cognitive_summary()

    assert summary is not None
    assert summary["sample_count"] == 1
    assert "average_accuracy" in summary


def test_orchestrator_rejects_malformed_meta_cognitive_summary() -> None:
    class BadMetaEngine:
        def summarize_meta_cognition(self):
            return {"average_error": math.inf}

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.meta_cognitive_engine = BadMetaEngine()

    with pytest.raises(ValueError, match="meta_cognitive_summary"):
        orchestrator._meta_cognitive_summary()
