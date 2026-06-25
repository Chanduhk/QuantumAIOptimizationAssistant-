from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.decision_intelligence_model import (
    DecisionAnalysis,
    DecisionEvaluation,
    DecisionOption,
    DecisionRecommendation,
    DecisionTradeoff,
)


class DecisionIntelligenceEngine:
    """Evaluate multiple decision options using existing intelligence signals."""

    def __init__(self) -> None:
        self.decision_history: List[DecisionAnalysis] = []

    def evaluate_option(
        self,
        option: DecisionOption | Dict[str, Any],
        *,
        goals: List[Dict[str, Any]] | None = None,
        dependencies: Dict[str, Any] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        context: Dict[str, Any] | None = None,
        simulations: List[Dict[str, Any]] | None = None,
        optimization_results: Dict[str, Any] | None = None,
        risks: List[Dict[str, Any]] | None = None,
        momentum: Dict[str, Any] | None = None,
        learning_insights: List[Dict[str, Any]] | None = None,
    ) -> DecisionEvaluation:
        """Evaluate one decision option across utility, risk, confidence, and alignment."""
        option_obj = self._option(option)
        goals = self._dict_list([] if goals is None else goals, "goals")
        dependencies = self._dict({} if dependencies is None else dependencies, "dependencies")
        behavior_patterns = self._dict({} if behavior_patterns is None else behavior_patterns, "behavior_patterns")
        context = self._dict({} if context is None else context, "context")
        simulations = self._dict_list([] if simulations is None else simulations, "simulations")
        optimization_results = self._dict({} if optimization_results is None else optimization_results, "optimization_results")
        risks = self._dict_list([] if risks is None else risks, "risks")
        learning_insights = self._dict_list([] if learning_insights is None else learning_insights, "learning_insights")
        momentum = self._dict({} if momentum is None else momentum, "momentum")
        tradeoff = self.analyze_tradeoff(
            option_obj,
            goals=goals,
            dependencies=dependencies,
            behavior_patterns=behavior_patterns,
            context=context,
            simulations=simulations,
            optimization_results=optimization_results,
            risks=risks,
            momentum=momentum,
            learning_insights=learning_insights,
        )
        utility = self._bounded((tradeoff.benefit * 0.65) + ((100.0 - tradeoff.cost) * 0.2) + ((100.0 - tradeoff.effort) * 0.15), 0.0, 100.0)
        risk_score = tradeoff.risk
        confidence_score = self._bounded((tradeoff.confidence * 100.0) + min(15.0, len(learning_insights) * 2.0), 0.0, 100.0)
        alignment_score = tradeoff.alignment
        overall = self._bounded(
            (utility * 0.35)
            + ((100.0 - risk_score) * 0.25)
            + (confidence_score * 0.15)
            + (alignment_score * 0.25),
            0.0,
            100.0,
        )
        return DecisionEvaluation(
            option_id=option_obj.option_id,
            utility_score=round(utility, 2),
            risk_score=round(risk_score, 2),
            confidence_score=round(confidence_score, 2),
            alignment_score=round(alignment_score, 2),
            overall_score=round(overall, 2),
            evidence=self._evidence(option_obj, tradeoff, context, simulations),
        )

    def analyze_tradeoff(
        self,
        option: DecisionOption | Dict[str, Any],
        *,
        goals: List[Dict[str, Any]] | None = None,
        dependencies: Dict[str, Any] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        context: Dict[str, Any] | None = None,
        simulations: List[Dict[str, Any]] | None = None,
        optimization_results: Dict[str, Any] | None = None,
        risks: List[Dict[str, Any]] | None = None,
        momentum: Dict[str, Any] | None = None,
        learning_insights: List[Dict[str, Any]] | None = None,
    ) -> DecisionTradeoff:
        """Measure benefit, cost, risk, effort, alignment, and confidence."""
        option_obj = self._option(option)
        goals = self._dict_list([] if goals is None else goals, "goals")
        dependencies = self._dict({} if dependencies is None else dependencies, "dependencies")
        behavior_patterns = self._dict({} if behavior_patterns is None else behavior_patterns, "behavior_patterns")
        context = self._dict({} if context is None else context, "context")
        simulations = self._dict_list([] if simulations is None else simulations, "simulations")
        optimization_results = self._dict({} if optimization_results is None else optimization_results, "optimization_results")
        risks = self._dict_list([] if risks is None else risks, "risks")
        learning_insights = self._dict_list([] if learning_insights is None else learning_insights, "learning_insights")
        momentum = self._dict({} if momentum is None else momentum, "momentum")
        goal_alignment = self._goal_alignment(option_obj, goals)
        sim_success = self._simulation_success(simulations)
        productivity = self._productivity_factor(behavior_patterns)
        momentum_bonus = self._momentum_bonus(momentum, context)
        benefit = self._bounded((option_obj.expected_benefit * 0.45) + (sim_success * 25.0) + (productivity * 20.0) + momentum_bonus, 0.0, 100.0)
        dependency_risk = self._dependency_risk(dependencies, option_obj)
        contextual_risk = self._context_risk(context)
        risk = self._bounded(max(self._risk_list_score(risks), dependency_risk, contextual_risk, self._safe_float(option_obj.metadata.get("risk_score"), 0.0)), 0.0, 100.0)
        confidence = self._bounded(0.45 + min(0.25, len(simulations) * 0.04) + min(0.2, len(learning_insights) * 0.03) + self._optimization_confidence(optimization_results), 0.0, 1.0)
        return DecisionTradeoff(
            tradeoff_id=f"tradeoff-{option_obj.option_id}",
            option_id=option_obj.option_id,
            benefit=round(benefit, 2),
            cost=option_obj.estimated_cost,
            risk=round(risk, 2),
            effort=option_obj.estimated_effort,
            alignment=round(goal_alignment, 2),
            confidence=round(confidence, 4),
        )

    def analyze_decisions(
        self,
        options: List[DecisionOption | Dict[str, Any]],
        *,
        goals: List[Dict[str, Any]] | None = None,
        dependencies: Dict[str, Any] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        context: Dict[str, Any] | None = None,
        simulations: List[Dict[str, Any]] | None = None,
        optimization_results: Dict[str, Any] | None = None,
        risks: List[Dict[str, Any]] | None = None,
        momentum: Dict[str, Any] | None = None,
        learning_insights: List[Dict[str, Any]] | None = None,
        created_at: datetime | None = None,
    ) -> DecisionAnalysis:
        """Evaluate and rank multiple options."""
        option_objs = self._options(options)
        evaluations = [
            self.evaluate_option(
                option,
                goals=goals,
                dependencies=dependencies,
                behavior_patterns=behavior_patterns,
                context=context,
                simulations=simulations,
                optimization_results=optimization_results,
                risks=risks,
                momentum=momentum,
                learning_insights=learning_insights,
            )
            for option in option_objs
        ]
        tradeoffs = [
            self.analyze_tradeoff(
                option,
                goals=goals,
                dependencies=dependencies,
                behavior_patterns=behavior_patterns,
                context=context,
                simulations=simulations,
                optimization_results=optimization_results,
                risks=risks,
                momentum=momentum,
                learning_insights=learning_insights,
            )
            for option in option_objs
        ]
        ranked_evaluations = sorted(evaluations, key=lambda item: (-item.overall_score, item.risk_score, item.option_id))
        recommendations = self.generate_recommendations(option_objs, ranked_evaluations)
        created_at = created_at or datetime.utcnow()
        analysis = DecisionAnalysis(
            analysis_id=f"decision-analysis-{created_at.strftime('%Y%m%d')}-{len(self.decision_history) + 1}",
            options=option_objs,
            evaluations=evaluations,
            tradeoffs=tradeoffs,
            recommendations=recommendations,
            ranking=[evaluation.option_id for evaluation in ranked_evaluations],
            executive_summary=self.generate_executive_summary(option_objs, ranked_evaluations),
            confidence=round(sum(item.confidence_score for item in evaluations) / (len(evaluations) * 100.0), 4),
            created_at=created_at,
        )
        self.decision_history.append(analysis)
        return analysis

    def compare_scenarios(self, options: List[DecisionOption | Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        """Compare options and return ranked scenario-style output."""
        analysis = self.analyze_decisions(options, **kwargs)
        evaluations_by_id = {evaluation.option_id: evaluation for evaluation in analysis.evaluations}
        options_by_id = {option.option_id: option for option in analysis.options}
        return [
            {
                "rank": index,
                "option_id": option_id,
                "title": options_by_id[option_id].title,
                "overall_score": evaluations_by_id[option_id].overall_score,
                "risk_score": evaluations_by_id[option_id].risk_score,
            }
            for index, option_id in enumerate(analysis.ranking, start=1)
        ]

    def estimate_regret(
        self,
        option: DecisionOption | Dict[str, Any],
        evaluation: DecisionEvaluation | Dict[str, Any],
        *,
        best_overall_score: float | None = None,
    ) -> Dict[str, float]:
        """Estimate potential regret, opportunity cost, and missed value deterministically."""
        option_obj = self._option(option)
        evaluation_obj = evaluation if isinstance(evaluation, DecisionEvaluation) else DecisionEvaluation(**self._dict(evaluation, "evaluation"))
        best = evaluation_obj.overall_score if best_overall_score is None else self._bounded_number(best_overall_score, "best_overall_score")
        missed_value = max(0.0, best - evaluation_obj.overall_score)
        opportunity_cost = self._bounded(option_obj.estimated_cost * 0.35 + option_obj.estimated_effort * 0.25 + missed_value * 0.4, 0.0, 100.0)
        potential_regret = self._bounded((evaluation_obj.risk_score * 0.45) + opportunity_cost * 0.35 + missed_value * 0.2, 0.0, 100.0)
        return {
            "potential_regret": round(potential_regret, 2),
            "opportunity_cost": round(opportunity_cost, 2),
            "missed_value": round(missed_value, 2),
        }

    def generate_recommendations(
        self,
        options: List[DecisionOption],
        ranked_evaluations: List[DecisionEvaluation],
    ) -> List[DecisionRecommendation]:
        """Generate best, alternative, and avoid recommendations."""
        options_by_id = {option.option_id: option for option in options}
        recommendations: List[DecisionRecommendation] = []
        if not ranked_evaluations:
            return []
        best = ranked_evaluations[0]
        recommendations.append(
            DecisionRecommendation(
                recommendation_id=f"decision-best-{best.option_id}",
                recommendation_type="best_option",
                option_id=best.option_id,
                title=options_by_id[best.option_id].title,
                reasoning=f"Highest overall score at {best.overall_score:.2f}.",
                confidence=best.confidence_score / 100.0,
                priority=1,
            )
        )
        if len(ranked_evaluations) > 1:
            alternative = ranked_evaluations[1]
            recommendations.append(
                DecisionRecommendation(
                    recommendation_id=f"decision-alternative-{alternative.option_id}",
                    recommendation_type="alternative_option",
                    option_id=alternative.option_id,
                    title=options_by_id[alternative.option_id].title,
                    reasoning="Strong fallback if the best option is unavailable.",
                    confidence=alternative.confidence_score / 100.0,
                    priority=2,
                )
            )
            avoid = ranked_evaluations[-1]
            recommendations.append(
                DecisionRecommendation(
                    recommendation_id=f"decision-avoid-{avoid.option_id}",
                    recommendation_type="avoid_option",
                    option_id=avoid.option_id,
                    title=options_by_id[avoid.option_id].title,
                    reasoning=f"Lowest score with risk {avoid.risk_score:.2f}.",
                    confidence=max(0.1, avoid.confidence_score / 100.0),
                    priority=3,
                )
            )
        return sorted({item.recommendation_id: item for item in recommendations}.values(), key=lambda item: (item.priority, item.recommendation_id))

    def explain_decision(self, analysis: DecisionAnalysis | Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Explain selected, rejected, tradeoff, risk, and expected outcome reasons."""
        analysis_obj = self._analysis(analysis) if analysis is not None else (self.decision_history[-1] if self.decision_history else None)
        if analysis_obj is None:
            return {"summary": "No decision analysis available.", "why_chosen": [], "why_rejected": [], "tradeoffs": [], "risks": [], "expected_outcome": "unknown"}
        evaluations = {evaluation.option_id: evaluation for evaluation in analysis_obj.evaluations}
        best_id = analysis_obj.ranking[0]
        worst_id = analysis_obj.ranking[-1]
        best = evaluations[best_id]
        worst = evaluations[worst_id]
        return {
            "summary": analysis_obj.executive_summary,
            "why_chosen": [f"{best_id} has the strongest overall score ({best.overall_score:.2f})."],
            "why_rejected": [f"{worst_id} ranked lowest due to score {worst.overall_score:.2f} and risk {worst.risk_score:.2f}."],
            "tradeoffs": [asdict(tradeoff) for tradeoff in analysis_obj.tradeoffs],
            "risks": [f"{evaluation.option_id}: risk {evaluation.risk_score:.2f}" for evaluation in analysis_obj.evaluations],
            "expected_outcome": f"Expected best outcome from {best_id} with confidence {best.confidence_score:.2f}.",
        }

    def generate_executive_summary(self, options: List[DecisionOption], ranked_evaluations: List[DecisionEvaluation]) -> str:
        """Generate compact executive recommendation text."""
        if not ranked_evaluations:
            return "No options were evaluated."
        options_by_id = {option.option_id: option for option in options}
        best = ranked_evaluations[0]
        confidence_level = "high" if best.confidence_score >= 75.0 else "medium" if best.confidence_score >= 45.0 else "low"
        return f"Recommend {options_by_id[best.option_id].title} with {confidence_level} confidence and overall score {best.overall_score:.2f}."

    def summarize_decision_intelligence(self) -> Dict[str, Any] | None:
        """Return optional orchestrator-ready decision intelligence outputs."""
        if not self.decision_history:
            return None
        latest = self.decision_history[-1]
        return {
            "decision_analysis": {
                "analysis_id": latest.analysis_id,
                "option_count": len(latest.options),
                "ranking": list(latest.ranking),
                "confidence": latest.confidence,
            },
            "decision_recommendation": [asdict(item) for item in latest.recommendations],
            "decision_tradeoffs": [asdict(item) for item in latest.tradeoffs],
            "decision_summary": latest.executive_summary,
        }

    def _goal_alignment(self, option: DecisionOption, goals: List[Dict[str, Any]]) -> float:
        if not goals:
            return 50.0 + min(20.0, len(option.goal_ids) * 10.0)
        goal_ids = {str(goal.get("goal_id", goal.get("id"))) for goal in goals if goal.get("goal_id", goal.get("id")) is not None}
        aligned = sum(1 for goal_id in option.goal_ids if goal_id in goal_ids)
        priority_bonus = sum(self._safe_float(goal.get("priority"), 1.0) for goal in goals if str(goal.get("goal_id", goal.get("id"))) in option.goal_ids)
        return self._bounded((aligned / max(1, len(option.goal_ids) or 1)) * 70.0 + min(30.0, priority_bonus * 3.0), 0.0, 100.0)

    def _dependency_risk(self, dependencies: Dict[str, Any], option: DecisionOption) -> float:
        blocked = dependencies.get("blocked_tasks", [])
        blocked_count = len(blocked) if isinstance(blocked, list) else self._safe_float(blocked, 0.0)
        option_blocked = 20.0 if option.metadata.get("blocked") else 0.0
        return self._bounded(blocked_count * 12.0 + option_blocked, 0.0, 100.0)

    def _context_risk(self, context: Dict[str, Any]) -> float:
        risk_state = str(context.get("risk_state", context.get("context_summary", {}).get("risk_state", "low"))).lower()
        return {"low": 5.0, "medium": 30.0, "high": 60.0, "critical": 90.0}.get(risk_state, 10.0)

    def _risk_list_score(self, risks: List[Dict[str, Any]]) -> float:
        severity_scores = {"low": 10.0, "medium": 35.0, "high": 65.0, "critical": 90.0}
        return max((severity_scores.get(str(risk.get("severity", "low")).lower(), 10.0) for risk in risks), default=0.0)

    def _simulation_success(self, simulations: List[Dict[str, Any]]) -> float:
        if not simulations:
            return 0.5
        return self._bounded(sum(self._safe_float(item.get("success_probability"), 0.5) for item in simulations) / len(simulations), 0.0, 1.0)

    def _productivity_factor(self, behavior_patterns: Dict[str, Any]) -> float:
        value = self._safe_float(behavior_patterns.get("average_productivity"), 50.0)
        return self._bounded(value / 100.0 if value > 1.0 else value, 0.0, 1.0)

    def _momentum_bonus(self, momentum: Dict[str, Any], context: Dict[str, Any]) -> float:
        state = str(momentum.get("momentum_state", context.get("momentum_state", context.get("context_summary", {}).get("momentum_state", "neutral")))).lower()
        return {"positive": 12.0, "neutral": 4.0, "negative": -8.0}.get(state, 0.0)

    def _optimization_confidence(self, optimization_results: Dict[str, Any]) -> float:
        if not optimization_results:
            return 0.0
        selected = optimization_results.get("selected_future", {})
        return min(0.15, self._safe_float(selected.get("overall_score"), 0.0) / 700.0) if isinstance(selected, dict) else 0.05

    def _evidence(self, option: DecisionOption, tradeoff: DecisionTradeoff, context: Dict[str, Any], simulations: List[Dict[str, Any]]) -> List[str]:
        return [
            f"benefit={tradeoff.benefit:.2f}",
            f"risk={tradeoff.risk:.2f}",
            f"alignment={tradeoff.alignment:.2f}",
            f"context_risk={context.get('risk_state', context.get('context_summary', {}).get('risk_state', 'unknown'))}",
            f"simulation_count={len(simulations)}",
            f"option={option.option_id}",
        ]

    def _options(self, options: List[DecisionOption | Dict[str, Any]]) -> List[DecisionOption]:
        if not isinstance(options, list):
            raise ValueError("options must be a list.")
        if not options:
            raise ValueError("At least one decision option is required.")
        normalized = [self._option(option) for option in options]
        seen = set()
        for option in normalized:
            if option.option_id in seen:
                raise ValueError("decision option ids must be unique.")
            seen.add(option.option_id)
        return normalized

    def _option(self, option: DecisionOption | Dict[str, Any]) -> DecisionOption:
        return option if isinstance(option, DecisionOption) else DecisionOption(**self._dict(option, "option"))

    def _analysis(self, analysis: DecisionAnalysis | Dict[str, Any]) -> DecisionAnalysis:
        return analysis if isinstance(analysis, DecisionAnalysis) else DecisionAnalysis(**self._dict(analysis, "analysis"))

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        return dict(value)

    def _dict_list(self, value: Any, field_name: str) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list of dictionaries.")
        if any(not isinstance(item, dict) for item in value):
            raise ValueError(f"{field_name} entries must be dictionaries.")
        return [dict(item) for item in value]

    def _bounded_number(self, value: Any, field_name: str) -> float:
        return self._bounded(self._finite_number(value, field_name), 0.0, 100.0)

    def _finite_number(self, value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return number

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
