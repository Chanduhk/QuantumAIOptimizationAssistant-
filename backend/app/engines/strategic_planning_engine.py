from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.app.domain.goal_model import Goal, Milestone
from backend.app.domain.strategic_plan_model import RoadmapItem, StrategicPlan


class StrategicPlanningEngine:
    """Generate deterministic long-horizon plans from goals, milestones, tasks, and dependencies."""

    def __init__(
        self,
        goal_intelligence_engine: Any | None = None,
        dependency_intelligence_engine: Any | None = None,
    ) -> None:
        self.goal_intelligence_engine = goal_intelligence_engine
        self.dependency_intelligence_engine = dependency_intelligence_engine
        self.strategic_plans: List[StrategicPlan] = []

    def generate_7_day_plan(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> StrategicPlan:
        """Generate a one-week strategic plan."""
        return self.generate_plan(7, tasks=tasks, behavior_patterns=behavior_patterns, now=now)

    def generate_30_day_plan(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> StrategicPlan:
        """Generate a 30-day strategic plan."""
        return self.generate_plan(30, tasks=tasks, behavior_patterns=behavior_patterns, now=now)

    def generate_90_day_plan(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> StrategicPlan:
        """Generate a 90-day strategic plan."""
        return self.generate_plan(90, tasks=tasks, behavior_patterns=behavior_patterns, now=now)

    def generate_plan(
        self,
        horizon_days: int,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> StrategicPlan:
        """Generate a strategic roadmap for the requested horizon."""
        if not isinstance(horizon_days, int) or isinstance(horizon_days, bool) or horizon_days <= 0:
            raise ValueError("horizon_days must be a positive integer.")
        if behavior_patterns is None:
            behavior_patterns = {}
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        now = now or datetime.utcnow()
        goals = self._collect_goals()
        milestones = self._collect_milestones()
        task_list = self._collect_tasks(tasks)
        enriched_tasks = self._enrich_dependencies(task_list)
        ordered_tasks = self._order_tasks(enriched_tasks, goals)
        roadmap_items = self._build_roadmap_items(
            ordered_tasks,
            milestones,
            goals,
            horizon_days,
            behavior_patterns,
        )
        risk_assessment = self.assess_risk(
            horizon_days=horizon_days,
            tasks=enriched_tasks,
            behavior_patterns=behavior_patterns,
            now=now,
        )
        confidence = self._confidence_score(risk_assessment["risk_score"], behavior_patterns, ordered_tasks)
        plan = StrategicPlan(
            plan_id=self._plan_id(horizon_days, goals, milestones, now),
            horizon_days=horizon_days,
            created_at=now,
            goal_ids=[goal.goal_id for goal in goals],
            milestone_ids=[milestone.milestone_id for milestone in milestones],
            risk_score=risk_assessment["risk_score"],
            confidence_score=confidence,
            roadmap_items=roadmap_items,
        )
        self.strategic_plans.append(plan)
        return plan

    def forecast_goals(
        self,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> List[Dict[str, Any]]:
        """Estimate deterministic goal completion probabilities."""
        if behavior_patterns is None:
            behavior_patterns = {}
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        now = now or datetime.utcnow()
        forecasts: List[Dict[str, Any]] = []
        for goal in self._collect_goals():
            health = self._goal_health(goal.goal_id, now)
            productivity = self._productivity_factor(behavior_patterns)
            probability = self._bounded(
                (float(health.get("progress", goal.progress)) * 0.55)
                + (productivity * 25.0)
                + ((100.0 - float(health.get("risk_score", 0.0))) * 0.2),
                0.0,
                100.0,
            )
            forecasts.append(
                {
                    "goal_id": goal.goal_id,
                    "goal_completion_probability": round(probability / 100.0, 4),
                    "risk_level": self._risk_level(float(health.get("risk_score", 0.0))),
                    "health_status": health.get("health_status", "healthy"),
                }
            )
        return sorted(forecasts, key=lambda item: str(item["goal_id"]))

    def forecast_milestones(
        self,
        behavior_patterns: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Estimate deterministic milestone completion probabilities."""
        if behavior_patterns is None:
            behavior_patterns = {}
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        productivity = self._productivity_factor(behavior_patterns)
        forecasts: List[Dict[str, Any]] = []
        for milestone in self._collect_milestones():
            probability = self._bounded((milestone.progress * 0.7) + (productivity * 30.0), 0.0, 100.0)
            forecasts.append(
                {
                    "milestone_id": milestone.milestone_id,
                    "goal_id": milestone.goal_id,
                    "milestone_completion_probability": round(probability / 100.0, 4),
                    "status": milestone.status,
                }
            )
        return sorted(forecasts, key=lambda item: (str(item["goal_id"]), str(item["milestone_id"])))

    def assess_risk(
        self,
        *,
        horizon_days: int,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> Dict[str, Any]:
        """Assess strategic risk across deadlines, dependencies, neglect, and workload."""
        if not isinstance(horizon_days, int) or horizon_days <= 0:
            raise ValueError("horizon_days must be a positive integer.")
        behavior_patterns = behavior_patterns or {}
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        now = now or datetime.utcnow()
        enriched_tasks = self._enrich_dependencies(self._collect_tasks(tasks))
        blocked_count = sum(1 for task in enriched_tasks if task.get("blocked"))
        neglected_count = sum(1 for goal in self._collect_goals() if self._goal_health(goal.goal_id, now).get("neglected"))
        overdue_milestones = [
            milestone.milestone_id
            for milestone in self._collect_milestones()
            if milestone.status not in {"done", "complete", "completed"} and milestone.progress < 100.0
        ]
        total_hours = sum(self._task_duration(task) for task in enriched_tasks)
        capacity = self._daily_capacity(behavior_patterns) * horizon_days
        overload_ratio = total_hours / capacity if capacity > 0 else 0.0
        overload_score = max(0.0, (overload_ratio - 1.0) * 45.0)
        risk_score = self._bounded(
            (blocked_count * 18.0)
            + (neglected_count * 12.0)
            + (len(overdue_milestones) * 6.0)
            + overload_score,
            0.0,
            100.0,
        )
        return {
            "risk_score": round(risk_score, 2),
            "risk_level": self._risk_level(risk_score),
            "blocked_task_count": blocked_count,
            "neglected_goal_count": neglected_count,
            "overdue_milestone_ids": sorted(overdue_milestones),
            "overload_ratio": round(overload_ratio, 4),
        }

    def recommend_next_week(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> Dict[str, Any]:
        """Return a compact next-week recommendation from a seven-day plan."""
        plan = self.generate_7_day_plan(tasks, behavior_patterns, now=now)
        first_items = [asdict(item) for item in plan.roadmap_items[:5]]
        return {
            "plan_id": plan.plan_id,
            "horizon_days": plan.horizon_days,
            "risk_score": plan.risk_score,
            "confidence_score": plan.confidence_score,
            "recommended_items": first_items,
        }

    def summarize_active_plans(self) -> Dict[str, Any] | None:
        """Return a compact summary of generated strategic plans, if any exist."""
        if not self.strategic_plans:
            return None
        latest = self.strategic_plans[-1]
        return {
            "plan_id": latest.plan_id,
            "horizon_days": latest.horizon_days,
            "risk_score": latest.risk_score,
            "confidence_score": latest.confidence_score,
            "roadmap_item_count": len(latest.roadmap_items),
        }

    def _collect_goals(self) -> List[Goal]:
        graph = getattr(self.goal_intelligence_engine, "goal_graph", None)
        goals = getattr(graph, "goals", {})
        return [goals[goal_id] for goal_id in sorted(goals)]

    def _collect_milestones(self) -> List[Milestone]:
        graph = getattr(self.goal_intelligence_engine, "goal_graph", None)
        milestones = getattr(graph, "milestones", {})
        return [milestones[milestone_id] for milestone_id in sorted(milestones)]

    def _collect_tasks(self, tasks: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
        if tasks is None:
            graph = getattr(self.goal_intelligence_engine, "goal_graph", None)
            goal_tasks = getattr(graph, "goal_tasks", {})
            tasks = [
                dict(task)
                for goal_id in sorted(goal_tasks)
                for task in goal_tasks.get(goal_id, [])
            ]
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        collected: List[Dict[str, Any]] = []
        seen_ids = set()
        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            task_copy = dict(task)
            raw_id = task_copy.get("id", f"task-{index}")
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise ValueError("Each task id must be a non-empty string when provided.")
            task_id = raw_id.strip()
            if task_id in seen_ids:
                raise ValueError("task ids must be unique.")
            seen_ids.add(task_id)
            task_copy["id"] = task_id
            self._task_duration(task_copy)
            collected.append(task_copy)
        return collected

    def _enrich_dependencies(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.dependency_intelligence_engine is None or not tasks:
            return [dict(task) for task in tasks]
        return self.dependency_intelligence_engine.enrich_tasks_with_dependencies(tasks)

    def _order_tasks(self, tasks: List[Dict[str, Any]], goals: List[Goal]) -> List[Dict[str, Any]]:
        if not tasks:
            return []
        goal_priority = {goal.goal_id: goal.priority for goal in goals}
        order_index = {task["id"]: index for index, task in enumerate(tasks)}
        if self.dependency_intelligence_engine is not None:
            execution_order = self.dependency_intelligence_engine.recommend_execution_order(tasks)
            order_index.update({task_id: index for index, task_id in enumerate(execution_order)})
        return sorted(
            [dict(task) for task in tasks],
            key=lambda task: (
                bool(task.get("blocked")),
                order_index.get(task["id"], len(order_index)),
                -float(goal_priority.get(task.get("goal_id"), 0)),
                -self._safe_float(task.get("decision_score"), 0.0),
                str(task["id"]),
            ),
        )

    def _build_roadmap_items(
        self,
        tasks: List[Dict[str, Any]],
        milestones: List[Milestone],
        goals: List[Goal],
        horizon_days: int,
        behavior_patterns: Dict[str, Any],
    ) -> List[RoadmapItem]:
        goal_priority = {goal.goal_id: goal.priority for goal in goals}
        milestone_by_goal = {}
        for milestone in milestones:
            milestone_by_goal.setdefault(milestone.goal_id, []).append(milestone)
        for goal_id in milestone_by_goal:
            milestone_by_goal[goal_id].sort(key=lambda milestone: (milestone.progress, milestone.milestone_id))
        capacity = self._daily_capacity(behavior_patterns)
        consumed_hours = 0.0
        items: List[RoadmapItem] = []
        for sequence, task in enumerate(tasks, start=1):
            duration = self._task_duration(task)
            start_day = int(consumed_hours // capacity) + 1
            consumed_hours += duration
            end_day = max(start_day, int(math.ceil(consumed_hours / capacity)))
            goal_id = task.get("goal_id") if isinstance(task.get("goal_id"), str) else None
            milestone_id = None
            if goal_id in milestone_by_goal and milestone_by_goal[goal_id]:
                milestone_id = milestone_by_goal[goal_id][0].milestone_id
            priority_score = self._bounded(
                (float(goal_priority.get(goal_id, 0)) * 8.0)
                + self._safe_float(task.get("decision_score"), 0.0) * 0.2
                + self._safe_float(task.get("dependency_score"), 0.0) * 0.2,
                0.0,
                100.0,
            )
            risk_score = self._bounded(
                (35.0 if task.get("blocked") else 0.0)
                + max(0.0, end_day - horizon_days) * 8.0
                + self._safe_float(task.get("dependency_impact_score"), 0.0) * 0.2,
                0.0,
                100.0,
            )
            items.append(
                RoadmapItem(
                    sequence=sequence,
                    goal_id=goal_id,
                    milestone_id=milestone_id,
                    task_id=task["id"],
                    recommended_start_day=start_day,
                    recommended_end_day=end_day,
                    priority_score=round(priority_score, 2),
                    risk_score=round(risk_score, 2),
                )
            )
        return items

    def _goal_health(self, goal_id: str, now: datetime) -> Dict[str, Any]:
        if self.goal_intelligence_engine is None:
            return {"goal_id": goal_id, "progress": 0.0, "risk_score": 0.0, "health_status": "healthy"}
        return self.goal_intelligence_engine.analyze_goal_health(goal_id, now=now)

    def _plan_id(self, horizon_days: int, goals: List[Goal], milestones: List[Milestone], now: datetime) -> str:
        goal_part = "-".join(goal.goal_id for goal in goals) or "no-goals"
        milestone_part = "-".join(milestone.milestone_id for milestone in milestones) or "no-milestones"
        return f"strategic-{horizon_days}-{now.strftime('%Y%m%d')}-{goal_part}-{milestone_part}"

    def _confidence_score(self, risk_score: float, behavior_patterns: Dict[str, Any], tasks: List[Dict[str, Any]]) -> float:
        productivity = self._productivity_factor(behavior_patterns) * 20.0
        evidence = min(15.0, len(tasks) * 2.0)
        return round(self._bounded(100.0 - risk_score + productivity + evidence - 20.0, 0.0, 100.0), 2)

    def _productivity_factor(self, behavior_patterns: Dict[str, Any]) -> float:
        if "average_productivity" in behavior_patterns:
            value = self._safe_float(behavior_patterns.get("average_productivity"), 0.5)
            return self._bounded(value / 100.0 if value > 1.0 else value, 0.0, 1.0)
        hourly = behavior_patterns.get("hourly_productivity", {})
        if isinstance(hourly, dict) and hourly:
            values = [self._safe_float(value, 0.0) for value in hourly.values()]
            return self._bounded((sum(values) / len(values)) / 100.0, 0.0, 1.0)
        return 0.5

    def _daily_capacity(self, behavior_patterns: Dict[str, Any]) -> float:
        for key in ("daily_capacity_hours", "available_hours", "focus_hours_per_day"):
            if key in behavior_patterns:
                return self._bounded(self._safe_float(behavior_patterns[key], 6.0), 1.0, 16.0)
        return 6.0

    def _task_duration(self, task: Dict[str, Any]) -> float:
        value = task.get("estimated_duration", task.get("duration", 1.0))
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError("task duration must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError("task duration must be finite.")
        if number <= 0:
            raise ValueError("task duration must be positive.")
        return number

    def _risk_level(self, risk_score: float) -> str:
        if risk_score >= 75.0:
            return "critical"
        if risk_score >= 50.0:
            return "high"
        if risk_score >= 25.0:
            return "medium"
        return "low"

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
