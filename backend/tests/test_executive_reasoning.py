from dataclasses import FrozenInstanceError

import pytest

from backend.app.domain.executive_reasoning_model import (
    Evidence,
    EvidenceConflict,
    ExecutiveRecommendation,
    ExecutiveReasoningTrace,
)
from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
from backend.app.orchestrator.executive_reasoning import ExecutiveReasoningEngine


def evidence(source="DecisionIntelligenceEngine", recommendation="Use optimized plan", **overrides):
    payload = {
        "source": source,
        "confidence": 82.0,
        "recommendation": recommendation,
        "risk_level": "low",
        "priority": 2,
        "score": 84.0,
        "explanation": "Strong evidence supports this action.",
        "metadata": {},
    }
    payload.update(overrides)
    return Evidence(**payload)


def sample_reasoning_inputs():
    tasks = [
        {
            "id": "task-1",
            "title": "Build executive reasoning",
            "priority": 5,
            "predicted_productivity": 86.0,
        }
    ]
    return {
        "executive_context": {
            "context": {"current_tasks": tasks},
            "context_snapshot": {"risk_state": "low", "momentum_state": "positive", "confidence": 76.0},
            "behavior_learning": {
                "behavior_learning_summary": {"habit_strength": 82.0},
                "behavior_insights": [],
            },
            "adaptive_life": {"burnout_probability": 0.1},
            "meta_cognitive": {"average_error": 8.0, "risk_level": "low"},
        },
        "executive_objectives": {
            "goals": [{"goal_id": "goal-1", "title": "Ship platform"}],
            "goal_state": [{"goal_id": "goal-1", "title": "Ship platform", "priority": 8}],
            "dependency_state": {"blocked_tasks": [], "critical_path": ["task-1"]},
            "knowledge_state": {"knowledge_health": {"knowledge_connectivity_score": 72.0}},
        },
        "decision_state": {
            "predicted_tasks": tasks,
            "recommended_task_order": tasks,
        },
        "candidate_plans": {"plans": [{"plan_type": "optimized_schedule", "plan": {"tasks": tasks}}]},
        "recommended_plan": {
            "option_id": "candidate-1",
            "title": "Optimized Schedule",
            "reasoning": "Best current plan.",
            "overall_score": 88.0,
            "decision_analysis": None,
        },
        "future_analysis": {
            "simulation": {
                "scenario_id": "baseline",
                "scenario_name": "Baseline",
                "success_probability": 0.84,
                "risk_score": 11.0,
                "confidence_score": 82.0,
            },
            "ranked_futures": [
                {
                    "selected_scenario_id": "baseline",
                    "selected_scenario_name": "Baseline",
                    "overall_score": 86.0,
                    "optimization_summary": {
                        "selected_future": {
                            "scenario_id": "baseline",
                            "scenario_name": "Baseline",
                            "overall_score": 86.0,
                        }
                    },
                }
            ],
        },
        "tradeoff_analysis": {"tradeoffs": [{"description": "Moderate effort for strategic gain."}]},
        "risk_summary": {"risk_score": 11.0, "risk_level": "low"},
        "reflection": {"meta_cognitive": {"average_error": 8.0, "risk_level": "low"}},
    }


def test_evidence_validation_and_immutability():
    item = evidence()

    assert item.confidence == 82.0
    with pytest.raises(FrozenInstanceError):
        item.confidence = 1.0
    with pytest.raises(ValueError, match="confidence must be finite"):
        evidence(confidence=float("nan"))
    with pytest.raises(ValueError, match="score must be finite"):
        evidence(score=float("inf"))
    with pytest.raises(ValueError, match="priority must be a positive integer"):
        evidence(priority=0)
    with pytest.raises(ValueError, match="risk_level"):
        evidence(risk_level="severe")


def test_conflict_trace_and_recommendation_validation():
    conflict = EvidenceConflict("A", "B", "Different recommendations.", 50.0, "Use stronger evidence.")
    trace = ExecutiveReasoningTrace(
        evidence_used=[evidence()],
        conflicts_found=[conflict],
        reasoning_steps=["Collected evidence."],
        selected_strategy="Use optimized plan",
        confidence=80.0,
        rejected_alternatives=[{"recommendation": "Other", "why_rejected": "Lower score"}],
        tradeoffs=[{"category": "risk", "benefit": 70.0, "cost": 10.0}],
        risk_summary={"risk_score": 10.0, "risk_level": "low"},
    )
    recommendation = ExecutiveRecommendation(
        recommended_action="Use optimized plan",
        confidence=80.0,
        executive_priority=1,
        why="Best evidence.",
        expected_benefits=["Goal progress"],
        known_risks=["No major risks"],
        alternatives=[{"recommendation": "Other"}],
        reasoning_trace=trace,
    )

    assert recommendation.reasoning_trace.conflicts_found[0].severity == 50.0
    with pytest.raises(ValueError, match="confidence must be between"):
        ExecutiveRecommendation(
            recommended_action="Bad",
            confidence=101.0,
            executive_priority=1,
            why="Bad confidence.",
            expected_benefits=["Benefit"],
            known_risks=["Risk"],
            alternatives=[],
            reasoning_trace=trace,
        )


def test_normalize_evidence_rejects_malformed_inputs():
    engine = ExecutiveReasoningEngine()

    normalized = engine.normalize_evidence(
        {
            "source": "FutureSimulationEngine",
            "title": "Baseline",
            "confidence_score": 77.0,
            "overall_score": 81.0,
            "risk_score": 12.0,
            "reasoning": "Simulation supports baseline.",
        }
    )

    assert normalized.source == "FutureSimulationEngine"
    assert normalized.score == 81.0
    with pytest.raises(ValueError, match="evidence payload"):
        engine.normalize_evidence(["bad"])
    with pytest.raises(ValueError, match="confidence must be finite"):
        engine.normalize_evidence({"source": "X", "recommendation": "Y", "confidence": float("inf")})


def test_collect_evidence_from_executive_outputs():
    engine = ExecutiveReasoningEngine()
    evidence_items = engine.collect_evidence(**sample_reasoning_inputs())
    sources = {item.source for item in evidence_items}

    assert "DecisionEngine" in sources
    assert "GoalIntelligenceEngine" in sources
    assert "DependencyIntelligenceEngine" in sources
    assert "FutureSimulationEngine" in sources
    assert "MultiObjectiveOptimizationEngine" in sources
    assert "ExecutiveBrain" in sources


def test_conflict_detection_and_dependency_override():
    engine = ExecutiveReasoningEngine()
    items = [
        evidence("GoalIntelligenceEngine", "Advance Goal A", confidence=85.0, score=80.0),
        evidence(
            "DependencyIntelligenceEngine",
            "Resolve dependency blockers",
            confidence=88.0,
            risk_level="high",
            priority=1,
            score=40.0,
            metadata={"blocked": True},
        ),
    ]

    conflicts = engine.detect_conflicts(items)
    recommendation = engine.reason(extra_evidence=items)

    assert any("Dependency evidence reports blockers" in conflict.conflict_reason for conflict in conflicts)
    assert recommendation.recommended_action == "Resolve dependency blockers"
    assert any("Dependency blockers" in risk for risk in recommendation.known_risks)


def test_confidence_propagation_rewards_agreement_and_penalizes_conflicts():
    engine = ExecutiveReasoningEngine()
    agreeing = [
        evidence("DecisionIntelligenceEngine", "Use optimized plan", confidence=90.0, score=90.0),
        evidence("MultiObjectiveOptimizationEngine", "Use optimized plan", confidence=88.0, score=88.0),
        evidence("FutureSimulationEngine", "Use optimized plan", confidence=84.0, score=86.0, metadata={"simulation_supported": True}),
    ]
    conflicting = agreeing + [
        evidence("AdaptiveLifeOperatingSystem", "Reduce workload pressure", confidence=85.0, risk_level="high", score=35.0, metadata={"aggressive_planning_warning": True})
    ]

    high_confidence = engine.reason(extra_evidence=agreeing).confidence
    lower_confidence = engine.reason(extra_evidence=conflicting).confidence

    assert high_confidence > lower_confidence
    assert lower_confidence >= 0.0


def test_tradeoff_analysis_and_alternative_ranking():
    engine = ExecutiveReasoningEngine()
    selected = evidence("DecisionIntelligenceEngine", "Use optimized plan", score=92.0)
    alternatives = [
        evidence("GoalIntelligenceEngine", "Advance Goal A", score=78.0),
        evidence("AdaptiveLifeOperatingSystem", "Reduce workload pressure", risk_level="high", score=55.0),
    ]
    conflicts = engine.detect_conflicts([selected] + alternatives)

    tradeoffs = engine.analyze_tradeoffs(selected, [selected] + alternatives, conflicts)
    rejected = engine.evaluate_alternatives(selected, alternatives)

    assert {item["category"] for item in tradeoffs} == {
        "dependency_impact",
        "goal_progress",
        "productivity",
        "strategic_benefit",
    }
    assert rejected[0]["score"] >= rejected[-1]["score"]
    assert "why_rejected" in rejected[0]


def test_reasoning_trace_is_explainable_and_deterministic():
    engine = ExecutiveReasoningEngine()
    first = engine.reason(**sample_reasoning_inputs())
    second = engine.reason(**sample_reasoning_inputs())

    assert engine.to_dict(first) == engine.to_dict(second)
    assert first.reasoning_trace.reasoning_steps[0].startswith("Collected")
    assert first.confidence > 0.0
    assert first.reasoning_trace.selected_strategy == first.recommended_action


def test_missing_sources_produce_safe_recommendation():
    recommendation = ExecutiveReasoningEngine().reason()

    assert recommendation.recommended_action == "Request more evidence before committing to a plan"
    assert recommendation.confidence < 50.0
    assert recommendation.reasoning_trace.evidence_used[0].metadata["missing_evidence"] is True


def test_large_evidence_sets_are_deterministic():
    engine = ExecutiveReasoningEngine()
    items = [
        evidence(
            source=f"Source{i % 5}",
            recommendation=f"Action {i % 7}",
            confidence=50.0 + (i % 40),
            score=45.0 + (i % 50),
            priority=(i % 9) + 1,
        )
        for i in range(75)
    ]

    first = engine.reason(extra_evidence=items)
    second = engine.reason(extra_evidence=list(reversed(items)))

    assert first.recommended_action == second.recommended_action
    assert first.confidence == second.confidence


def test_executive_brain_includes_reasoning_outputs():
    result = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])

    assert "executive_reasoning" in result
    assert "executive_confidence" in result
    assert "executive_tradeoffs" in result
    assert "executive_conflicts" in result
    assert "executive_trace" in result
    assert result["executive_reasoning"]["recommended_action"]
    assert 0.0 <= result["executive_confidence"]["confidence"] <= 100.0


def test_executive_brain_rejects_non_finite_reasoning_inputs():
    class BadReasoningEngine:
        def reason(self, **kwargs):
            return ExecutiveRecommendation(
                recommended_action="Bad",
                confidence=float("nan"),
                executive_priority=1,
                why="Bad.",
                expected_benefits=["Benefit"],
                known_risks=["Risk"],
                alternatives=[],
                reasoning_trace={
                    "evidence_used": [evidence()],
                    "conflicts_found": [],
                    "reasoning_steps": ["Bad."],
                    "selected_strategy": "Bad",
                    "confidence": 1.0,
                    "rejected_alternatives": [],
                    "tradeoffs": [],
                    "risk_summary": {"risk_score": 1.0, "risk_level": "low"},
                },
            )

    with pytest.raises(ValueError, match="confidence must be finite"):
        ExecutiveCognitiveBrain(executive_reasoning_engine=BadReasoningEngine()).execute_planning_request(
            [],
            behavior_patterns={},
            goals=[],
        )


def test_executive_brain_preserves_original_sections_with_additive_reasoning():
    result = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])
    required_d1_keys = {
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
    }

    assert required_d1_keys <= set(result)
    assert result["recommended_plan"]["executive_confidence"] == result["executive_confidence"]["confidence"]
