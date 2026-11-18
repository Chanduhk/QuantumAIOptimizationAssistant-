from __future__ import annotations

import math
from typing import Any, Dict, List

from backend.app.domain.optimization_input_contract import DurationValue, normalize_duration
from backend.app.domain.prediction_provenance import PredictionResult, PredictionStatus
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

    def predict_task_hour_with_provenance(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        *,
        task_id: int | str,
        candidate_start_hour: int,
        task_type: str,
        duration: DurationValue,
    ) -> PredictionResult:
        """Return a task/hour prediction with provenance without changing legacy APIs.

        A trained legacy ProductivityModel is explicitly marked ineligible for
        optimizer use because its training/inference duration feature units are
        not verified. No model version is synthesized.
        """

        def result(
            status: PredictionStatus,
            *,
            value: float | None = None,
            model_trained: bool | None = None,
            history_count: int | None = None,
            history_count_status: str = "UNAVAILABLE",
            fallback_used: bool = False,
            duration_input: DurationValue | None = None,
            reason: str | None = None,
            model_version: str | None = None,
            feature_schema_version: str | None = None,
            target_schema_version: str | None = None,
            model_version_status: str = "MODEL_VERSION_NOT_AVAILABLE",
            optimizer_eligibility: str | None = None,
        ) -> PredictionResult:
            if optimizer_eligibility is not None:
                eligible = optimizer_eligibility
            elif status is PredictionStatus.TRAINED_MODEL:
                eligible = "MODEL_FEATURE_UNIT_UNVERIFIED"
            elif status is PredictionStatus.COLD_START_HEURISTIC:
                eligible = "COLD_START_NOT_ELIGIBLE"
            else:
                eligible = status.value
            return PredictionResult(
                task_id=task_id,
                candidate_start_hour=candidate_start_hour,
                value=value,
                score_unit="productivity_points",
                prediction_source=status,
                model_trained=model_trained,
                history_count=history_count,
                history_count_status=history_count_status,
                model_version=model_version,
                model_version_status=model_version_status,
                feature_schema_version=feature_schema_version,
                target_schema_version=target_schema_version,
                fallback_used=fallback_used,
                duration_input=duration_input,
                validity=status in {PredictionStatus.TRAINED_MODEL, PredictionStatus.COLD_START_HEURISTIC},
                status=status,
                optimizer_eligibility=eligible,
                reason=reason,
            )

        if (
            isinstance(candidate_start_hour, bool)
            or not isinstance(candidate_start_hour, int)
            or not 6 <= candidate_start_hour <= 22
        ):
            raise ValueError("candidate_start_hour must be an integer in the RL action domain 6..22.")
        if isinstance(task_id, bool) or not isinstance(task_id, (int, str)) or not str(task_id).strip():
            raise ValueError("task_id must be a non-empty stable integer or string.")
        if isinstance(task_id, int) and task_id <= 0:
            raise ValueError("integer task_id must be positive.")
        if not isinstance(task_type, str) or not task_type.strip():
            return result(PredictionStatus.INVALID_INPUT, reason="task_type must be non-empty.")
        if not isinstance(duration, DurationValue) or not duration.optimizer_eligible:
            return result(PredictionStatus.INVALID_INPUT, reason="duration must have known-unit normalized provenance.")
        if behavior_engine is None:
            return result(PredictionStatus.UNAVAILABLE, reason="behavior engine is unavailable.", duration_input=duration)

        model = getattr(behavior_engine, "productivity_model", None)
        trained_before = getattr(model, "is_trained", None)
        if not isinstance(trained_before, bool):
            return result(PredictionStatus.UNAVAILABLE, reason="model training state is unavailable.", duration_input=duration)

        try:
            raw_value = behavior_engine.predict_task_productivity(
                hour_of_day=candidate_start_hour,
                task_type=task_type.strip(),
                duration=duration.normalized_hours,
            )
        except (AttributeError, ValueError, TypeError) as exc:
            return result(
                PredictionStatus.UNAVAILABLE,
                model_trained=bool(getattr(model, "is_trained", False)),
                duration_input=duration,
                reason=f"prediction unavailable: {type(exc).__name__}.",
            )

        trained_after = getattr(model, "is_trained", None)
        if trained_after is True:
            try:
                prediction = self._normalize_prediction(raw_value)
            except ValueError:
                return result(
                    PredictionStatus.INVALID_INPUT,
                    model_trained=True,
                    duration_input=duration,
                    reason="model returned a non-finite score.",
                )
            metadata = getattr(model, "metadata", None)
            metadata = metadata if isinstance(metadata, dict) else {}
            count = metadata.get("training_sample_count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 5:
                count = None
            compatibility_check = getattr(model, "_metadata_is_compatible", None)
            compatible = (
                getattr(model, "compatibility_status", None) == "OPTIMIZATION_COMPATIBLE"
                and callable(compatibility_check)
                and compatibility_check() is True
                and count is not None
            )
            model_version = metadata.get("model_version") if compatible else None
            feature_schema_version = metadata.get("feature_schema_version") if compatible else None
            target_schema_version = metadata.get("target_schema_version") if compatible else None
            return result(
                PredictionStatus.TRAINED_MODEL,
                value=prediction,
                model_trained=True,
                history_count=count,
                history_count_status="AVAILABLE" if count is not None else "UNAVAILABLE",
                duration_input=duration,
                reason=None if compatible else "MODEL_FEATURE_UNIT_UNVERIFIED",
                model_version=model_version,
                model_version_status="AVAILABLE" if model_version else "MODEL_VERSION_NOT_AVAILABLE",
                feature_schema_version=feature_schema_version,
                target_schema_version=target_schema_version,
                optimizer_eligibility=("ELIGIBLE_HEURISTIC_PROXY" if compatible else "MODEL_FEATURE_UNIT_UNVERIFIED"),
            )

        if trained_before is False and trained_after is False:
            try:
                prediction = self._normalize_prediction(raw_value)
            except ValueError:
                return result(
                    PredictionStatus.INVALID_INPUT,
                    model_trained=False,
                    duration_input=duration,
                    reason="fallback returned a non-finite score.",
                )
            behavior_rows = getattr(behavior_engine, "behavior_data_df", None)
            shape = getattr(behavior_rows, "shape", None)
            count = shape[0] if isinstance(shape, tuple) and shape and isinstance(shape[0], int) else None
            return result(
                PredictionStatus.COLD_START_HEURISTIC,
                value=prediction,
                model_trained=False,
                history_count=count,
                history_count_status="AVAILABLE" if count is not None else "UNAVAILABLE",
                fallback_used=True,
                duration_input=duration,
                reason="hour_only_cold_start_heuristic_not_personalized",
            )

        return result(
            PredictionStatus.UNAVAILABLE,
            model_trained=trained_after if isinstance(trained_after, bool) else None,
            duration_input=duration,
            reason="model training state changed to an unsupported value.",
        )

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

        # Base ratio from behavior patterns
        if behavior_patterns.get("average_completion_time") is None:
            average_completion_ratio = 1.0
        else:
            average_completion_ratio = self._positive_finite_float(
                behavior_patterns["average_completion_time"],
                field_name="average_completion_time",
            )

        # Refine with trained DurationRatioModel when available in production
        try:
            from backend.app.ml.model_registry import get_model_registry
            reg = get_model_registry()
            dur_rec = reg.get_latest_model("DurationRatioModel")
            if dur_rec and getattr(dur_rec.metadata, "status", None) == "production":
                d_obj = dur_rec.model_object
                if hasattr(d_obj, "predict_ratio"):
                    model_ratio = d_obj.predict_ratio(safe_duration * 60.0)
                    if 0.1 <= model_ratio <= 10.0:
                        average_completion_ratio = float(model_ratio)
        except Exception:
            pass

        productivity_adjustment = max(0.65, 1.2 - (safe_productivity / 200.0))
        completion_time = max(0.25, safe_duration * average_completion_ratio * productivity_adjustment)
        return self._positive_finite_float(completion_time, field_name="completion_time_prediction")

    def _resolve_duration(self, task: Dict[str, Any]) -> float:
        estimate = task.get("estimated_duration")
        if estimate is None:
            raise ValueError("estimated_duration is required for forward prediction.")
        unit = task.get("estimated_duration_unit")
        source = task.get("estimated_duration_source")
        if unit is None or source is None:
            raise ValueError("explicit estimated_duration_unit and source are required for prediction.")
        return normalize_duration(estimate, unit, source).normalized_hours

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
