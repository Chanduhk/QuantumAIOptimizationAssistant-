from __future__ import annotations

from typing import Any, Dict, List

from backend.app.services.behavior_engine import BehaviorIntelligenceEngine


class PredictionEngine:
    """Estimate productivity, success probability, and completion time outcomes."""

    def predict_productivity(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        task: Dict[str, Any],
        behavior_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(task, dict):
            raise ValueError("task must be a dictionary.")
        if behavior_patterns is None:
            behavior_patterns = {}

        default_hour = self._resolve_hour(task, behavior_patterns, 0)
        duration = self._resolve_duration(task)
        prediction = behavior_engine.predict_task_productivity(
            hour_of_day=default_hour,
            task_type=str(task.get("task_type", "general")),
            duration=duration,
        )
        success_probability = self._estimate_success_probability(
            prediction,
            float(task.get("priority") or 3.0),
        )
        completion_time_prediction = self._estimate_completion_time(
            duration,
            prediction,
            behavior_patterns,
        )

        predicted_task = dict(task)
        predicted_task["prediction_hour"] = default_hour
        predicted_task["predicted_productivity"] = round(prediction, 2)
        predicted_task["task_success_probability"] = round(success_probability, 4)
        predicted_task["completion_time_prediction"] = round(completion_time_prediction, 2)
        return predicted_task

    def predict_batch(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if tasks is None:
            raise ValueError("tasks must be a list of dictionaries.")
        if behavior_patterns is None:
            behavior_patterns = {}
        return [
            self._predict_with_index(behavior_engine, task, behavior_patterns, index)
            for index, task in enumerate(tasks)
        ]

    def _predict_with_index(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        task: Dict[str, Any],
        behavior_patterns: Dict[str, Any],
        index: int,
    ) -> Dict[str, Any]:
        if not isinstance(task, dict):
            raise ValueError("Each task must be a dictionary.")
        default_hour = self._resolve_hour(task, behavior_patterns, index)
        duration = self._resolve_duration(task)
        prediction = behavior_engine.predict_task_productivity(
            hour_of_day=default_hour,
            task_type=str(task.get("task_type", "general")),
            duration=duration,
        )

        predicted_task = dict(task)
        predicted_task["prediction_hour"] = default_hour
        predicted_task["predicted_productivity"] = round(prediction, 2)
        return predicted_task

    def _resolve_hour(
        self,
        task: Dict[str, Any],
        behavior_patterns: Dict[str, Any],
        index: int,
    ) -> int:
        for key in ("optimized_hour", "scheduled_hour", "hour_of_day"):
            hour = self._safe_hour(task.get(key))
            if hour is not None:
                return hour

        best_focus_hours = [
            hour
            for hour in (self._safe_hour(item) for item in behavior_patterns.get("best_focus_hours", []))
            if hour is not None
        ]
        if best_focus_hours:
            return best_focus_hours[index % len(best_focus_hours)]
        return 10

    def _estimate_success_probability(self, predicted_productivity: float, priority: float) -> float:
        probability = (predicted_productivity / 100.0) * 0.75 + min(priority, 5.0) * 0.05
        return max(0.05, min(0.99, probability))

    def _estimate_completion_time(
        self,
        base_duration: float,
        predicted_productivity: float,
        behavior_patterns: Dict[str, Any],
    ) -> float:
        average_completion_ratio = self._safe_positive_float(
            behavior_patterns.get("average_completion_time", 1.0),
            default=1.0,
        )
        productivity_adjustment = max(0.65, 1.2 - (predicted_productivity / 200.0))
        return max(0.25, base_duration * average_completion_ratio * productivity_adjustment)

    def _resolve_duration(self, task: Dict[str, Any]) -> float:
        duration = self._safe_positive_float(
            task.get("estimated_duration", task.get("actual_duration", 1.0)),
            default=1.0,
        )
        return duration

    def _safe_positive_float(self, value: Any, default: float = 1.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if number <= 0:
            return default
        return number

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
