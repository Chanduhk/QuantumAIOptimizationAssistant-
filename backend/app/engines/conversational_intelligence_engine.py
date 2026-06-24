from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.conversation_model import (
    ClarificationQuestion,
    ConversationContext,
    ConversationTurn,
    ExplanationResult,
)


class ConversationalIntelligenceEngine:
    """Deterministic conversation and explanation layer for structured intelligence outputs."""

    INTENTS = {
        "schedule_question",
        "decision_question",
        "goal_question",
        "risk_question",
        "opportunity_question",
        "optimization_question",
        "simulation_question",
        "strategy_question",
        "productivity_question",
        "clarification_needed",
        "general_question",
    }

    def __init__(self, max_history_size: int = 50) -> None:
        if not isinstance(max_history_size, int) or isinstance(max_history_size, bool) or max_history_size <= 0:
            raise ValueError("max_history_size must be a positive integer.")
        self.max_history_size = max_history_size
        self.turn_history: List[ConversationTurn] = []
        self.contexts: Dict[str, ConversationContext] = {}
        self.latest_outputs: Dict[str, Any] = {}

    def detect_intent(self, message: str) -> str:
        """Classify user intent with deterministic keyword rules."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string.")
        text = message.lower()
        if any(word in text for word in ("schedule", "calendar", "hour", "time slot")):
            return "schedule_question"
        if any(word in text for word in ("why this task", "decision", "rank", "prioritize", "priority")):
            return "decision_question"
        if any(word in text for word in ("goal", "milestone", "objective")):
            return "goal_question"
        if any(word in text for word in ("risk", "burnout", "overload", "blocked", "drift")):
            return "risk_question"
        if any(word in text for word in ("opportunity", "quick win", "leverage", "momentum")):
            return "opportunity_question"
        if any(word in text for word in ("optimize", "optimization", "selected future", "tradeoff")):
            return "optimization_question"
        if any(word in text for word in ("simulate", "simulation", "scenario", "future")):
            return "simulation_question"
        if any(word in text for word in ("strategy", "strategic", "roadmap", "plan")):
            return "strategy_question"
        if any(word in text for word in ("productivity", "focus", "energy")):
            return "productivity_question"
        if any(word in text for word in ("clarify", "not sure", "choose", "which should")):
            return "clarification_needed"
        return "general_question"

    def add_turn(
        self,
        *,
        conversation_id: str,
        role: str,
        message: str,
        intent: str | None = None,
        metadata: Dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ConversationTurn:
        """Add a turn and update bounded conversation context."""
        metadata = metadata or {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary.")
        detected_intent = intent or self.detect_intent(message)
        if detected_intent not in self.INTENTS:
            raise ValueError("intent is not supported.")
        turn = ConversationTurn(
            turn_id=f"turn-{len(self.turn_history) + 1}",
            role=role,
            message=message,
            timestamp=timestamp or datetime.utcnow(),
            intent=detected_intent,
            metadata=dict(metadata),
        )
        self.turn_history.append(turn)
        if len(self.turn_history) > self.max_history_size:
            overflow = len(self.turn_history) - self.max_history_size
            self.turn_history = self.turn_history[overflow:]
        context = self.contexts.get(conversation_id) or ConversationContext(conversation_id=conversation_id)
        active_goal_ids = context.active_goal_ids + self._metadata_strings(metadata, "goal_id", "goal_ids")
        active_topics = context.active_topics + [detected_intent.replace("_question", "")]
        memory_references = context.memory_references + self._metadata_strings(metadata, "memory_reference", "memory_references")
        recent_intents = (context.recent_intents + [detected_intent])[-5:]
        self.contexts[conversation_id] = ConversationContext(
            conversation_id=conversation_id,
            active_goal_ids=active_goal_ids[-5:],
            active_topics=active_topics[-5:],
            recent_intents=recent_intents,
            memory_references=memory_references[-5:],
            conversation_summary=self._conversation_summary(recent_intents, active_topics, memory_references),
        )
        self.latest_outputs["conversation_summary"] = self.contexts[conversation_id].conversation_summary
        return turn

    def get_context(self, conversation_id: str) -> ConversationContext:
        """Return a context object for a conversation, creating an empty one if needed."""
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError("conversation_id must be a non-empty string.")
        conversation_id = conversation_id.strip()
        context = self.contexts.get(conversation_id)
        if context is None:
            context = ConversationContext(conversation_id=conversation_id)
            self.contexts[conversation_id] = context
        return context

    def explain_decision(self, task: Dict[str, Any], decision_breakdown: Dict[str, Any]) -> ExplanationResult:
        """Explain why a task was ranked or selected."""
        task = self._dict(task, "task")
        breakdown = self._dict(decision_breakdown, "decision_breakdown")
        title = str(task.get("title", task.get("id", "Task")))
        factors = self._positive_factors(
            breakdown,
            {
                "priority_score": "Priority increased the ranking.",
                "productivity_score": "Predicted productivity supported this choice.",
                "goal_alignment_score": "The task aligns with active goals.",
                "strategic_score": "Strategic importance increased the score.",
                "deadline_score": "Deadline urgency increased priority.",
                "dependency_score": "Dependency position improved execution value.",
                "energy_alignment_score": "Energy alignment supports execution.",
                "duration_penalty": "Duration reduced the score.",
                "context_switch_penalty": "Context switching reduced the score.",
            },
        )
        result = ExplanationResult(
            explanation_type="decision",
            title=f"Why {title} was recommended",
            summary=f"{title} was evaluated using priority, productivity, goal alignment, timing, dependencies, and execution cost.",
            key_factors=factors,
            recommendations=["Use this explanation to decide whether the ranking matches your intent."],
            confidence=0.86,
        )
        return self._store_explanation("decision_explanation", result)

    def explain_schedule(self, scheduled_task: Dict[str, Any]) -> ExplanationResult:
        """Explain why a task was scheduled at its assigned time."""
        task = self._dict(scheduled_task, "scheduled_task")
        hour = task.get("scheduled_hour", task.get("optimized_hour", task.get("hour_of_day", "unknown")))
        factors = [
            f"Scheduled hour: {hour}.",
            f"Predicted productivity: {self._safe_float(task.get('predicted_productivity'), 0.0):.2f}.",
            f"Capacity impact: {self._safe_float(task.get('estimated_duration', task.get('duration')), 1.0):.2f} hours.",
        ]
        if task.get("focus_hour_aligned") is True or task.get("scheduled_hour") in task.get("best_focus_hours", []):
            factors.append("The selected hour aligns with a focus window.")
        result = ExplanationResult(
            explanation_type="schedule",
            title="Schedule Explanation",
            summary="The task was placed based on timing, productivity expectations, focus alignment, and capacity.",
            key_factors=factors,
            recommendations=["Keep this slot if the timing still matches your energy and constraints."],
            confidence=0.82,
        )
        return self._store_explanation("schedule_explanation", result)

    def explain_simulation(self, simulation_result: Dict[str, Any]) -> ExplanationResult:
        """Explain a simulated future outcome."""
        result_dict = self._dict(simulation_result, "simulation_result")
        state = self._dict(result_dict.get("projected_state", {}), "projected_state")
        scenario = state.get("scenario_type", result_dict.get("scenario_id", "scenario"))
        risk = self._safe_float(result_dict.get("risk_score"), 0.0)
        success = self._safe_float(result_dict.get("success_probability"), 0.0)
        result = ExplanationResult(
            explanation_type="simulation",
            title=f"Simulation: {str(scenario).replace('_', ' ').title()}",
            summary=f"This scenario projects a {success:.0%} success probability with risk score {risk:.2f}.",
            key_factors=[
                f"Projected completion days: {state.get('projected_completion_days', 'unknown')}.",
                f"Projected goal state: {state.get('projected_goal_state', 'unknown')}.",
                f"Blocked task count: {state.get('blocked_task_count', 0)}.",
            ],
            recommendations=[str(item) for item in result_dict.get("recommendations", [])] or ["Review scenario assumptions before acting."],
            confidence=0.8,
        )
        return self._store_explanation("simulation_explanation", result)

    def explain_optimization(self, optimization_result: Dict[str, Any]) -> ExplanationResult:
        """Explain why an optimized future was selected."""
        result_dict = self._dict(optimization_result, "optimization_result")
        selected = self._dict(result_dict.get("selected_future", result_dict), "selected_future")
        ranking = result_dict.get("ranking", result_dict.get("optimization_summary", {}).get("ranking", []))
        tradeoffs = result_dict.get("tradeoffs", [])
        factors = [
            f"Selected future: {selected.get('scenario_name', selected.get('scenario_id', 'unknown'))}.",
            f"Overall score: {self._safe_float(selected.get('overall_score'), self._safe_float(result_dict.get('overall_score'), 0.0)):.2f}.",
            f"Ranked alternatives considered: {len(ranking) if isinstance(ranking, list) else 0}.",
        ]
        if isinstance(tradeoffs, list):
            factors.extend(str(item) for item in tradeoffs[:3])
        result = ExplanationResult(
            explanation_type="optimization",
            title="Optimization Outcome",
            summary="The selected future won by balancing objective scores, tradeoffs, risk, and alignment.",
            key_factors=factors,
            recommendations=[str(item) for item in result_dict.get("recommendations", [])] or ["Review major tradeoffs before committing."],
            confidence=0.84,
        )
        return self._store_explanation("optimization_explanation", result)

    def explain_goal(self, goal_health: Dict[str, Any]) -> ExplanationResult:
        """Explain goal health, momentum, neglect, dependencies, and forecast risk."""
        goal = self._dict(goal_health, "goal_health")
        goal_id = goal.get("goal_id", "goal")
        factors = [
            f"Progress: {self._safe_float(goal.get('progress'), 0.0):.2f}%.",
            f"Health status: {goal.get('health_status', 'unknown')}.",
            f"Risk score: {self._safe_float(goal.get('risk_score'), 0.0):.2f}.",
            f"Neglected: {bool(goal.get('neglected', False))}.",
            f"Dependency risk: {self._safe_float(goal.get('dependency_risk_score'), 0.0):.2f}.",
        ]
        result = ExplanationResult(
            explanation_type="goal",
            title=f"Goal Explanation: {goal_id}",
            summary="Goal health combines progress, momentum, neglect risk, dependency risk, and completion forecast.",
            key_factors=factors,
            recommendations=["Prioritize one concrete next action if health is at risk."],
            confidence=0.83,
        )
        return self._store_explanation("goal_explanation", result)

    def explain_risk(self, risk_context: Dict[str, Any]) -> ExplanationResult:
        """Explain burnout, overload, drift, forecast, and dependency risks."""
        risk = self._dict(risk_context, "risk_context")
        factors = [
            f"Burnout level: {risk.get('burnout_level', risk.get('burnout_assessment', {}).get('burnout_level', 'unknown'))}.",
            f"Load status: {risk.get('load_status', risk.get('capacity', {}).get('load_status', 'unknown'))}.",
            f"Strategic alignment: {self._safe_float(risk.get('strategic_alignment_score', risk.get('strategic_alignment', {}).get('strategic_alignment_score')), 100.0):.2f}.",
            f"Forecast risk: {self._safe_float(risk.get('risk_score'), 0.0):.2f}.",
            f"Blocked dependencies: {risk.get('blocked_task_count', 0)}.",
        ]
        result = ExplanationResult(
            explanation_type="risk",
            title="Risk Explanation",
            summary="Risk is driven by burnout pressure, overload, strategic drift, forecast uncertainty, and dependency bottlenecks.",
            key_factors=factors,
            recommendations=["Reduce load, unblock dependencies, and restore goal-aligned work before expanding commitments."],
            confidence=0.81,
        )
        return self._store_explanation("risk_explanation", result)

    def explain_opportunity(self, opportunity_context: Dict[str, Any]) -> ExplanationResult:
        """Explain high-momentum goals, quick wins, and leverage opportunities."""
        context = self._dict(opportunity_context, "opportunity_context")
        category = str(context.get("category", "opportunity"))
        result = ExplanationResult(
            explanation_type="opportunity",
            title=f"Opportunity: {category.replace('_', ' ').title()}",
            summary=str(context.get("expected_benefit", "This opportunity can improve progress with favorable effort-to-impact.")),
            key_factors=[
                f"Impact score: {self._safe_float(context.get('impact_score'), 0.0):.2f}.",
                f"Confidence: {self._safe_float(context.get('confidence'), 0.0):.2f}.",
                f"Recommended action: {context.get('recommended_action', 'Review and act if aligned')}.",
            ],
            recommendations=[str(context.get("recommended_action", "Review this opportunity."))],
            confidence=self._bounded(self._safe_float(context.get("confidence"), 0.75), 0.0, 1.0),
        )
        return self._store_explanation("opportunity_explanation", result)

    def generate_clarification_questions(self, context: Dict[str, Any]) -> List[ClarificationQuestion]:
        """Generate deterministic clarification questions when required data is missing or ambiguous."""
        context = self._dict(context, "context")
        questions: List[ClarificationQuestion] = []
        if not context.get("goal_id") and not context.get("goal_ids"):
            questions.append(
                ClarificationQuestion(
                    question="Which goal should this decision optimize for?",
                    reason="Goal ambiguity exists.",
                    priority=1,
                )
            )
        objectives = context.get("optimization_objectives")
        if not objectives or (isinstance(objectives, list) and len(objectives) > 1):
            questions.append(
                ClarificationQuestion(
                    question="Would you prefer to maximize productivity, reduce stress, or accelerate goals before optimization?",
                    reason="Multiple optimization objectives are possible.",
                    priority=1,
                )
            )
        if not context.get("available_hours") and context.get("intent") == "schedule_question":
            questions.append(
                ClarificationQuestion(
                    question="How many hours are realistically available for this schedule?",
                    reason="Schedule capacity is missing.",
                    priority=2,
                )
            )
        return sorted(questions, key=lambda item: (item.priority, item.question))

    def generate_recommendation_narrative(self, recommendation: Dict[str, Any]) -> str:
        """Convert structured recommendation data into natural language."""
        recommendation = self._dict(recommendation, "recommendation")
        goal_alignment = self._safe_float(recommendation.get("goal_alignment_score"), 0.0)
        risk = str(recommendation.get("risk", recommendation.get("risk_level", "unknown"))).lower()
        action = str(recommendation.get("action", recommendation.get("recommended_action", "this action")))
        if goal_alignment >= 80 and risk in {"low", "medium"}:
            return f"{action} strongly supports your primary goals while maintaining a {risk} risk profile."
        if risk in {"high", "critical"}:
            return f"{action} may help, but it carries {risk} risk and should be paired with mitigation."
        return f"{action} is a reasonable next step based on the available context."

    def summarize_conversational_intelligence(self) -> Dict[str, Any] | None:
        """Return latest conversational outputs when any have been generated."""
        if not self.latest_outputs:
            return None
        return dict(self.latest_outputs)

    def _store_explanation(self, key: str, result: ExplanationResult) -> ExplanationResult:
        self.latest_outputs[key] = asdict(result)
        return result

    def _conversation_summary(self, intents: List[str], topics: List[str], memory_references: List[str]) -> str:
        if not intents:
            return ""
        latest_intent = intents[-1].replace("_", " ")
        topic_text = ", ".join(sorted(set(topics[-3:]))) if topics else "general"
        memory_text = f" Memory references: {', '.join(memory_references[-2:])}." if memory_references else ""
        return f"Recent intent: {latest_intent}. Active topics: {topic_text}.{memory_text}"

    def _metadata_strings(self, metadata: Dict[str, Any], singular: str, plural: str) -> List[str]:
        values: List[str] = []
        if singular in metadata and metadata[singular] is not None:
            values.append(str(metadata[singular]))
        raw_plural = metadata.get(plural, [])
        if isinstance(raw_plural, list):
            values.extend(str(item) for item in raw_plural if item is not None)
        elif raw_plural:
            values.append(str(raw_plural))
        return values

    def _positive_factors(self, breakdown: Dict[str, Any], labels: Dict[str, str]) -> List[str]:
        factors = []
        for key in sorted(labels):
            if key in breakdown:
                score = self._safe_float(breakdown[key], 0.0)
                if score != 0.0:
                    factors.append(f"{labels[key]} ({key}: {score:.2f})")
        return factors or ["No dominant score factors were provided."]

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        return dict(value)

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number

    def _bounded(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
