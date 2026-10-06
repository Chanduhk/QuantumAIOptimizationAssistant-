from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from backend.app.models.behavior_data import BehaviorData as _BehaviorData
from backend.app.models.base import Base
from backend.app.models.task import Task


TASK_STATE_CREATED = "created"
TASK_STATE_STARTED = "started"
TASK_STATE_COMPLETED = "completed"
SUPPORTED_STATES = frozenset({TASK_STATE_CREATED, TASK_STATE_STARTED, TASK_STATE_COMPLETED})
ACTUAL_DURATION_TOLERANCE_MINUTES = 1e-6


class TaskLifecycleService:
    """Collect real task lifecycle data needed for future leakage-safe ML datasets."""

    def __init__(self, session: Session, *, clock: Callable[[], datetime] | None = None) -> None:
        if session is None:
            raise ValueError("session is required.")
        self.session = session
        self.clock = clock or (lambda: datetime.now(timezone.utc).replace(tzinfo=None))
        ensure_task_lifecycle_schema(session)

    def create_task(
        self,
        *,
        user_id: int,
        title: str,
        task_type: str,
        priority: int,
        estimated_duration: float,
        estimated_duration_unit: str = "minutes",
        estimated_duration_source: str = "task_api",
        created_at: datetime | None = None,
    ) -> Task:
        """Create a task with prediction-time fields only."""

        timestamp = self._timestamp(created_at, "created_at")
        task = Task(
            user_id=self._positive_int(user_id, "user_id"),
            title=self._safe_text(title, "title"),
            task_type=self._safe_text(task_type, "task_type"),
            priority=self._priority(priority),
            estimated_duration=self._positive_float(estimated_duration, "estimated_duration"),
            estimated_duration_unit=self._duration_unit(estimated_duration_unit),
            estimated_duration_source=self._safe_text(estimated_duration_source, "estimated_duration_source"),
            actual_duration=None,
            start_time=None,
            end_time=None,
            completed=False,
            created_at=timestamp,
            lifecycle_state=TASK_STATE_CREATED,
            outcome_valid=None,
        )
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def start_task(self, *, task_id: int, user_id: int | None = None, started_at: datetime | None = None) -> Task:
        """Mark a created task as started while preserving prediction-time chronology."""

        task = self._get_task(task_id=task_id, user_id=user_id)
        if bool(task.completed) or task.lifecycle_state == TASK_STATE_COMPLETED:
            raise ValueError("completed task cannot be started.")
        if task.start_time is not None:
            raise ValueError("task has already been started.")
        timestamp = self._timestamp(started_at, "started_at")
        created_at = self._created_at(task)
        if timestamp < created_at:
            raise ValueError("started_at cannot be before created_at.")
        task.start_time = timestamp
        task.lifecycle_state = TASK_STATE_STARTED
        self.session.commit()
        self.session.refresh(task)
        return task

    def complete_task(
        self,
        *,
        task_id: int,
        user_id: int | None = None,
        completed_at: datetime | None = None,
        actual_duration: float | None = None,
    ) -> Task:
        """Record a completed outcome and label-only actual duration."""

        task = self._get_task(task_id=task_id, user_id=user_id)
        if bool(task.completed) or task.lifecycle_state == TASK_STATE_COMPLETED:
            raise ValueError("task has already been completed.")
        if task.start_time is None:
            raise ValueError("task must be started before completion.")
        timestamp = self._timestamp(completed_at, "completed_at")
        if timestamp <= task.start_time:
            raise ValueError("completed_at must be after start_time.")
        derived_duration = (timestamp - task.start_time).total_seconds() / 60.0
        if derived_duration <= 0 or not math.isfinite(derived_duration):
            raise ValueError("derived actual duration must be positive and finite.")
        if actual_duration is None:
            stored_duration = derived_duration
        else:
            stored_duration = self._positive_float(actual_duration, "actual_duration")
            if abs(stored_duration - derived_duration) > ACTUAL_DURATION_TOLERANCE_MINUTES:
                raise ValueError("actual_duration conflicts with start_time/completed_at duration.")
        task.actual_duration = stored_duration
        task.end_time = timestamp
        task.completed = True
        task.lifecycle_state = TASK_STATE_COMPLETED
        task.outcome_valid = True
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_task(self, *, task_id: int, user_id: int | None = None) -> Task:
        """Return one task by ID, optionally scoped to a user."""

        return self._get_task(task_id=task_id, user_id=user_id)

    def get_all_tasks(self, *, user_id: int) -> list[Task]:
        """Return all tasks for a given user regardless of completion state."""
        return self.session.query(Task).filter(
            Task.user_id == self._positive_int(user_id, "user_id")
        ).order_by(Task.created_at.desc()).all()

    def serialize_task(self, task: Task) -> dict[str, Any]:
        """Return a deterministic API-safe task representation."""

        return {
            "id": task.id,
            "user_id": task.user_id,
            "title": task.title,
            "task_type": task.task_type,
            "priority": task.priority,
            "estimated_duration": task.estimated_duration,
            "estimated_duration_unit": task.estimated_duration_unit,
            "estimated_duration_source": task.estimated_duration_source,
            "actual_duration": task.actual_duration,
            "created_at": None if task.created_at is None else task.created_at.isoformat(),
            "start_time": None if task.start_time is None else task.start_time.isoformat(),
            "end_time": None if task.end_time is None else task.end_time.isoformat(),
            "completed": bool(task.completed),
            "lifecycle_state": task.lifecycle_state,
            "outcome_valid": task.outcome_valid,
        }

    def _get_task(self, *, task_id: int, user_id: int | None) -> Task:
        query = self.session.query(Task).filter(Task.id == self._positive_int(task_id, "task_id"))
        if user_id is not None:
            query = query.filter(Task.user_id == self._positive_int(user_id, "user_id"))
        task = query.one_or_none()
        if task is None:
            raise ValueError("task not found.")
        return task

    def _timestamp(self, value: datetime | None, field_name: str) -> datetime:
        timestamp = self.clock() if value is None else value
        if not isinstance(timestamp, datetime):
            raise ValueError(f"{field_name} must be a datetime.")
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        return timestamp

    def _created_at(self, task: Task) -> datetime:
        if task.created_at is not None:
            return task.created_at
        if task.start_time is not None:
            return task.start_time
        raise ValueError("task.created_at is required before starting.")

    @staticmethod
    def _safe_text(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        text_value = value.strip()
        if any(ord(char) < 32 for char in text_value):
            raise ValueError(f"{field_name} cannot contain control characters.")
        return text_value

    @staticmethod
    def _positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer.")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a positive integer.") from None
        if number <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
        return number

    @classmethod
    def _priority(cls, value: Any) -> int:
        priority = cls._positive_int(value, "priority")
        if priority > 5:
            raise ValueError("priority must be between 1 and 5.")
        return priority

    @staticmethod
    def _duration_unit(value: str) -> str:
        if value not in {"minutes", "hours"}:
            raise ValueError("estimated_duration_unit must be 'minutes' or 'hours'.")
        return value

    @staticmethod
    def _positive_float(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be numeric.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        if number <= 0:
            raise ValueError(f"{field_name} must be positive.")
        return number


def ensure_task_lifecycle_schema(session: Session) -> None:
    """Add missing nullable lifecycle columns for existing Task tables without data reset."""

    bind = session.get_bind()
    ensure_task_lifecycle_schema_for_bind(bind)


def ensure_task_lifecycle_schema_for_bind(bind: Any) -> None:
    """Add missing nullable lifecycle columns for a SQLAlchemy bind."""

    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)
    if "tasks" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    missing = [
        (name, ddl)
        for name, ddl in (
            ("created_at", "DATETIME"),
            ("lifecycle_state", "VARCHAR(32)"),
            ("outcome_valid", "BOOLEAN"),
            ("estimated_duration_unit", "VARCHAR(16)"),
            ("estimated_duration_source", "VARCHAR(64)"),
        )
        if name not in existing_columns
    ]
    if not missing:
        return

    dialect = bind.dialect.name
    with bind.begin() as connection:
        for column_name, column_type in missing:
            if dialect == "postgresql":
                connection.execute(text(f"ALTER TABLE tasks ADD COLUMN IF NOT EXISTS {column_name} {column_type}"))
            else:
                connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_type}"))
