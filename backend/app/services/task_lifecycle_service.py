from __future__ import annotations

import json
import math
import threading
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

_ENSURED_BINDS: set[int] = set()
_SCHEMA_LOCK = threading.Lock()


def is_schema_ensured(bind: Any) -> bool:
    """Return True if schema verification has already executed for this engine/bind."""
    return id(bind) in _ENSURED_BINDS


def reset_schema_ensured_cache() -> None:
    """Clear the ensured binds cache (useful for testing)."""
    with _SCHEMA_LOCK:
        _ENSURED_BINDS.clear()


class TaskLifecycleService:
    """Collect real task lifecycle data needed for future leakage-safe ML datasets."""

    def __init__(self, session: Session, *, clock: Callable[[], datetime] | None = None) -> None:
        if session is None:
            raise ValueError("session is required.")
        self.session = session
        self.clock = clock or (lambda: datetime.now(timezone.utc).replace(tzinfo=None))
        bind = session.get_bind()
        if id(bind) not in _ENSURED_BINDS:
            ensure_task_lifecycle_schema_for_bind(bind)

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
        description: str | None = None,
        deadline: datetime | None = None,
        dependencies: list[Any] | None = None,
        goal_id: int | None = None,
        context_info: str | None = None,
        created_at: datetime | None = None,
    ) -> Task:
        """Create a task with prediction-time fields and optional goal/deadline/dependency relationships."""

        uid = self._positive_int(user_id, "user_id")
        timestamp = self._timestamp(created_at, "created_at")

        validated_deadline = self._deadline(deadline)
        validated_goal_id = self._validate_goal(goal_id, uid)
        validated_deps_json = self._validate_dependencies(dependencies, current_task_id=None, user_id=uid)

        task = Task(
            user_id=uid,
            title=self._safe_text(title, "title"),
            description=str(description).strip() if description is not None else None,
            task_type=self._safe_text(task_type, "task_type"),
            priority=self._priority(priority),
            deadline=validated_deadline,
            dependencies=validated_deps_json,
            goal_id=validated_goal_id,
            context_info=str(context_info).strip() if context_info is not None else None,
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

    def update_task(
        self,
        *,
        task_id: int,
        user_id: int,
        title: str | None = None,
        description: str | None = None,
        task_type: str | None = None,
        priority: int | None = None,
        estimated_duration: float | None = None,
        estimated_duration_unit: str | None = None,
        deadline: datetime | None = None,
        dependencies: list[Any] | None = None,
        goal_id: int | None = None,
        context_info: str | None = None,
        clear_deadline: bool = False,
        clear_goal: bool = False,
        clear_dependencies: bool = False,
    ) -> Task:
        """Update fields on an existing task with user isolation and dependency cycle checks."""
        task = self._get_task(task_id=task_id, user_id=user_id)

        if title is not None:
            task.title = self._safe_text(title, "title")
        if description is not None:
            task.description = str(description).strip()
        if task_type is not None:
            task.task_type = self._safe_text(task_type, "task_type")
        if priority is not None:
            task.priority = self._priority(priority)
        if estimated_duration is not None:
            task.estimated_duration = self._positive_float(estimated_duration, "estimated_duration")
        if estimated_duration_unit is not None:
            task.estimated_duration_unit = self._duration_unit(estimated_duration_unit)

        if clear_deadline:
            task.deadline = None
        elif deadline is not None:
            task.deadline = self._deadline(deadline)

        if clear_goal:
            task.goal_id = None
        elif goal_id is not None:
            task.goal_id = self._validate_goal(goal_id, user_id)

        if clear_dependencies:
            task.dependencies = None
        elif dependencies is not None:
            task.dependencies = self._validate_dependencies(dependencies, current_task_id=task.id, user_id=user_id)

        if context_info is not None:
            task.context_info = str(context_info).strip()

        self.session.commit()
        self.session.refresh(task)
        return task

    def delete_task(self, *, task_id: int, user_id: int) -> bool:
        """Delete a task and remove references to it from other tasks' dependencies."""
        task = self._get_task(task_id=task_id, user_id=user_id)
        tid = task.id

        # Clean references in other tasks
        other_tasks = self.session.query(Task).filter(Task.user_id == user_id, Task.id != tid).all()
        for other in other_tasks:
            deps = self._parse_dependencies(other.dependencies)
            if tid in deps:
                remaining = [d for d in deps if d != tid]
                other.dependencies = json.dumps(remaining) if remaining else None

        self.session.delete(task)
        self.session.commit()
        return True

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
        focus_rating: float | None = None,
        energy_rating: float | None = None,
        productivity_rating: float | None = None,
        feedback_notes: str | None = None,
    ) -> Task:
        """Record a completed outcome and label-only actual duration with optional user feedback."""

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

        if any(v is not None for v in (focus_rating, energy_rating, productivity_rating, feedback_notes)):
            task.focus_rating = None if focus_rating is None else self._rating(focus_rating, "focus_rating")
            task.energy_rating = None if energy_rating is None else self._rating(energy_rating, "energy_rating")
            task.productivity_rating = None if productivity_rating is None else self._rating(productivity_rating, "productivity_rating")
            task.feedback_notes = None if feedback_notes is None else self._safe_text(feedback_notes, "feedback_notes")
            task.feedback_submitted_at = timestamp

        self.session.commit()
        self.session.refresh(task)
        return task

    def record_feedback(
        self,
        *,
        task_id: int,
        user_id: int | None = None,
        focus_rating: float,
        energy_rating: float,
        productivity_rating: float,
        feedback_notes: str | None = None,
        submitted_at: datetime | None = None,
    ) -> Task:
        """Record genuine user ratings (1.0 to 5.0) after task completion."""

        task = self._get_task(task_id=task_id, user_id=user_id)
        if not bool(task.completed) or task.lifecycle_state != TASK_STATE_COMPLETED:
            raise ValueError("Feedback can only be recorded for completed tasks.")
        timestamp = self._timestamp(submitted_at, "submitted_at")
        task.focus_rating = self._rating(focus_rating, "focus_rating")
        task.energy_rating = self._rating(energy_rating, "energy_rating")
        task.productivity_rating = self._rating(productivity_rating, "productivity_rating")
        task.feedback_notes = None if feedback_notes is None else self._safe_text(feedback_notes, "feedback_notes")
        task.feedback_submitted_at = timestamp
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_task(self, *, task_id: int, user_id: int | None = None) -> Task:
        """Return one task by ID, optionally scoped to a user."""

        task = self._get_task(task_id=task_id, user_id=user_id)
        if not bool(task.completed) and task.lifecycle_state != TASK_STATE_STARTED and task.start_time is not None:
            task.lifecycle_state = TASK_STATE_STARTED
            self.session.commit()
            self.session.refresh(task)
        elif bool(task.completed) and task.lifecycle_state != TASK_STATE_COMPLETED:
            task.lifecycle_state = TASK_STATE_COMPLETED
            self.session.commit()
            self.session.refresh(task)
        return task

    def get_all_tasks(self, *, user_id: int) -> list[Task]:
        """Return all tasks for a given user regardless of completion state."""
        tasks = self.session.query(Task).filter(
            Task.user_id == self._positive_int(user_id, "user_id")
        ).order_by(Task.created_at.desc()).all()
        needs_commit = False
        for t in tasks:
            if not bool(t.completed) and t.lifecycle_state != TASK_STATE_STARTED and t.start_time is not None:
                t.lifecycle_state = TASK_STATE_STARTED
                needs_commit = True
            elif bool(t.completed) and t.lifecycle_state != TASK_STATE_COMPLETED:
                t.lifecycle_state = TASK_STATE_COMPLETED
                needs_commit = True
        if needs_commit:
            self.session.commit()
        return tasks

    def serialize_task(self, task: Task) -> dict[str, Any]:
        """Return a deterministic API-safe task representation."""

        effective_lifecycle_state = task.lifecycle_state
        if bool(task.completed) or effective_lifecycle_state == TASK_STATE_COMPLETED:
            effective_lifecycle_state = TASK_STATE_COMPLETED
        elif task.start_time is not None or effective_lifecycle_state == TASK_STATE_STARTED:
            effective_lifecycle_state = TASK_STATE_STARTED
        elif not effective_lifecycle_state:
            effective_lifecycle_state = TASK_STATE_CREATED

        parsed_deps = self._parse_dependencies(task.dependencies)
        deadline_str = None
        if task.deadline is not None:
            deadline_str = task.deadline.isoformat() if task.deadline.tzinfo else task.deadline.replace(tzinfo=timezone.utc).isoformat()

        return {
            "id": task.id,
            "user_id": task.user_id,
            "title": task.title,
            "description": task.description or "",
            "task_type": task.task_type,
            "priority": task.priority,
            "deadline": deadline_str,
            "dependencies": parsed_deps,
            "goal_id": task.goal_id,
            "context_info": task.context_info or "",
            "estimated_duration": task.estimated_duration,
            "estimated_duration_unit": task.estimated_duration_unit,
            "estimated_duration_source": task.estimated_duration_source,
            "actual_duration": task.actual_duration,
            "created_at": None if task.created_at is None else (task.created_at.replace(tzinfo=timezone.utc) if task.created_at.tzinfo is None else task.created_at.astimezone(timezone.utc)).isoformat(),
            "start_time": None if task.start_time is None else (task.start_time.replace(tzinfo=timezone.utc) if task.start_time.tzinfo is None else task.start_time.astimezone(timezone.utc)).isoformat(),
            "end_time": None if task.end_time is None else (task.end_time.replace(tzinfo=timezone.utc) if task.end_time.tzinfo is None else task.end_time.astimezone(timezone.utc)).isoformat(),
            "completed": bool(task.completed),
            "lifecycle_state": effective_lifecycle_state,
            "outcome_valid": task.outcome_valid,
            "focus_rating": task.focus_rating,
            "energy_rating": task.energy_rating,
            "productivity_rating": task.productivity_rating,
            "feedback_notes": task.feedback_notes,
            "feedback_submitted_at": None if task.feedback_submitted_at is None else (task.feedback_submitted_at.replace(tzinfo=timezone.utc) if task.feedback_submitted_at.tzinfo is None else task.feedback_submitted_at.astimezone(timezone.utc)).isoformat(),
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

    def _deadline(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise ValueError("deadline must be a datetime.")
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def _validate_goal(self, goal_id: int | None, user_id: int) -> int | None:
        if goal_id is None:
            return None
        from backend.app.models.goal import Goal
        gid = self._positive_int(goal_id, "goal_id")
        goal = self.session.query(Goal).filter(Goal.id == gid, Goal.user_id == user_id).one_or_none()
        if goal is None:
            raise ValueError(f"Goal with id {gid} not found or unauthorized.")
        return goal.id

    @staticmethod
    def _parse_dependencies(raw: Any) -> list[int]:
        if not raw:
            return []
        if isinstance(raw, list):
            res = []
            for item in raw:
                try:
                    res.append(int(item))
                except (ValueError, TypeError):
                    pass
            return sorted(list(set(res)))
        if isinstance(raw, str):
            raw_str = raw.strip()
            if not raw_str:
                return []
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, list):
                    return sorted(list(set(int(x) for x in parsed if str(x).isdigit() or isinstance(x, (int, float)))))
            except Exception:
                pass
            res = []
            for part in raw_str.split(","):
                part = part.strip()
                if part.isdigit():
                    res.append(int(part))
            return sorted(list(set(res)))
        return []

    def _validate_dependencies(
        self,
        dep_input: list[Any] | None,
        *,
        current_task_id: int | None,
        user_id: int,
    ) -> str | None:
        if not dep_input:
            return None
        dep_ids = self._parse_dependencies(dep_input)
        if not dep_ids:
            return None

        clean_ids: set[int] = set()
        for did in dep_ids:
            if did <= 0:
                raise ValueError("Dependency task IDs must be positive integers.")
            if current_task_id is not None and did == current_task_id:
                raise ValueError("A task cannot depend on itself.")
            clean_ids.add(did)

        # Check all prerequisite tasks exist and belong to the same user
        existing_tasks = self.session.query(Task).filter(Task.id.in_(clean_ids), Task.user_id == user_id).all()
        found_ids = {t.id for t in existing_tasks}
        missing = clean_ids - found_ids
        if missing:
            raise ValueError(f"Prerequisite tasks not found or unauthorized: {sorted(missing)}.")

        # Cycle detection
        from backend.app.knowledge.dependency_graph import DependencyGraph
        from backend.app.domain.dependency_model import TaskDependency
        graph = DependencyGraph()

        all_user_tasks = self.session.query(Task).filter(Task.user_id == user_id).all()
        for t in all_user_tasks:
            graph.tasks.add(str(t.id))
            if current_task_id is not None and t.id == current_task_id:
                continue
            for existing_dep in self._parse_dependencies(t.dependencies):
                graph.add_dependency(
                    TaskDependency(
                        dependency_id=f"db:{t.id}:{existing_dep}",
                        task_id=str(t.id),
                        depends_on_task_id=str(existing_dep),
                        dependency_type="hard",
                    )
                )

        task_ref = str(current_task_id) if current_task_id is not None else "candidate_new_task"
        graph.tasks.add(task_ref)
        for did in clean_ids:
            graph.add_dependency(
                TaskDependency(
                    dependency_id=f"candidate:{task_ref}:{did}",
                    task_id=task_ref,
                    depends_on_task_id=str(did),
                    dependency_type="hard",
                )
            )

        cycles = graph.detect_cycles()
        if cycles:
            raise ValueError(f"Dependency cycle detected involving tasks: {cycles[0]}.")

        return json.dumps(sorted(list(clean_ids)))

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
        if any(ord(char) < 32 for char in text_value if char not in "\n\r\t"):
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

    @staticmethod
    def _rating(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be numeric.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        if not (1.0 <= number <= 5.0):
            raise ValueError(f"{field_name} must be between 1.0 and 5.0.")
        return round(number, 2)


def ensure_task_lifecycle_schema(session: Session, force: bool = False) -> None:
    """Add missing nullable lifecycle columns for existing Task tables without data reset."""

    bind = session.get_bind()
    ensure_task_lifecycle_schema_for_bind(bind, force=force)


def ensure_task_lifecycle_schema_for_bind(bind: Any, force: bool = False) -> None:
    """Add missing nullable lifecycle columns for a SQLAlchemy bind."""
    bind_id = id(bind)
    if not force and bind_id in _ENSURED_BINDS:
        return

    with _SCHEMA_LOCK:
        if not force and bind_id in _ENSURED_BINDS:
            return

        inspector = inspect(bind)
        table_names = inspector.get_table_names()
        if "tasks" not in table_names or "goals" not in table_names:
            Base.metadata.create_all(bind=bind)
            inspector = inspect(bind)
            table_names = inspector.get_table_names()
            if "tasks" not in table_names:
                _ENSURED_BINDS.add(bind_id)
                return

        existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
        missing = [
            (name, ddl)
            for name, ddl in (
                ("description", "VARCHAR(1000)"),
                ("deadline", "DATETIME"),
                ("dependencies", "VARCHAR(500)"),
                ("goal_id", "INTEGER"),
                ("context_info", "VARCHAR(1000)"),
                ("created_at", "DATETIME"),
                ("lifecycle_state", "VARCHAR(32)"),
                ("outcome_valid", "BOOLEAN"),
                ("estimated_duration_unit", "VARCHAR(16)"),
                ("estimated_duration_source", "VARCHAR(64)"),
                ("focus_rating", "FLOAT"),
                ("energy_rating", "FLOAT"),
                ("productivity_rating", "FLOAT"),
                ("feedback_notes", "VARCHAR(1000)"),
                ("feedback_submitted_at", "DATETIME"),
            )
            if name not in existing_columns
        ]
        if missing:
            dialect = getattr(bind, "dialect", None)
            dialect_name = dialect.name if dialect else "sqlite"
            with bind.begin() as connection:
                for column_name, column_type in missing:
                    if dialect_name == "postgresql":
                        connection.execute(text(f"ALTER TABLE tasks ADD COLUMN IF NOT EXISTS {column_name} {column_type}"))
                    else:
                        connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_type}"))

        _ENSURED_BINDS.add(bind_id)
