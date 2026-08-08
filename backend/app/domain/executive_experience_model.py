from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass(frozen=True)
class ExecutiveDecisionRecord:
    """Recorded executive recommendation and eventual outcome."""

    decision_id: str
    timestamp: datetime
    executive_context: Dict[str, Any]
    selected_strategy: str
    confidence: float
    reasoning_trace: Dict[str, Any]
    evidence_summary: Dict[str, Any]
    tradeoffs: List[Dict[str, Any]]
    risks: Dict[str, Any]
    expected_outcome: Dict[str, Any]
    actual_outcome: Dict[str, Any] | None
    success_score: float | None
    execution_time: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", _required_text(self.decision_id, "decision_id"))
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")
        object.__setattr__(self, "executive_context", _dict(self.executive_context, "executive_context"))
        object.__setattr__(self, "selected_strategy", _required_text(self.selected_strategy, "selected_strategy"))
        object.__setattr__(self, "confidence", _bounded_float(self.confidence, "confidence", 0.0, 100.0))
        object.__setattr__(self, "reasoning_trace", _dict(self.reasoning_trace, "reasoning_trace"))
        if not self.reasoning_trace.get("reasoning_steps"):
            raise ValueError("reasoning_trace must include reasoning_steps.")
        object.__setattr__(self, "evidence_summary", _dict(self.evidence_summary, "evidence_summary"))
        object.__setattr__(self, "tradeoffs", _dict_list(self.tradeoffs, "tradeoffs"))
        object.__setattr__(self, "risks", _dict(self.risks, "risks"))
        object.__setattr__(self, "expected_outcome", _dict(self.expected_outcome, "expected_outcome"))
        if self.actual_outcome is not None:
            object.__setattr__(self, "actual_outcome", _dict(self.actual_outcome, "actual_outcome"))
        if self.success_score is not None:
            object.__setattr__(self, "success_score", _bounded_float(self.success_score, "success_score", 0.0, 100.0))
        object.__setattr__(self, "execution_time", _bounded_float(self.execution_time, "execution_time", 0.0, 1_000_000.0))


@dataclass(frozen=True)
class ExecutivePattern:
    """Deterministic pattern found across executive decision history."""

    pattern_name: str
    frequency: int
    success_rate: float
    average_confidence: float
    common_failures: List[str] = field(default_factory=list)
    common_successes: List[str] = field(default_factory=list)
    recommended_strategy: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "pattern_name", _required_text(self.pattern_name, "pattern_name"))
        if not isinstance(self.frequency, int) or isinstance(self.frequency, bool) or self.frequency < 0:
            raise ValueError("frequency must be a non-negative integer.")
        object.__setattr__(self, "success_rate", _bounded_float(self.success_rate, "success_rate", 0.0, 100.0))
        object.__setattr__(self, "average_confidence", _bounded_float(self.average_confidence, "average_confidence", 0.0, 100.0))
        object.__setattr__(self, "common_failures", _string_list(self.common_failures, "common_failures", allow_empty=True))
        object.__setattr__(self, "common_successes", _string_list(self.common_successes, "common_successes", allow_empty=True))
        object.__setattr__(self, "recommended_strategy", _required_text(self.recommended_strategy or self.pattern_name, "recommended_strategy"))


@dataclass(frozen=True)
class ExecutiveLearningSnapshot:
    """Aggregate executive experience learning snapshot."""

    total_decisions: int
    successful_decisions: int
    failed_decisions: int
    overall_success_rate: float
    confidence_calibration: Dict[str, Any]
    top_patterns: List[Dict[str, Any]]
    improvement_areas: List[str]

    def __post_init__(self) -> None:
        for field_name in ("total_decisions", "successful_decisions", "failed_decisions"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")
        if self.successful_decisions + self.failed_decisions > self.total_decisions:
            raise ValueError("successful_decisions and failed_decisions cannot exceed total_decisions.")
        object.__setattr__(self, "overall_success_rate", _bounded_float(self.overall_success_rate, "overall_success_rate", 0.0, 100.0))
        object.__setattr__(self, "confidence_calibration", _dict(self.confidence_calibration, "confidence_calibration"))
        object.__setattr__(self, "top_patterns", _dict_list(self.top_patterns, "top_patterns"))
        object.__setattr__(self, "improvement_areas", _string_list(self.improvement_areas, "improvement_areas", allow_empty=True))


@dataclass(frozen=True)
class ExecutiveStrategyProfile:
    """Performance profile for one selected executive strategy."""

    strategy_name: str
    times_used: int
    success_rate: float
    average_confidence: float
    recommended_weight: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_name", _required_text(self.strategy_name, "strategy_name"))
        if not isinstance(self.times_used, int) or isinstance(self.times_used, bool) or self.times_used < 0:
            raise ValueError("times_used must be a non-negative integer.")
        object.__setattr__(self, "success_rate", _bounded_float(self.success_rate, "success_rate", 0.0, 100.0))
        object.__setattr__(self, "average_confidence", _bounded_float(self.average_confidence, "average_confidence", 0.0, 100.0))
        object.__setattr__(self, "recommended_weight", _bounded_float(self.recommended_weight, "recommended_weight", 0.0, 2.0))


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    if number < minimum or number > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}.")
    return round(number, 4)


def _dict(value: object, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")
    _validate_payload(value, field_name)
    return dict(value)


def _dict_list(value: object, field_name: str) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{field_name} must be a list of dictionaries.")
    for item in value:
        _validate_payload(item, field_name)
    return [dict(item) for item in value]


def _string_list(value: object, field_name: str, *, allow_empty: bool) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    normalized = [item.strip() for item in value if item.strip()]
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _validate_payload(value: object, field_name: str) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _validate_payload(nested, field_name)
        return
    if isinstance(value, list):
        for nested in value:
            _validate_payload(nested, field_name)
        return
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)) and not math.isfinite(float(value)):
        raise ValueError(f"{field_name} contains non-finite numeric value.")
