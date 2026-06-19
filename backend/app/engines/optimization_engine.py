from __future__ import annotations

from typing import Any, Dict, List


class OptimizationEngine:
    """Re-map scheduled tasks to maximize productivity-weighted output."""

    def optimize_schedule(
        self,
        scheduled_tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        if scheduled_tasks is None:
            raise ValueError("scheduled_tasks must be a list of dictionaries.")
        if behavior_patterns is None:
            behavior_patterns = {}
        if not scheduled_tasks:
            return {"optimized_schedule": [], "projected_productivity_gain": 0.0}

        hourly_productivity = {
            int(hour): self._safe_float(score)
            for hour, score in behavior_patterns.get("hourly_productivity", {}).items()
            if self._safe_hour(hour) is not None
        }
        ranked_hours = sorted(
            {
                self._safe_hour(task.get("scheduled_hour", 10)) or 10
                for task in scheduled_tasks
                if isinstance(task, dict)
            },
            key=lambda hour: hourly_productivity.get(hour, 0.0),
            reverse=True,
        )
        ranked_tasks = sorted(
            self._validate_tasks(scheduled_tasks),
            key=lambda task: self._safe_float(task.get("predicted_productivity", 0.0)),
            reverse=True,
        )

        optimized_schedule: List[Dict[str, Any]] = []
        baseline_score = 0.0
        optimized_score = 0.0

        for index, task in enumerate(ranked_tasks):
            selected_hour = ranked_hours[index % len(ranked_hours)]
            duration = self._safe_positive_float(
                task.get("estimated_duration", task.get("actual_duration", 1.0)),
                default=1.0,
            )
            optimized_task = dict(task)
            optimized_task["optimized_hour"] = selected_hour
            optimized_task["optimized_end_hour"] = round(selected_hour + duration, 2)
            optimized_task["hour_productivity_score"] = round(hourly_productivity.get(selected_hour, 0.0), 2)
            optimized_schedule.append(optimized_task)

            baseline_score += self._safe_float(task.get("schedule_score", 0.0))
            optimized_score += self._safe_float(optimized_task.get("hour_productivity_score", 0.0))

        optimized_schedule.sort(key=lambda task: float(task["optimized_hour"]))
        projected_gain = round(optimized_score - baseline_score, 2)

        return {
            "optimized_schedule": optimized_schedule,
            "projected_productivity_gain": projected_gain,
        }

    def _validate_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        validated_tasks: List[Dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Each scheduled task must be a dictionary.")
            validated_tasks.append(task)
        return validated_tasks

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_positive_float(self, value: Any, default: float = 1.0) -> float:
        number = self._safe_float(value, default=default)
        return number if number > 0 else default

    def _safe_hour(self, value: Any) -> int | None:
        try:
            hour = int(value)
        except (TypeError, ValueError):
            return None
        if 0 <= hour <= 23:
            return hour
        return None
