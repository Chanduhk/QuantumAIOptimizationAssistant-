from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """Actionable recommendation generated from current planning signals."""

    title: str
    priority: int
    reason: str
    action: str


class RecommendationEngine:
    """Generate ranked daily recommendations from context, evaluation, and forecast signals."""

    def __init__(
        self,
        session: Any = None,
        days_back: int = 90,
        engine_registry: Any = None,
        monitor: Any = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.engine_registry = engine_registry
        self.monitor = monitor

    async def generate_recommendations(self, user_id: int) -> Dict[str, Any]:
        """Orchestrate AI brain signals to produce a comprehensive recommendation response."""
        from backend.app.engines.brain_workflow import QuantumLifeBrain

        if not self.session:
            raise ValueError("Database session is required to generate recommendations.")

        brain = QuantumLifeBrain(session=self.session)
        # plan_day is a synchronous operation
        context = {}
        evaluation = {}
        behavior_patterns = {}
        prioritized_tasks = []

        try:
            plan_output = brain.plan_day(user_id=user_id, days_back=self.days_back)
            context = plan_output.get("context", {})
            evaluation = plan_output.get("optimization", {})
            behavior_patterns = plan_output.get("behavior_patterns", {})
            prioritized_tasks = plan_output.get("prioritized_tasks", [])
        except ValueError as exc:
            # Handle empty tasks or other logical pipeline aborts cleanly
            if "No active tasks" not in str(exc):
                raise

        # Default forecast_score for daily generation
        forecast_score = 0.8

        # Run pure engine recommendation generation
        recommendations = self.generate_daily_recommendations(
            context=context,
            evaluation=evaluation,
            forecast_score=forecast_score,
        )

        focus_hours = [f"{hour}:00" for hour in behavior_patterns.get("best_focus_hours", [])]
        if not focus_hours:
            focus_hours = ["09:00", "14:00"]

        task_ordering = [task.get("title", f"Task {task.get('id')}") for task in prioritized_tasks[:5]]

        schedule_improvements = []
        goal_progress_alerts = []
        behavioral_insights = []

        for rec in recommendations:
            msg = f"{rec.title}: {rec.reason} -> {rec.action}"
            if "Overload" in rec.reason or "Stress" in rec.reason or "Recovery" in rec.title:
                schedule_improvements.append(msg)
            elif "Forecast" in rec.reason or "Risk" in rec.title:
                goal_progress_alerts.append(msg)
            else:
                behavioral_insights.append(msg)

        if not prioritized_tasks:
            behavioral_insights.append("You currently have no active tasks. Consider defining your goals for the day.")

        if not schedule_improvements:
            schedule_improvements.append("Schedule is optimal. No critical improvements needed.")
        if not goal_progress_alerts:
            goal_progress_alerts.append("All goals are tracking positively against the forecast.")
        if not behavioral_insights:
            behavioral_insights.append("Focus on high-leverage tasks to maintain productivity.")

        return {
            "focus_hours": focus_hours,
            "task_ordering": task_ordering,
            "schedule_improvements": schedule_improvements,
            "goal_progress_alerts": goal_progress_alerts,
            "behavioral_insights": behavioral_insights,
        }

    def generate_from_context(self, context: Any) -> List[Recommendation]:
        """
        Generate recommendations from a ContextState-compatible object.

        Args:
            context: ContextState dataclass or dictionary containing overload_score.

        Returns:
            Ranked recommendations derived from context metrics.
        """
        overload_score = self._get_float(context, "overload_score")
        recommendations: List[Recommendation] = []

        if overload_score > 1.2:
            recommendations.append(
                Recommendation(
                    title="Reduce Workload",
                    priority=90,
                    reason=f"Overload score is {overload_score:.2f}, above the 1.20 threshold.",
                    action="Defer or shorten lower-priority tasks before generating the next schedule.",
                )
            )

        ranked = self._rank(recommendations)
        logger.info("Generated %s context recommendations.", len(ranked))
        return ranked

    def generate_from_scores(self, evaluation: Dict[str, Any]) -> List[Recommendation]:
        """
        Generate recommendations from DayEvaluator-compatible metrics.

        Args:
            evaluation: Evaluation dictionary from AIBrain or DayEvaluator output.

        Returns:
            Ranked recommendations derived from schedule quality metrics.
        """
        if not isinstance(evaluation, dict):
            raise TypeError("evaluation must be a dictionary.")

        productivity_score = self._get_float(evaluation, "productivity_score")
        stress_penalty = self._get_float(evaluation, "stress_penalty")
        energy_alignment_score = self._get_float(
            evaluation,
            "energy_alignment_score",
            fallback_key="energy_alignment",
        )
        recommendations: List[Recommendation] = []

        if stress_penalty > 0.5:
            recommendations.append(
                Recommendation(
                    title="Schedule Recovery",
                    priority=85,
                    reason=f"Stress penalty is {stress_penalty:.2f}, indicating excess load pressure.",
                    action="Add recovery time and reduce the number of scheduled work blocks.",
                )
            )

        if energy_alignment_score < 0.5:
            recommendations.append(
                Recommendation(
                    title="Reorder High Energy Tasks",
                    priority=75,
                    reason=(
                        f"Energy alignment score is {energy_alignment_score:.2f}, "
                        "below the 0.50 threshold."
                    ),
                    action="Move high-priority tasks to morning and medium-priority tasks to afternoon.",
                )
            )

        if productivity_score > 0.8:
            recommendations.append(
                Recommendation(
                    title="Maintain Current Strategy",
                    priority=40,
                    reason=f"Productivity score is {productivity_score:.2f}, above the 0.80 target.",
                    action="Keep the current scheduling strategy unless forecast risk increases.",
                )
            )

        ranked = self._rank(recommendations)
        logger.info("Generated %s score recommendations.", len(ranked))
        return ranked

    def generate_from_forecast(self, forecast_score: float) -> List[Recommendation]:
        """
        Generate recommendations from the multi-day forecast score.

        Args:
            forecast_score: Numeric score returned by MultiDayForecaster.simulate().

        Returns:
            Ranked forecast-risk recommendations.
        """
        score = float(forecast_score)
        recommendations: List[Recommendation] = []

        if score < 0.6:
            recommendations.append(
                Recommendation(
                    title="Reduce Future Risk",
                    priority=80,
                    reason=f"Forecast score is {score:.2f}, below the 0.60 threshold.",
                    action="Reduce backlog risk by protecting urgent tasks and deferring low-value work.",
                )
            )

        ranked = self._rank(recommendations)
        logger.info("Generated %s forecast recommendations.", len(ranked))
        return ranked

    def generate_daily_recommendations(
        self,
        context: Any,
        evaluation: Dict[str, Any],
        forecast_score: float,
    ) -> List[Recommendation]:
        """
        Generate ranked daily recommendations from all available AI brain outputs.

        Args:
            context: ContextState dataclass or dictionary.
            evaluation: Evaluation dictionary from AIBrain.
            forecast_score: Numeric score returned by forecast.py.

        Returns:
            Ranked, de-duplicated list of recommendations.
        """
        recommendations = []
        recommendations.extend(self.generate_from_context(context))
        recommendations.extend(self.generate_from_scores(evaluation))
        recommendations.extend(self.generate_from_forecast(forecast_score))

        ranked = self._rank(self._dedupe(recommendations))
        logger.info("Generated %s daily recommendations.", len(ranked))
        return ranked

    def record_cycle(self, result: Dict[str, Any]) -> List[Recommendation]:
        """
        Compatibility hook for AIBrain recommendation_engine integration.

        Args:
            result: AIBrain daily cycle result.

        Returns:
            Ranked recommendations for the provided cycle result.
        """
        if not isinstance(result, dict):
            raise TypeError("result must be a dictionary.")
        return self.generate_daily_recommendations(
            context=result.get("context"),
            evaluation=result.get("evaluation", {}),
            forecast_score=float(result.get("forecast_score", 0.0)),
        )

    def _rank(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        return sorted(recommendations, key=lambda recommendation: recommendation.priority, reverse=True)

    def _dedupe(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        seen_titles = set()
        output: List[Recommendation] = []
        for recommendation in recommendations:
            if recommendation.title in seen_titles:
                continue
            seen_titles.add(recommendation.title)
            output.append(recommendation)
        return output

    def _get_float(self, source: Any, key: str, *, fallback_key: str = "") -> float:
        value = None
        if isinstance(source, dict):
            value = source.get(key)
            if value is None and fallback_key:
                value = source.get(fallback_key)
        else:
            value = getattr(source, key, None)
            if value is None and fallback_key:
                value = getattr(source, fallback_key, None)

        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning("Unable to convert %s to float: %r", key, value)
            return 0.0
