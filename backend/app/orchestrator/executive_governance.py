from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Dict, List

from backend.app.domain.executive_governance_model import (
    ExecutiveGovernanceSummary,
    ExecutivePolicy,
    GovernanceAudit,
    GovernanceDecision,
    GovernanceRecommendation,
    GovernanceRule,
    GovernanceViolation,
)


class ExecutiveGovernanceEngine:
    """Evaluate executive recommendations against deterministic policies.

    The engine consumes existing executive outputs as read-only input and returns
    governance diagnostics, violations, audits, and recommendations. It does not
    plan, reason, allocate resources, supervise execution, or mutate inputs.
    """

    DEFAULT_MAX_HISTORY = 500
    MIN_POLICY_SCORE = 60.0
    HIGH_RISK_LIMIT = 70.0
    LOW_RESOURCE_LIMIT = 45.0
    LOW_EXECUTION_LIMIT = 45.0

    def __init__(self, max_history: int = DEFAULT_MAX_HISTORY, policies: List[ExecutivePolicy | Dict[str, Any]] | None = None) -> None:
        if not isinstance(max_history, int) or isinstance(max_history, bool) or max_history <= 0:
            raise ValueError("max_history must be a positive integer.")
        self.max_history = max_history
        self.policies = self._normalize_policies(policies)
        self._audits: List[GovernanceAudit] = []
        self._audit_sequence = 0

    def evaluate_policy_compliance(self, *, executive_reasoning: Dict[str, Any] | None = None, resource_outputs: Dict[str, Any] | None = None, execution_outputs: Dict[str, Any] | None = None, context_outputs: Dict[str, Any] | None = None) -> Dict[str, float]:
        """Evaluate policy compliance from upstream executive outputs."""
        reasoning = self._dict(executive_reasoning or {}, "executive_reasoning")
        resources = self._dict(resource_outputs or {}, "resource_outputs")
        execution = self._dict(execution_outputs or {}, "execution_outputs")
        context = self._dict(context_outputs or {}, "context_outputs")
        goal_alignment = self.evaluate_goal_alignment(reasoning=reasoning, context_outputs=context)
        strategy_alignment = self.evaluate_strategy_alignment(reasoning=reasoning, context_outputs=context)
        risk_compliance = self.evaluate_risk_tolerance(reasoning=reasoning, context_outputs=context)
        resource_compliance = self.evaluate_resource_policy(resource_outputs=resources)
        execution_compliance = self.evaluate_execution_policy(execution_outputs=execution)
        policy_compliance = self._average([goal_alignment, strategy_alignment, risk_compliance, resource_compliance, execution_compliance])
        return {
            "policy_compliance": policy_compliance,
            "goal_alignment": goal_alignment,
            "strategy_alignment": strategy_alignment,
            "risk_compliance": risk_compliance,
            "resource_compliance": resource_compliance,
            "execution_compliance": execution_compliance,
        }

    def evaluate_goal_alignment(self, *, reasoning: Dict[str, Any] | None = None, context_outputs: Dict[str, Any] | None = None) -> float:
        """Evaluate whether the recommendation remains aligned with goals."""
        payload = self._dict(reasoning or {}, "reasoning")
        context = self._dict(context_outputs or {}, "context_outputs")
        trace = payload.get("reasoning_trace", {}) if isinstance(payload.get("reasoning_trace"), dict) else {}
        evidence = trace.get("evidence_used", []) if isinstance(trace.get("evidence_used", []), list) else []
        goal_evidence = any(isinstance(item, dict) and item.get("source") == "GoalIntelligenceEngine" for item in evidence)
        goals = context.get("goals", []) if isinstance(context.get("goals", []), list) else []
        base = self._score(payload.get("confidence", 50.0), 0.0, 100.0)
        return round(self._clamp(base + (12.0 if goal_evidence or goals else -18.0), 0.0, 100.0), 2)

    def evaluate_strategy_alignment(self, *, reasoning: Dict[str, Any] | None = None, context_outputs: Dict[str, Any] | None = None) -> float:
        """Evaluate strategic discipline using reasoning confidence and context drift signals."""
        payload = self._dict(reasoning or {}, "reasoning")
        context = self._dict(context_outputs or {}, "context_outputs")
        confidence = self._score(payload.get("confidence", 50.0), 0.0, 100.0)
        drift_penalty = 18.0 if context.get("strategic_drift") else 0.0
        return round(self._clamp(confidence - drift_penalty, 0.0, 100.0), 2)

    def evaluate_risk_tolerance(self, *, reasoning: Dict[str, Any] | None = None, context_outputs: Dict[str, Any] | None = None) -> float:
        """Evaluate whether executive risk is inside policy appetite."""
        payload = self._dict(reasoning or {}, "reasoning")
        context = self._dict(context_outputs or {}, "context_outputs")
        trace = payload.get("reasoning_trace", {}) if isinstance(payload.get("reasoning_trace"), dict) else {}
        risk = trace.get("risk_summary", {}) if isinstance(trace.get("risk_summary"), dict) else {}
        risk_score = self._score(risk.get("risk_score", context.get("risk_score", 20.0)), 0.0, 100.0)
        if str(risk.get("risk_level", context.get("risk_level", "low"))).lower() in {"high", "critical"}:
            risk_score = max(risk_score, self.HIGH_RISK_LIMIT)
        return round(self._clamp(100.0 - risk_score, 0.0, 100.0), 2)

    def evaluate_resource_policy(self, *, resource_outputs: Dict[str, Any] | None = None) -> float:
        """Evaluate compliance with resource protection policies."""
        resources = self._dict(resource_outputs or {}, "resource_outputs")
        health = self._nested_score(resources, ["resource_health", "overall_resource_score"], 60.0)
        reserve = self._nested_score(resources, ["resource_health", "executive_reserve"], 60.0)
        recovery = self._nested_score(resources, ["resource_health", "recovery_readiness"], 60.0)
        conflicts = len(resources.get("resource_conflicts", [])) if isinstance(resources.get("resource_conflicts", []), list) else 0
        return round(self._clamp(self._average([health, reserve, recovery]) - conflicts * 4.0, 0.0, 100.0), 2)

    def evaluate_execution_policy(self, *, execution_outputs: Dict[str, Any] | None = None) -> float:
        """Evaluate execution discipline using existing execution supervision output."""
        execution = self._dict(execution_outputs or {}, "execution_outputs")
        health = self._nested_score(execution, ["execution_health", "execution_health"], 65.0)
        confidence = self._nested_score(execution, ["execution_confidence", "confidence"], 60.0)
        deviations = len(execution.get("execution_deviations", [])) if isinstance(execution.get("execution_deviations", []), list) else 0
        return round(self._clamp(self._average([health, confidence]) - deviations * 5.0, 0.0, 100.0), 2)

    def detect_policy_conflicts(self, compliance: Dict[str, float] | None = None) -> List[GovernanceViolation]:
        """Detect conflicts between policy dimensions from compliance scores."""
        scores = self._dict(compliance or {}, "compliance")
        violations = []
        high = [key for key, value in sorted(scores.items()) if key != "policy_compliance" and self._score(value, 0.0, 100.0) >= 75.0]
        low = [key for key, value in sorted(scores.items()) if key != "policy_compliance" and self._score(value, 0.0, 100.0) < 45.0]
        if high and low:
            violations.append(self._violation("governance_instability", "policy_compliance", "ExecutiveGovernance", 60.0, "Policy dimensions disagree materially.", "Improve governance discipline", {"high": high, "low": low}))
        return violations

    def detect_governance_violations(self, *, compliance: Dict[str, float], executive_reasoning: Dict[str, Any] | None = None, resource_outputs: Dict[str, Any] | None = None, execution_outputs: Dict[str, Any] | None = None, context_outputs: Dict[str, Any] | None = None) -> List[GovernanceViolation]:
        """Detect deterministic governance violations against active policies."""
        scores = self._dict(compliance, "compliance")
        violations: List[GovernanceViolation] = []
        for key, value in sorted(scores.items()):
            if key != "policy_compliance" and self._score(value, 0.0, 100.0) < self.MIN_POLICY_SCORE:
                violations.append(self._violation("policy_violation", key, "ExecutiveGovernance", 100.0 - float(value), f"{key} is below governance threshold.", "Strengthen policy compliance", {"score": value}))
        violations.extend(self.detect_policy_conflicts(scores))
        violations.extend(self.detect_priority_inversion(context_outputs or {}, executive_reasoning or {}))
        violations.extend(self.detect_constraint_violation(resource_outputs or {}, execution_outputs or {}))
        return self._dedupe_violations(violations)

    def detect_priority_inversion(self, context_outputs: Dict[str, Any] | None = None, executive_reasoning: Dict[str, Any] | None = None) -> List[GovernanceViolation]:
        """Detect priority inversion from context and reasoning metadata."""
        context = self._dict(context_outputs or {}, "context_outputs")
        reasoning = self._dict(executive_reasoning or {}, "executive_reasoning")
        if not context.get("priority_inversion") and self._score(reasoning.get("executive_priority", 3), 1.0, 10.0) <= 5.0:
            return []
        return [self._violation("priority_inversion", "decision_quality", "DecisionIntelligenceEngine", 62.0, "Executive priority appears inverted.", "Rebalance priorities")]

    def detect_constraint_violation(self, resource_outputs: Dict[str, Any] | None = None, execution_outputs: Dict[str, Any] | None = None) -> List[GovernanceViolation]:
        """Detect resource and execution constraint violations."""
        resources = self._dict(resource_outputs or {}, "resource_outputs")
        execution = self._dict(execution_outputs or {}, "execution_outputs")
        violations: List[GovernanceViolation] = []
        if self._nested_score(resources, ["resource_health", "executive_reserve"], 70.0) < self.LOW_RESOURCE_LIMIT:
            violations.append(self._violation("constraint_violation", "executive_reserve", "ExecutiveResourceEngine", 70.0, "Executive reserve is below policy minimum.", "Increase executive reserve"))
        if self._nested_score(resources, ["resource_health", "recovery_readiness"], 70.0) < self.LOW_RESOURCE_LIMIT:
            violations.append(self._violation("resource_misuse", "recovery_protection", "ExecutiveResourceEngine", 68.0, "Recovery protection is below policy minimum.", "Increase recovery reserve"))
        if self._nested_score(execution, ["execution_health", "execution_health"], 70.0) < self.LOW_EXECUTION_LIMIT:
            violations.append(self._violation("execution_inconsistency", "execution_discipline", "ExecutiveExecutionEngine", 72.0, "Execution discipline is below governance policy.", "Reduce execution risk"))
        return violations

    def estimate_governance_confidence(self, compliance: Dict[str, float], violations: List[GovernanceViolation | Dict[str, Any]]) -> float:
        """Estimate bounded governance confidence from compliance and violations."""
        scores = self._dict(compliance, "compliance")
        violation_objs = [self._violation_obj(item) for item in violations]
        base = self._score(scores.get("policy_compliance", 50.0), 0.0, 100.0)
        penalty = sum(item.impact_score for item in violation_objs) * 0.08
        return round(self._clamp(base - penalty, 0.0, 100.0), 2)

    def estimate_policy_stability(self, violations: List[GovernanceViolation | Dict[str, Any]]) -> float:
        """Estimate policy stability from violation severity."""
        violation_objs = [self._violation_obj(item) for item in violations]
        if not violation_objs:
            return 100.0
        average_impact = sum(item.impact_score for item in violation_objs) / len(violation_objs)
        return round(self._clamp(100.0 - average_impact, 0.0, 100.0), 2)

    def generate_governance_recommendations(self, violations: List[GovernanceViolation | Dict[str, Any]], confidence: float) -> List[GovernanceRecommendation]:
        """Generate recommendation-only governance corrections."""
        confidence_score = self._score(confidence, 0.0, 100.0)
        recommendations = []
        for violation in [self._violation_obj(item) for item in violations]:
            recommendations.append(
                GovernanceRecommendation(
                    f"governance-recommendation-{self._slug(violation.recommended_correction)}",
                    violation.recommended_correction,
                    1 if violation.severity in {"high", "critical"} else 3,
                    max(35.0, min(100.0, confidence_score + violation.impact_score * 0.25)),
                    violation.description,
                    [violation.affected_policy],
                    {"violation_id": violation.violation_id},
                )
            )
        if not recommendations:
            recommendations.append(GovernanceRecommendation("governance-recommendation-maintain-discipline", "Protect strategic objectives", 4, confidence_score, "Executive recommendation complies with governance policy.", ["strategic_alignment"]))
        return self._dedupe_recommendations(recommendations)

    def generate_governance_dashboard(self, decision: GovernanceDecision | Dict[str, Any], summary: ExecutiveGovernanceSummary | Dict[str, Any], recommendations: List[GovernanceRecommendation | Dict[str, Any]]) -> Dict[str, Any]:
        """Generate deterministic governance dashboard output."""
        decision_obj = decision if isinstance(decision, GovernanceDecision) else GovernanceDecision(**self._dict(decision, "decision"))
        summary_obj = summary if isinstance(summary, ExecutiveGovernanceSummary) else ExecutiveGovernanceSummary(**self._dict(summary, "summary"))
        dashboard = {
            "governance_status": decision_obj.status,
            "policy_compliance": summary_obj.policy_compliance,
            "active_violations": [asdict(item) for item in decision_obj.violations],
            "governance_health": summary_obj.governance_health,
            "strategic_discipline": summary_obj.strategic_discipline,
            "risk_compliance": summary_obj.risk_compliance,
            "constraint_status": "clear" if not decision_obj.violations else "violations_detected",
            "recommendations": [asdict(self._recommendation_obj(item)) for item in recommendations],
            "executive_governance_summary": summary_obj.executive_summary,
        }
        self._validate_payload(dashboard, "governance_dashboard")
        return dashboard

    def generate_governance_summary(self, *, executive_reasoning: Dict[str, Any] | None = None, executive_experience: Dict[str, Any] | None = None, execution_outputs: Dict[str, Any] | None = None, resource_outputs: Dict[str, Any] | None = None, adaptive_life: Dict[str, Any] | None = None, meta_cognitive: Dict[str, Any] | None = None, decision_intelligence: Dict[str, Any] | None = None, goal_intelligence: Dict[str, Any] | None = None, context_awareness: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Return all Executive Brain governance outputs from existing outputs."""
        context_outputs = self._merge_context(adaptive_life or {}, meta_cognitive or {}, decision_intelligence or {}, goal_intelligence or {}, context_awareness or {})
        compliance = self.evaluate_policy_compliance(executive_reasoning=executive_reasoning or {}, resource_outputs=resource_outputs or {}, execution_outputs=execution_outputs or {}, context_outputs=context_outputs)
        violations = self.detect_governance_violations(compliance=compliance, executive_reasoning=executive_reasoning or {}, resource_outputs=resource_outputs or {}, execution_outputs=execution_outputs or {}, context_outputs=context_outputs)
        confidence = self.estimate_governance_confidence(compliance, violations)
        stability = self.estimate_policy_stability(violations)
        summary = self._summary(compliance, violations, confidence, stability, executive_experience or {})
        decision = self._decision(compliance, violations, confidence, summary)
        recommendations = self.generate_governance_recommendations(violations, confidence)
        dashboard = self.generate_governance_dashboard(decision, summary, recommendations)
        audit = self.generate_governance_audit(decision, violations)
        outputs = {
            "governance_state": asdict(decision),
            "governance_health": {
                "governance_health": summary.governance_health,
                "policy_compliance": summary.policy_compliance,
                "strategic_discipline": summary.strategic_discipline,
                "decision_integrity": summary.decision_integrity,
                "constraint_compliance": summary.constraint_compliance,
                "executive_stability": summary.executive_stability,
                "long_term_sustainability": summary.long_term_sustainability,
                "risk_compliance": summary.risk_compliance,
                "overall_governance_score": summary.overall_governance_score,
            },
            "governance_dashboard": dashboard,
            "governance_summary": asdict(summary),
            "governance_recommendations": [asdict(item) for item in recommendations],
            "governance_audit": asdict(audit),
            "governance_confidence": {"confidence": confidence},
            "governance_policy_compliance": compliance,
            "governance_violations": [asdict(item) for item in violations],
            "executive_governance_score": {"score": summary.overall_governance_score},
        }
        self._validate_governance_outputs(outputs)
        return outputs

    def generate_governance_audit(self, decision: GovernanceDecision | Dict[str, Any], violations: List[GovernanceViolation | Dict[str, Any]]) -> GovernanceAudit:
        """Generate bounded deterministic governance audit record."""
        decision_obj = decision if isinstance(decision, GovernanceDecision) else GovernanceDecision(**self._dict(decision, "decision"))
        violation_objs = [self._violation_obj(item) for item in violations]
        self._audit_sequence += 1
        audit = GovernanceAudit(
            f"governance-audit-{self._audit_sequence}",
            [policy.policy_id for policy in self.policies if policy.enabled],
            violation_objs,
            decision_obj,
            f"Governance audit evaluated {len(self.policies)} policies and found {len(violation_objs)} violations.",
        )
        self._audits.append(audit)
        if len(self._audits) > self.max_history:
            self._audits = self._audits[-self.max_history :]
        return audit

    def _summary(self, compliance: Dict[str, float], violations: List[GovernanceViolation], confidence: float, stability: float, experience: Dict[str, Any]) -> ExecutiveGovernanceSummary:
        policy_compliance = self._score(compliance.get("policy_compliance", 50.0), 0.0, 100.0)
        strategic = self._score(compliance.get("strategy_alignment", 50.0), 0.0, 100.0)
        goal = self._score(compliance.get("goal_alignment", 50.0), 0.0, 100.0)
        risk = self._score(compliance.get("risk_compliance", 50.0), 0.0, 100.0)
        resource = self._score(compliance.get("resource_compliance", 50.0), 0.0, 100.0)
        execution = self._score(compliance.get("execution_compliance", 50.0), 0.0, 100.0)
        decision_integrity = self._clamp((confidence + goal + strategic) / 3.0, 0.0, 100.0)
        constraint = self._clamp((resource + execution + risk) / 3.0, 0.0, 100.0)
        sustainability = self._clamp((resource + risk + stability) / 3.0, 0.0, 100.0)
        health = self._clamp((policy_compliance + decision_integrity + constraint + stability) / 4.0, 0.0, 100.0)
        overall = self._clamp(health * 0.35 + policy_compliance * 0.25 + strategic * 0.15 + risk * 0.15 + sustainability * 0.1, 0.0, 100.0)
        summary = f"Governance score is {round(overall, 2)} with {len(violations)} active violations."
        return ExecutiveGovernanceSummary("executive-governance-summary", health, policy_compliance, strategic, decision_integrity, constraint, stability, sustainability, risk, overall, summary, {"experience_decision_count": experience.get("decision_count", 0) if isinstance(experience, dict) else 0})

    def _decision(self, compliance: Dict[str, float], violations: List[GovernanceViolation], confidence: float, summary: ExecutiveGovernanceSummary) -> GovernanceDecision:
        status = "approved" if not violations and summary.overall_governance_score >= 70.0 else "approved_with_conditions" if summary.overall_governance_score >= 45.0 else "needs_review"
        if any(item.severity == "critical" for item in violations):
            status = "blocked"
        return GovernanceDecision("governance-decision-current", status, compliance["policy_compliance"], confidence, violations, f"Governance decision is {status}.", {"overall_governance_score": summary.overall_governance_score})

    def _normalize_policies(self, policies: List[ExecutivePolicy | Dict[str, Any]] | None) -> List[ExecutivePolicy]:
        if policies is None:
            policies = self._default_policies()
        if not isinstance(policies, list):
            raise ValueError("policies must be a list.")
        normalized = [policy if isinstance(policy, ExecutivePolicy) else ExecutivePolicy(**self._dict(policy, "policy")) for policy in policies]
        ids = [policy.policy_id for policy in normalized]
        if len(ids) != len(set(ids)):
            raise ValueError("policies must have unique IDs.")
        return sorted(normalized, key=lambda item: (item.priority, item.policy_id))

    def _default_policies(self) -> List[ExecutivePolicy]:
        return [
            ExecutivePolicy("policy-strategic-alignment", "Protect strategic alignment", "strategic_alignment", 1, 60.0),
            ExecutivePolicy("policy-risk-appetite", "Stay within risk appetite", "risk_appetite", 1, 60.0),
            ExecutivePolicy("policy-resource-protection", "Protect finite resources", "resource_protection", 2, 60.0),
            ExecutivePolicy("policy-execution-discipline", "Maintain execution discipline", "execution_discipline", 2, 60.0),
            ExecutivePolicy("policy-sustainability", "Protect long-term sustainability", "long_term_sustainability", 3, 60.0),
        ]

    def _merge_context(self, adaptive: Dict[str, Any], meta: Dict[str, Any], decision: Dict[str, Any], goals: Dict[str, Any], awareness: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for name, payload in sorted({"adaptive_life": adaptive, "meta_cognitive": meta, "decision_intelligence": decision, "goal_intelligence": goals, "context_awareness": awareness}.items()):
            if payload:
                merged[name] = self._dict(payload, name)
        risk_level = merged.get("context_awareness", {}).get("risk_state") or merged.get("meta_cognitive", {}).get("risk_level")
        if risk_level:
            merged["risk_level"] = risk_level
            if str(risk_level).lower() in {"high", "critical"}:
                merged["risk_score"] = 75.0
        if merged.get("context_awareness", {}).get("strategic_drift"):
            merged["strategic_drift"] = True
        if merged.get("context_awareness", {}).get("priority_inversion"):
            merged["priority_inversion"] = True
        return merged

    def _violation(self, violation_type: str, policy: str, subsystem: str, impact: float, description: str, correction: str, metadata: Dict[str, Any] | None = None) -> GovernanceViolation:
        impact_score = self._clamp(impact, 0.0, 100.0)
        return GovernanceViolation(f"governance-violation-{violation_type}-{policy}", violation_type, self._severity_from_score(impact_score), policy, subsystem, impact_score, description, correction, metadata or {})

    def _dedupe_violations(self, violations: List[GovernanceViolation]) -> List[GovernanceViolation]:
        seen = set()
        result = []
        for violation in violations:
            key = (violation.violation_type, violation.affected_policy, violation.affected_subsystem)
            if key not in seen:
                seen.add(key)
                result.append(violation)
        return sorted(result, key=lambda item: (-item.impact_score, item.violation_type, item.affected_policy))

    def _dedupe_recommendations(self, recommendations: List[GovernanceRecommendation]) -> List[GovernanceRecommendation]:
        seen = set()
        result = []
        for recommendation in recommendations:
            if recommendation.recommendation_id not in seen:
                seen.add(recommendation.recommendation_id)
                result.append(recommendation)
        return sorted(result, key=lambda item: (item.priority, -item.confidence, item.action))

    def _validate_governance_outputs(self, outputs: Dict[str, Any]) -> None:
        expected = {"governance_state", "governance_health", "governance_dashboard", "governance_summary", "governance_recommendations", "governance_audit", "governance_confidence", "governance_policy_compliance", "governance_violations", "executive_governance_score"}
        if set(outputs) != expected:
            raise ValueError("governance outputs have invalid fields.")
        for key in expected - {"governance_recommendations", "governance_violations"}:
            if not isinstance(outputs[key], dict):
                raise ValueError(f"{key} must be a dictionary.")
        for key in ("governance_recommendations", "governance_violations"):
            if not isinstance(outputs[key], list):
                raise ValueError(f"{key} must be a list.")
        self._validate_payload(outputs, "governance outputs")

    def _validate_payload(self, value: Any, field_name: str) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                self._validate_payload(nested, field_name)
            return
        if isinstance(value, list):
            for nested in value:
                self._validate_payload(nested, field_name)
            return
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return
        if isinstance(value, (int, float)) and not math.isfinite(float(value)):
            raise ValueError(f"{field_name} contains non-finite numeric value.")

    def _nested_score(self, payload: Dict[str, Any], path: List[str], default: float) -> float:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict):
                return default
            value = value.get(key, default)
        return self._score(value, 0.0, 100.0)

    def _score(self, value: Any, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError("governance numeric inputs must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError("governance numeric inputs must be finite.")
        if number < minimum or number > maximum:
            raise ValueError("governance numeric inputs are out of range.")
        return number

    def _average(self, values: List[float]) -> float:
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    def _severity_from_score(self, score: float) -> str:
        if score >= 75.0:
            return "critical"
        if score >= 50.0:
            return "high"
        if score >= 25.0:
            return "medium"
        return "low"

    def _violation_obj(self, value: GovernanceViolation | Dict[str, Any]) -> GovernanceViolation:
        return value if isinstance(value, GovernanceViolation) else GovernanceViolation(**self._dict(value, "violation"))

    def _recommendation_obj(self, value: GovernanceRecommendation | Dict[str, Any]) -> GovernanceRecommendation:
        return value if isinstance(value, GovernanceRecommendation) else GovernanceRecommendation(**self._dict(value, "recommendation"))

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        self._validate_payload(value, field_name)
        return dict(value)

    def _slug(self, value: str) -> str:
        return "-".join(part for part in value.lower().split() if part)

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, round(value, 4)))
