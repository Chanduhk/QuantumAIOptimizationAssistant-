from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.goal_model import Goal
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.knowledge.goal_graph import GoalGraph


class GoalIntelligenceEngine:
    """Analyze goal health and enrich tasks with goal-aware decision signals."""

    def __init__(self, goal_graph: GoalGraph | None = None, dependency_engine: Any | None = None) -> None:
        self.goal_graph = goal_graph or GoalGraph()
        self.decision_engine = DecisionEngine()
        self.dependency_engine = dependency_engine

    def prioritize_goals(self, *, now: datetime | None = None) -> List[Dict[str, Any]]:
        """Return goals sorted by priority, risk, and low progress."""
        analyzed = [self.analyze_goal_health(goal.goal_id, now=now) for goal in self.goal_graph.goals.values()]
        return sorted(
            analyzed,
            key=lambda item: (
                -float(item["priority"]),
                -float(item["risk_score"]),
                float(item["progress"]),
                str(item["goal_id"]),
            ),
        )

    def analyze_goal_health(self, goal_id: str, *, now: datetime | None = None) -> Dict[str, Any]:
        """Return health, risk, neglect, and progress metrics for one goal."""
        now = now or datetime.utcnow()
        goal = self.goal_graph.goals.get(goal_id)
        if goal is None:
            raise ValueError(f"Unknown goal_id: {goal_id}")
        progress = self.goal_graph.get_goal_progress(goal_id)
        task_count = len(self.goal_graph.get_goal_tasks(goal_id))
        deadline_score = self._deadline_pressure(goal, now)
        activity_score = min(25.0, task_count * 5.0)
        completion_score = progress * 0.5
        risk_score = self._risk_score(progress, deadline_score, task_count)
        health_score = self._bounded(completion_score + activity_score - (risk_score * 0.3), 0.0, 100.0)
        status = self._health_status(health_score, risk_score)
        neglected = self.detect_neglect(goal_id, now=now)["neglected"]
        result = {
            "goal_id": goal.goal_id,
            "title": goal.title,
            "priority": goal.priority,
            "progress": round(progress, 2),
            "task_count": task_count,
            "deadline_pressure": round(deadline_score, 2),
            "risk_score": round(risk_score, 2),
            "goal_health_score": round(health_score, 2),
            "health_status": status,
            "neglected": neglected,
        }
        if self.dependency_engine is not None:
            result = self.dependency_engine.apply_goal_dependency_context(
                result,
                self.goal_graph.get_goal_tasks(goal_id),
            )
        return result

    def track_progress(self, goal_id: str) -> Dict[str, Any]:
        """Return progress details for a goal."""
        return {
            "goal_id": goal_id,
            "progress": self.goal_graph.get_goal_progress(goal_id),
            "task_count": len(self.goal_graph.get_goal_tasks(goal_id)),
            "dependencies": self.goal_graph.get_goal_dependencies(goal_id),
        }

    def detect_neglect(
        self,
        goal_id: str,
        *,
        now: datetime | None = None,
        neglect_days: int = 30,
    ) -> Dict[str, Any]:
        """Flag goals with no recent linked task activity."""
        if neglect_days <= 0:
            raise ValueError("neglect_days must be positive.")
        now = now or datetime.utcnow()
        last_activity = self.goal_graph.get_last_activity(goal_id)
        if last_activity is None:
            days_inactive = (now - self.goal_graph.goals[goal_id].created_at).days
        else:
            days_inactive = (now - last_activity).days
        return {
            "goal_id": goal_id,
            "days_inactive": max(0, days_inactive),
            "neglected": days_inactive >= neglect_days,
        }

    def assess_goal_risk(self, goal_id: str, *, now: datetime | None = None) -> Dict[str, Any]:
        """Return a compact risk assessment for a goal."""
        health = self.analyze_goal_health(goal_id, now=now)
        return {
            "goal_id": goal_id,
            "risk_score": health["risk_score"],
            "health_status": health["health_status"],
            "neglected": health["neglected"],
        }

    def enrich_tasks_with_goal_alignment(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add goal_alignment_score to task copies when a linked goal is known."""
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        enriched: List[Dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            task_copy = dict(task)
            goal_id = task_copy.get("goal_id")
            if isinstance(goal_id, str) and goal_id in self.goal_graph.goals:
                task_copy["goal_alignment_score"] = self._task_goal_alignment(task_copy, goal_id)
            enriched.append(task_copy)
        return enriched

    def recommend_next_best_action(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any] | None = None,
    ) -> Dict[str, Any] | None:
        """Return the task that best improves goal progress and decision score."""
        if not tasks:
            return None
        behavior_patterns = behavior_patterns or {}
        enriched = self.enrich_tasks_with_goal_alignment(tasks)
        predicted = [
            {
                "id": task.get("id"),
                "predicted_productivity": task.get("predicted_productivity", 0.0),
            }
            for task in enriched
        ]
        ranked = self.decision_engine.prioritize_tasks(enriched, predicted, behavior_patterns)
        return ranked[0] if ranked else None

    def _task_goal_alignment(self, task: Dict[str, Any], goal_id: str) -> float:
        goal = self.goal_graph.goals[goal_id]
        goal_priority = min(10.0, float(goal.priority)) * 6.0
        progress_gap = (100.0 - self.goal_graph.get_goal_progress(goal_id)) * 0.3
        task_hint = self._bounded_float(task.get("goal_alignment_score", 0.0), 0.0, 100.0)
        return round(self._bounded(goal_priority + progress_gap + (task_hint * 0.4), 0.0, 100.0), 2)

    def _deadline_pressure(self, goal: Goal, now: datetime) -> float:
        if goal.target_date is None:
            return 0.0
        hours_remaining = (goal.target_date - now).total_seconds() / 3600.0
        if hours_remaining <= 0:
            return 35.0
        if hours_remaining <= 24:
            return 28.0
        if hours_remaining <= 168:
            return 18.0
        return 5.0

    def _risk_score(self, progress: float, deadline_pressure: float, task_count: int) -> float:
        inactivity_penalty = 15.0 if task_count == 0 else 0.0
        return self._bounded((100.0 - progress) * 0.45 + deadline_pressure + inactivity_penalty, 0.0, 100.0)

    def _health_status(self, health_score: float, risk_score: float) -> str:
        if risk_score >= 70.0 or health_score < 30.0:
            return "critical"
        if risk_score >= 40.0 or health_score < 60.0:
            return "at_risk"
        return "healthy"

    def _bounded_float(self, value: Any, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return minimum
        if not math.isfinite(number):
            return minimum
        return self._bounded(number, minimum, maximum)

    def _bounded(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
