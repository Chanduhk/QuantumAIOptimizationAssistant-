from __future__ import annotations

from typing import Any, Dict, List


class OptimizationEngine:
    """Re-map scheduled tasks to maximize productivity-weighted output."""

    def optimize_schedule(
        self,
        scheduled_tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not scheduled_tasks:
            return {"optimized_schedule": [], "projected_productivity_gain": 0.0}

        hourly_productivity = {
            int(hour): float(score)
            for hour, score in behavior_patterns.get("hourly_productivity", {}).items()
        }
        ranked_hours = sorted(
            {int(task.get("scheduled_hour", 10)) for task in scheduled_tasks},
            key=lambda hour: hourly_productivity.get(hour, 0.0),
            reverse=True,
        )
        ranked_tasks = sorted(
            scheduled_tasks,
            key=lambda task: float(task.get("predicted_productivity", 0.0)),
            reverse=True,
        )

        optimized_schedule: List[Dict[str, Any]] = []
        baseline_score = 0.0
        optimized_score = 0.0

        for index, task in enumerate(ranked_tasks):
            selected_hour = ranked_hours[index % len(ranked_hours)]
            duration = float(task.get("estimated_duration") or task.get("actual_duration") or 1.0)
            optimized_task = dict(task)
            optimized_task["optimized_hour"] = selected_hour
            optimized_task["optimized_end_hour"] = round(selected_hour + duration, 2)
            optimized_task["hour_productivity_score"] = round(hourly_productivity.get(selected_hour, 0.0), 2)
            optimized_schedule.append(optimized_task)

            baseline_score += float(task.get("schedule_score", 0.0))
            optimized_score += float(task.get("hour_productivity_score", 0.0))

        optimized_schedule.sort(key=lambda task: float(task["optimized_hour"]))
        projected_gain = round(optimized_score - baseline_score, 2)

        return {
            "optimized_schedule": optimized_schedule,
            "projected_productivity_gain": projected_gain,
        }
