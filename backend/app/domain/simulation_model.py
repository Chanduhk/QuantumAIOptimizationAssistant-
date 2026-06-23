from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class SimulationScenario:
    """In-memory description of a deterministic future-state simulation."""

    scenario_id: str
    scenario_name: str
    horizon_days: int
    goal_ids: List[str]
    task_ids: List[str]
    assumptions: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string.")
        if not isinstance(self.scenario_name, str) or not self.scenario_name.strip():
            raise ValueError("scenario_name must be a non-empty string.")
        if not isinstance(self.horizon_days, int) or isinstance(self.horizon_days, bool) or self.horizon_days <= 0:
            raise ValueError("horizon_days must be a positive integer.")
        if not isinstance(self.goal_ids, list) or any(not isinstance(goal_id, str) for goal_id in self.goal_ids):
            raise ValueError("goal_ids must be a list of strings.")
        if not isinstance(self.task_ids, list) or any(not isinstance(task_id, str) for task_id in self.task_ids):
            raise ValueError("task_ids must be a list of strings.")
        if not isinstance(self.assumptions, dict):
            raise ValueError("assumptions must be a dictionary.")
        self.scenario_id = self.scenario_id.strip()
        self.scenario_name = self.scenario_name.strip()
        self.goal_ids = sorted(set(self.goal_ids))
        self.task_ids = sorted(set(self.task_ids))


@dataclass
class SimulationResult:
    """Deterministic outcome estimate for a simulation scenario."""

    scenario_id: str
    success_probability: float
    goal_completion_probability: float
    milestone_completion_probability: float
    workload_score: float
    risk_score: float
    confidence_score: float
    projected_state: Dict[str, Any]
    recommendations: List[str]

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string.")
        self.success_probability = _bounded_float(self.success_probability, "success_probability", 0.0, 1.0)
        self.goal_completion_probability = _bounded_float(
            self.goal_completion_probability,
            "goal_completion_probability",
            0.0,
            1.0,
        )
        self.milestone_completion_probability = _bounded_float(
            self.milestone_completion_probability,
            "milestone_completion_probability",
            0.0,
            1.0,
        )
        self.workload_score = _bounded_float(self.workload_score, "workload_score", 0.0, 100.0)
        self.risk_score = _bounded_float(self.risk_score, "risk_score", 0.0, 100.0)
        self.confidence_score = _bounded_float(self.confidence_score, "confidence_score", 0.0, 100.0)
        if not isinstance(self.projected_state, dict):
            raise ValueError("projected_state must be a dictionary.")
        if not isinstance(self.recommendations, list) or any(
            not isinstance(recommendation, str) for recommendation in self.recommendations
        ):
            raise ValueError("recommendations must be a list of strings.")


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return max(minimum, min(maximum, number))
