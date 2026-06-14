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
        ranked_hours = self._rank_hours(behavior_patterns, day_start, day_end)
        scheduled_tasks: List[Dict[str, Any]] = []

        for index, task in enumerate(tasks):
            target_hour = ranked_hours[index % len(ranked_hours)]
            duration = float(task.get("estimated_duration") or task.get("actual_duration") or 1.0)
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
                int(hour)
                for hour in hourly_productivity.keys()
                if day_start <= int(hour) <= day_end
            ),
            key=lambda hour: float(hourly_productivity.get(hour, 0.0)),
            reverse=True,
        )

        fallback_hours = [
            int(hour)
            for hour in behavior_patterns.get("best_focus_hours", [])
            if day_start <= int(hour) <= day_end
        ]

        ordered_hours: List[int] = []
        for hour in ranked + fallback_hours + list(range(day_start, day_end + 1)):
            if hour not in ordered_hours:
                ordered_hours.append(hour)

        return ordered_hours
