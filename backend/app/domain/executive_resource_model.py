from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List


SEVERITIES = {"low", "medium", "high", "critical"}
RESOURCE_NAMES = {
    "time",
    "energy",
    "attention",
    "cognitive_load",
    "strategic_capacity",
    "operational_capacity",
    "recovery_capacity",
    "risk_budget",
    "learning_capacity",
    "decision_capacity",
    "executive_reserve",
}
CONFLICT_TYPES = {
    "over_allocation",
    "under_utilization",
    "attention_fragmentation",
    "context_switching",
    "energy_overload",
    "risk_saturation",
    "strategic_starvation",
    "recovery_deficit",
    "decision_fatigue",
    "resource_imbalance",
}


@dataclass(frozen=True)
class ResourceState:
    """Validated snapshot of executive resource availability and consumption."""

    state_id: str
    available_time: float
    consumed_time: float
    available_energy: float
    consumed_energy: float
    cognitive_load: float
    attention_quality: float
    strategic_capacity: float
    operational_capacity: float
    recovery_capacity: float
    risk_budget: float
    learning_capacity: float
    decision_capacity: float
    executive_reserve: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", _required_text(self.state_id, "state_id"))
        for name in (
            "available_time",
            "consumed_time",
            "available_energy",
            "consumed_energy",
            "cognitive_load",
            "attention_quality",
            "strategic_capacity",
            "operational_capacity",
            "recovery_capacity",
            "risk_budget",
            "learning_capacity",
            "decision_capacity",
            "executive_reserve",
        ):
            object.__setattr__(self, name, _bounded_float(getattr(self, name), name, 0.0, 100.0))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class ResourceAllocation:
    """Validated resource allocation quality for one resource dimension."""

    allocation_id: str
    resource_name: str
    allocated_percent: float
    consumed_percent: float
    utilization: float
    priority: int
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allocation_id", _required_text(self.allocation_id, "allocation_id"))
        object.__setattr__(self, "resource_name", _resource_name(self.resource_name))
        object.__setattr__(self, "allocated_percent", _bounded_float(self.allocated_percent, "allocated_percent", 0.0, 100.0))
        object.__setattr__(self, "consumed_percent", _bounded_float(self.consumed_percent, "consumed_percent", 0.0, 100.0))
        object.__setattr__(self, "utilization", _bounded_float(self.utilization, "utilization", 0.0, 200.0))
        object.__setattr__(self, "priority", _priority(self.priority))
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class ResourceConflict:
    """Validated conflict detected in executive resource allocation."""

    conflict_id: str
    conflict_type: str
    severity: str
    affected_resource: str
    impact_score: float
    description: str
    recommended_action: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflict_id", _required_text(self.conflict_id, "conflict_id"))
        conflict_type = _required_text(self.conflict_type, "conflict_type").lower()
        if conflict_type not in CONFLICT_TYPES:
            raise ValueError("conflict_type must be valid.")
        object.__setattr__(self, "conflict_type", conflict_type)
        object.__setattr__(self, "severity", _severity(self.severity))
        object.__setattr__(self, "affected_resource", _resource_name(self.affected_resource))
        object.__setattr__(self, "impact_score", _bounded_float(self.impact_score, "impact_score", 0.0, 100.0))
        object.__setattr__(self, "description", _required_text(self.description, "description"))
        object.__setattr__(self, "recommended_action", _required_text(self.recommended_action, "recommended_action"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class AttentionAllocation:
    """Validated attention distribution for executive resource supervision."""

    allocation_id: str
    focus_blocks: int
    meeting_load: float
    context_switches: int
    deep_work_percent: float
    fragmented_attention_percent: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allocation_id", _required_text(self.allocation_id, "allocation_id"))
        for name in ("focus_blocks", "context_switches"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        object.__setattr__(self, "meeting_load", _bounded_float(self.meeting_load, "meeting_load", 0.0, 100.0))
        object.__setattr__(self, "deep_work_percent", _bounded_float(self.deep_work_percent, "deep_work_percent", 0.0, 100.0))
        object.__setattr__(self, "fragmented_attention_percent", _bounded_float(self.fragmented_attention_percent, "fragmented_attention_percent", 0.0, 100.0))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class EnergyProfile:
    """Validated executive energy and recovery profile."""

    profile_id: str
    available_energy: float
    consumed_energy: float
    energy_stability: float
    recovery_readiness: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _required_text(self.profile_id, "profile_id"))
        for name in ("available_energy", "consumed_energy", "energy_stability", "recovery_readiness"):
            object.__setattr__(self, name, _bounded_float(getattr(self, name), name, 0.0, 100.0))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class CapacityForecast:
    """Validated deterministic capacity forecast from existing executive outputs."""

    forecast_id: str
    horizon_days: int
    available_capacity: float
    projected_demand: float
    utilization: float
    risk_level: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "forecast_id", _required_text(self.forecast_id, "forecast_id"))
        if not isinstance(self.horizon_days, int) or isinstance(self.horizon_days, bool) or self.horizon_days <= 0:
            raise ValueError("horizon_days must be a positive integer.")
        for name in ("available_capacity", "projected_demand", "confidence"):
            object.__setattr__(self, name, _bounded_float(getattr(self, name), name, 0.0, 100.0))
        object.__setattr__(self, "utilization", _bounded_float(self.utilization, "utilization", 0.0, 200.0))
        risk_level = _required_text(self.risk_level, "risk_level").lower()
        if risk_level not in SEVERITIES:
            raise ValueError("risk_level must be low, medium, high, or critical.")
        object.__setattr__(self, "risk_level", risk_level)
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class ResourceRecommendation:
    """Validated recommendation-only resource allocation adjustment."""

    recommendation_id: str
    action: str
    priority: int
    expected_benefit: float
    rationale: str
    affected_resources: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendation_id", _required_text(self.recommendation_id, "recommendation_id"))
        object.__setattr__(self, "action", _required_text(self.action, "action"))
        object.__setattr__(self, "priority", _priority(self.priority))
        object.__setattr__(self, "expected_benefit", _bounded_float(self.expected_benefit, "expected_benefit", 0.0, 100.0))
        object.__setattr__(self, "rationale", _required_text(self.rationale, "rationale"))
        resources = [_resource_name(resource) for resource in _string_list(self.affected_resources, "affected_resources", allow_empty=False)]
        if len(resources) != len(set(resources)):
            raise ValueError("affected_resources must be unique.")
        object.__setattr__(self, "affected_resources", resources)
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class ExecutiveResourceSummary:
    """Validated aggregate executive resource supervision summary."""

    summary_id: str
    resource_health: float
    resource_utilization: float
    attention_quality: float
    energy_stability: float
    strategic_capacity: float
    recovery_readiness: float
    cognitive_load: float
    execution_capacity: float
    executive_reserve: float
    overall_resource_score: float
    executive_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary_id", _required_text(self.summary_id, "summary_id"))
        for name in (
            "resource_health",
            "resource_utilization",
            "attention_quality",
            "energy_stability",
            "strategic_capacity",
            "recovery_readiness",
            "cognitive_load",
            "execution_capacity",
            "executive_reserve",
            "overall_resource_score",
        ):
            object.__setattr__(self, name, _bounded_float(getattr(self, name), name, 0.0, 100.0))
        object.__setattr__(self, "executive_summary", _required_text(self.executive_summary, "executive_summary"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _resource_name(value: object) -> str:
    resource = _required_text(value, "resource_name").lower()
    if resource not in RESOURCE_NAMES:
        raise ValueError("resource_name must be valid.")
    return resource


def _severity(value: object) -> str:
    severity = _required_text(value, "severity").lower()
    if severity not in SEVERITIES:
        raise ValueError("severity must be low, medium, high, or critical.")
    return severity


def _priority(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 5:
        raise ValueError("priority must be an integer from 1 to 5.")
    return value


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
