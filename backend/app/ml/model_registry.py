from __future__ import annotations

import logging
import math
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

    def promote_model(self, model_name: str, version: int, *, require_evidence: bool = True) -> ModelMetadata:
        """Promote a staging model to production and demote the current production model."""
        target_record = self.store.get(model_name, version)
        if target_record is None:
            raise ValueError(f"Model '{model_name}' version {version} was not found.")
        if target_record.metadata.status == ModelStatus.TRAINING:
            raise ValueError("Training models must move to staging before production.")

        current_production = self.get_latest_model(model_name)
        if current_production is not None and current_production.metadata.version == version:
            return self._copy_metadata(current_production.metadata)

        if require_evidence:
            self._validate_candidate_and_compare_production(target_record, current_production)

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

    def _validate_candidate_and_compare_production(
        self,
        target_record: ModelRecord,
        current_production: Optional[ModelRecord],
    ) -> None:
        """Validate candidate evaluation metrics and ensure it improves upon current production."""
        metrics = target_record.metadata.metrics or {}
        if not metrics:
            raise ValueError("Candidate model cannot be promoted: missing evaluation metrics.")

        # Evidence requirement: No synthetic or demo data
        if metrics.get("demo_only") or metrics.get("no_real_training_samples_available"):
            raise ValueError("Model trained on synthetic or demo data cannot be promoted to production.")

        cand_eval = metrics.get("evaluation_metrics")
        if not isinstance(cand_eval, dict):
            cand_eval = metrics

        is_regression = ("mae" in cand_eval or "rmse" in cand_eval)

        if is_regression:
            cand_mae = cand_eval.get("mae")
            cand_rmse = cand_eval.get("rmse")
            cand_mape = cand_eval.get("mape")
            cand_bias = cand_eval.get("directional_bias")

            if cand_mae is None and cand_rmse is None:
                raise ValueError("Candidate regression model missing primary error metric (MAE or RMSE).")

            if cand_mae is not None:
                if not isinstance(cand_mae, (int, float)) or isinstance(cand_mae, bool) or not math.isfinite(cand_mae) or cand_mae < 0:
                    raise ValueError(f"Candidate model has invalid MAE: {cand_mae}. MAE must be a non-negative finite number.")

            if cand_rmse is not None:
                if not isinstance(cand_rmse, (int, float)) or isinstance(cand_rmse, bool) or not math.isfinite(cand_rmse) or cand_rmse < 0:
                    raise ValueError(f"Candidate model has invalid RMSE: {cand_rmse}. RMSE must be a non-negative finite number.")

            if cand_mape is not None:
                if not isinstance(cand_mape, (int, float)) or isinstance(cand_mape, bool) or not math.isfinite(cand_mape) or cand_mape < 0:
                    raise ValueError(f"Candidate model has invalid MAPE: {cand_mape}. MAPE must be a non-negative finite number.")

            # Directional bias criterion:
            # Target ratios center near 1.0. A bias |bias| > 1.5 indicates severe systematic skew.
            if cand_bias is not None:
                if not isinstance(cand_bias, (int, float)) or isinstance(cand_bias, bool) or not math.isfinite(cand_bias):
                    raise ValueError(f"Candidate model has invalid directional_bias: {cand_bias}.")
                if abs(cand_bias) > 1.5:
                    raise ValueError(
                        f"Candidate directional bias {cand_bias:.4f} exceeds allowable safety threshold (|bias| <= 1.5)."
                    )

            # Evaluation sample count requirement: at least 3 hold-out evaluation samples
            # are strictly required to reliably compare candidate against production.
            MINIMUM_EVALUATION_SAMPLES_FOR_PROMOTION = 3
            sample_count = cand_eval.get("sample_count")
            if sample_count is None:
                sample_count = cand_eval.get("validation_sample_count")
            if sample_count is None:
                sample_count = metrics.get("validation_sample_count")
            if sample_count is not None:
                if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < MINIMUM_EVALUATION_SAMPLES_FOR_PROMOTION:
                    raise ValueError(
                        f"Candidate model has insufficient evaluation data (sample count: {sample_count} < {MINIMUM_EVALUATION_SAMPLES_FOR_PROMOTION}). "
                        f"At least {MINIMUM_EVALUATION_SAMPLES_FOR_PROMOTION} hold-out validation samples are required for a statistically defensible evaluation."
                    )

            if current_production is not None:
                prod_metrics = current_production.metadata.metrics or {}
                prod_eval = prod_metrics.get("evaluation_metrics")
                if not isinstance(prod_eval, dict):
                    prod_eval = prod_metrics

                prod_is_regression = ("mae" in prod_eval or "rmse" in prod_eval)
                if not prod_is_regression:
                    raise ValueError("Incompatible model evaluation types: cannot compare regression candidate against non-regression production model.")

                # Target definition compatibility check
                cand_target = metrics.get("target_schema_version") or metrics.get("target_name")
                prod_target = prod_metrics.get("target_schema_version") or prod_metrics.get("target_name")
                if cand_target and prod_target and cand_target != prod_target:
                    raise ValueError(
                        f"Incompatible target definitions: candidate evaluates '{cand_target}' while production evaluates '{prod_target}'."
                    )

                # Evaluation protocol compatibility check
                cand_proto = metrics.get("evaluation_protocol")
                prod_proto = prod_metrics.get("evaluation_protocol")
                if cand_proto and prod_proto and cand_proto != prod_proto:
                    raise ValueError(
                        f"Incompatible evaluation protocols: candidate used '{cand_proto}' while production used '{prod_proto}'."
                    )

                prod_mae = prod_eval.get("mae")
                prod_rmse = prod_eval.get("rmse")

                if cand_mae is not None and prod_mae is not None:
                    if cand_mae > prod_mae:
                        raise ValueError(
                            f"Candidate model is inferior: candidate MAE ({cand_mae:.4f}) > production MAE ({prod_mae:.4f})."
                        )
                    elif cand_mae == prod_mae:
                        # Secondary comparison: RMSE
                        if cand_rmse is not None and prod_rmse is not None:
                            if cand_rmse > prod_rmse:
                                raise ValueError(
                                    f"Candidate model is inferior: equal MAE but candidate RMSE ({cand_rmse:.4f}) > production RMSE ({prod_rmse:.4f})."
                                )
                            elif cand_rmse == prod_rmse:
                                prod_bias = prod_eval.get("directional_bias")
                                if cand_bias is not None and prod_bias is not None:
                                    if abs(cand_bias) >= abs(prod_bias):
                                        raise ValueError(
                                            f"Candidate model does not improve on approved production model (equal error and bias |{cand_bias:.4f}| >= |{prod_bias:.4f}|)."
                                        )
                                else:
                                    raise ValueError("Candidate model does not improve on approved production model (equal error metrics).")
                        else:
                            raise ValueError("Candidate model does not improve on approved production model (equal MAE).")
                elif cand_rmse is not None and prod_rmse is not None:
                    if cand_rmse >= prod_rmse:
                        raise ValueError(
                            f"Candidate model is inferior or equal: candidate RMSE ({cand_rmse:.4f}) >= production RMSE ({prod_rmse:.4f})."
                        )
                else:
                    raise ValueError("Incompatible regression metrics: candidate and production do not share comparable MAE or RMSE.")
        else:
            # Classification / general score model
            cand_score = target_record.metadata.accuracy_score
            if not isinstance(cand_score, (int, float)) or isinstance(cand_score, bool) or not math.isfinite(cand_score) or cand_score < 0:
                raise ValueError("Model with negative accuracy/validation score cannot be promoted to production.")

            if current_production is not None:
                prod_metrics = current_production.metadata.metrics or {}
                prod_eval = prod_metrics.get("evaluation_metrics")
                if not isinstance(prod_eval, dict):
                    prod_eval = prod_metrics
                if "mae" in prod_eval or "rmse" in prod_eval:
                    raise ValueError("Incompatible model evaluation types: cannot compare non-regression candidate against regression production model.")

                prod_score = current_production.metadata.accuracy_score
                if cand_score <= prod_score:
                    raise ValueError(
                        f"Candidate model '{target_record.metadata.model_name}' version {target_record.metadata.version} with score {cand_score:.4f} "
                        f"is inferior to current production version {current_production.metadata.version} with score {prod_score:.4f} and cannot replace it."
                    )


_SHARED_REGISTRY: Optional[ModelRegistry] = None
_REGISTRY_LOCK = RLock()


def get_model_registry() -> ModelRegistry:
    """Return the shared singleton ModelRegistry instance."""
    global _SHARED_REGISTRY
    with _REGISTRY_LOCK:
        if _SHARED_REGISTRY is None:
            _SHARED_REGISTRY = ModelRegistry()
        return _SHARED_REGISTRY


def reset_model_registry() -> None:
    """Reset the shared singleton registry (for isolated test runs)."""
    global _SHARED_REGISTRY
    with _REGISTRY_LOCK:
        _SHARED_REGISTRY = None
