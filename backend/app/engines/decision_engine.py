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
        if tasks is None:
            raise ValueError("tasks must be a list of dictionaries.")
        if predicted_tasks is None:
            predicted_tasks = []
        if behavior_patterns is None:
            behavior_patterns = {}

        prediction_by_id = {
            task.get("id"): self._safe_float(task.get("predicted_productivity", 0.0))
            for task in predicted_tasks
            if isinstance(task, dict)
        }
        preferred_task_types = {
            str(task_type).lower() for task_type in behavior_patterns.get("preferred_task_types", [])
        }

        prioritized_tasks: List[Dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            predicted_productivity = prediction_by_id.get(task.get("id"), 0.0)
            priority = self._safe_float(task.get("priority"), default=0.0)
            duration = max(
                0.0,
                self._safe_float(
                    task.get("estimated_duration", task.get("actual_duration", 1.0)),
                    default=1.0,
                ),
            )
            preferred_boost = 8.0 if str(task.get("task_type", "")).lower() in preferred_task_types else 0.0
            decision_score = (priority * 14.0) + (predicted_productivity * 0.7) + preferred_boost - (
                duration * 1.5
            )

            prioritized_task = dict(task)
            prioritized_task["predicted_productivity"] = round(predicted_productivity, 2)
            prioritized_task["decision_score"] = round(decision_score, 2)
            prioritized_tasks.append(prioritized_task)

        return sorted(prioritized_tasks, key=lambda task: float(task["decision_score"]), reverse=True)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
