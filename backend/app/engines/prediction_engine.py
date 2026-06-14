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
        default_hour = self._resolve_hour(task, behavior_patterns, 0)
        duration = float(task.get("estimated_duration") or task.get("actual_duration") or 1.0)
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
        default_hour = self._resolve_hour(task, behavior_patterns, index)
        duration = float(task.get("estimated_duration") or task.get("actual_duration") or 1.0)
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
        if task.get("optimized_hour") is not None:
            return int(task["optimized_hour"])
        if task.get("scheduled_hour") is not None:
            return int(task["scheduled_hour"])
        if task.get("hour_of_day") is not None:
            return int(task["hour_of_day"])

        best_focus_hours = [int(hour) for hour in behavior_patterns.get("best_focus_hours", [])]
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
        average_completion_ratio = float(behavior_patterns.get("average_completion_time", 1.0))
        productivity_adjustment = max(0.65, 1.2 - (predicted_productivity / 200.0))
        return max(0.25, base_duration * average_completion_ratio * productivity_adjustment)
