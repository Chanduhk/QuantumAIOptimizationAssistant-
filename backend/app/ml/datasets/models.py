from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping


SEVERITIES = frozenset({"ERROR", "WARNING", "QUARANTINE"})


@dataclass(frozen=True)
class DataQualityIssue:
    """Immutable data-quality issue emitted during dataset construction."""

    severity: str
    code: str
    message: str
    task_id: str | None = None
    event_id: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError("severity must be ERROR, WARNING, or QUARANTINE.")
        object.__setattr__(self, "code", _safe_text(self.code, "code"))
        object.__setattr__(self, "message", _safe_text(self.message, "message"))
        if self.task_id is not None:
            object.__setattr__(self, "task_id", _safe_text(self.task_id, "task_id"))
        if self.event_id is not None:
            object.__setattr__(self, "event_id", _safe_text(self.event_id, "event_id"))


@dataclass(frozen=True)
class PredictionSnapshot:
    """Immutable boundary between prediction-time facts and future outcomes."""

    task_id: str
    user_id: str
    prediction_timestamp: datetime
    task_state: Mapping[str, Any]
    historical_context: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _safe_text(self.task_id, "task_id"))
        object.__setattr__(self, "user_id", _safe_text(self.user_id, "user_id"))
        object.__setattr__(self, "prediction_timestamp", _datetime(self.prediction_timestamp, "prediction_timestamp"))
        object.__setattr__(self, "task_state", _freeze_mapping(self.task_state, "task_state"))
        object.__setattr__(self, "historical_context", _freeze_mapping(self.historical_context, "historical_context"))


@dataclass(frozen=True)
class DatasetRow:
    """Immutable supervised-learning row for the duration-ratio target."""

    example_id: str
    task_id: str
    user_id: str
    prediction_timestamp: datetime
    features: Mapping[str, Any]
    target: Mapping[str, float]
    provenance: Mapping[str, Any]
    dataset_version: str
    schema_version: str
    feature_version: str
    label_version: str

    def __post_init__(self) -> None:
        for field_name in ("example_id", "task_id", "user_id", "dataset_version", "schema_version", "feature_version", "label_version"):
            object.__setattr__(self, field_name, _safe_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "prediction_timestamp", _datetime(self.prediction_timestamp, "prediction_timestamp"))
        features = _freeze_mapping(self.features, "features")
        if "duration_ratio" in features or any("actual_duration" in key for key in features):
            raise ValueError("features cannot contain target or actual-duration fields.")
        target = _freeze_mapping(self.target, "target")
        if set(target) != {"duration_ratio"}:
            raise ValueError("target must contain only duration_ratio.")
        ratio = _finite(target["duration_ratio"], "duration_ratio")
        if ratio < 0.0:
            raise ValueError("duration_ratio cannot be negative.")
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "target", MappingProxyType({"duration_ratio": ratio}))
        object.__setattr__(self, "provenance", _freeze_mapping(self.provenance, "provenance"))

    def signature(self) -> tuple[Any, ...]:
        """Return a deterministic signature for reproducibility checks."""

        return (
            self.example_id,
            self.task_id,
            self.user_id,
            self.prediction_timestamp.isoformat(),
            tuple(sorted(self.features.items())),
            tuple(sorted(self.target.items())),
            self.dataset_version,
            self.schema_version,
            self.feature_version,
            self.label_version,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""

        return {
            "example_id": self.example_id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "prediction_timestamp": self.prediction_timestamp.isoformat(),
            "features": _thaw_mapping(self.features),
            "target": _thaw_mapping(self.target),
            "provenance": _thaw_mapping(self.provenance),
            "dataset_version": self.dataset_version,
            "schema_version": self.schema_version,
            "feature_version": self.feature_version,
            "label_version": self.label_version,
        }


@dataclass(frozen=True)
class DatasetMetadata:
    """Immutable lightweight metadata for one deterministic dataset build."""

    dataset_version: str
    schema_version: str
    feature_version: str
    label_version: str
    creation_timestamp: str
    source_period_start: datetime | None
    source_period_end: datetime | None
    raw_event_count: int
    valid_event_count: int
    invalid_event_count: int
    row_count: int
    valid_row_count: int
    rejected_row_count: int

    def __post_init__(self) -> None:
        for field_name in ("dataset_version", "schema_version", "feature_version", "label_version", "creation_timestamp"):
            object.__setattr__(self, field_name, _safe_text(getattr(self, field_name), field_name))
        for field_name in ("source_period_start", "source_period_end"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _datetime(value, field_name))
        for field_name in ("raw_event_count", "valid_event_count", "invalid_event_count", "row_count", "valid_row_count", "rejected_row_count"):
            object.__setattr__(self, field_name, _non_negative_int(getattr(self, field_name), field_name))


def _safe_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    text = value.strip()
    if any(ord(char) < 32 for char in text):
        raise ValueError(f"{field_name} cannot contain control characters.")
    return text


def _datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime.")
    return value


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer.") from None
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return number


def _freeze_mapping(values: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if not isinstance(values, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    frozen: dict[str, Any] = {}
    for key in sorted(values):
        normalized = _safe_text(str(key), f"{field_name} key")
        frozen[normalized] = _freeze_value(values[key], f"{field_name}.{normalized}")
    return MappingProxyType(frozen)


def _freeze_value(value: Any, field_name: str) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite.")
    if isinstance(value, Mapping):
        return _freeze_mapping(value, field_name)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item, field_name) for item in value)
    if isinstance(value, list):
        return tuple(_freeze_value(item, field_name) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_value(item, field_name) for item in value))
    return value


def _thaw_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _thaw_value(values[key]) for key in sorted(values)}


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _thaw_mapping(value)
    if isinstance(value, tuple):
        return tuple(_thaw_value(item) for item in value)
    return value
