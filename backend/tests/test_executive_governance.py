from dataclasses import FrozenInstanceError

import pytest

from backend.app.domain.executive_governance_model import (
    ExecutiveGovernanceSummary,
    ExecutivePolicy,
    GovernanceAudit,
    GovernanceDecision,
    GovernanceRecommendation,
    GovernanceRule,
    GovernanceViolation,
)
from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
from backend.app.orchestrator.executive_governance import ExecutiveGovernanceEngine


def reasoning(**overrides):
    payload = {
        "recommended_action": "Use optimized plan",
        "confidence": 82.0,
        "executive_priority": 2,
        "reasoning_trace": {
            "evidence_used": [{"source": "GoalIntelligenceEngine", "confidence": 80.0}],
            "conflicts_found": [],
            "risk_summary": {"risk_score": 12.0, "risk_level": "low"},
            "tradeoffs": [],
        },
    }
    payload.update(overrides)
    return payload


def resources(**overrides):
    payload = {
        "resource_health": {
            "overall_resource_score": 78.0,
            "executive_reserve": 72.0,
            "recovery_readiness": 74.0,
        },
        "resource_conflicts": [],
    }
    payload.update(overrides)
    return payload


def execution(**overrides):
    payload = {
        "execution_health": {"execution_health": 76.0},
        "execution_confidence": {"confidence": 80.0},
        "execution_deviations": [],
    }
    payload.update(overrides)
    return payload


def violation(**overrides):
    payload = {
        "violation_id": "violation-1",
        "violation_type": "policy_violation",
        "severity": "medium",
        "affected_policy": "risk_appetite",
        "affected_subsystem": "ExecutiveGovernance",
        "impact_score": 40.0,
        "description": "Risk compliance is low.",
        "recommended_correction": "Reduce execution risk",
    }
    payload.update(overrides)
    return GovernanceViolation(**payload)


def decision(**overrides):
    payload = {
        "decision_id": "decision-1",
        "status": "approved_with_conditions",
        "compliance_score": 70.0,
        "confidence": 75.0,
        "violations": [violation()],
        "rationale": "Approved with policy conditions.",
    }
    payload.update(overrides)
    return GovernanceDecision(**payload)


def summary(**overrides):
    payload = {
        "summary_id": "summary-1",
        "governance_health": 75.0,
        "policy_compliance": 70.0,
        "strategic_discipline": 80.0,
        "decision_integrity": 80.0,
        "constraint_compliance": 70.0,
        "executive_stability": 75.0,
        "long_term_sustainability": 72.0,
        "risk_compliance": 80.0,
        "overall_governance_score": 76.0,
        "executive_summary": "Governance healthy.",
    }
    payload.update(overrides)
    return ExecutiveGovernanceSummary(**payload)


def test_policy_rule_domain_validation_and_immutability():
    policy = ExecutivePolicy("policy-1", "Protect strategy", "strategic_alignment", 1, 60.0)
    rule = GovernanceRule("rule-1", "policy-1", "risk_score", "<=", 60.0, "high")

    assert policy.category == "strategic_alignment"
    assert rule.operator == "<="
    with pytest.raises(FrozenInstanceError):
        policy.threshold = 10.0
    with pytest.raises(ValueError, match="category must be valid"):
        ExecutivePolicy("bad", "Bad", "invalid", 1, 60.0)
    with pytest.raises(ValueError, match="operator must be valid"):
        GovernanceRule("bad", "policy-1", "score", "contains", 60.0, "low")
    with pytest.raises(ValueError, match="threshold must be finite"):
        ExecutivePolicy("bad", "Bad", "risk_appetite", 1, float("nan"))


def test_violation_decision_recommendation_audit_summary_validation():
    item = violation()
    current_decision = decision()
    recommendation = GovernanceRecommendation("rec-1", "Reduce execution risk", 1, 75.0, "Risk is elevated.", ["risk_appetite"])
    audit = GovernanceAudit("audit-1", ["policy-1"], [item], current_decision, "Audit complete.")
    current_summary = summary()

    assert item.severity == "medium"
    assert recommendation.affected_policies == ["risk_appetite"]
    assert audit.decision.status == "approved_with_conditions"
    assert current_summary.overall_governance_score == 76.0
    with pytest.raises(ValueError, match="violation_type must be valid"):
        violation(violation_type="bad")
    with pytest.raises(ValueError, match="violations must have unique IDs"):
        GovernanceDecision("bad", "approved", 70.0, 70.0, [item, item], "Duplicate.")
    with pytest.raises(ValueError, match="affected_policies must be unique"):
        GovernanceRecommendation("bad", "Act", 1, 70.0, "Reason.", ["risk_appetite", "risk_appetite"])
    with pytest.raises(ValueError, match="audit_summary must be a non-empty string"):
        GovernanceAudit("bad", [], [], decision(violations=[]), "")


def test_policy_compliance_scores_use_existing_outputs():
    engine = ExecutiveGovernanceEngine()
    scores = engine.evaluate_policy_compliance(
        executive_reasoning=reasoning(),
        resource_outputs=resources(),
        execution_outputs=execution(),
        context_outputs={"goals": [{"goal_id": "goal-1"}], "risk_level": "low"},
    )

    assert set(scores) == {
        "policy_compliance",
        "goal_alignment",
        "strategy_alignment",
        "risk_compliance",
        "resource_compliance",
        "execution_compliance",
    }
    assert scores["policy_compliance"] > 60.0


def test_goal_and_strategy_alignment_degrade_with_missing_goal_and_drift():
    engine = ExecutiveGovernanceEngine()

    goal_score = engine.evaluate_goal_alignment(reasoning=reasoning(reasoning_trace={"evidence_used": [], "risk_summary": {}, "conflicts_found": [], "tradeoffs": []}), context_outputs={})
    strategy_score = engine.evaluate_strategy_alignment(reasoning=reasoning(confidence=70.0), context_outputs={"strategic_drift": True})

    assert goal_score < 70.0
    assert strategy_score == 52.0


def test_risk_resource_and_execution_policy_boundaries():
    engine = ExecutiveGovernanceEngine()

    assert engine.evaluate_risk_tolerance(reasoning=reasoning(reasoning_trace={"risk_summary": {"risk_score": 80.0, "risk_level": "critical"}, "evidence_used": [], "conflicts_found": [], "tradeoffs": []})) == 20.0
    assert engine.evaluate_resource_policy(resource_outputs=resources(resource_health={"overall_resource_score": 40.0, "executive_reserve": 30.0, "recovery_readiness": 30.0}, resource_conflicts=[{"id": "conflict"}])) < 40.0
    assert engine.evaluate_execution_policy(execution_outputs=execution(execution_health={"execution_health": 40.0}, execution_confidence={"confidence": 40.0}, execution_deviations=[{"id": "d1"}])) == 35.0


def test_policy_conflicts_and_governance_violations():
    engine = ExecutiveGovernanceEngine()
    compliance = {
        "policy_compliance": 50.0,
        "goal_alignment": 85.0,
        "strategy_alignment": 35.0,
        "risk_compliance": 40.0,
        "resource_compliance": 80.0,
        "execution_compliance": 55.0,
    }
    conflicts = engine.detect_policy_conflicts(compliance)
    violations = engine.detect_governance_violations(compliance=compliance)

    assert conflicts
    assert any(item.violation_type == "governance_instability" for item in violations)
    assert any(item.violation_type == "policy_violation" for item in violations)


def test_priority_inversion_and_constraint_violation_detection():
    engine = ExecutiveGovernanceEngine()

    priority = engine.detect_priority_inversion({"priority_inversion": True}, reasoning(executive_priority=9))
    constraints = engine.detect_constraint_violation(
        resources(resource_health={"overall_resource_score": 30.0, "executive_reserve": 20.0, "recovery_readiness": 25.0}),
        execution(execution_health={"execution_health": 30.0}),
    )

    assert priority[0].violation_type == "priority_inversion"
    assert {item.violation_type for item in constraints} == {"constraint_violation", "resource_misuse", "execution_inconsistency"}


def test_confidence_stability_and_recommendations():
    engine = ExecutiveGovernanceEngine()
    violations = [violation(impact_score=50.0)]
    compliance = {"policy_compliance": 80.0}
    confidence = engine.estimate_governance_confidence(compliance, violations)
    stability = engine.estimate_policy_stability(violations)
    recommendations = engine.generate_governance_recommendations(violations, confidence)

    assert confidence == 76.0
    assert stability == 50.0
    assert recommendations[0].action == "Reduce execution risk"


def test_recommendations_include_default_when_no_violations():
    recommendations = ExecutiveGovernanceEngine().generate_governance_recommendations([], 90.0)

    assert recommendations[0].action == "Protect strategic objectives"
    assert recommendations[0].priority == 4


def test_dashboard_and_audit_generation():
    engine = ExecutiveGovernanceEngine()
    current_decision = decision()
    current_summary = summary()
    recommendations = engine.generate_governance_recommendations(current_decision.violations, 75.0)
    dashboard = engine.generate_governance_dashboard(current_decision, current_summary, recommendations)
    audit = engine.generate_governance_audit(current_decision, current_decision.violations)

    assert dashboard["governance_status"] == "approved_with_conditions"
    assert dashboard["active_violations"]
    assert audit.audit_summary


def test_generate_governance_summary_outputs_schema():
    outputs = ExecutiveGovernanceEngine().generate_governance_summary(
        executive_reasoning=reasoning(),
        executive_experience={"decision_count": 1},
        execution_outputs=execution(),
        resource_outputs=resources(),
        context_awareness={"risk_state": "low"},
    )

    assert set(outputs) == {
        "governance_state",
        "governance_health",
        "governance_dashboard",
        "governance_summary",
        "governance_recommendations",
        "governance_audit",
        "governance_confidence",
        "governance_policy_compliance",
        "governance_violations",
        "executive_governance_score",
    }
    assert outputs["governance_summary"]["executive_summary"]


def test_high_risk_summary_generates_risk_violation():
    outputs = ExecutiveGovernanceEngine().generate_governance_summary(
        executive_reasoning=reasoning(reasoning_trace={"risk_summary": {"risk_score": 90.0, "risk_level": "critical"}, "evidence_used": [], "conflicts_found": [], "tradeoffs": []}),
        execution_outputs=execution(),
        resource_outputs=resources(),
    )

    assert any(item["affected_policy"] == "risk_compliance" for item in outputs["governance_violations"])


def test_resource_and_execution_failures_generate_conditioned_decision():
    outputs = ExecutiveGovernanceEngine().generate_governance_summary(
        executive_reasoning=reasoning(),
        execution_outputs=execution(execution_health={"execution_health": 20.0}, execution_confidence={"confidence": 20.0}),
        resource_outputs=resources(resource_health={"overall_resource_score": 20.0, "executive_reserve": 20.0, "recovery_readiness": 20.0}),
    )

    assert outputs["governance_state"]["status"] in {"approved_with_conditions", "blocked", "needs_review"}
    assert outputs["governance_violations"]


def test_malformed_inputs_nan_infinity_and_invalid_containers():
    engine = ExecutiveGovernanceEngine()

    with pytest.raises(ValueError, match="max_history must be a positive integer"):
        ExecutiveGovernanceEngine(max_history=0)
    with pytest.raises(ValueError, match="policies must have unique IDs"):
        ExecutiveGovernanceEngine(policies=[ExecutivePolicy("p", "One", "risk_appetite", 1, 50.0), ExecutivePolicy("p", "Two", "risk_appetite", 1, 50.0)])
    with pytest.raises(ValueError, match="executive_reasoning must be a dictionary"):
        engine.evaluate_policy_compliance(executive_reasoning=["bad"])
    with pytest.raises(ValueError, match="finite"):
        engine.generate_governance_summary(executive_reasoning=reasoning(confidence=float("inf")))
    with pytest.raises(ValueError, match="out of range"):
        engine.estimate_governance_confidence({"policy_compliance": -1.0}, [])


def test_bounded_audit_history_after_large_dataset():
    engine = ExecutiveGovernanceEngine(max_history=3)
    for _ in range(10):
        engine.generate_governance_summary(executive_reasoning=reasoning(), execution_outputs=execution(), resource_outputs=resources())

    assert len(engine._audits) == 3
    assert engine._audits[0].audit_id == "governance-audit-8"


def test_large_policy_set_is_sorted_and_deterministic():
    policies = [ExecutivePolicy(f"policy-{index}", f"Policy {index}", "policy_compliance", 5 - index % 5, 50.0) for index in range(50)]
    first = ExecutiveGovernanceEngine(policies=policies).generate_governance_summary(executive_reasoning=reasoning(), execution_outputs=execution(), resource_outputs=resources())
    second = ExecutiveGovernanceEngine(policies=policies).generate_governance_summary(executive_reasoning=reasoning(), execution_outputs=execution(), resource_outputs=resources())

    assert first == second
    assert len(first["governance_audit"]["policies_evaluated"]) == 50


def test_governance_outputs_are_deterministic():
    first = ExecutiveGovernanceEngine().generate_governance_summary(executive_reasoning=reasoning(), execution_outputs=execution(), resource_outputs=resources())
    second = ExecutiveGovernanceEngine().generate_governance_summary(executive_reasoning=reasoning(), execution_outputs=execution(), resource_outputs=resources())

    assert first == second


def test_executive_brain_governance_integration_and_backward_compatibility():
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "task-1", "task_type": "deep_work", "estimated_duration": 1.0}],
        behavior_patterns={"average_energy_level": 75.0},
        goals=[{"goal_id": "goal-1"}],
    )

    existing_keys = {
        "executive_context",
        "executive_objectives",
        "candidate_plans",
        "recommended_plan",
        "future_analysis",
        "tradeoff_analysis",
        "risk_summary",
        "executive_summary",
        "explanations",
        "reflection",
        "resource_state",
    }
    governance_keys = {
        "governance_state",
        "governance_health",
        "governance_dashboard",
        "governance_summary",
        "governance_recommendations",
        "governance_audit",
        "governance_confidence",
        "governance_policy_compliance",
        "governance_violations",
        "executive_governance_score",
    }

    assert existing_keys <= set(result)
    assert governance_keys <= set(result)
    assert 0.0 <= result["executive_governance_score"]["score"] <= 100.0
    assert result["governance_summary"]["executive_summary"]


def test_executive_brain_governance_outputs_are_deterministic():
    first = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])
    second = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])

    for key in (
        "governance_state",
        "governance_health",
        "governance_dashboard",
        "governance_summary",
        "governance_recommendations",
        "governance_audit",
        "governance_confidence",
        "governance_policy_compliance",
        "governance_violations",
        "executive_governance_score",
    ):
        assert first[key] == second[key]
