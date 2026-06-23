from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class ReflectionRecord:
    """Observed prediction-vs-outcome record for meta-cognitive analysis."""

    record_id: str
    engine_name: str
    prediction: Any
    actual_result: Any
    error_score: float
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.record_id, str) or not self.record_id.strip():
            raise ValueError("record_id must be a non-empty string.")
        if not isinstance(self.engine_name, str) or not self.engine_name.strip():
            raise ValueError("engine_name must be a non-empty string.")
        self.record_id = self.record_id.strip()
        self.engine_name = self.engine_name.strip()
        self.error_score = _bounded_float(self.error_score, "error_score", 0.0, 100.0)
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary.")


@dataclass
class StrategyRecommendation:
    """Deterministic recommendation generated from reflection history."""

    recommendation_id: str
    engine_name: str
    problem_detected: str
    root_cause: str
    recommended_adjustment: str
    confidence: float
    priority: int

    def __post_init__(self) -> None:
        for field_name in (
            "recommendation_id",
            "engine_name",
            "problem_detected",
            "root_cause",
            "recommended_adjustment",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string.")
            setattr(self, field_name, value.strip())
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority <= 0:
            raise ValueError("priority must be a positive integer.")


@dataclass
class PerformanceSummary:
    """Aggregated performance state for one engine."""

    engine_name: str
    sample_count: int
    average_error: float
    average_accuracy: float
    trend: str
    risk_level: str
    recommendations: List[StrategyRecommendation | Dict[str, Any]]

    def __post_init__(self) -> None:
        if not isinstance(self.engine_name, str) or not self.engine_name.strip():
            raise ValueError("engine_name must be a non-empty string.")
        if not isinstance(self.sample_count, int) or isinstance(self.sample_count, bool) or self.sample_count < 0:
            raise ValueError("sample_count must be a non-negative integer.")
        self.average_error = _bounded_float(self.average_error, "average_error", 0.0, 100.0)
        self.average_accuracy = _bounded_float(self.average_accuracy, "average_accuracy", 0.0, 100.0)
        if self.trend not in {"improving", "stable", "declining", "insufficient_data"}:
            raise ValueError("trend must be improving, stable, declining, or insufficient_data.")
        if self.risk_level not in {"low", "medium", "high", "critical"}:
            raise ValueError("risk_level must be low, medium, high, or critical.")
        if not isinstance(self.recommendations, list):
            raise ValueError("recommendations must be a list.")
        self.engine_name = self.engine_name.strip()
        self.recommendations = [
            item if isinstance(item, StrategyRecommendation) else StrategyRecommendation(**item)
            for item in self.recommendations
        ]


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return max(minimum, min(maximum, number))
