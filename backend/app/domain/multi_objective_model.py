from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class OptimizationObjective:
    """Weighted objective used to score simulated futures."""

    objective_name: str
    weight: float
    description: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.objective_name, str) or not self.objective_name.strip():
            raise ValueError("objective_name must be a non-empty string.")
        self.objective_name = self.objective_name.strip()
        self.weight = _bounded_float(self.weight, "weight", 0.0, 100.0)
        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean.")


@dataclass
class OptimizationResult:
    """Selected future and scoring details from multi-objective optimization."""

    selected_scenario_id: str
    selected_scenario_name: str
    overall_score: float
    objective_scores: Dict[str, float]
    tradeoffs: List[str]
    recommendations: List[str]
    optimization_summary: Dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.selected_scenario_id, str) or not self.selected_scenario_id.strip():
            raise ValueError("selected_scenario_id must be a non-empty string.")
        if not isinstance(self.selected_scenario_name, str) or not self.selected_scenario_name.strip():
            raise ValueError("selected_scenario_name must be a non-empty string.")
        self.overall_score = _bounded_float(self.overall_score, "overall_score", 0.0, 100.0)
        if not isinstance(self.objective_scores, dict):
            raise ValueError("objective_scores must be a dictionary.")
        self.objective_scores = {
            str(name): _bounded_float(score, "objective_score", 0.0, 100.0)
            for name, score in self.objective_scores.items()
        }
        if not isinstance(self.tradeoffs, list) or any(not isinstance(tradeoff, str) for tradeoff in self.tradeoffs):
            raise ValueError("tradeoffs must be a list of strings.")
        if not isinstance(self.recommendations, list) or any(
            not isinstance(recommendation, str) for recommendation in self.recommendations
        ):
            raise ValueError("recommendations must be a list of strings.")
        if not isinstance(self.optimization_summary, dict):
            raise ValueError("optimization_summary must be a dictionary.")


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return max(minimum, min(maximum, number))
