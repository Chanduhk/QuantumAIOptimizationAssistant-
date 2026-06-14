from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Any, Dict, List, Optional, Protocol

from backend.app.monitoring import AIMonitor


class ModelStatus(str, Enum):
    """Supported lifecycle states for registered models."""

    TRAINING = "training"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ModelMetadata:
    """Metadata tracked for each registered model version."""

    model_name: str
    version: int
    training_timestamp: str
    accuracy_score: float
    status: ModelStatus
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelRecord:
    """One stored model version with its in-memory object and metadata."""

    metadata: ModelMetadata
    model_object: Any


class ModelStore(Protocol):
    """Storage contract for model registry backends."""

    def save(self, record: ModelRecord) -> ModelRecord:
        """Persist a model record."""

    def update(self, record: ModelRecord) -> ModelRecord:
        """Update an existing model record."""

    def get(self, model_name: str, version: int) -> Optional[ModelRecord]:
        """Fetch one model record by name and version."""

    def list(self, model_name: str) -> List[ModelRecord]:
        """List all records for one model family."""


class InMemoryModelStore:
    """Thread-safe in-memory storage backend for model registry records."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: Dict[str, List[ModelRecord]] = {}

    def save(self, record: ModelRecord) -> ModelRecord:
        with self._lock:
            self._records.setdefault(record.metadata.model_name, [])
            self._records[record.metadata.model_name].append(record)
        return record

    def update(self, record: ModelRecord) -> ModelRecord:
        with self._lock:
            model_versions = self._records.setdefault(record.metadata.model_name, [])
            for index, existing in enumerate(model_versions):
                if existing.metadata.version == record.metadata.version:
                    model_versions[index] = record
                    return record
        raise ValueError(
            f"Model '{record.metadata.model_name}' version {record.metadata.version} was not found."
        )

    def get(self, model_name: str, version: int) -> Optional[ModelRecord]:
        with self._lock:
            for record in self._records.get(model_name, []):
                if record.metadata.version == version:
                    return record
        return None

    def list(self, model_name: str) -> List[ModelRecord]:
        with self._lock:
            return list(self._records.get(model_name, []))


class ModelRegistry:
    """Manage model versions, promotion, and rollback for ML components.

    The registry is storage-agnostic: today it uses an in-memory store, but
    the public API is written so the backend can later be replaced with Redis,
    PostgreSQL, MLflow, or another external system.
    """

    def __init__(
        self,
        *,
        store: Optional[ModelStore] = None,
        monitor: Optional[AIMonitor] = None,
    ) -> None:
        self.store = store or InMemoryModelStore()
        self.monitor = monitor
        self.logger = logging.getLogger(__name__)
        self._promotion_history: Dict[str, List[int]] = {}

    def register_model(
        self,
        model_name: str,
        model_object: Any,
        metrics: Dict[str, Any],
    ) -> ModelMetadata:
        """Register a newly trained model version in staging.

        This is the natural handoff point from `LearningEngine` after training.
        """
        if not model_name or not str(model_name).strip():
            raise ValueError("model_name is required.")
        if model_object is None:
            raise ValueError("model_object is required.")

        normalized_name = str(model_name).strip()
        normalized_metrics = deepcopy(metrics or {})
        version = self._next_version(normalized_name)
        status = self._coerce_status(normalized_metrics.get("status", ModelStatus.STAGING.value))
        timestamp = self._resolve_training_timestamp(normalized_metrics)

        metadata = ModelMetadata(
            model_name=normalized_name,
            version=version,
            training_timestamp=timestamp,
            accuracy_score=self._extract_accuracy_score(normalized_metrics),
            status=status,
            metrics=normalized_metrics,
        )
        record = ModelRecord(metadata=metadata, model_object=model_object)
        self.store.save(record)

        self.logger.info(
            "Registered model '%s' version %s with status '%s'.",
            normalized_name,
            version,
            metadata.status.value,
        )
        self._log_model_metrics("MODEL_REGISTERED", metadata)

        return self._copy_metadata(metadata)

    def get_latest_model(self, model_name: str) -> Optional[ModelRecord]:
        """Return the latest production model for prediction-time use."""
        production_records = [
            record
            for record in self.store.list(model_name)
            if record.metadata.status == ModelStatus.PRODUCTION
        ]
        if not production_records:
            return None

        latest_record = max(production_records, key=lambda record: record.metadata.version)
        self.logger.info(
            "Loaded production model '%s' version %s.",
            latest_record.metadata.model_name,
            latest_record.metadata.version,
        )
        return latest_record

    def promote_model(self, model_name: str, version: int) -> ModelMetadata:
        """Promote a staging model to production and demote the current production model."""
        target_record = self.store.get(model_name, version)
        if target_record is None:
            raise ValueError(f"Model '{model_name}' version {version} was not found.")
        if target_record.metadata.status == ModelStatus.TRAINING:
            raise ValueError("Training models must move to staging before production.")

        current_production = self.get_latest_model(model_name)
        if current_production is not None and current_production.metadata.version == version:
            return self._copy_metadata(current_production.metadata)

        if current_production is not None:
            current_production.metadata.status = ModelStatus.STAGING
            self.store.update(current_production)

        target_record.metadata.status = ModelStatus.PRODUCTION
        self.store.update(target_record)

        history = self._promotion_history.setdefault(model_name, [])
        if not history or history[-1] != version:
            history.append(version)

        self.logger.info(
            "Promoted model '%s' version %s to production.",
            model_name,
            version,
        )
        self._log_model_metrics("MODEL_PROMOTED", target_record.metadata)

        return self._copy_metadata(target_record.metadata)

    def rollback_model(self, model_name: str) -> ModelMetadata:
        """Rollback production traffic to the previous promoted model version."""
        current_production = self.get_latest_model(model_name)
        if current_production is None:
            raise ValueError(f"No production model is available for '{model_name}'.")

        history = self._promotion_history.get(model_name, [])
        if len(history) < 2:
            raise ValueError(f"No previous production version is available for '{model_name}'.")
        if history[-1] != current_production.metadata.version:
            history.append(current_production.metadata.version)

        current_version = history.pop()
        previous_version = history[-1]
        previous_record = self.store.get(model_name, previous_version)
        if previous_record is None:
            history.append(current_version)
            raise ValueError(
                f"Previous production model '{model_name}' version {previous_version} was not found."
            )

        current_production.metadata.status = ModelStatus.STAGING
        previous_record.metadata.status = ModelStatus.PRODUCTION
        self.store.update(current_production)
        self.store.update(previous_record)

        self.logger.warning(
            "Rolled back model '%s' from version %s to version %s.",
            model_name,
            current_version,
            previous_version,
        )
        self._log_model_metrics("MODEL_ROLLBACK", previous_record.metadata)

        return self._copy_metadata(previous_record.metadata)

    def list_models(self, model_name: str) -> List[ModelMetadata]:
        """Return metadata for all registered versions of a model family."""
        records = sorted(
            self.store.list(model_name),
            key=lambda record: record.metadata.version,
        )
        return [self._copy_metadata(record.metadata) for record in records]

    def _next_version(self, model_name: str) -> int:
        existing_records = self.store.list(model_name)
        if not existing_records:
            return 1
        return max(record.metadata.version for record in existing_records) + 1

    def _resolve_training_timestamp(self, metrics: Dict[str, Any]) -> str:
        raw_timestamp = metrics.get("training_timestamp")
        if raw_timestamp:
            return str(raw_timestamp)
        return datetime.utcnow().isoformat()

    def _extract_accuracy_score(self, metrics: Dict[str, Any]) -> float:
        for key in ("accuracy_score", "accuracy", "score"):
            if key in metrics:
                return round(float(metrics[key]), 4)
        return 0.0

    def _coerce_status(self, value: Any) -> ModelStatus:
        try:
            return ModelStatus(str(value).lower())
        except ValueError as exc:
            raise ValueError(
                "status must be one of: training, staging, production."
            ) from exc

    def _copy_metadata(self, metadata: ModelMetadata) -> ModelMetadata:
        return ModelMetadata(
            model_name=metadata.model_name,
            version=metadata.version,
            training_timestamp=metadata.training_timestamp,
            accuracy_score=metadata.accuracy_score,
            status=metadata.status,
            metrics=deepcopy(metadata.metrics),
        )

    def _log_model_metrics(self, event_name: str, metadata: ModelMetadata) -> None:
        if self.monitor is None:
            return

        self.monitor.log_event(event_name)
        self.monitor.log_training_metrics(
            "ModelRegistry",
            {
                "model_name": metadata.model_name,
                "version": metadata.version,
                "status": metadata.status.value,
                "accuracy_score": metadata.accuracy_score,
                **deepcopy(metadata.metrics),
            },
        )
