"""ProductivityModel - ML model for predicting task productivity.

Uses RandomForestRegressor to predict productivity scores (0-100) based on:
- Hour of day
- Task type
- Task duration

Handles model training, prediction, persistence, and feature importance extraction.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)


class ProductivityModel:
    """ML model for predicting productivity scores."""

    # Task types recognized by the model
    VALID_TASK_TYPES = {"coding", "research", "writing", "meeting", "admin"}

    def __init__(self, model_path: Optional[str] = None) -> None:
        """Initialize ProductivityModel.

        Args:
            model_path: Optional path to load a pre-trained model from disk.
                       If not provided, creates a new untrained model.
        """
        self.model_path = model_path
        self.model: Optional[RandomForestRegressor] = None
        self.is_trained = False
        self.feature_names = ["hour_of_day", "task_type_encoded", "duration"]
        self.task_type_encoder: Optional[LabelEncoder] = None
        self.training_data_shape: Optional[tuple] = None

        if model_path and Path(model_path).exists():
            self.load(model_path)

    def train(self, data: Union[pd.DataFrame, Dict[str, Any]]) -> Dict[str, float]:
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
        if isinstance(data, dict):
            data = pd.DataFrame([data])
        elif not isinstance(data, pd.DataFrame):
            raise ValueError("Data must be a pandas DataFrame or dict")

        if data.empty:
            raise ValueError("Training data cannot be empty")
        if len(data) < 3:
            raise ValueError("Training data must contain at least 3 samples")

        # Validate required columns
        required = {"hour_of_day", "task_type", "duration", "productivity_score"}
        missing = required - set(data.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Create working copy
        df = data.copy()

        # Initialize task type encoder
        self._ensure_task_type_encoder()

        # Prepare features
        try:
            X = self._prepare_features(df)
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            raise ValueError(f"Invalid training data: {e}") from e

        y = df["productivity_score"].values

        # Ensure numeric outputs
        y = np.clip(y, 0, 100)

        # Create and train model
        self.model = self._create_model()

        self.model.fit(X, y)
        self.is_trained = True
        self.training_data_shape = X.shape

        # Calculate metrics
        y_pred = self.model.predict(X)
        train_r2 = self.model.score(X, y)
        mae = float(np.mean(np.abs(y_pred - y)))
        rmse = float(np.sqrt(np.mean((y_pred - y) ** 2)))

        metrics = {
            "accuracy": float(np.clip(train_r2, 0, 1)),
            "mae": mae,
            "rmse": rmse,
            "samples": int(len(df)),
        }

        logger.info(f"Model trained: {metrics}")
        return metrics

    def predict(self, hour: int, task_type: str, duration: float) -> float:
        """Predict productivity for a single task.

        Args:
            hour: Hour of day (0-23)
            task_type: Type of task (coding, research, writing, meeting, admin)
            duration: Task duration in minutes

        Returns:
            Predicted productivity score (0-100)

        Raises:
            ValueError: If model not trained or inputs invalid
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        # Validate inputs
        if not isinstance(hour, (int, float)) or not (0 <= hour <= 23):
            raise ValueError(f"Hour must be 0-23, got {hour}")

        if task_type not in self.VALID_TASK_TYPES:
            raise ValueError(f"Task type must be one of {self.VALID_TASK_TYPES}, got {task_type}")

        if not isinstance(duration, (int, float)) or duration <= 0:
            raise ValueError(f"Duration must be > 0, got {duration}")

        self._ensure_task_type_encoder()

        # Prepare input
        X = np.array(
            [
                [
                    float(hour),
                    float(self.task_type_encoder.transform([task_type])[0]),
                    float(duration),
                ]
            ]
        )

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
                predictions.append(50.0)  # Default mid-range score

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
            self.is_trained = self.model is not None
            self._ensure_task_type_encoder()
            if self.is_trained and not self._loaded_model_is_compatible():
                logger.warning(
                    "Loaded model at %s is incompatible with the current sklearn runtime; retraining required.",
                    filepath,
                )
                self.model = self._create_model()
                self.is_trained = False
            logger.info(f"Model loaded from {filepath}")
        except Exception as e:
            raise ValueError(f"Error loading model: {e}") from e

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
        if self.model is None:
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
        task_types = df["task_type"].astype(str).values
        task_type_encoded = self.task_type_encoder.transform(task_types).astype(float)
        features.append(task_type_encoded)

        # Duration (minutes, normalized)
        duration = df["duration"].astype(float).values
        features.append(duration)

        return np.column_stack(features)
