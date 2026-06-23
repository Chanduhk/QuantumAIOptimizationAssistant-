from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.goal_model import Goal, Milestone


class GoalGraph:
    """Deterministic in-memory graph for goals, milestones, dependencies, and task links."""

    def __init__(self) -> None:
        self.goals: Dict[str, Goal] = {}
        self.milestones: Dict[str, Milestone] = {}
        self.goal_tasks: Dict[str, List[Dict[str, Any]]] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.activity_log: Dict[str, List[datetime]] = {}

    def add_goal(self, goal: Goal | Dict[str, Any]) -> Goal:
        """Add or replace a goal."""
        goal_obj = goal if isinstance(goal, Goal) else Goal(**goal)
        self.goals[goal_obj.goal_id] = goal_obj
        self.goal_tasks.setdefault(goal_obj.goal_id, [])
        self.dependencies.setdefault(goal_obj.goal_id, [])
        self.activity_log.setdefault(goal_obj.goal_id, [])
        return goal_obj

    def add_milestone(self, milestone: Milestone | Dict[str, Any]) -> Milestone:
        """Add or replace a milestone for an existing goal."""
        milestone_obj = milestone if isinstance(milestone, Milestone) else Milestone(**milestone)
        if milestone_obj.goal_id not in self.goals:
            raise ValueError("Cannot add milestone for unknown goal.")
        self.milestones[milestone_obj.milestone_id] = milestone_obj
        return milestone_obj

    def add_dependency(self, goal_id: str, depends_on_goal_id: str) -> None:
        """Declare that a goal depends on another goal."""
        self._require_goal(goal_id)
        self._require_goal(depends_on_goal_id)
        dependencies = self.dependencies.setdefault(goal_id, [])
        if depends_on_goal_id not in dependencies:
            dependencies.append(depends_on_goal_id)
            dependencies.sort()

    def link_task_to_goal(
        self,
        task: Dict[str, Any],
        goal_id: str,
        *,
        activity_at: datetime | None = None,
    ) -> Dict[str, Any]:
        """Attach a task snapshot to a goal."""
        self._require_goal(goal_id)
        if not isinstance(task, dict):
            raise ValueError("task must be a dictionary.")
        task_copy = dict(task)
        task_copy["goal_id"] = goal_id
        self.goal_tasks.setdefault(goal_id, []).append(task_copy)
        self.activity_log.setdefault(goal_id, []).append(activity_at or datetime.utcnow())
        return task_copy

    def get_goal_tasks(self, goal_id: str) -> List[Dict[str, Any]]:
        """Return task snapshots linked to a goal."""
        self._require_goal(goal_id)
        return [dict(task) for task in self.goal_tasks.get(goal_id, [])]

    def get_goal_progress(self, goal_id: str) -> float:
        """Return blended goal progress from goal and milestone progress."""
        goal = self._require_goal(goal_id)
        milestones = [milestone for milestone in self.milestones.values() if milestone.goal_id == goal_id]
        if not milestones:
            return round(goal.progress, 2)
        milestone_average = sum(milestone.progress for milestone in milestones) / len(milestones)
        return round((goal.progress * 0.5) + (milestone_average * 0.5), 2)

    def get_goal_dependencies(self, goal_id: str) -> List[str]:
        """Return dependency goal ids for a goal."""
        self._require_goal(goal_id)
        return list(self.dependencies.get(goal_id, []))

    def get_last_activity(self, goal_id: str) -> datetime | None:
        """Return most recent activity timestamp for a goal."""
        self._require_goal(goal_id)
        entries = self.activity_log.get(goal_id, [])
        return max(entries) if entries else None

    def goal_snapshots(self) -> List[Dict[str, Any]]:
        """Return deterministic goal dictionaries for reporting."""
        return [
            {
                **asdict(self.goals[goal_id]),
                "progress": self.get_goal_progress(goal_id),
                "task_count": len(self.goal_tasks.get(goal_id, [])),
                "dependencies": self.get_goal_dependencies(goal_id),
            }
            for goal_id in sorted(self.goals)
        ]

    def _require_goal(self, goal_id: str) -> Goal:
        if goal_id not in self.goals:
            raise ValueError(f"Unknown goal_id: {goal_id}")
        return self.goals[goal_id]
