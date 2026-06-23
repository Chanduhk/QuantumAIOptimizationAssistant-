from __future__ import annotations

import math
from typing import Any, Dict, List


class DecisionEngine:
    """Rank tasks using business priority and predicted execution quality."""

    def prioritize_tasks(
        self,
        tasks: List[Dict[str, Any]],
        predicted_tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if tasks is None:
            raise ValueError("tasks must be a list of dictionaries.")
        if predicted_tasks is None:
            predicted_tasks = []
        if behavior_patterns is None:
            behavior_patterns = {}

        prediction_by_id = {
            task.get("id"): self._bounded_float(
                task.get("predicted_productivity", 0.0),
                default=0.0,
                minimum=0.0,
                maximum=100.0,
            )
            for task in predicted_tasks
            if isinstance(task, dict)
        }
        preferred_task_types = {
            str(task_type).lower() for task_type in behavior_patterns.get("preferred_task_types", [])
        }
        dominant_task_type = self._dominant_task_type(behavior_patterns)
        average_energy_level = self._optional_bounded_float(
            behavior_patterns.get("average_energy_level"),
            minimum=0.0,
            maximum=100.0,
        )

        prioritized_tasks: List[Dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            predicted_productivity = prediction_by_id.get(task.get("id"), 0.0)
            priority = self._bounded_float(task.get("priority"), default=0.0, minimum=0.0, maximum=10.0)
            duration = self._bounded_float(
                task.get("estimated_duration", task.get("actual_duration", 1.0)),
                default=1.0,
                minimum=0.0,
                maximum=24.0,
            )
            task_type = str(task.get("task_type", "")).lower()
            preferred_boost = 8.0 if task_type in preferred_task_types else 0.0
            breakdown = self._decision_breakdown(
                task=task,
                task_type=task_type,
                priority=priority,
                predicted_productivity=predicted_productivity,
                duration=duration,
                preferred_boost=preferred_boost,
                average_energy_level=average_energy_level,
                dominant_task_type=dominant_task_type,
            )
            decision_score = sum(breakdown.values())

            prioritized_task = dict(task)
            prioritized_task["predicted_productivity"] = round(predicted_productivity, 2)
            prioritized_task["decision_score"] = round(decision_score, 2)
            prioritized_task["decision_breakdown"] = {
                key: round(value, 2) for key, value in breakdown.items()
            }
            prioritized_tasks.append(prioritized_task)

        return sorted(
            prioritized_tasks,
            key=lambda task: (
                -float(task["decision_score"]),
                -float(task["decision_breakdown"].get("priority_score", 0.0)),
                str(task.get("id", "")),
                str(task.get("title", "")),
            ),
        )

    def _decision_breakdown(
        self,
        *,
        task: Dict[str, Any],
        task_type: str,
        priority: float,
        predicted_productivity: float,
        duration: float,
        preferred_boost: float,
        average_energy_level: float | None,
        dominant_task_type: str | None,
    ) -> Dict[str, float]:
        strategic_importance = self._bounded_float(
            task.get("strategic_importance"),
            default=0.0,
            minimum=0.0,
            maximum=10.0,
        )
        goal_alignment = self._bounded_float(
            task.get("goal_alignment_score"),
            default=0.0,
            minimum=0.0,
            maximum=100.0,
        )
        if goal_alignment <= 1.0:
            goal_alignment *= 100.0
        times_deferred = self._bounded_float(
            task.get("times_deferred"),
            default=0.0,
            minimum=0.0,
            maximum=10.0,
        )
        energy_requirement = self._bounded_float(
            task.get("energy_requirement"),
            default=0.0,
            minimum=0.0,
            maximum=100.0,
        )

        return {
            "priority_score": priority * 14.0,
            "productivity_score": predicted_productivity * 0.7,
            "deadline_score": self._deadline_score(task.get("deadline_hours_remaining")),
            "strategic_score": strategic_importance * 4.0,
            "goal_alignment_score": goal_alignment * 0.2,
            "dependency_score": self._bounded_float(
                task.get("dependency_score"),
                default=0.0,
                minimum=-100.0,
                maximum=100.0,
            ) * 0.3,
            "critical_path_priority": self._bounded_float(
                task.get("critical_path_priority"),
                default=0.0,
                minimum=0.0,
                maximum=100.0,
            ) * 0.2,
            "blocked_penalty": -1000.0 if task.get("blocked") is True else 0.0,
            "starvation_score": times_deferred * 2.0,
            "energy_alignment_score": self._energy_alignment_score(
                energy_requirement,
                average_energy_level,
            ),
            "preferred_task_type_score": preferred_boost,
            "context_switch_penalty": self._context_switch_penalty(task_type, dominant_task_type),
            "duration_penalty": -(duration * 1.5),
        }

    def _deadline_score(self, value: Any) -> float:
        deadline_hours = self._optional_bounded_float(value, minimum=-168.0, maximum=720.0)
        if deadline_hours is None:
            return 0.0
        if deadline_hours <= 0:
            return 30.0
        if deadline_hours <= 4:
            return 24.0
        if deadline_hours <= 24:
            return 18.0 - ((deadline_hours - 4.0) * 0.3)
        if deadline_hours <= 72:
            return max(3.0, 10.0 - ((deadline_hours - 24.0) * 0.12))
        return 0.0

    def _energy_alignment_score(
        self,
        energy_requirement: float,
        average_energy_level: float | None,
    ) -> float:
        if average_energy_level is None or energy_requirement <= 0:
            return 0.0
        difference = abs(average_energy_level - energy_requirement)
        return max(0.0, 12.0 - (difference * 0.2))

    def _context_switch_penalty(self, task_type: str, dominant_task_type: str | None) -> float:
        if not dominant_task_type or not task_type:
            return 0.0
        if task_type == dominant_task_type:
            return 0.0
        return -6.0

    def _dominant_task_type(self, behavior_patterns: Dict[str, Any]) -> str | None:
        explicit = behavior_patterns.get("current_task_type") or behavior_patterns.get("dominant_task_type")
        if explicit is None:
            return None
        normalized = str(explicit).strip().lower()
        return normalized or None

    def _optional_bounded_float(
        self,
        value: Any,
        *,
        minimum: float,
        maximum: float,
    ) -> float | None:
        if value is None:
            return None
        number = self._finite_float(value, default=None)
        if number is None:
            return None
        return max(minimum, min(maximum, number))

    def _bounded_float(
        self,
        value: Any,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        number = self._finite_float(value, default=default)
        return max(minimum, min(maximum, number))

    def _finite_float(self, value: Any, default: float | None) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        number = self._finite_float(value, default=default)
        return default if number is None else number
