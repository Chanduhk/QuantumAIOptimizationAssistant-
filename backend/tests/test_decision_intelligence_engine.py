from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime

import pytest

from backend.app.domain.decision_intelligence_model import (
    DecisionAnalysis,
    DecisionEvaluation,
    DecisionOption,
    DecisionRecommendation,
    DecisionTradeoff,
)
from backend.app.engines.decision_intelligence_engine import DecisionIntelligenceEngine
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def _options() -> list[dict]:
    return [
        {
            "option_id": "a",
            "title": "Accelerate goal",
            "expected_benefit": 90,
            "estimated_cost": 20,
            "estimated_effort": 30,
            "goal_ids": ["g1"],
        },
        {
            "option_id": "b",
            "title": "Maintain pace",
            "expected_benefit": 65,
            "estimated_cost": 10,
            "estimated_effort": 15,
            "goal_ids": ["g1"],
        },
        {
            "option_id": "c",
            "title": "Accept risky work",
            "expected_benefit": 80,
            "estimated_cost": 70,
            "estimated_effort": 80,
            "metadata": {"risk_score": 90},
        },
    ]


def _context() -> dict:
    return {
        "goals": [{"goal_id": "g1", "priority": 8, "progress": 50}],
        "dependencies": {"blocked_tasks": []},
        "behavior_patterns": {"average_productivity": 80},
        "context": {"context_summary": {"risk_state": "low", "momentum_state": "positive"}},
        "simulations": [{"scenario_id": "s1", "success_probability": 0.8, "risk_score": 20}],
        "optimization_results": {"selected_future": {"overall_score": 85}},
        "risks": [{"severity": "low"}],
        "momentum": {"momentum_state": "positive"},
        "learning_insights": [{"insight_id": "i1", "confidence": 0.8}],
    }


def test_decision_intelligence_domain_validation() -> None:
    option = DecisionOption("o1", "Option", expected_benefit=120, estimated_cost=-5, goal_ids=["g2", "g1", "g1"])
    evaluation = DecisionEvaluation("o1", 120, -1, 50, 40, 30, ["b", "a", "a"])
    tradeoff = DecisionTradeoff("t1", "o1", 120, 10, 20, 30, 40, 2)
    recommendation = DecisionRecommendation("r1", "Best_Option", "o1", "Option", "Reason", 2, 1)
    analysis = DecisionAnalysis(
        "a1",
        [asdict(option)],
        [asdict(evaluation)],
        [asdict(tradeoff)],
        [asdict(recommendation)],
        ["b", "a", "a"],
        "Summary",
        2,
    )

    assert option.expected_benefit == 100.0
    assert option.estimated_cost == 0.0
    assert option.goal_ids == ["g1", "g2"]
    assert evaluation.utility_score == 100.0
    assert tradeoff.confidence == 1.0
    assert recommendation.recommendation_type == "best_option"
    assert analysis.ranking == ["b", "a"]
    assert analysis.confidence == 1.0

    with pytest.raises(ValueError, match="option_id"):
        DecisionOption("", "Option")

    with pytest.raises(ValueError, match="overall_score"):
        DecisionEvaluation("o1", 1, 1, 1, 1, math.inf)

    with pytest.raises(ValueError, match="priority"):
        DecisionRecommendation("r2", "best", "o1", "Option", "Reason", 1, 0)


def test_option_evaluation_uses_goal_simulation_behavior_context_and_optimization() -> None:
    engine = DecisionIntelligenceEngine()
    ctx = _context()

    evaluation = engine.evaluate_option(_options()[0], **ctx)

    assert evaluation.option_id == "a"
    assert evaluation.utility_score > 60
    assert evaluation.risk_score < 40
    assert evaluation.confidence_score > 40
    assert evaluation.alignment_score > 70
    assert evaluation.overall_score > 60
    assert any("simulation_count=1" in item for item in evaluation.evidence)


def test_tradeoff_analysis_measures_required_dimensions() -> None:
    tradeoff = DecisionIntelligenceEngine().analyze_tradeoff(_options()[0], **_context())

    assert tradeoff.benefit > 0
    assert tradeoff.cost == 20
    assert tradeoff.risk >= 0
    assert tradeoff.effort == 30
    assert tradeoff.alignment > 0
    assert 0 <= tradeoff.confidence <= 1


def test_decision_scoring_recommendations_and_ranking() -> None:
    engine = DecisionIntelligenceEngine()

    analysis = engine.analyze_decisions(_options(), created_at=datetime(2026, 1, 1), **_context())

    assert analysis.analysis_id == "decision-analysis-20260101-1"
    assert analysis.ranking[0] == "a"
    assert len(analysis.recommendations) == 3
    assert analysis.recommendations[0].recommendation_type == "best_option"
    assert analysis.recommendations[-1].recommendation_type == "avoid_option"
    assert "Recommend Accelerate goal" in analysis.executive_summary


def test_scenario_comparison_returns_ranked_options() -> None:
    ranking = DecisionIntelligenceEngine().compare_scenarios(
        _options(),
        created_at=datetime(2026, 1, 1),
        **_context(),
    )

    assert [item["rank"] for item in ranking] == [1, 2, 3]
    assert ranking[0]["option_id"] == "a"
    assert ranking[-1]["risk_score"] >= ranking[0]["risk_score"]


def test_regret_analysis_estimates_regret_opportunity_cost_and_missed_value() -> None:
    engine = DecisionIntelligenceEngine()
    evaluation = DecisionEvaluation("c", 30, 90, 50, 20, 35)

    regret = engine.estimate_regret(_options()[2], evaluation, best_overall_score=80)

    assert regret["missed_value"] == 45.0
    assert regret["opportunity_cost"] > 0
    assert regret["potential_regret"] > regret["missed_value"] * 0.2


def test_explainability_and_executive_summary() -> None:
    engine = DecisionIntelligenceEngine()

    empty = engine.explain_decision()
    analysis = engine.analyze_decisions(_options(), created_at=datetime(2026, 1, 1), **_context())
    explanation = engine.explain_decision(analysis)

    assert empty["summary"] == "No decision analysis available."
    assert explanation["why_chosen"]
    assert explanation["why_rejected"]
    assert explanation["tradeoffs"]
    assert explanation["risks"]
    assert "confidence" in explanation["expected_outcome"]


def test_empty_and_malformed_decisions_are_rejected() -> None:
    engine = DecisionIntelligenceEngine()

    with pytest.raises(ValueError, match="At least one"):
        engine.analyze_decisions([])

    with pytest.raises(ValueError, match="options"):
        engine.analyze_decisions({})

    with pytest.raises(ValueError, match="option"):
        engine.evaluate_option([])

    with pytest.raises(ValueError, match="goals"):
        engine.evaluate_option(_options()[0], goals={})

    with pytest.raises(ValueError, match="unique"):
        engine.analyze_decisions([_options()[0], _options()[0]])


def test_large_option_sets_and_determinism() -> None:
    def build() -> dict:
        options = [
            {
                "option_id": f"option-{index}",
                "title": f"Option {index}",
                "expected_benefit": 50 + index,
                "estimated_cost": index % 10,
                "estimated_effort": index % 12,
                "goal_ids": ["g1"] if index % 2 == 0 else [],
            }
            for index in range(30)
        ]
        engine = DecisionIntelligenceEngine()
        analysis = engine.analyze_decisions(options, created_at=datetime(2026, 1, 1), **_context())
        return {
            "analysis": asdict(analysis),
            "summary": engine.summarize_decision_intelligence(),
            "ranking": engine.compare_scenarios(options, created_at=datetime(2026, 1, 2), **_context()),
        }

    first = build()
    second = build()

    assert first == second
    assert len(first["analysis"]["options"]) == 30


def test_summary_is_optional_and_valid_after_analysis() -> None:
    engine = DecisionIntelligenceEngine()

    assert engine.summarize_decision_intelligence() is None

    engine.analyze_decisions(_options(), created_at=datetime(2026, 1, 1), **_context())
    summary = engine.summarize_decision_intelligence()

    assert set(summary) == {"decision_analysis", "decision_recommendation", "decision_tradeoffs", "decision_summary"}
    assert summary["decision_analysis"]["ranking"][0] == "a"


def test_orchestrator_decision_intelligence_outputs_are_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.decision_intelligence_engine = DecisionIntelligenceEngine()

    assert orchestrator._decision_intelligence_outputs() is None

    orchestrator.decision_intelligence_engine.analyze_decisions(
        _options(),
        created_at=datetime(2026, 1, 1),
        **_context(),
    )
    outputs = orchestrator._decision_intelligence_outputs()

    assert outputs is not None
    assert "decision_analysis" in outputs


def test_orchestrator_rejects_malformed_decision_intelligence_outputs() -> None:
    class BadDecisionIntelligenceEngine:
        def summarize_decision_intelligence(self):
            return {
                "decision_analysis": {"bad": math.inf},
                "decision_recommendation": [],
                "decision_tradeoffs": [],
                "decision_summary": "bad",
            }

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.decision_intelligence_engine = BadDecisionIntelligenceEngine()

    with pytest.raises(ValueError, match="finite"):
        orchestrator._decision_intelligence_outputs()
