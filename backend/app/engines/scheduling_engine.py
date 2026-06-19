from __future__ import annotations

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
        if tasks is None:
            raise ValueError("tasks must be a list of dictionaries.")
        if behavior_patterns is None:
            behavior_patterns = {}
        if day_start > day_end:
            raise ValueError("day_start must be less than or equal to day_end.")

        ranked_hours = self._rank_hours(behavior_patterns, day_start, day_end)
        scheduled_tasks: List[Dict[str, Any]] = []

        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            target_hour = ranked_hours[index % len(ranked_hours)]
            duration = self._safe_positive_float(
                task.get("estimated_duration", task.get("actual_duration", 1.0)),
                default=1.0,
            )
            scheduled_task = dict(task)
            scheduled_task["scheduled_hour"] = target_hour
            scheduled_task["scheduled_end_hour"] = round(target_hour + duration, 2)
            scheduled_task["schedule_score"] = round(
                float(behavior_patterns.get("hourly_productivity", {}).get(target_hour, 0.0)),
                2,
            )
            scheduled_tasks.append(scheduled_task)

        return sorted(scheduled_tasks, key=lambda task: float(task["scheduled_hour"]))

    def _rank_hours(
        self,
        behavior_patterns: Dict[str, Any],
        day_start: int,
        day_end: int,
    ) -> List[int]:
        hourly_productivity = behavior_patterns.get("hourly_productivity", {})
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

        fallback_hours = [
            parsed_hour
            for hour in behavior_patterns.get("best_focus_hours", [])
            for parsed_hour in [self._safe_hour(hour)]
            if parsed_hour is not None and day_start <= parsed_hour <= day_end
        ]

        ordered_hours: List[int] = []
        for hour in ranked + fallback_hours + list(range(day_start, day_end + 1)):
            if hour not in ordered_hours:
                ordered_hours.append(hour)

        return ordered_hours

    def _safe_hour(self, value: Any) -> int | None:
        try:
            hour = int(value)
        except (TypeError, ValueError):
            return None
        if 0 <= hour <= 23:
            return hour
        return None

    def _safe_positive_float(self, value: Any, default: float = 1.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if number <= 0:
            return default
        return number
