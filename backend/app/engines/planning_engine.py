from __future__ import annotations

from typing import Any, Dict, List


class PlanningEngine:
    """Build a daily execution plan using behavioral context."""

    def generate_daily_plan(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        if tasks is None:
            raise ValueError("tasks must be a list of dictionaries.")
        if behavior_patterns is None:
            behavior_patterns = {}

        best_focus_hours = [
            hour
            for hour in (self._safe_hour(item) for item in behavior_patterns.get("best_focus_hours", []))
            if hour is not None
        ]
        preferred_task_types = {
            str(task_type).lower() for task_type in behavior_patterns.get("preferred_task_types", [])
        }

        plan_items: List[Dict[str, Any]] = []
        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            recommended_hour = task.get("optimized_hour") or task.get("scheduled_hour")
            if recommended_hour is None and best_focus_hours:
                recommended_hour = best_focus_hours[(index - 1) % len(best_focus_hours)]
            recommended_hour = self._safe_hour(recommended_hour)

            task_type = str(task.get("task_type", "")).lower()
            aligned = task_type in preferred_task_types
            rationale_parts = []
            if recommended_hour is not None:
                rationale_parts.append(f"scheduled near focus hour {recommended_hour}:00")
            if aligned:
                rationale_parts.append("matches preferred task type")
            predicted_productivity = self._safe_float(task.get("predicted_productivity"))
            if predicted_productivity is not None:
                rationale_parts.append(
                    f"predicted productivity {round(predicted_productivity, 2)}"
                )

            plan_items.append(
                {
                    "sequence": index,
                    "task_id": task.get("id"),
                    "title": task.get("title"),
                    "task_type": task.get("task_type"),
                    "priority": task.get("priority"),
                    "recommended_hour": recommended_hour,
                    "estimated_duration": task.get("estimated_duration"),
                    "predicted_productivity": task.get("predicted_productivity"),
                    "focus_alignment": aligned,
                    "rationale": "; ".join(rationale_parts) or "planned using default heuristics",
                }
            )

        return {
            "plan_date_context": "daily",
            "best_focus_hours": best_focus_hours,
            "preferred_task_types": sorted(preferred_task_types),
            "tasks": plan_items,
        }

    def _safe_hour(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            hour = int(value)
        except (TypeError, ValueError):
            return None
        if 0 <= hour <= 23:
            return hour
        return None

    def _safe_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
