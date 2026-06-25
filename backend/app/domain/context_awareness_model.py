from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


VALID_DIRECTIONS = {"improving", "declining", "stable", "major_transition"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_MOMENTUM = {"positive", "negative", "neutral"}


@dataclass
class ContextSignal:
    """Single signal contributing to dynamic context awareness."""

    signal_id: str
    signal_type: str
    value: float
    confidence: float
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.signal_id = _required_text(self.signal_id, "signal_id")
        self.signal_type = _required_text(self.signal_type, "signal_type").lower()
        self.value = _bounded_float(self.value, "value", 0.0, 100.0)
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        self.source = _required_text(self.source, "source")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")
        self.metadata = _dict(self.metadata, "metadata")


@dataclass
class ContextSnapshot:
    """Current state snapshot across focus, workload, goals, momentum, risk, and energy."""

    snapshot_id: str
    focus_state: str
    workload_state: str
    goal_state: str
    momentum_state: str
    risk_state: str
    energy_state: str
    confidence: float
    signals: List[ContextSignal | Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.snapshot_id = _required_text(self.snapshot_id, "snapshot_id")
        self.focus_state = _required_text(self.focus_state, "focus_state").lower()
        self.workload_state = _required_text(self.workload_state, "workload_state").lower()
        self.goal_state = _required_text(self.goal_state, "goal_state").lower()
        self.momentum_state = _choice(self.momentum_state, "momentum_state", VALID_MOMENTUM)
        self.risk_state = _severity(self.risk_state)
        self.energy_state = _required_text(self.energy_state, "energy_state").lower()
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        self.signals = [signal if isinstance(signal, ContextSignal) else ContextSignal(**signal) for signal in self.signals]
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")


@dataclass
class ContextShift:
    """Detected movement between context snapshots."""

    shift_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    shift_type: str
    direction: str
    magnitude: float
    confidence: float

    def __post_init__(self) -> None:
        self.shift_id = _required_text(self.shift_id, "shift_id")
        self.from_snapshot_id = _required_text(self.from_snapshot_id, "from_snapshot_id")
        self.to_snapshot_id = _required_text(self.to_snapshot_id, "to_snapshot_id")
        self.shift_type = _required_text(self.shift_type, "shift_type").lower()
        self.direction = _choice(self.direction, "direction", VALID_DIRECTIONS)
        self.magnitude = _bounded_float(self.magnitude, "magnitude", 0.0, 100.0)
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)


@dataclass
class ContextConflict:
    """Conflict between current context dimensions."""

    conflict_id: str
    conflict_type: str
    severity: str
    description: str
    affected_items: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def __post_init__(self) -> None:
        self.conflict_id = _required_text(self.conflict_id, "conflict_id")
        self.conflict_type = _required_text(self.conflict_type, "conflict_type").lower()
        self.severity = _severity(self.severity)
        self.description = _required_text(self.description, "description")
        self.affected_items = _string_list(self.affected_items, "affected_items")
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)


@dataclass
class ContextInsight:
    """Context-aware recommendation with evidence and confidence."""

    insight_id: str
    insight: str
    confidence: float
    evidence: List[str]
    recommendation: str

    def __post_init__(self) -> None:
        self.insight_id = _required_text(self.insight_id, "insight_id")
        self.insight = _required_text(self.insight, "insight")
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        self.evidence = _string_list(self.evidence, "evidence")
        self.recommendation = _required_text(self.recommendation, "recommendation")


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
    return max(minimum, min(maximum, number))


def _choice(value: object, field_name: str, choices: set[str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be one of {', '.join(sorted(choices))}.")
    normalized = value.strip().lower()
    if normalized not in choices:
        raise ValueError(f"{field_name} must be one of {', '.join(sorted(choices))}.")
    return normalized


def _severity(value: object) -> str:
    return _choice(value, "severity", VALID_SEVERITIES)


def _string_list(value: object, field_name: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    return sorted(dict.fromkeys(item.strip() for item in value if item.strip()))


def _dict(value: object, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")
    return dict(value)
