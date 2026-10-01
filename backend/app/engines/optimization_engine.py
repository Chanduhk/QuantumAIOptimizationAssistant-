from __future__ import annotations

import math
from typing import Any, Dict, List


class OptimizationEngine:
    """Re-map scheduled tasks to maximize productivity-weighted output."""

    def optimize_schedule(
        self,
        scheduled_tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(scheduled_tasks, list):
            raise ValueError("scheduled_tasks must be a list of dictionaries.")
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        if not scheduled_tasks:
            return {"optimized_schedule": [], "projected_productivity_gain": 0.0}

        hourly_productivity = self._normalize_hourly_productivity(
            behavior_patterns.get("hourly_productivity", {}),
        )
        validated_tasks = self._validate_tasks(scheduled_tasks)
        ranked_hours = sorted(
            {
                self._resolve_scheduled_hour(task)
                for task in validated_tasks
            },
            key=lambda hour: (-hourly_productivity.get(hour, 0.0), hour),
        )
        ranked_tasks = sorted(
            validated_tasks,
            key=lambda task: (
                -self._optional_finite_float(
                    task,
                    "predicted_productivity",
                    default=0.0,
                    field_name="predicted_productivity",
                ),
                str(task.get("id", "")),
            ),
        )
        schedule_window_end = max(ranked_hours)

        optimized_schedule: List[Dict[str, Any]] = []
        baseline_score = 0.0
        optimized_score = 0.0

        for index, task in enumerate(ranked_tasks):
            selected_hour = ranked_hours[index % len(ranked_hours)]
            duration = self._resolve_duration(task)
            optimized_end_hour = round(selected_hour + duration, 2)
            optimized_task = dict(task)
            optimized_task["optimized_hour"] = selected_hour
            optimized_task["optimized_end_hour"] = optimized_end_hour
            # Hourly productivity lookup requires an integer hour key.
            optimized_task["hour_productivity_score"] = round(hourly_productivity.get(int(selected_hour), 0.0), 2)
            if optimized_end_hour > schedule_window_end:
                optimized_task["optimized_schedule_warning"] = "optimized_end_hour exceeds scheduling window."
                optimized_task["capacity_warning"] = (
                    f"Task extends beyond optimized scheduling window ending at hour {schedule_window_end}."
                )
            optimized_schedule.append(optimized_task)

            baseline_score += self._optional_finite_float(
                task,
                "schedule_score",
                default=0.0,
                field_name="schedule_score",
            )
            optimized_score += self._finite_float(
                optimized_task.get("hour_productivity_score", 0.0),
                field_name="hour_productivity_score",
            )

        optimized_schedule.sort(
            key=lambda task: (
                float(task["optimized_hour"]),
                str(task.get("id", "")),
            ),
        )
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
            self._resolve_scheduled_hour(task)
            self._resolve_duration(task)
            self._optional_finite_float(
                task,
                "predicted_productivity",
                default=0.0,
                field_name="predicted_productivity",
            )
            self._optional_finite_float(
                task,
                "schedule_score",
                default=0.0,
                field_name="schedule_score",
            )
            validated_tasks.append(task)
        return validated_tasks

    def _normalize_hourly_productivity(self, hourly_productivity: Any) -> Dict[int, float]:
        if hourly_productivity is None:
            return {}
        if not isinstance(hourly_productivity, dict):
            raise ValueError("hourly_productivity must be a dictionary.")

        normalized: Dict[float, float] = {}
        for hour, score in hourly_productivity.items():
            parsed_hour = self._safe_hour(hour)
            if parsed_hour is None:
                raise ValueError("hourly_productivity hours must be hours from 0 to 24.")
            normalized[parsed_hour] = self._finite_float(
                score,
                field_name="hourly_productivity scores",
            )
        return normalized

    def _resolve_scheduled_hour(self, task: Dict[str, Any]) -> float:
        if task.get("scheduled_hour") is None:
            return 10.0
        hour = self._safe_hour(task.get("scheduled_hour"))
        if hour is None:
            raise ValueError("scheduled_hour must be an hour from 0 to 24.")
        return hour

    def _resolve_duration(self, task: Dict[str, Any]) -> float:
        if task.get("estimated_duration") is not None:
            raw_duration = task["estimated_duration"]
        elif task.get("actual_duration") is not None:
            raw_duration = task["actual_duration"]
        else:
            raw_duration = 1.0
        return self._positive_finite_float(raw_duration, field_name="duration")

    def _optional_finite_float(
        self,
        task: Dict[str, Any],
        key: str,
        *,
        default: float,
        field_name: str,
    ) -> float:
        if task.get(key) is None:
            return default
        return self._finite_float(task[key], field_name=field_name)

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

    def _safe_hour(self, value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            hour = float(value)
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                hour = float(stripped)
            except ValueError:
                return None
        else:
            return None
        if 0 <= hour <= 24.0:
            return hour
        return None
