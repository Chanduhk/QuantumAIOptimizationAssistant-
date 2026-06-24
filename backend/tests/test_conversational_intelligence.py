from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime

import pytest

from backend.app.domain.conversation_model import (
    ClarificationQuestion,
    ConversationContext,
    ConversationTurn,
    ExplanationResult,
)
from backend.app.engines.conversational_intelligence_engine import ConversationalIntelligenceEngine
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_conversation_domain_model_validation() -> None:
    turn = ConversationTurn("t1", "USER", "Explain my schedule", datetime(2026, 1, 1), "schedule_question", {})
    context = ConversationContext("c1", ["g2", "g1", "g1"], ["risk"], ["risk_question"], ["research"], "Summary")
    explanation = ExplanationResult("decision", "Title", "Summary", ["factor"], ["rec"], 2)
    question = ClarificationQuestion("Which goal?", "Goal ambiguity exists.", 1)

    assert turn.role == "user"
    assert context.active_goal_ids == ["g1", "g2"]
    assert explanation.confidence == 1.0
    assert question.priority == 1

    with pytest.raises(ValueError, match="role"):
        ConversationTurn("t2", "bad", "Message")

    with pytest.raises(ValueError, match="message"):
        ConversationTurn("t3", "user", "")

    with pytest.raises(ValueError, match="confidence"):
        ExplanationResult("x", "T", "S", [], [], math.inf)

    with pytest.raises(ValueError, match="priority"):
        ClarificationQuestion("Q", "R", 0)


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("Why is this on my schedule?", "schedule_question"),
        ("Why this task decision?", "decision_question"),
        ("How is my goal doing?", "goal_question"),
        ("What is the burnout risk?", "risk_question"),
        ("Any quick win opportunity?", "opportunity_question"),
        ("Explain optimization tradeoff", "optimization_question"),
        ("Simulate the future scenario", "simulation_question"),
        ("Show strategic roadmap", "strategy_question"),
        ("How is my productivity?", "productivity_question"),
        ("Can you clarify which should matter?", "clarification_needed"),
        ("Hello there", "general_question"),
    ],
)
def test_intent_detection(message: str, intent: str) -> None:
    assert ConversationalIntelligenceEngine().detect_intent(message) == intent


def test_decision_explanation() -> None:
    engine = ConversationalIntelligenceEngine()

    result = engine.explain_decision(
        {"id": "t1", "title": "Write proposal"},
        {
            "priority_score": 70,
            "productivity_score": 20,
            "goal_alignment_score": 15,
            "strategic_score": 10,
            "deadline_score": 5,
            "dependency_score": 3,
            "energy_alignment_score": 4,
            "duration_penalty": -2,
            "context_switch_penalty": -1,
        },
    )

    assert result.explanation_type == "decision"
    assert "Write proposal" in result.title
    assert any("Priority" in factor for factor in result.key_factors)
    assert engine.summarize_conversational_intelligence()["decision_explanation"]["title"] == result.title


def test_schedule_explanation() -> None:
    result = ConversationalIntelligenceEngine().explain_schedule(
        {
            "id": "t1",
            "scheduled_hour": 9,
            "best_focus_hours": [9],
            "predicted_productivity": 85,
            "estimated_duration": 2,
        }
    )

    assert result.explanation_type == "schedule"
    assert any("focus" in factor.lower() for factor in result.key_factors)


def test_simulation_explanation() -> None:
    result = ConversationalIntelligenceEngine().explain_simulation(
        {
            "scenario_id": "simulation-baseline",
            "success_probability": 0.72,
            "risk_score": 30,
            "projected_state": {
                "scenario_type": "baseline",
                "projected_completion_days": 12,
                "projected_goal_state": "on_track",
                "blocked_task_count": 0,
            },
            "recommendations": ["Maintain current strategy"],
        }
    )

    assert result.explanation_type == "simulation"
    assert "72%" in result.summary
    assert result.recommendations == ["Maintain current strategy"]


def test_optimization_explanation() -> None:
    result = ConversationalIntelligenceEngine().explain_optimization(
        {
            "selected_future": {"scenario_id": "s1", "scenario_name": "Accelerated", "overall_score": 82},
            "ranking": [{"scenario_id": "s1"}, {"scenario_id": "s2"}],
            "tradeoffs": ["Higher productivity vs higher risk"],
            "recommendations": ["Review tradeoffs"],
        }
    )

    assert result.explanation_type == "optimization"
    assert any("Higher productivity" in factor for factor in result.key_factors)


def test_goal_explanation() -> None:
    result = ConversationalIntelligenceEngine().explain_goal(
        {
            "goal_id": "g1",
            "progress": 65,
            "health_status": "at_risk",
            "risk_score": 35,
            "neglected": True,
            "dependency_risk_score": 20,
        }
    )

    assert result.explanation_type == "goal"
    assert any("Neglected: True" in factor for factor in result.key_factors)


def test_risk_explanation() -> None:
    result = ConversationalIntelligenceEngine().explain_risk(
        {
            "burnout_level": "high",
            "load_status": "overload",
            "strategic_alignment_score": 42,
            "risk_score": 70,
            "blocked_task_count": 2,
        }
    )

    assert result.explanation_type == "risk"
    assert "burnout" in result.summary.lower()
    assert any("overload" in factor for factor in result.key_factors)


def test_opportunity_explanation() -> None:
    result = ConversationalIntelligenceEngine().explain_opportunity(
        {
            "category": "quick_win",
            "impact_score": 80,
            "confidence": 0.9,
            "recommended_action": "Batch quick wins",
            "expected_benefit": "Increase completion velocity",
        }
    )

    assert result.explanation_type == "opportunity"
    assert result.confidence == 0.9
    assert result.recommendations == ["Batch quick wins"]


def test_clarification_generation() -> None:
    questions = ConversationalIntelligenceEngine().generate_clarification_questions(
        {"intent": "schedule_question", "optimization_objectives": ["productivity", "stress"]}
    )

    assert [question.priority for question in questions] == sorted(question.priority for question in questions)
    assert any("Which goal" in question.question for question in questions)
    assert any("realistically available" in question.question for question in questions)


def test_recommendation_narratives() -> None:
    engine = ConversationalIntelligenceEngine()

    strong = engine.generate_recommendation_narrative(
        {"action": "Do the research task", "goal_alignment_score": 92, "risk": "low"}
    )
    risky = engine.generate_recommendation_narrative(
        {"action": "Accept extra work", "goal_alignment_score": 40, "risk": "critical"}
    )

    assert "strongly supports" in strong
    assert "critical risk" in risky


def test_conversation_context_tracking_and_memory_awareness() -> None:
    engine = ConversationalIntelligenceEngine(max_history_size=2)

    engine.add_turn(
        conversation_id="c1",
        role="user",
        message="Explain my research goal",
        metadata={"goal_id": "g1", "memory_reference": "AI research goals"},
        timestamp=datetime(2026, 1, 1),
    )
    engine.add_turn(conversation_id="c1", role="assistant", message="Here is the explanation.")
    engine.add_turn(conversation_id="c1", role="user", message="What is the risk?")
    context = engine.get_context("c1")

    assert len(engine.turn_history) == 2
    assert "g1" in context.active_goal_ids
    assert "AI research goals" in context.memory_references
    assert "Memory references" in context.conversation_summary
    assert engine.summarize_conversational_intelligence()["conversation_summary"] == context.conversation_summary


def test_malformed_inputs_are_rejected() -> None:
    engine = ConversationalIntelligenceEngine()

    with pytest.raises(ValueError, match="max_history_size"):
        ConversationalIntelligenceEngine(max_history_size=0)

    with pytest.raises(ValueError, match="message"):
        engine.detect_intent("")

    with pytest.raises(ValueError, match="metadata"):
        engine.add_turn(conversation_id="c1", role="user", message="Hello", metadata="bad")

    with pytest.raises(ValueError, match="intent"):
        engine.add_turn(conversation_id="c1", role="user", message="Hello", intent="bad")

    with pytest.raises(ValueError, match="task"):
        engine.explain_decision([], {})

    with pytest.raises(ValueError, match="context"):
        engine.generate_clarification_questions([])


def test_determinism_and_empty_context() -> None:
    first = ConversationalIntelligenceEngine()
    second = ConversationalIntelligenceEngine()

    assert asdict(first.get_context("c1")) == asdict(second.get_context("c1"))
    assert first.detect_intent("Explain optimization tradeoff") == second.detect_intent("Explain optimization tradeoff")
    assert first.summarize_conversational_intelligence() is None


def test_orchestrator_conversational_outputs_are_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.conversational_intelligence_engine = ConversationalIntelligenceEngine()

    assert orchestrator._conversational_intelligence_outputs() is None

    orchestrator.conversational_intelligence_engine.add_turn(
        conversation_id="c1",
        role="user",
        message="Explain optimization tradeoff",
    )
    outputs = orchestrator._conversational_intelligence_outputs()

    assert outputs is not None
    assert "conversation_summary" in outputs


def test_orchestrator_rejects_malformed_conversational_outputs() -> None:
    class BadConversationEngine:
        def summarize_conversational_intelligence(self):
            return {"unsupported": {"confidence": math.inf}}

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.conversational_intelligence_engine = BadConversationEngine()

    with pytest.raises(ValueError, match="unsupported"):
        orchestrator._conversational_intelligence_outputs()
