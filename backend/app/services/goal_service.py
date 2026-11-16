from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.goal import Goal
from backend.app.models.task import Task


SUPPORTED_GOAL_STATUSES = frozenset({"active", "completed", "paused", "archived"})


class GoalService:
    """Persistent lifecycle and progress management for user goals."""

    def __init__(self, session: Session, *, clock: Optional[Callable[[], datetime]] = None) -> None:
        if session is None:
            raise ValueError("session is required.")
        self.session = session
        self.clock = clock or (lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def create_goal(
        self,
        *,
        user_id: int,
        title: str,
        description: str = "",
        category: str = "general",
        priority: int = 1,
        target_date: Optional[datetime] = None,
        status: str = "active",
        progress: float = 0.0,
    ) -> Goal:
        """Create and persist a new goal for a user."""
        uid = self._positive_int(user_id, "user_id")
        clean_title = self._safe_text(title, "title")
        prio = self._positive_int(priority, "priority")
        clean_status = str(status or "active").strip().lower()
        if clean_status not in SUPPORTED_GOAL_STATUSES:
            raise ValueError(f"status must be one of {sorted(SUPPORTED_GOAL_STATUSES)}.")

        clean_progress = self._bounded_float(progress, "progress", 0.0, 100.0)
        now = self.clock()

        goal = Goal(
            user_id=uid,
            title=clean_title,
            description=str(description or "").strip(),
            category=str(category or "general").strip().lower(),
            priority=prio,
            target_date=self._normalize_dt(target_date),
            status=clean_status,
            progress=clean_progress,
            created_at=now,
            updated_at=now,
        )
        self.session.add(goal)
        self.session.commit()
        self.session.refresh(goal)
        return goal

    def get_goal(self, goal_id: int, user_id: Optional[int] = None) -> Goal:
        """Retrieve a single goal, enforcing user isolation if user_id is provided."""
        gid = self._positive_int(goal_id, "goal_id")
        query = self.session.query(Goal).filter(Goal.id == gid)
        if user_id is not None:
            query = query.filter(Goal.user_id == self._positive_int(user_id, "user_id"))
        goal = query.one_or_none()
        if goal is None:
            raise ValueError("Goal not found.")
        return goal

    def list_goals(self, user_id: int, status: Optional[str] = None) -> List[Goal]:
        """List all goals for a user, optionally filtered by status."""
        uid = self._positive_int(user_id, "user_id")
        query = self.session.query(Goal).filter(Goal.user_id == uid)
        if status:
            clean_status = status.strip().lower()
            if clean_status in SUPPORTED_GOAL_STATUSES:
                query = query.filter(Goal.status == clean_status)
        return query.order_by(Goal.priority.desc(), Goal.created_at.desc()).all()

    def update_goal(
        self,
        goal_id: int,
        user_id: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[int] = None,
        target_date: Optional[datetime] = None,
        status: Optional[str] = None,
        progress: Optional[float] = None,
    ) -> Goal:
        """Update fields on an existing goal with full validation."""
        goal = self.get_goal(goal_id, user_id=user_id)
        if title is not None:
            goal.title = self._safe_text(title, "title")
        if description is not None:
            goal.description = str(description).strip()
        if category is not None:
            goal.category = str(category).strip().lower()
        if priority is not None:
            goal.priority = self._positive_int(priority, "priority")
        if target_date is not None:
            goal.target_date = self._normalize_dt(target_date)
        if status is not None:
            clean_status = str(status).strip().lower()
            if clean_status not in SUPPORTED_GOAL_STATUSES:
                raise ValueError(f"status must be one of {sorted(SUPPORTED_GOAL_STATUSES)}.")
            goal.status = clean_status
        if progress is not None:
            goal.progress = self._bounded_float(progress, "progress", 0.0, 100.0)

        goal.updated_at = self.clock()
        self.session.commit()
        self.session.refresh(goal)
        return goal

    def delete_goal(self, goal_id: int, user_id: int) -> bool:
        """Delete a goal and unlink any tasks pointing to it."""
        goal = self.get_goal(goal_id, user_id=user_id)
        # Unlink associated tasks
        self.session.query(Task).filter(Task.goal_id == goal.id, Task.user_id == user_id).update({"goal_id": None})
        self.session.delete(goal)
        self.session.commit()
        return True

    def calculate_progress(self, goal_id: int, user_id: int) -> float:
        """Compute blended goal progress from manual progress and linked task completion."""
        goal = self.get_goal(goal_id, user_id=user_id)
        tasks = self.session.query(Task).filter(Task.goal_id == goal.id, Task.user_id == user_id).all()
        if not tasks:
            return round(goal.progress, 2)
        completed_count = sum(1 for t in tasks if bool(t.completed))
        task_ratio = (completed_count / len(tasks)) * 100.0
        # If manual progress was set, blend 50/50 with task completion; otherwise use task completion
        if goal.progress > 0:
            blended = (goal.progress * 0.4) + (task_ratio * 0.6)
        else:
            blended = task_ratio
        return round(min(100.0, max(0.0, blended)), 2)

    def serialize_goal(self, goal: Goal) -> Dict[str, Any]:
        """Convert a Goal instance to an API-safe dictionary."""
        tasks = self.session.query(Task).filter(Task.goal_id == goal.id, Task.user_id == goal.user_id).all()
        task_count = len(tasks)
        completed_count = sum(1 for t in tasks if bool(t.completed))
        computed_progress = self.calculate_progress(goal.id, goal.user_id)

        target_str = None
        if goal.target_date:
            target_str = goal.target_date.isoformat() if goal.target_date.tzinfo else goal.target_date.replace(tzinfo=timezone.utc).isoformat()

        created_str = None
        if goal.created_at:
            created_str = goal.created_at.isoformat() if goal.created_at.tzinfo else goal.created_at.replace(tzinfo=timezone.utc).isoformat()

        updated_str = None
        if goal.updated_at:
            updated_str = goal.updated_at.isoformat() if goal.updated_at.tzinfo else goal.updated_at.replace(tzinfo=timezone.utc).isoformat()

        return {
            "id": goal.id,
            "user_id": goal.user_id,
            "title": goal.title,
            "description": goal.description or "",
            "category": goal.category or "general",
            "priority": goal.priority,
            "target_date": target_str,
            "status": goal.status,
            "progress": computed_progress,
            "task_count": task_count,
            "completed_task_count": completed_count,
            "created_at": created_str,
            "updated_at": updated_str,
        }

    @staticmethod
    def _safe_text(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        text_val = value.strip()
        if any(ord(c) < 32 for c in text_val if c not in "\n\r\t"):
            raise ValueError(f"{field_name} cannot contain control characters.")
        return text_val

    @staticmethod
    def _positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer.")
        try:
            val = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a positive integer.") from None
        if val <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
        return val

    @staticmethod
    def _bounded_float(value: Any, field_name: str, minimum: float, maximum: float) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(val):
            raise ValueError(f"{field_name} must be finite.")
        return max(minimum, min(maximum, val))

    @staticmethod
    def _normalize_dt(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise ValueError("target_date must be a datetime.")
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
