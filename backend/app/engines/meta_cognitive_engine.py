from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.meta_cognitive_model import (
    PerformanceSummary,
    ReflectionRecord,
    StrategyRecommendation,
)


class MetaCognitiveEngine:
    """Passive reflection engine for measuring AI subsystem quality over time."""

    def __init__(self, max_history_size: int = 1000) -> None:
        if not isinstance(max_history_size, int) or isinstance(max_history_size, bool) or max_history_size <= 0:
            raise ValueError("max_history_size must be a positive integer.")
        self.max_history_size = max_history_size
        self.reflection_history: List[ReflectionRecord] = []

    def record_reflection(
        self,
        *,
        engine_name: str,
        prediction: Any,
        actual_result: Any,
        error_score: float | None = None,
        confidence: float = 0.5,
        metadata: Dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ReflectionRecord:
        """Store one reflection record without mutating any engine behavior."""
        engine_name = self._engine_name(engine_name)
        metadata = metadata or {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary.")
        computed_error = self._error_score(prediction, actual_result) if error_score is None else error_score
        record = ReflectionRecord(
            record_id=f"reflection-{engine_name.lower().replace(' ', '-')}-{len(self.reflection_history) + 1}",
            engine_name=engine_name,
            prediction=prediction,
            actual_result=actual_result,
            error_score=computed_error,
            confidence=confidence,
            timestamp=timestamp or datetime.utcnow(),
            metadata=dict(metadata),
        )
        self.reflection_history.append(record)
        if len(self.reflection_history) > self.max_history_size:
            overflow = len(self.reflection_history) - self.max_history_size
            self.reflection_history = self.reflection_history[overflow:]
        return record

    def analyze_prediction_accuracy(
        self,
        *,
        predicted_productivity: Any,
        actual_productivity: Any,
        confidence: float = 0.5,
    ) -> Dict[str, Any]:
        """Analyze productivity prediction accuracy."""
        predicted = self._bounded_number(predicted_productivity, "predicted_productivity", 0.0, 100.0)
        actual = self._bounded_number(actual_productivity, "actual_productivity", 0.0, 100.0)
        error = abs(predicted - actual)
        return {
            "accuracy_score": round(max(0.0, 100.0 - error), 2),
            "error_score": round(error, 2),
            "confidence_band": self._confidence_band(confidence),
        }

    def analyze_schedule_drift(
        self,
        *,
        scheduled_hour: Any,
        actual_execution_hour: Any,
    ) -> Dict[str, Any]:
        """Analyze scheduling drift in hours."""
        scheduled = self._hour(scheduled_hour, "scheduled_hour")
        actual = self._hour(actual_execution_hour, "actual_execution_hour")
        drift = abs(actual - scheduled)
        return {
            "schedule_drift": drift,
            "drift_severity": self._drift_severity(drift),
        }

    def analyze_decision_quality(
        self,
        *,
        recommended_task: Dict[str, Any],
        completed_task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze whether the recommended task aligned with the completed task."""
        if not isinstance(recommended_task, dict) or not isinstance(completed_task, dict):
            raise ValueError("recommended_task and completed_task must be dictionaries.")
        recommended_id = recommended_task.get("id")
        completed_id = completed_task.get("id")
        if recommended_id is None or completed_id is None:
            raise ValueError("recommended_task and completed_task require id fields.")
        same_task = str(recommended_id) == str(completed_id)
        recommended_goal = recommended_task.get("goal_id")
        completed_goal = completed_task.get("goal_id")
        same_goal = recommended_goal is not None and recommended_goal == completed_goal
        quality = 100.0 if same_task else 70.0 if same_goal else 35.0
        return {
            "decision_quality_score": quality,
            "decision_alignment": "exact" if same_task else "goal_aligned" if same_goal else "misaligned",
        }

    def analyze_simulation_accuracy(
        self,
        *,
        simulated_outcome: Any,
        actual_outcome: Any,
    ) -> Dict[str, Any]:
        """Analyze simulation outcome accuracy."""
        error = self._error_score(simulated_outcome, actual_outcome)
        return {
            "simulation_accuracy": round(max(0.0, 100.0 - error), 2),
            "simulation_error": round(error, 2),
        }

    def analyze_optimization_accuracy(
        self,
        *,
        projected_gain: Any,
        actual_gain: Any,
    ) -> Dict[str, Any]:
        """Analyze projected-vs-actual optimization gain."""
        error = self._error_score(projected_gain, actual_gain)
        return {
            "optimization_accuracy": round(max(0.0, 100.0 - error), 2),
            "optimization_error": round(error, 2),
        }

    def generate_performance_summary(self, engine_name: str) -> PerformanceSummary:
        """Return an aggregate performance summary for one engine."""
        engine_name = self._engine_name(engine_name)
        records = self._records_for(engine_name)
        if not records:
            return PerformanceSummary(
                engine_name=engine_name,
                sample_count=0,
                average_error=0.0,
                average_accuracy=100.0,
                trend="insufficient_data",
                risk_level="low",
                recommendations=[],
            )
        average_error = sum(record.error_score for record in records) / len(records)
        recommendations = self.generate_strategy_recommendations(engine_name=engine_name)
        return PerformanceSummary(
            engine_name=engine_name,
            sample_count=len(records),
            average_error=round(average_error, 2),
            average_accuracy=round(max(0.0, 100.0 - average_error), 2),
            trend=self._trend(records),
            risk_level=self._risk_level(average_error),
            recommendations=recommendations,
        )

    def generate_reflection_report(self) -> Dict[str, Any]:
        """Generate a deterministic report across all reflection history."""
        if not self.reflection_history:
            return {
                "sample_count": 0,
                "top_recurring_errors": [],
                "most_accurate_engines": [],
                "least_accurate_engines": [],
                "risk_areas": [],
                "improvement_opportunities": [],
                "performance_trends": {},
            }
        engine_names = sorted({record.engine_name for record in self.reflection_history})
        summaries = [self.generate_performance_summary(engine_name) for engine_name in engine_names]
        most_accurate = sorted(summaries, key=lambda item: (-item.average_accuracy, item.engine_name))
        least_accurate = sorted(summaries, key=lambda item: (item.average_accuracy, item.engine_name))
        risk_areas = [
            summary.engine_name
            for summary in sorted(summaries, key=lambda item: (-item.average_error, item.engine_name))
            if summary.risk_level in {"high", "critical"}
        ]
        return {
            "sample_count": len(self.reflection_history),
            "top_recurring_errors": self._top_recurring_errors(),
            "most_accurate_engines": [summary.engine_name for summary in most_accurate[:3]],
            "least_accurate_engines": [summary.engine_name for summary in least_accurate[:3]],
            "risk_areas": risk_areas,
            "improvement_opportunities": [
                asdict(recommendation)
                for recommendation in self.generate_strategy_recommendations()
            ],
            "performance_trends": {
                summary.engine_name: summary.trend
                for summary in summaries
            },
        }

    def generate_strategy_recommendations(
        self,
        *,
        engine_name: str | None = None,
    ) -> List[StrategyRecommendation]:
        """Generate deterministic recommendations from reflection history."""
        engine_names = [self._engine_name(engine_name)] if engine_name is not None else sorted(
            {record.engine_name for record in self.reflection_history}
        )
        recommendations: List[StrategyRecommendation] = []
        for name in engine_names:
            records = self._records_for(name)
            if not records:
                continue
            average_error = sum(record.error_score for record in records) / len(records)
            trend = self._trend(records)
            metadata_keys = {str(key).lower() for record in records for key in record.metadata}
            recommendation = self._recommendation_for(name, average_error, trend, metadata_keys)
            if recommendation is not None:
                recommendations.append(recommendation)
        return sorted(recommendations, key=lambda item: (item.priority, item.engine_name, item.recommendation_id))

    def summarize_meta_cognition(self) -> Dict[str, Any] | None:
        """Return compact meta-cognitive summary when reflection history exists."""
        if not self.reflection_history:
            return None
        report = self.generate_reflection_report()
        average_error = sum(record.error_score for record in self.reflection_history) / len(self.reflection_history)
        return {
            "sample_count": len(self.reflection_history),
            "average_error": round(average_error, 2),
            "average_accuracy": round(max(0.0, 100.0 - average_error), 2),
            "risk_area_count": len(report["risk_areas"]),
            "recommendation_count": len(report["improvement_opportunities"]),
        }

    def _recommendation_for(
        self,
        engine_name: str,
        average_error: float,
        trend: str,
        metadata_keys: set[str],
    ) -> StrategyRecommendation | None:
        if average_error < 15.0 and trend != "declining":
            return None
        lower_name = engine_name.lower()
        if "schedule" in lower_name or "scheduling" in lower_name:
            adjustment = "Reduce scheduling preference for overloaded periods"
            cause = "Schedule drift exceeded acceptable tolerance"
        elif "decision" in lower_name:
            adjustment = "Increase priority weighting for strategic tasks"
            cause = "Completed tasks diverged from recommended task order"
        elif "goal" in lower_name or "milestone" in lower_name:
            adjustment = "Improve milestone forecasting inputs"
            cause = "Goal or milestone forecasts showed recurring error"
        elif "simulation" in lower_name:
            adjustment = "Increase dependency-risk consideration"
            cause = "Simulated outcomes diverged from actual outcomes"
        elif "optimization" in lower_name:
            adjustment = "Rebalance optimization objectives toward observed outcomes"
            cause = "Projected gain diverged from actual gain"
        else:
            adjustment = "Reduce confidence in evening productivity predictions" if "evening" in metadata_keys else "Review calibration inputs for this engine"
            cause = "Average error exceeded target threshold"
        priority = 1 if average_error >= 50.0 or trend == "declining" else 2
        confidence = min(1.0, max(0.35, average_error / 100.0 + (0.2 if trend == "declining" else 0.0)))
        return StrategyRecommendation(
            recommendation_id=f"strategy-{engine_name.lower().replace(' ', '-')}",
            engine_name=engine_name,
            problem_detected=f"{self._risk_level(average_error)} error level",
            root_cause=cause,
            recommended_adjustment=adjustment,
            confidence=round(confidence, 4),
            priority=priority,
        )

    def _records_for(self, engine_name: str) -> List[ReflectionRecord]:
        return [record for record in self.reflection_history if record.engine_name == engine_name]

    def _top_recurring_errors(self) -> List[Dict[str, Any]]:
        buckets: Dict[str, List[float]] = {}
        for record in self.reflection_history:
            error_type = str(record.metadata.get("error_type", record.engine_name))
            buckets.setdefault(error_type, []).append(record.error_score)
        return [
            {
                "error_type": error_type,
                "count": len(scores),
                "average_error": round(sum(scores) / len(scores), 2),
            }
            for error_type, scores in sorted(
                buckets.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        ][:5]

    def _trend(self, records: List[ReflectionRecord]) -> str:
        if len(records) < 3:
            return "insufficient_data"
        ordered = sorted(records, key=lambda record: (record.timestamp, record.record_id))
        midpoint = len(ordered) // 2
        early = ordered[:midpoint]
        recent = ordered[midpoint:]
        early_error = sum(record.error_score for record in early) / len(early)
        recent_error = sum(record.error_score for record in recent) / len(recent)
        if recent_error <= early_error - 5.0:
            return "improving"
        if recent_error >= early_error + 5.0:
            return "declining"
        return "stable"

    def _risk_level(self, error_score: float) -> str:
        if error_score >= 60.0:
            return "critical"
        if error_score >= 35.0:
            return "high"
        if error_score >= 15.0:
            return "medium"
        return "low"

    def _confidence_band(self, confidence: Any) -> str:
        value = self._bounded_number(confidence, "confidence", 0.0, 1.0)
        if value >= 0.75:
            return "high"
        if value >= 0.4:
            return "medium"
        return "low"

    def _drift_severity(self, drift: int) -> str:
        if drift >= 4:
            return "critical"
        if drift >= 2:
            return "high"
        if drift == 1:
            return "medium"
        return "low"

    def _hour(self, value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer hour from 0 to 23.")
        if isinstance(value, int):
            hour = value
        elif isinstance(value, str) and value.strip().isdigit():
            hour = int(value.strip())
        else:
            raise ValueError(f"{field_name} must be an integer hour from 0 to 23.")
        if not 0 <= hour <= 23:
            raise ValueError(f"{field_name} must be an integer hour from 0 to 23.")
        return hour

    def _error_score(self, prediction: Any, actual_result: Any) -> float:
        predicted = self._numeric_value(prediction)
        actual = self._numeric_value(actual_result)
        return round(min(100.0, abs(predicted - actual)), 2)

    def _numeric_value(self, value: Any) -> float:
        if isinstance(value, dict):
            candidates = [
                "actual_productivity",
                "predicted_productivity",
                "success_probability",
                "projected_gain",
                "actual_gain",
                "score",
                "value",
            ]
            for key in candidates:
                if key in value:
                    return self._finite_number(value[key], key)
            numeric_values = [
                self._finite_number(item, "value")
                for item in value.values()
                if isinstance(item, (int, float)) and not isinstance(item, bool)
            ]
            if numeric_values:
                return sum(numeric_values) / len(numeric_values)
            raise ValueError("numeric prediction or actual_result value is required.")
        return self._finite_number(value, "value")

    def _bounded_number(self, value: Any, field_name: str, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, self._finite_number(value, field_name)))

    def _finite_number(self, value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return number

    def _engine_name(self, engine_name: Any) -> str:
        if not isinstance(engine_name, str) or not engine_name.strip():
            raise ValueError("engine_name must be a non-empty string.")
        return engine_name.strip()
