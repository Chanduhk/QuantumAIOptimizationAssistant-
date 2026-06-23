from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Goal:
    """In-memory domain model for a long-term objective."""

    goal_id: str
    title: str
    description: str = ""
    priority: int = 1
    target_date: Optional[datetime] = None
    status: str = "active"
    progress: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise ValueError("goal_id must be a non-empty string.")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string.")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority <= 0:
            raise ValueError("priority must be a positive integer.")
        self.progress = _bounded_float(self.progress, "progress", 0.0, 100.0)
        self.status = str(self.status or "active").strip().lower()


@dataclass
class Milestone:
    """In-memory domain model for a milestone within a goal."""

    milestone_id: str
    goal_id: str
    title: str
    progress: float = 0.0
    status: str = "active"

    def __post_init__(self) -> None:
        if not isinstance(self.milestone_id, str) or not self.milestone_id.strip():
            raise ValueError("milestone_id must be a non-empty string.")
        if not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise ValueError("goal_id must be a non-empty string.")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string.")
        self.progress = _bounded_float(self.progress, "progress", 0.0, 100.0)
        self.status = str(self.status or "active").strip().lower()


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{field_name} must be finite.")
    return max(minimum, min(maximum, number))
