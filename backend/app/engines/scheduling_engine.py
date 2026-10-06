from __future__ import annotations

from backend.app.domain.optimization_input_contract import normalize_duration

import math
from typing import Any, Dict, List


class SchedulingEngine:
    """Assign tasks to time slots that align with the user's behavior profile."""

    def optimize_schedule(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        day_start: int = 8,
        day_end: int = 20,
    ) -> List[Dict[str, Any]]:
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        if not self._is_integer_hour(day_start) or not self._is_integer_hour(day_end):
            raise ValueError("day_start and day_end must be integer hours.")
        if day_start >= day_end:
            raise ValueError("day_start must be less than day_end.")

        hourly_productivity = self._normalize_hourly_productivity(
            behavior_patterns.get("hourly_productivity", {}),
        )
        ranked_hours = self._rank_hours(behavior_patterns, hourly_productivity, day_start, day_end)
        scheduled_tasks: List[Dict[str, Any]] = []

        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            target_hour = ranked_hours[index % len(ranked_hours)]
            duration = self._resolve_duration(task)
            scheduled_end_hour = round(target_hour + duration, 2)
            scheduled_task = dict(task)
            scheduled_task["scheduled_hour"] = target_hour
            scheduled_task["scheduled_end_hour"] = scheduled_end_hour
            scheduled_task["schedule_score"] = round(hourly_productivity.get(target_hour, 0.0), 2)
            if scheduled_end_hour > day_end:
                scheduled_task["schedule_warning"] = "scheduled_end_hour exceeds day_end."
                scheduled_task["capacity_warning"] = (
                    f"Task extends beyond scheduling window ending at hour {day_end}."
                )
            scheduled_tasks.append(scheduled_task)

        return sorted(scheduled_tasks, key=lambda task: float(task["scheduled_hour"]))

    def _rank_hours(
        self,
        behavior_patterns: Dict[str, Any],
        hourly_productivity: Dict[int, float],
        day_start: int,
        day_end: int,
    ) -> List[int]:
        ranked = sorted(
            (
                parsed_hour
                for hour in hourly_productivity.keys()
                for parsed_hour in [self._safe_hour(hour)]
                if parsed_hour is not None and day_start <= parsed_hour <= day_end
            ),
            key=lambda hour: float(hourly_productivity.get(hour, 0.0)),
            reverse=True,
        )

        best_focus_hours = behavior_patterns.get("best_focus_hours", [])
        if best_focus_hours is None:
            best_focus_hours = []
        if not isinstance(best_focus_hours, list):
            raise ValueError("best_focus_hours must be a list of integer hours.")

        fallback_hours: List[int] = []
        for hour in best_focus_hours:
            parsed_hour = self._safe_hour(hour)
            if parsed_hour is None:
                raise ValueError("best_focus_hours must contain integer hours from 0 to 23.")
            if day_start <= parsed_hour <= day_end:
                fallback_hours.append(parsed_hour)

        ordered_hours: List[int] = []
        for hour in ranked + fallback_hours + list(range(day_start, day_end + 1)):
            if hour not in ordered_hours:
                ordered_hours.append(hour)

        return ordered_hours

    def _safe_hour(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            hour = value
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped or not stripped.isdigit():
                return None
            hour = int(stripped)
        else:
            return None
        if 0 <= hour <= 23:
            return hour
        return None

    def _normalize_hourly_productivity(self, hourly_productivity: Any) -> Dict[int, float]:
        if hourly_productivity is None:
            return {}
        if not isinstance(hourly_productivity, dict):
            raise ValueError("hourly_productivity must be a dictionary.")

        normalized: Dict[int, float] = {}
        for hour, score in hourly_productivity.items():
            parsed_hour = self._safe_hour(hour)
            if parsed_hour is None:
                raise ValueError("hourly_productivity hours must be integer hours from 0 to 23.")
            normalized[parsed_hour] = self._finite_float(
                score,
                field_name="hourly_productivity scores",
            )
        return normalized

    def _resolve_duration(self, task: Dict[str, Any]) -> float:
        if task.get("estimated_duration") is None:
            raise ValueError("estimated_duration is required for forward scheduling.")
        duration_unit = task.get("estimated_duration_unit")
        duration_source = task.get("estimated_duration_source")
        if duration_unit is None or duration_source is None:
            raise ValueError("explicit estimated duration unit and source are required.")
        return normalize_duration(task["estimated_duration"], duration_unit, duration_source).normalized_hours

    def _positive_finite_float(self, value: Any, field_name: str) -> float:
        number = self._finite_float(value, field_name=field_name)
        if number <= 0:
            raise ValueError(f"{field_name} must be positive.")
        return number

    def _finite_float(self, value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return number

    def _is_integer_hour(self, value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 23
