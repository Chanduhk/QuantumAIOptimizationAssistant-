from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean, median
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from backend.app.ml.datasets.models import DatasetRow
from backend.app.ml.datasets.splitter import DatasetSplit
from backend.app.ml.readiness import MINIMUM_TRAINING_ROWS, NOT_READY_INSUFFICIENT_DATA, READY_FOR_TRAINING


FEATURE_SCHEMA_VERSION = "duration_features_v0.1"
MODEL_VERSION = "duration-ratio-ridge-v0.1"
TARGET_SCHEMA_VERSION = "duration_ratio_v0.1"

# The 12-feature contract defined in Phase 5
FEATURE_NAMES: Tuple[str, ...] = (
    "estimated_duration_minutes",
    "priority",
    "task_type",
    "prediction_hour",
    "prediction_day_of_week",
    "time_since_task_created_minutes",
    "scheduled_start_hour",
    "hours_until_scheduled_start",
    "prior_completed_task_count",
    "prior_duration_ratio_mean",
    "prior_duration_ratio_median",
    "prior_same_type_duration_ratio_mean",
)


@dataclass(frozen=True)
class EvaluationReport:
    """Evaluation metrics on chronological temporal hold-out split."""

    sample_count: int
    feature_count: int
    mae: float
    rmse: float
    mape: float
    directional_bias: float
    median_error: float
    training_period: Tuple[str, str]
    evaluation_period: Tuple[str, str]
    train_sample_count: int
    validation_sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "feature_count": self.feature_count,
            "mae": self.mae,
            "rmse": self.rmse,
            "mape": self.mape,
            "directional_bias": self.directional_bias,
            "median_error": self.median_error,
            "training_period": list(self.training_period),
            "evaluation_period": list(self.evaluation_period),
            "train_sample_count": self.train_sample_count,
            "validation_sample_count": self.validation_sample_count,
        }


class DurationRatioBaselineRegressor:
    """Explainable L2-regularized linear baseline for duration ratio prediction.

    Strictly refuses training if real data does not meet the readiness contract.
    """

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self.is_trained = False
        self.feature_names = list(FEATURE_NAMES)
        self.scaler: Optional[StandardScaler] = None
        self.task_type_encoder: Optional[OneHotEncoder] = None
        self.model: Optional[Ridge] = None
        self.metadata: Optional[Dict[str, Any]] = None
        self.evaluation_report: Optional[EvaluationReport] = None

    def train_on_split(self, split: DatasetSplit) -> EvaluationReport:
        """Train exclusively on train partition and evaluate on validation partition."""
        train_rows = split.train
        val_rows = split.validation or split.test

        if len(train_rows) < MINIMUM_TRAINING_ROWS:
            raise ValueError(
                f"Cannot train duration model: {len(train_rows)} training rows is below "
                f"the required minimum of {MINIMUM_TRAINING_ROWS} ({NOT_READY_INSUFFICIENT_DATA})."
            )

        if not val_rows:
            raise ValueError("Validation hold-out partition cannot be empty for temporal validation.")

        X_train, y_train = self._extract_features_and_target(train_rows, fit_preprocessors=True)
        assert self.scaler is not None
        assert self.model is not None

        self.model.fit(X_train, y_train)
        self.is_trained = True

        report = self.evaluate(val_rows, train_rows=train_rows)
        self.evaluation_report = report

        # Store immutable artifact metadata
        train_timestamps = [r.prediction_timestamp for r in train_rows]
        val_timestamps = [r.prediction_timestamp for r in val_rows]
        self.metadata = {
            "model_version": MODEL_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "target_schema_version": TARGET_SCHEMA_VERSION,
            "training_timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "train_sample_count": len(train_rows),
            "validation_sample_count": len(val_rows),
            "feature_count": len(self.feature_names),
            "training_period": [min(train_timestamps).isoformat(), max(train_timestamps).isoformat()],
            "evaluation_period": [min(val_timestamps).isoformat(), max(val_timestamps).isoformat()],
            "evaluation_metrics": report.to_dict(),
        }

        return report

    def predict(self, row: DatasetRow) -> float:
        """Predict expected duration ratio for a single row."""
        if not self.is_trained or self.model is None or self.scaler is None:
            raise ValueError("Model must be trained before predicting.")

        features_df = pd.DataFrame([row.features])[list(FEATURE_NAMES)]
        X = self._transform_features(features_df)
        pred = float(self.model.predict(X)[0])
        # Duration ratio must be physically positive and reasonable
        return max(0.1, min(10.0, pred))

    def evaluate(self, rows: Sequence[DatasetRow], *, train_rows: Optional[Sequence[DatasetRow]] = None) -> EvaluationReport:
        """Evaluate model performance on an holdout set without data leakage."""
        if not self.is_trained or self.model is None or self.scaler is None:
            raise ValueError("Model must be trained before evaluation.")

        if not rows:
            raise ValueError("Evaluation rows cannot be empty.")

        y_true = np.array([float(r.target["duration_ratio"]) for r in rows], dtype=float)
        y_pred = np.array([self.predict(r) for r in rows], dtype=float)

        errors = y_pred - y_true
        abs_errors = np.abs(errors)
        pe = abs_errors / np.maximum(y_true, 1e-4)

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        mape = float(np.mean(pe)) * 100.0
        directional_bias = float(np.mean(errors))  # Positive = overestimating duration
        med_err = float(np.median(errors))

        eval_timestamps = [r.prediction_timestamp for r in rows]
        if train_rows:
            train_timestamps = [r.prediction_timestamp for r in train_rows]
            train_period = (min(train_timestamps).isoformat(), max(train_timestamps).isoformat())
            train_count = len(train_rows)
        else:
            train_period = ("N/A", "N/A")
            train_count = 0

        eval_period = (min(eval_timestamps).isoformat(), max(eval_timestamps).isoformat())

        return EvaluationReport(
            sample_count=len(rows),
            feature_count=len(self.feature_names),
            mae=round(mae, 4),
            rmse=round(rmse, 4),
            mape=round(mape, 2),
            directional_bias=round(directional_bias, 4),
            median_error=round(med_err, 4),
            training_period=train_period,
            evaluation_period=eval_period,
            train_sample_count=train_count,
            validation_sample_count=len(rows),
        )

    def _extract_features_and_target(
        self,
        rows: Sequence[DatasetRow],
        *,
        fit_preprocessors: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray]:
        data = [r.features for r in rows]
        targets = [float(r.target["duration_ratio"]) for r in rows]
        df = pd.DataFrame(data)[list(FEATURE_NAMES)]

        if fit_preprocessors:
            self.task_type_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
            task_type_onehot = self.task_type_encoder.fit_transform(df[["task_type"]])

            numeric_cols = [c for c in FEATURE_NAMES if c != "task_type"]
            self.scaler = StandardScaler()
            numeric_scaled = self.scaler.fit_transform(df[numeric_cols])

            X = np.hstack([numeric_scaled, task_type_onehot])
            self.model = Ridge(alpha=self.alpha)
        else:
            X = self._transform_features(df)

        return X, np.array(targets, dtype=float)

    def _transform_features(self, df: pd.DataFrame) -> np.ndarray:
        assert self.task_type_encoder is not None
        assert self.scaler is not None
        task_type_onehot = self.task_type_encoder.transform(df[["task_type"]])
        numeric_cols = [c for c in FEATURE_NAMES if c != "task_type"]
        numeric_scaled = self.scaler.transform(df[numeric_cols])
        return np.hstack([numeric_scaled, task_type_onehot])
