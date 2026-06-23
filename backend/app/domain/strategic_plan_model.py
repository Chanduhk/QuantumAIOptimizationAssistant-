from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class RoadmapItem:
    """A single ordered item in a strategic roadmap."""

    sequence: int
    goal_id: Optional[str]
    milestone_id: Optional[str]
    task_id: Optional[str]
    recommended_start_day: int
    recommended_end_day: int
    priority_score: float
    risk_score: float

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence <= 0:
            raise ValueError("sequence must be a positive integer.")
        if not isinstance(self.recommended_start_day, int) or self.recommended_start_day < 1:
            raise ValueError("recommended_start_day must be a positive integer.")
        if not isinstance(self.recommended_end_day, int) or self.recommended_end_day < self.recommended_start_day:
            raise ValueError("recommended_end_day must be greater than or equal to recommended_start_day.")
        self.priority_score = _bounded_float(self.priority_score, "priority_score", 0.0, 100.0)
        self.risk_score = _bounded_float(self.risk_score, "risk_score", 0.0, 100.0)


@dataclass
class StrategicPlan:
    """In-memory long-horizon plan for goals, milestones, tasks, and dependencies."""

    plan_id: str
    horizon_days: int
    goal_ids: List[str]
    milestone_ids: List[str]
    risk_score: float
    confidence_score: float
    roadmap_items: List[RoadmapItem | Dict[str, Any]]
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise ValueError("plan_id must be a non-empty string.")
        if not isinstance(self.horizon_days, int) or isinstance(self.horizon_days, bool) or self.horizon_days <= 0:
            raise ValueError("horizon_days must be a positive integer.")
        if not isinstance(self.goal_ids, list) or any(not isinstance(goal_id, str) for goal_id in self.goal_ids):
            raise ValueError("goal_ids must be a list of strings.")
        if not isinstance(self.milestone_ids, list) or any(
            not isinstance(milestone_id, str) for milestone_id in self.milestone_ids
        ):
            raise ValueError("milestone_ids must be a list of strings.")
        self.risk_score = _bounded_float(self.risk_score, "risk_score", 0.0, 100.0)
        self.confidence_score = _bounded_float(self.confidence_score, "confidence_score", 0.0, 100.0)
        self.goal_ids = sorted(set(self.goal_ids))
        self.milestone_ids = sorted(set(self.milestone_ids))
        self.roadmap_items = [
            item if isinstance(item, RoadmapItem) else RoadmapItem(**item)
            for item in self.roadmap_items
        ]


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return max(minimum, min(maximum, number))
