from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """Actionable recommendation generated from current planning signals."""

    title: str
    priority: int
    reason: str
    action: str


@dataclass
class ActionableProposal:
    """Structured, executable recommendation proposal."""

    proposal_id: str
    category: str
    title: str
    reason: str
    action_type: str
    target_id: Optional[int]
    impact_summary: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
        from backend.app.models.goal import Goal
        from backend.app.models.task import Task
        from backend.app.services.goal_service import GoalService
        from backend.app.services.task_lifecycle_service import TaskLifecycleService

        if not self.session:
            raise ValueError("Database session is required to generate recommendations.")

        brain = QuantumLifeBrain(session=self.session)
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
            if "No active tasks" not in str(exc):
                raise

        forecast_score = 0.8
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

        # --- Generate Structured Actionable Proposals ---
        actionable_proposals: List[Dict[str, Any]] = []
        task_service = TaskLifecycleService(self.session)
        active_db_tasks = self.session.query(Task).filter(
            Task.user_id == user_id,
            Task.completed.is_(False),
        ).all()
        serialized_tasks = [task_service.serialize_task(t) for t in active_db_tasks]

        goal_service = GoalService(self.session)
        active_db_goals = goal_service.list_goals(user_id=user_id, status="active")

        # 1. Dependency Unblock Proposal
        bottleneck_tasks = [t for t in serialized_tasks if t.get("blocking_count", 0) > 0 and not t.get("is_blocked")]
        if bottleneck_tasks:
            top_bottleneck = max(bottleneck_tasks, key=lambda item: int(item.get("blocking_count", 0)))
            b_count = int(top_bottleneck.get("blocking_count", 1))
            actionable_proposals.append({
                "proposal_id": f"unblock-{top_bottleneck['id']}",
                "category": "dependency_unblock",
                "title": f"Prioritize Key Blocker: {top_bottleneck['title']}",
                "reason": f"Completing '{top_bottleneck['title']}' will immediately unblock {b_count} dependent task(s).",
                "action_type": "prioritize_task",
                "target_id": top_bottleneck["id"],
                "impact_summary": f"Unblocks {b_count} dependent task(s)",
                "payload": {"task_id": top_bottleneck["id"], "priority": 5},
            })

        # 2. Energy Reschedule Proposal
        deep_work_types = {"coding", "programming", "architecture", "research", "design", "writing", "analysis"}
        unscheduled_deep = [
            t for t in serialized_tasks
            if str(t.get("task_type", "")).lower() in deep_work_types
            and not t.get("scheduled_start_time")
            and not t.get("is_blocked")
        ]
        if unscheduled_deep:
            target_deep = unscheduled_deep[0]
            first_focus_hour = behavior_patterns.get("best_focus_hours", [9])[0] if behavior_patterns.get("best_focus_hours") else 9
            now_utc = datetime.now(timezone.utc)
            slot_dt = now_utc.replace(hour=first_focus_hour, minute=0, second=0, microsecond=0)
            if slot_dt < now_utc:
                slot_dt = slot_dt + timedelta(days=1)
            actionable_proposals.append({
                "proposal_id": f"energy-{target_deep['id']}",
                "category": "energy_reschedule",
                "title": f"Schedule '{target_deep['title']}' in Peak Window",
                "reason": f"Aligns high-cognitive '{target_deep['task_type']}' task with your {first_focus_hour}:00 peak productivity window.",
                "action_type": "reschedule_task",
                "target_id": target_deep["id"],
                "impact_summary": "Maximizes deep work focus and output",
                "payload": {"task_id": target_deep["id"], "scheduled_start_time": slot_dt.isoformat()},
            })

        # 3. Goal Risk Mitigation Proposal
        for g in active_db_goals:
            analytics = goal_service.get_goal_analytics(g.id, user_id)
            if analytics.get("health_status") in ("at_risk", "behind", "critical"):
                actionable_proposals.append({
                    "proposal_id": f"goal-mitigate-{g.id}",
                    "category": "goal_risk_mitigation",
                    "title": f"Protect Goal: {g.title}",
                    "reason": f"Goal is currently {analytics.get('health_status')} with {analytics.get('days_needed')} days needed. Elevate priority of linked tasks.",
                    "action_type": "boost_goal_tasks",
                    "target_id": g.id,
                    "impact_summary": f"Elevates all tasks for '{g.title}' to Priority 4+",
                    "payload": {"goal_id": g.id, "boost_priority": 4},
                })
                break

        # 4. Cognitive Workload & Energy Budgeting
        deep_work_mins = sum(
            float(t.get("estimated_duration") or 60.0)
            for t in serialized_tasks
            if str(t.get("task_type", "")).lower() in deep_work_types
        )
        sustainable_limit_mins = 240.0
        utilization_pct = round((deep_work_mins / sustainable_limit_mins) * 100.0, 1)
        fatigue_risk = "high" if deep_work_mins > 300.0 else "moderate" if deep_work_mins > 210.0 else "low"

        if deep_work_mins > sustainable_limit_mins:
            lowest_deep = min(
                [t for t in serialized_tasks if str(t.get("task_type", "")).lower() in deep_work_types],
                key=lambda x: int(x.get("priority", 3)),
                default=None,
            )
            if lowest_deep:
                actionable_proposals.append({
                    "proposal_id": f"balance-workload-{lowest_deep['id']}",
                    "category": "workload_balance",
                    "title": "Rebalance Daily Cognitive Budget",
                    "reason": f"Current deep work commitment ({round(deep_work_mins / 60.0, 1)}h) exceeds sustainable 4-hour limit.",
                    "action_type": "reschedule_task",
                    "target_id": lowest_deep["id"],
                    "impact_summary": "Protects against cognitive fatigue and error rate spikes",
                    "payload": {"task_id": lowest_deep["id"], "defer_days": 1},
                })

        cognitive_budget = {
            "deep_work_minutes": round(deep_work_mins, 1),
            "deep_work_hours": round(deep_work_mins / 60.0, 2),
            "sustainable_limit_minutes": sustainable_limit_mins,
            "sustainable_limit_hours": 4.0,
            "cognitive_utilization_pct": min(200.0, utilization_pct),
            "fatigue_risk": fatigue_risk,
        }

        return {
            "focus_hours": focus_hours,
            "task_ordering": task_ordering,
            "schedule_improvements": schedule_improvements,
            "goal_progress_alerts": goal_progress_alerts,
            "behavioral_insights": behavioral_insights,
            "actionable_proposals": actionable_proposals,
            "cognitive_budget": cognitive_budget,
        }

    def apply_proposal(
        self,
        user_id: int,
        proposal_id: str,
        action_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an actionable recommendation proposal directly."""
        from backend.app.models.task import Task
        from backend.app.services.task_lifecycle_service import TaskLifecycleService

        svc = TaskLifecycleService(session=self.session)

        if action_type == "prioritize_task":
            tid = int(payload.get("task_id", 0))
            new_prio = int(payload.get("priority", 5))
            updated = svc.update_task(task_id=tid, user_id=user_id, priority=new_prio)
            return {"applied": True, "action_type": action_type, "task": svc.serialize_task(updated)}

        if action_type == "reschedule_task":
            tid = int(payload.get("task_id", 0))
            sched_time_str = payload.get("scheduled_start_time")
            defer_days = int(payload.get("defer_days", 0))

            task = svc.get_task(task_id=tid, user_id=user_id)
            new_start = None
            if sched_time_str:
                clean = sched_time_str.replace("Z", "+00:00")
                new_start = datetime.fromisoformat(clean)
            elif defer_days > 0:
                base = task.scheduled_start_time or datetime.now(timezone.utc)
                new_start = base + timedelta(days=defer_days)

            updated = svc.update_task(
                task_id=tid,
                user_id=user_id,
                scheduled_start_time=new_start,
                reschedule_count=(task.reschedule_count or 0) + 1,
            )
            return {"applied": True, "action_type": action_type, "task": svc.serialize_task(updated)}

        if action_type == "boost_goal_tasks":
            gid = int(payload.get("goal_id", 0))
            min_prio = int(payload.get("boost_priority", 4))
            tasks = self.session.query(Task).filter(
                Task.goal_id == gid,
                Task.user_id == user_id,
                Task.completed.is_(False),
            ).all()
            boosted_count = 0
            for t in tasks:
                if (t.priority or 0) < min_prio:
                    t.priority = min_prio
                    boosted_count += 1
            self.session.commit()
            return {"applied": True, "action_type": action_type, "goal_id": gid, "boosted_tasks_count": boosted_count}

        raise ValueError(f"Unsupported proposal action_type: '{action_type}'")

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
