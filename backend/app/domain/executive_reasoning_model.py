from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List


RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}


@dataclass(frozen=True)
class Evidence:
    """Normalized recommendation evidence from one intelligence source."""

    source: str
    confidence: float
    recommendation: str
    risk_level: str
    priority: int
    score: float
    explanation: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "confidence", _bounded_float(self.confidence, "confidence", 0.0, 100.0))
        object.__setattr__(self, "recommendation", _required_text(self.recommendation, "recommendation"))
        risk_level = _required_text(self.risk_level, "risk_level").lower()
        if risk_level not in RISK_LEVELS:
            raise ValueError("risk_level must be low, medium, high, critical, or unknown.")
        object.__setattr__(self, "risk_level", risk_level)
        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority <= 0:
            raise ValueError("priority must be a positive integer.")
        object.__setattr__(self, "score", _bounded_float(self.score, "score", 0.0, 100.0))
        object.__setattr__(self, "explanation", _required_text(self.explanation, "explanation"))
        object.__setattr__(self, "metadata", _metadata(self.metadata, "metadata"))


@dataclass(frozen=True)
class EvidenceConflict:
    """A deterministic disagreement found between two evidence sources."""

    source_a: str
    source_b: str
    conflict_reason: str
    severity: float
    resolution_strategy: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_a", _required_text(self.source_a, "source_a"))
        object.__setattr__(self, "source_b", _required_text(self.source_b, "source_b"))
        object.__setattr__(self, "conflict_reason", _required_text(self.conflict_reason, "conflict_reason"))
        object.__setattr__(self, "severity", _bounded_float(self.severity, "severity", 0.0, 100.0))
        object.__setattr__(self, "resolution_strategy", _required_text(self.resolution_strategy, "resolution_strategy"))


@dataclass(frozen=True)
class ExecutiveReasoningTrace:
    """Explainable chain of evidence fusion and conflict resolution."""

    evidence_used: List[Evidence | Dict[str, Any]]
    conflicts_found: List[EvidenceConflict | Dict[str, Any]]
    reasoning_steps: List[str]
    selected_strategy: str
    confidence: float
    rejected_alternatives: List[Dict[str, Any]]
    tradeoffs: List[Dict[str, Any]]
    risk_summary: Dict[str, Any]

    def __post_init__(self) -> None:
        evidence = [item if isinstance(item, Evidence) else Evidence(**_dict(item, "evidence")) for item in self.evidence_used]
        conflicts = [
            item if isinstance(item, EvidenceConflict) else EvidenceConflict(**_dict(item, "conflict"))
            for item in self.conflicts_found
        ]
        object.__setattr__(self, "evidence_used", evidence)
        object.__setattr__(self, "conflicts_found", conflicts)
        object.__setattr__(self, "reasoning_steps", _string_list(self.reasoning_steps, "reasoning_steps"))
        object.__setattr__(self, "selected_strategy", _required_text(self.selected_strategy, "selected_strategy"))
        object.__setattr__(self, "confidence", _bounded_float(self.confidence, "confidence", 0.0, 100.0))
        object.__setattr__(self, "rejected_alternatives", _dict_list(self.rejected_alternatives, "rejected_alternatives"))
        object.__setattr__(self, "tradeoffs", _dict_list(self.tradeoffs, "tradeoffs"))
        object.__setattr__(self, "risk_summary", _metadata(self.risk_summary, "risk_summary"))


@dataclass(frozen=True)
class ExecutiveRecommendation:
    """Final executive recommendation produced by evidence fusion."""

    recommended_action: str
    confidence: float
    executive_priority: int
    why: str
    expected_benefits: List[str]
    known_risks: List[str]
    alternatives: List[Dict[str, Any]]
    reasoning_trace: ExecutiveReasoningTrace | Dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommended_action", _required_text(self.recommended_action, "recommended_action"))
        object.__setattr__(self, "confidence", _bounded_float(self.confidence, "confidence", 0.0, 100.0))
        if not isinstance(self.executive_priority, int) or isinstance(self.executive_priority, bool) or self.executive_priority <= 0:
            raise ValueError("executive_priority must be a positive integer.")
        object.__setattr__(self, "why", _required_text(self.why, "why"))
        object.__setattr__(self, "expected_benefits", _string_list(self.expected_benefits, "expected_benefits"))
        object.__setattr__(self, "known_risks", _string_list(self.known_risks, "known_risks"))
        object.__setattr__(self, "alternatives", _dict_list(self.alternatives, "alternatives"))
        trace = (
            self.reasoning_trace
            if isinstance(self.reasoning_trace, ExecutiveReasoningTrace)
            else ExecutiveReasoningTrace(**_dict(self.reasoning_trace, "reasoning_trace"))
        )
        object.__setattr__(self, "reasoning_trace", trace)


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


def _string_list(value: object, field_name: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field_name} must be a list of non-empty strings.")
    return [item.strip() for item in value]


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


def _metadata(value: object, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")
    _validate_payload(value, field_name)
    return dict(value)


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
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError(f"{field_name} contains non-finite numeric value.")
