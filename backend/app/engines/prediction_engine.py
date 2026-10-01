from __future__ import annotations

import math
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
        self._validate_behavior_engine(behavior_engine)
        if not isinstance(task, dict):
            raise ValueError("task must be a dictionary.")
        self._validate_behavior_patterns(behavior_patterns)

        default_hour = self._resolve_hour(task, behavior_patterns, 0)
        duration = self._resolve_duration(task)
        priority = self._resolve_priority(task)
        prediction = self._normalize_prediction(
            behavior_engine.predict_task_productivity(
                hour_of_day=default_hour,
                task_type=str(task.get("task_type", "general")),
                duration=duration,
            )
        )
        success_probability = self._estimate_success_probability(
            prediction,
            priority,
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
        self._validate_behavior_engine(behavior_engine)
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        self._validate_behavior_patterns(behavior_patterns)
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
        self._resolve_priority(task)
        prediction = self._normalize_prediction(
            behavior_engine.predict_task_productivity(
                hour_of_day=default_hour,
                task_type=str(task.get("task_type", "general")),
                duration=duration,
            )
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
            if task.get(key) is not None:
                hour = self._safe_hour(task.get(key))
                if hour is None:
                    raise ValueError(f"{key} must be an hour from 0 to 24.")
                return hour

        best_focus_hours = behavior_patterns.get("best_focus_hours", [])
        if best_focus_hours is None:
            best_focus_hours = []
        if not isinstance(best_focus_hours, list):
            raise ValueError("best_focus_hours must be a list of integer hours.")

        normalized_focus_hours: List[float] = []
        for item in best_focus_hours:
            hour = self._safe_hour(item)
            if hour is None:
                raise ValueError("best_focus_hours must contain hours from 0 to 24.")
            normalized_focus_hours.append(hour)

        best_focus_hours = normalized_focus_hours
        if best_focus_hours:
            return best_focus_hours[index % len(best_focus_hours)]
        return 10

    def _estimate_success_probability(self, predicted_productivity: float, priority: float) -> float:
        safe_productivity = self._normalize_prediction(predicted_productivity)
        safe_priority = self._positive_or_zero_float(priority, field_name="priority")
        probability = (safe_productivity / 100.0) * 0.75 + min(safe_priority, 5.0) * 0.05
        return max(0.05, min(0.99, probability))

    def _estimate_completion_time(
        self,
        base_duration: float,
        predicted_productivity: float,
        behavior_patterns: Dict[str, Any],
    ) -> float:
        self._validate_behavior_patterns(behavior_patterns)
        safe_duration = self._positive_finite_float(base_duration, field_name="duration")
        safe_productivity = self._normalize_prediction(predicted_productivity)
        if behavior_patterns.get("average_completion_time") is None:
            average_completion_ratio = 1.0
        else:
            average_completion_ratio = self._positive_finite_float(
                behavior_patterns["average_completion_time"],
                field_name="average_completion_time",
            )
        productivity_adjustment = max(0.65, 1.2 - (safe_productivity / 200.0))
        completion_time = max(0.25, safe_duration * average_completion_ratio * productivity_adjustment)
        return self._positive_finite_float(completion_time, field_name="completion_time_prediction")

    def _resolve_duration(self, task: Dict[str, Any]) -> float:
        if task.get("estimated_duration") is not None:
            raw_duration = task["estimated_duration"]
        elif task.get("actual_duration") is not None:
            raw_duration = task["actual_duration"]
        else:
            raw_duration = 1.0
        return self._positive_finite_float(raw_duration, field_name="duration")

    def _resolve_priority(self, task: Dict[str, Any]) -> float:
        if task.get("priority") is None:
            return 3.0
        return self._positive_or_zero_float(task["priority"], field_name="priority")

    def _normalize_prediction(self, value: Any) -> float:
        prediction = self._finite_float(value, field_name="predicted_productivity")
        return max(0.0, min(100.0, prediction))

    def _positive_or_zero_float(self, value: Any, field_name: str) -> float:
        number = self._finite_float(value, field_name=field_name)
        if number < 0:
            raise ValueError(f"{field_name} must be non-negative.")
        return number

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

    def _validate_behavior_engine(self, behavior_engine: BehaviorIntelligenceEngine) -> None:
        if behavior_engine is None or not callable(
            getattr(behavior_engine, "predict_task_productivity", None)
        ):
            raise ValueError("behavior_engine must provide predict_task_productivity.")

    def _validate_behavior_patterns(self, behavior_patterns: Dict[str, Any]) -> None:
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
