from __future__ import annotations

from typing import Any, Dict, List


class DecisionEngine:
    """Rank tasks using business priority and predicted execution quality."""

    def prioritize_tasks(
        self,
        tasks: List[Dict[str, Any]],
        predicted_tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        prediction_by_id = {
            task.get("id"): float(task.get("predicted_productivity", 0.0))
            for task in predicted_tasks
        }
        preferred_task_types = {
            str(task_type).lower() for task_type in behavior_patterns.get("preferred_task_types", [])
        }

        prioritized_tasks: List[Dict[str, Any]] = []
        for task in tasks:
            predicted_productivity = prediction_by_id.get(task.get("id"), 0.0)
            priority = float(task.get("priority") or 0.0)
            duration = float(task.get("estimated_duration") or task.get("actual_duration") or 1.0)
            preferred_boost = 8.0 if str(task.get("task_type", "")).lower() in preferred_task_types else 0.0
            decision_score = (priority * 14.0) + (predicted_productivity * 0.7) + preferred_boost - (
                duration * 1.5
            )

            prioritized_task = dict(task)
            prioritized_task["predicted_productivity"] = round(predicted_productivity, 2)
            prioritized_task["decision_score"] = round(decision_score, 2)
            prioritized_tasks.append(prioritized_task)

        return sorted(prioritized_tasks, key=lambda task: float(task["decision_score"]), reverse=True)
