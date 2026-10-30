"""ProductivityModel - ML model for predicting task productivity.

Uses RandomForestRegressor to predict productivity scores (0-100) based on:
- Hour of day
- Task type
- Task duration

Handles model training, prediction, persistence, and feature importance extraction.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from backend.app.domain.optimization_input_contract import normalize_duration

logger = logging.getLogger(__name__)


class ProductivityModel:
    """ML model for predicting productivity scores."""

    MODEL_VERSION = "productivity-rf-v1"
    FEATURE_SCHEMA_VERSION = "productivity-features-v1"
    TARGET_SCHEMA_VERSION = "heuristic-productivity-v1"
    DATASET_SCHEMA_VERSION = "behavior-dataset-v2"
    FEATURE_NAMES = ("hour_of_day", "task_type_encoded", "duration_hours")

    # Task types recognized by the model
    VALID_TASK_TYPES = {"coding", "research", "writing", "meeting", "admin", "other"}

    def __init__(self, model_path: Optional[str] = None) -> None:
        """Initialize ProductivityModel.

        Args:
            model_path: Optional path to load a pre-trained model from disk.
                       If not provided, creates a new untrained model.
        """
        self.model_path = model_path
        self.model: Optional[RandomForestRegressor] = None
        self.is_trained = False
        self.feature_names = list(self.FEATURE_NAMES)
        self.metadata: Optional[Dict[str, Any]] = None
        self.compatibility_status = "UNTRAINED"
        self.readiness_status = "NOT_READY_NO_GROUND_TRUTH_LABELS"
        self.demo_mode = False
        self.task_type_encoder: Optional[LabelEncoder] = None
        self.training_data_shape: Optional[tuple] = None

        if model_path and Path(model_path).exists():
            if "demo" in str(model_path).lower():
                self.demo_mode = True
                self.readiness_status = "DEMO_ONLY"
            self.load(model_path)

    def train(self, data: Union[pd.DataFrame, Dict[str, Any]]) -> Dict[str, Any]:
        """Train the productivity model.

        Args:
            data: Training data as a pandas DataFrame with columns:
                  - hour_of_day: int (0-23)
                  - task_type: str (coding, research, writing, meeting, admin)
                  - duration: float (minutes)
                  - productivity_score: float (0-100, target)

        Returns:
            Dictionary with training metrics:
            - accuracy: R² score on training data
            - mae: Mean Absolute Error
            - rmse: Root Mean Squared Error
            - samples: Number of training samples

        Raises:
            ValueError: If data is invalid or missing required columns
        """
        if not isinstance(data, pd.DataFrame):
            raise ValueError("Training data must be a provenance-tagged pandas DataFrame")

        if data.empty:
            raise ValueError("Training data cannot be empty")
        if len(data) < 5:
            raise ValueError("Training data must contain at least 5 samples for a held-out validation set")
        duration_unit = data.attrs.get("duration_unit")
        dataset_version = data.attrs.get("dataset_schema_version")
        target_version = data.attrs.get("target_schema_version")
        if duration_unit not in {"minutes", "hours"}:
            raise ValueError("Training duration unit must be explicitly tagged as minutes or hours")
        if dataset_version != self.DATASET_SCHEMA_VERSION:
            raise ValueError("Training dataset schema is missing or incompatible")
        if target_version != self.TARGET_SCHEMA_VERSION:
            raise ValueError("Training target schema is missing or incompatible")

        # Validate required columns
        required = {"hour_of_day", "task_type", "duration", "productivity_score"}
        missing = required - set(data.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Create working copy
        df = data.copy()

        # Initialize task type encoder
        self._ensure_task_type_encoder()

        # Normalize explicitly tagged duration values once. The model schema
        # and all inference inputs use hours.
        try:
            df["duration"] = [
                normalize_duration(value, duration_unit, "training_dataframe.duration").normalized_hours
                for value in pd.to_numeric(df["duration"], errors="raise").tolist()
            ]
            X = self._prepare_features(df)
        except Exception as e:
            logger.error("Error preparing productivity features: %s", type(e).__name__)
            raise ValueError(f"Invalid training data: {type(e).__name__}") from e

        y = pd.to_numeric(df["productivity_score"], errors="raise").to_numpy(dtype=float)
        if not np.isfinite(y).all():
            raise ValueError("Training targets must be finite")

        # Ensure numeric outputs
        y = np.clip(y, 0, 100)

        train_x, validation_x, train_y, validation_y = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        validation_model = self._create_model()
        validation_model.fit(train_x, train_y)
        validation_prediction = validation_model.predict(validation_x)
        validation_r2 = float(validation_model.score(validation_x, validation_y)) if len(validation_y) > 1 else 0.0
        metrics = {
            "validation_r2": validation_r2,
            "validation_mae": float(np.mean(np.abs(validation_prediction - validation_y))),
            "validation_rmse": float(np.sqrt(np.mean((validation_prediction - validation_y) ** 2))),
            "training_samples": int(len(train_y)),
            "validation_samples": int(len(validation_y)),
            "mae": float(np.mean(np.abs(validation_prediction - validation_y))),
            "rmse": float(np.sqrt(np.mean((validation_prediction - validation_y) ** 2))),
        }

        self.model = self._create_model()
        self.model.fit(X, y)
        self.is_trained = True
        self.training_data_shape = X.shape
        self.metadata = {
            "model_version": self.MODEL_VERSION,
            "feature_schema_version": self.FEATURE_SCHEMA_VERSION,
            "target_schema_version": self.TARGET_SCHEMA_VERSION,
            "duration_unit": "hours",
            "training_duration_unit": duration_unit,
            "feature_names": list(self.FEATURE_NAMES),
            "training_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "training_sample_count": int(len(X)),
            "dataset_schema_version": dataset_version,
            "target_semantics": "heuristic_derived_productivity_proxy_not_observed_ground_truth",
            "validation_metrics": metrics.copy(),
        }
        self.compatibility_status = "OPTIMIZATION_COMPATIBLE"
        logger.info("Productivity model trained with %d samples", len(X))
        return {**metrics, "samples": int(len(X))}

    def predict(self, hour: int, task_type: str, duration: float) -> float:
        """Predict productivity for a single task.

        Args:
            hour: Hour of day (0-23)
            task_type: Type of task (coding, research, writing, meeting, admin)
            duration: Task duration in hours

        Returns:
            Predicted productivity score (0-100)

        Raises:
            ValueError: If model not trained or inputs invalid
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        # Validate inputs
        if isinstance(hour, bool) or not isinstance(hour, (int, float)) or not np.isfinite(hour) or not (0 <= hour <= 23):
            raise ValueError(f"Hour must be 0-23, got {hour}")

        # If task type is unknown, fall back to "other" if supported, else leave as is (will raise in encoder or retrain)
        if task_type not in self.VALID_TASK_TYPES:
            task_type = "other"

        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not np.isfinite(duration) or duration <= 0:
            raise ValueError("Duration in hours must be positive and finite")
        if not self._metadata_is_compatible():
            raise ValueError("Model metadata is missing or incompatible")

        self._ensure_task_type_encoder()

        # Prepare input
        inference_frame = pd.DataFrame([{
            "hour_of_day": float(hour),
            "task_type": task_type,
            "duration": float(duration),
        }])
        X = self._prepare_features(inference_frame)

        # Predict and clip to valid range
        prediction = float(self.model.predict(X)[0])
        return float(np.clip(prediction, 0, 100))

    def predict_batch(self, tasks: List[Dict[str, Any]]) -> List[float]:
        """Predict productivity for multiple tasks.

        Args:
            tasks: List of dicts with keys: hour, task_type, duration

        Returns:
            List of predicted productivity scores
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        predictions = []
        for task in tasks:
            try:
                pred = self.predict(
                    hour=int(task["hour"]),
                    task_type=str(task["task_type"]),
                    duration=float(task["duration"]),
                )
                predictions.append(pred)
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping invalid task {task}: {e}")
                raise ValueError(f"Invalid prediction input: {type(e).__name__}") from e

        return predictions

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the trained model.

        Returns:
            Dictionary mapping feature names to importance values (0-1)

        Raises:
            ValueError: If model not trained
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        importances = self.model.feature_importances_
        return {
            name: float(imp) for name, imp in zip(self.feature_names, importances)
        }

    def save(self, filepath: str) -> None:
        """Persist model to disk.

        Args:
            filepath: Path where model will be saved

        Raises:
            ValueError: If model not trained
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save model and metadata
        model_data = {
            "model": self.model,
            "task_type_encoder": self.task_type_encoder,
            "feature_names": self.feature_names,
            "training_data_shape": self.training_data_shape,
            "metadata": self.metadata,
        }

        joblib.dump(model_data, filepath)
        logger.info(f"Model saved to {filepath}")

    def load(self, filepath: str) -> None:
        """Load model from disk.

        Args:
            filepath: Path to load model from

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is invalid
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")

        try:
            model_data = joblib.load(filepath)
            self.model = model_data.get("model")
            self.task_type_encoder = model_data.get("task_type_encoder")
            self.feature_names = model_data.get("feature_names", self.feature_names)
            self.training_data_shape = model_data.get("training_data_shape")
            self.metadata = model_data.get("metadata")
            self.is_trained = self.model is not None
            self.compatibility_status = "OPTIMIZATION_COMPATIBLE" if self._metadata_is_compatible() else "MODEL_ARTIFACT_UNVERIFIED"
            self._ensure_task_type_encoder()
            if self.is_trained and (not self._metadata_is_compatible() or not self._loaded_model_is_compatible()):
                logger.warning(
                    "Loaded model at %s is unavailable because its runtime or data-contract compatibility is unverified.",
                    filepath,
                )
                self.model = None
                self.is_trained = False
            logger.info(f"Model loaded from {filepath}")
        except Exception as e:
            raise ValueError(f"Error loading model: {e}") from e


    def _metadata_is_compatible(self) -> bool:
        metadata = self.metadata
        if not isinstance(metadata, dict):
            return False
        required = {
            "model_version": self.MODEL_VERSION,
            "feature_schema_version": self.FEATURE_SCHEMA_VERSION,
            "target_schema_version": self.TARGET_SCHEMA_VERSION,
            "duration_unit": "hours",
            "feature_names": list(self.FEATURE_NAMES),
            "dataset_schema_version": self.DATASET_SCHEMA_VERSION,
            "target_semantics": "heuristic_derived_productivity_proxy_not_observed_ground_truth",
        }
        if any(metadata.get(key) != value for key, value in required.items()):
            return False
        if not isinstance(metadata.get("training_timestamp_utc"), str):
            return False
        if not isinstance(metadata.get("training_sample_count"), int) or metadata["training_sample_count"] < 5:
            return False
        if metadata.get("training_duration_unit") not in {"minutes", "hours"}:
            return False
        if not isinstance(metadata.get("training_timestamp_utc"), str):
            return False
        try:
            datetime.fromisoformat(metadata["training_timestamp_utc"])
        except ValueError:
            return False
        metrics = metadata.get("validation_metrics")
        if not isinstance(metrics, dict):
            return False
        for key in ("validation_r2", "validation_mae", "validation_rmse"):
            value = metrics.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
                return False
        return True

    def _create_model(self) -> RandomForestRegressor:
        """Create the standard RandomForestRegressor used by this model."""
        return RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )

    def _loaded_model_is_compatible(self) -> bool:
        """Return whether a loaded persisted model can predict in this runtime."""
        if self.model is None or self.task_type_encoder is None:
            return False
        # If the loaded model doesn't know about "other", it's incompatible and should retrain
        if "other" not in self.task_type_encoder.classes_:
            return False
        try:
            self.model.predict(np.array([[9.0, 0.0, 60.0]]))
            return True
        except Exception:
            logger.exception("Persisted productivity model compatibility check failed.")
            return False

    def _ensure_task_type_encoder(self) -> None:
        """Ensure the task-type encoder exists for current and legacy model artifacts."""
        if self.task_type_encoder is None:
            self.task_type_encoder = LabelEncoder()
            sorted_types = sorted(list(self.VALID_TASK_TYPES))
            self.task_type_encoder.fit(sorted_types)

    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare feature matrix from dataframe.

        Args:
            df: DataFrame with hour_of_day, task_type, duration columns

        Returns:
            Feature matrix suitable for model training/prediction
        """
        features = []

        # Hour of day (0-23)
        hour_of_day = df["hour_of_day"].astype(float).values
        features.append(hour_of_day)

        # Task type (encoded)
        task_types_raw = df["task_type"].astype(str).values
        # Map unseen labels to "other"
        known_types = set(self.task_type_encoder.classes_)
        task_types = [t if t in known_types else "other" for t in task_types_raw]
        task_type_encoded = self.task_type_encoder.transform(task_types).astype(float)
        features.append(task_type_encoded)

        # Duration is normalized to hours before feature preparation for both
        # fitting and inference. Keep the feature order versioned and explicit.
        duration = pd.to_numeric(df["duration"], errors="raise").to_numpy(dtype=float)
        if not np.isfinite(duration).all() or (duration <= 0).any():
            raise ValueError("duration_hours must be positive and finite")
        features.append(duration)

        return np.column_stack(features)
