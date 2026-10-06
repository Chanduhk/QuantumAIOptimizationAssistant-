"""Structured provenance for predictions used by future optimization."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from backend.app.domain.optimization_input_contract import DurationValue


class PredictionStatus(str, Enum):
    TRAINED_MODEL = "TRAINED_MODEL"
    COLD_START_HEURISTIC = "COLD_START_HEURISTIC"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class PredictionResult:
    task_id: int | str
    candidate_start_hour: int
    value: float | None
    score_unit: str
    prediction_source: PredictionStatus
    model_trained: bool | None
    history_count: int | None
    history_count_status: str
    model_version: str | None
    model_version_status: str
    fallback_used: bool
    duration_input: DurationValue | None
    validity: bool
    status: PredictionStatus
    optimizer_eligibility: str
    reason: str | None = None
    feature_schema_version: str | None = None
    target_schema_version: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.task_id, bool) or not isinstance(self.task_id, (int, str)) or not str(self.task_id).strip():
            raise ValueError("task_id must be a non-empty stable integer or string.")
        if isinstance(self.task_id, int) and self.task_id <= 0:
            raise ValueError("integer task_id must be positive.")
        if not isinstance(self.status, PredictionStatus) or not isinstance(self.prediction_source, PredictionStatus):
            raise ValueError("prediction status and source must use supported provenance values.")
        if isinstance(self.candidate_start_hour, bool) or not isinstance(self.candidate_start_hour, int):
            raise ValueError("candidate_start_hour must be an integer.")
        if not 6 <= self.candidate_start_hour <= 22:
            raise ValueError("candidate_start_hour must be within the RL action domain 6..22.")
        if self.status is not self.prediction_source:
            raise ValueError("status and prediction_source must agree.")
        if self.score_unit != "productivity_points":
            raise ValueError("score_unit must be productivity_points.")
        if self.history_count is not None and (
            isinstance(self.history_count, bool) or not isinstance(self.history_count, int) or self.history_count < 0
        ):
            raise ValueError("history_count must be a non-negative integer or None.")
        if self.history_count_status not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ValueError("history_count_status must be AVAILABLE or UNAVAILABLE.")
        if (self.history_count is None) != (self.history_count_status == "UNAVAILABLE"):
            raise ValueError("history_count and history_count_status disagree.")

        if self.status in {PredictionStatus.TRAINED_MODEL, PredictionStatus.COLD_START_HEURISTIC}:
            if self.value is None or isinstance(self.value, bool) or not math.isfinite(float(self.value)):
                raise ValueError("valid prediction statuses require a finite prediction value.")
            if not 0.0 <= float(self.value) <= 100.0:
                raise ValueError("prediction value must be within 0..100.")
            if not self.validity:
                raise ValueError("prediction value statuses must be marked valid.")
        elif self.value is not None or self.validity:
            raise ValueError("unavailable or invalid predictions must not carry a valid value.")

        if self.status is PredictionStatus.TRAINED_MODEL:
            if self.model_trained is not True or self.fallback_used:
                raise ValueError("trained-model provenance requires trained=true and fallback_used=false.")
            if self.duration_input is None:
                raise ValueError("trained-model predictions require normalized duration provenance.")
        elif self.status is PredictionStatus.COLD_START_HEURISTIC:
            if self.model_trained is not False or not self.fallback_used:
                raise ValueError("cold-start provenance requires trained=false and fallback_used=true.")
            if self.duration_input is None:
                raise ValueError("cold-start predictions require the supplied duration provenance, even when unused.")
        elif self.fallback_used:
            raise ValueError("unavailable/invalid predictions cannot claim a fallback score.")

        if self.model_version is not None and not self.model_version.strip():
            raise ValueError("model_version must be None or a non-empty available version.")
        if self.feature_schema_version is not None and not self.feature_schema_version.strip():
            raise ValueError("feature_schema_version must be None or a non-empty available version.")
        if self.target_schema_version is not None and not self.target_schema_version.strip():
            raise ValueError("target_schema_version must be None or a non-empty available version.")
        if self.model_version is None and self.model_version_status != "MODEL_VERSION_NOT_AVAILABLE":
            raise ValueError("missing model versions must be labeled MODEL_VERSION_NOT_AVAILABLE.")
        if self.model_version is not None and self.model_version_status != "AVAILABLE":
            raise ValueError("available model versions must be labeled AVAILABLE.")
