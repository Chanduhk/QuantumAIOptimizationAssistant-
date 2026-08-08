from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List


SEVERITIES = {"low", "medium", "high", "critical"}
POLICY_CATEGORIES = {
    "strategic_alignment",
    "goal_alignment",
    "risk_appetite",
    "resource_protection",
    "deep_work_protection",
    "recovery_protection",
    "executive_reserve",
    "learning_protection",
    "decision_quality",
    "execution_discipline",
    "long_term_sustainability",
    "policy_compliance",
}
VIOLATION_TYPES = {
    "policy_violation",
    "constraint_violation",
    "priority_inversion",
    "strategic_drift",
    "goal_misalignment",
    "resource_misuse",
    "risk_escalation",
    "decision_inconsistency",
    "execution_inconsistency",
    "governance_instability",
}
DECISION_STATUSES = {"approved", "approved_with_conditions", "blocked", "needs_review"}


@dataclass(frozen=True)
class ExecutivePolicy:
    """Immutable policy definition used to evaluate executive recommendations."""

    policy_id: str
    policy_name: str
    category: str
    priority: int
    threshold: float
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _required_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "policy_name", _required_text(self.policy_name, "policy_name"))
        object.__setattr__(self, "category", _category(self.category))
        object.__setattr__(self, "priority", _priority(self.priority))
        object.__setattr__(self, "threshold", _bounded_float(self.threshold, "threshold", 0.0, 100.0))
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean.")
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class GovernanceRule:
    """Immutable policy rule binding a metric to a governance action."""

    rule_id: str
    policy_id: str
    metric_name: str
    operator: str
    threshold: float
    severity: str
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", _required_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "policy_id", _required_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "metric_name", _required_text(self.metric_name, "metric_name"))
        operator = _required_text(self.operator, "operator")
        if operator not in {"<", "<=", ">", ">=", "==", "!="}:
            raise ValueError("operator must be valid.")
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "threshold", _bounded_float(self.threshold, "threshold", 0.0, 100.0))
        object.__setattr__(self, "severity", _severity(self.severity))
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean.")
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class GovernanceViolation:
    """Immutable governance violation detected against policy constraints."""

    violation_id: str
    violation_type: str
    severity: str
    affected_policy: str
    affected_subsystem: str
    impact_score: float
    description: str
    recommended_correction: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", _required_text(self.violation_id, "violation_id"))
        violation_type = _required_text(self.violation_type, "violation_type").lower()
        if violation_type not in VIOLATION_TYPES:
            raise ValueError("violation_type must be valid.")
        object.__setattr__(self, "violation_type", violation_type)
        object.__setattr__(self, "severity", _severity(self.severity))
        object.__setattr__(self, "affected_policy", _required_text(self.affected_policy, "affected_policy"))
        object.__setattr__(self, "affected_subsystem", _required_text(self.affected_subsystem, "affected_subsystem"))
        object.__setattr__(self, "impact_score", _bounded_float(self.impact_score, "impact_score", 0.0, 100.0))
        object.__setattr__(self, "description", _required_text(self.description, "description"))
        object.__setattr__(self, "recommended_correction", _required_text(self.recommended_correction, "recommended_correction"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class GovernanceDecision:
    """Immutable governance decision for an executive recommendation."""

    decision_id: str
    status: str
    compliance_score: float
    confidence: float
    violations: List[GovernanceViolation | Dict[str, Any]]
    rationale: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", _required_text(self.decision_id, "decision_id"))
        status = _required_text(self.status, "status").lower()
        if status not in DECISION_STATUSES:
            raise ValueError("status must be valid.")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "compliance_score", _bounded_float(self.compliance_score, "compliance_score", 0.0, 100.0))
        object.__setattr__(self, "confidence", _bounded_float(self.confidence, "confidence", 0.0, 100.0))
        violations = [item if isinstance(item, GovernanceViolation) else GovernanceViolation(**_dict(item, "violation")) for item in self.violations]
        ids = [item.violation_id for item in violations]
        if len(ids) != len(set(ids)):
            raise ValueError("violations must have unique IDs.")
        object.__setattr__(self, "violations", violations)
        object.__setattr__(self, "rationale", _required_text(self.rationale, "rationale"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class GovernanceRecommendation:
    """Immutable recommendation-only governance correction."""

    recommendation_id: str
    action: str
    priority: int
    confidence: float
    reason: str
    affected_policies: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendation_id", _required_text(self.recommendation_id, "recommendation_id"))
        object.__setattr__(self, "action", _required_text(self.action, "action"))
        object.__setattr__(self, "priority", _priority(self.priority))
        object.__setattr__(self, "confidence", _bounded_float(self.confidence, "confidence", 0.0, 100.0))
        object.__setattr__(self, "reason", _required_text(self.reason, "reason"))
        policies = _string_list(self.affected_policies, "affected_policies", allow_empty=False)
        if len(policies) != len(set(policies)):
            raise ValueError("affected_policies must be unique.")
        object.__setattr__(self, "affected_policies", policies)
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class GovernanceAudit:
    """Immutable audit record for one governance evaluation."""

    audit_id: str
    policies_evaluated: List[str]
    violations: List[GovernanceViolation | Dict[str, Any]]
    decision: GovernanceDecision | Dict[str, Any]
    audit_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "audit_id", _required_text(self.audit_id, "audit_id"))
        policies = _string_list(self.policies_evaluated, "policies_evaluated", allow_empty=True)
        if len(policies) != len(set(policies)):
            raise ValueError("policies_evaluated must be unique.")
        object.__setattr__(self, "policies_evaluated", policies)
        violations = [item if isinstance(item, GovernanceViolation) else GovernanceViolation(**_dict(item, "violation")) for item in self.violations]
        ids = [item.violation_id for item in violations]
        if len(ids) != len(set(ids)):
            raise ValueError("violations must have unique IDs.")
        object.__setattr__(self, "violations", violations)
        object.__setattr__(self, "decision", self.decision if isinstance(self.decision, GovernanceDecision) else GovernanceDecision(**_dict(self.decision, "decision")))
        object.__setattr__(self, "audit_summary", _required_text(self.audit_summary, "audit_summary"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


@dataclass(frozen=True)
class ExecutiveGovernanceSummary:
    """Immutable aggregate summary of executive governance health."""

    summary_id: str
    governance_health: float
    policy_compliance: float
    strategic_discipline: float
    decision_integrity: float
    constraint_compliance: float
    executive_stability: float
    long_term_sustainability: float
    risk_compliance: float
    overall_governance_score: float
    executive_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary_id", _required_text(self.summary_id, "summary_id"))
        for name in (
            "governance_health",
            "policy_compliance",
            "strategic_discipline",
            "decision_integrity",
            "constraint_compliance",
            "executive_stability",
            "long_term_sustainability",
            "risk_compliance",
            "overall_governance_score",
        ):
            object.__setattr__(self, name, _bounded_float(getattr(self, name), name, 0.0, 100.0))
        object.__setattr__(self, "executive_summary", _required_text(self.executive_summary, "executive_summary"))
        object.__setattr__(self, "metadata", _dict(self.metadata, "metadata"))


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _category(value: object) -> str:
    category = _required_text(value, "category").lower()
    if category not in POLICY_CATEGORIES:
        raise ValueError("category must be valid.")
    return category


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
