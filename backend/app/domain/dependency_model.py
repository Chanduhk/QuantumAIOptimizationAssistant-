from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_DEPENDENCY_TYPES = {"hard", "soft", "recommended"}


@dataclass(frozen=True)
class TaskDependency:
    """In-memory domain model for a task-to-task dependency."""

    dependency_id: str
    task_id: str
    depends_on_task_id: str
    dependency_type: str = "hard"

    def __post_init__(self) -> None:
        if not isinstance(self.dependency_id, str) or not self.dependency_id.strip():
            raise ValueError("dependency_id must be a non-empty string.")
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string.")
        if not isinstance(self.depends_on_task_id, str) or not self.depends_on_task_id.strip():
            raise ValueError("depends_on_task_id must be a non-empty string.")
        if self.task_id == self.depends_on_task_id:
            raise ValueError("A task cannot depend on itself.")
        normalized_type = str(self.dependency_type or "hard").strip().lower()
        if normalized_type not in SUPPORTED_DEPENDENCY_TYPES:
            raise ValueError("dependency_type must be hard, soft, or recommended.")
        object.__setattr__(self, "dependency_id", self.dependency_id.strip())
        object.__setattr__(self, "task_id", self.task_id.strip())
        object.__setattr__(self, "depends_on_task_id", self.depends_on_task_id.strip())
        object.__setattr__(self, "dependency_type", normalized_type)
