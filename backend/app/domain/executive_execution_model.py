from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


SEVERITIES = {"low", "medium", "high", "critical"}
STATUSES = {"not_started", "on_track", "at_risk", "blocked", "completed"}
DEVIATION_TYPES = {
    "late_execution",
    "missed_milestone",
    "blocked_dependency",
    "falling_confidence",
    "goal_drift",
    "schedule_drift",
    "capacity_overload",
    "context_mismatch",
    "priority_inversion",
    "confidence_degradation",
}


@dataclass(frozen=True)
class ExecutionCheckpoint:
    """Immutable checkpoint describing observed execution progress."""

    checkpoint_id: str
    timestamp: datetime
    selected_strategy: str
    planned_progress: float
    actual_progress: float
    confidence: float
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "checkpoint_id", _required_text(self.checkpoint_id, "checkpoint_id"))
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")
        object.__setattr__(self, "selected_strategy", _required_text(self.selected_strategy, "selected_strategy"))
        object.__setattr__(self, "planned_progress", _bounded_float(self.planned_progress, "planned_progress", 0.0, 100.0))
        object.__setattr__(self, "actual_progress", _bounded_float(self.actual_progress, "actual_progress", 0.0, 100.0))
        object.__setattr__(self, "confidence", _bounded_float(self.confidence, "confidence", 0.0, 100.0))
        status = _required_text(self.status, "status").lower()
        if status not in STATUSES:
            raise ValueError("status must be a valid execution status.")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class PlanExecutionState:
    """Current execution state for the selected executive strategy."""

    state_id: str
    timestamp: datetime
    selected_strategy: str
    progress: float
    execution_health: float
    execution_confidence: float
    execution_stability: float
    execution_momentum: float
    execution_risk: float
    schedule_reliability: float
    goal_progress: float
    recovery_readiness: float
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", _required_text(self.state_id, "state_id"))
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")
        object.__setattr__(self, "selected_strategy", _required_text(self.selected_strategy, "selected_strategy"))
        for field_name in (
            "progress",
            "execution_health",
            "execution_confidence",
            "execution_stability",
            "execution_momentum",
            "execution_risk",
            "schedule_reliability",
            "goal_progress",
            "recovery_readiness",
        ):
            object.__setattr__(self, field_name, _bounded_float(getattr(self, field_name), field_name, 0.0, 100.0))
        status = _required_text(self.status, "status").lower()
        if status not in STATUSES:
            raise ValueError("status must be a valid execution status.")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class ExecutionDeviation:
    """Detected divergence from the selected executive strategy."""

    deviation_id: str
    deviation_type: str
    severity: str
    severity_score: float
    detected_at: datetime
    affected_goals: List[str]
    description: str
    recommended_recovery: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "deviation_id", _required_text(self.deviation_id, "deviation_id"))
        deviation_type = _required_text(self.deviation_type, "deviation_type").lower()
        if deviation_type not in DEVIATION_TYPES:
            raise ValueError("deviation_type must be valid.")
        object.__setattr__(self, "deviation_type", deviation_type)
        object.__setattr__(self, "severity", _severity(self.severity))
        object.__setattr__(self, "severity_score", _bounded_float(self.severity_score, "severity_score", 0.0, 100.0))
        if not isinstance(self.detected_at, datetime):
            raise ValueError("detected_at must be a datetime.")
        object.__setattr__(self, "affected_goals", _string_list(self.affected_goals, "affected_goals", allow_empty=True))
        object.__setattr__(self, "description", _required_text(self.description, "description"))
        object.__setattr__(self, "recommended_recovery", _required_text(self.recommended_recovery, "recommended_recovery"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class ExecutiveAlert:
    """Executive supervision alert generated from deviations or health state."""

    alert_id: str
    alert_type: str
    severity: str
    message: str
    timestamp: datetime
    recommended_action: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "alert_id", _required_text(self.alert_id, "alert_id"))
        object.__setattr__(self, "alert_type", _required_text(self.alert_type, "alert_type").lower())
        object.__setattr__(self, "severity", _severity(self.severity))
        object.__setattr__(self, "message", _required_text(self.message, "message"))
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")
        object.__setattr__(self, "recommended_action", _required_text(self.recommended_action, "recommended_action"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class RecoveryRecommendation:
    """Recommendation-only recovery action for execution supervision."""

    recovery_id: str
    action: str
    priority: int
    expected_impact: float
    rationale: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recovery_id", _required_text(self.recovery_id, "recovery_id"))
        object.__setattr__(self, "action", _required_text(self.action, "action"))
        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority <= 0:
            raise ValueError("priority must be a positive integer.")
        object.__setattr__(self, "expected_impact", _bounded_float(self.expected_impact, "expected_impact", 0.0, 100.0))
        object.__setattr__(self, "rationale", _required_text(self.rationale, "rationale"))
        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime.")
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class ExecutionTimeline:
    """Bounded immutable timeline of execution supervision artifacts."""

    timeline_id: str
    checkpoints: List[ExecutionCheckpoint | Dict[str, Any]]
    deviations: List[ExecutionDeviation | Dict[str, Any]]
    alerts: List[ExecutiveAlert | Dict[str, Any]]
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeline_id", _required_text(self.timeline_id, "timeline_id"))
        object.__setattr__(
            self,
            "checkpoints",
            [item if isinstance(item, ExecutionCheckpoint) else ExecutionCheckpoint(**_dict(item, "checkpoint")) for item in self.checkpoints],
        )
        ids = [checkpoint.checkpoint_id for checkpoint in self.checkpoints]
        if len(ids) != len(set(ids)):
            raise ValueError("timeline checkpoints must have unique IDs.")
        object.__setattr__(
            self,
            "deviations",
            [item if isinstance(item, ExecutionDeviation) else ExecutionDeviation(**_dict(item, "deviation")) for item in self.deviations],
        )
        object.__setattr__(
            self,
            "alerts",
            [item if isinstance(item, ExecutiveAlert) else ExecutiveAlert(**_dict(item, "alert")) for item in self.alerts],
        )
        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime.")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _severity(value: object) -> str:
    severity = _required_text(value, "severity").lower()
    if severity not in SEVERITIES:
        raise ValueError("severity must be low, medium, high, or critical.")
    return severity


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
