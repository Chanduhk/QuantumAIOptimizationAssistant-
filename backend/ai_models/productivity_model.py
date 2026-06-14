from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


class ProductivityModel:
    """Random-forest regressor for predicting a user's productivity score."""

    feature_columns = ["hour_of_day", "task_type_encoded", "duration"]

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.model = RandomForestRegressor(
            n_estimators=300,
            random_state=42,
            min_samples_leaf=1,
            n_jobs=-1,
        )
        self.task_type_mapping: Dict[str, int] = {}
        self.is_trained = False

        if model_path and Path(model_path).exists():
            self.load_model(model_path)

    def _fit_task_type_mapping(self, task_types: Sequence[str]) -> None:
        unique_types = sorted(
            {str(task_type).strip().lower() for task_type in task_types if str(task_type).strip()}
        )
        if "other" not in unique_types:
            unique_types.append("other")
        self.task_type_mapping = {task_type: index for index, task_type in enumerate(unique_types)}

    def _encode_task_type(self, task_type: str) -> int:
        normalized = (task_type or "other").strip().lower()
        return self.task_type_mapping.get(normalized, self.task_type_mapping.get("other", 0))

    def _prepare_training_frame(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        required = {"hour_of_day", "task_type", "duration", "productivity_score"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"Missing required columns for training: {missing}")

        training_frame = frame[["hour_of_day", "task_type", "duration", "productivity_score"]].copy()
        training_frame["hour_of_day"] = pd.to_numeric(training_frame["hour_of_day"], errors="coerce")
        training_frame["duration"] = pd.to_numeric(training_frame["duration"], errors="coerce")
        training_frame["productivity_score"] = pd.to_numeric(
            training_frame["productivity_score"], errors="coerce"
        )
        training_frame["task_type"] = training_frame["task_type"].astype(str).str.strip().str.lower()
        training_frame = training_frame.dropna()

        if len(training_frame) < 5:
            raise ValueError("At least 5 behavior records are required to train the model.")

        self._fit_task_type_mapping(training_frame["task_type"].tolist())
        training_frame["task_type_encoded"] = training_frame["task_type"].map(self._encode_task_type)

        features = training_frame[self.feature_columns].astype(
            {"hour_of_day": int, "task_type_encoded": int, "duration": float}
        )
        target = training_frame["productivity_score"].astype(float)
        return features, target

    def train(self, frame: pd.DataFrame) -> Dict[str, float]:
        """Train the model and return evaluation metrics."""
        features, target = self._prepare_training_frame(frame)

        if len(features) >= 10:
            x_train, x_test, y_train, y_test = train_test_split(
                features,
                target,
                test_size=0.2,
                random_state=42,
            )
            evaluation_features = x_test
            evaluation_target = y_test
        else:
            x_train = features
            y_train = target
            evaluation_features = features
            evaluation_target = target

        self.model.fit(x_train, y_train)
        predictions = self.model.predict(evaluation_features)
        self.is_trained = True

        if self.model_path:
            self.save_model(self.model_path)

        rmse = mean_squared_error(evaluation_target, predictions, squared=False)
        r2_value = float(r2_score(evaluation_target, predictions)) if len(evaluation_target) > 1 else 1.0

        return {
            "training_samples": float(len(x_train)),
            "evaluation_samples": float(len(evaluation_features)),
            "r2_score": r2_value,
            "mae": float(mean_absolute_error(evaluation_target, predictions)),
            "rmse": float(rmse),
        }

    def predict(self, hour_of_day: int, task_type: str, duration: float) -> float:
        """Predict productivity for a single task."""
        if not self.is_trained:
            if self.model_path and Path(self.model_path).exists():
                self.load_model(self.model_path)
            else:
                raise ValueError("Model has not been trained.")

        input_frame = pd.DataFrame(
            [
                {
                    "hour_of_day": int(hour_of_day),
                    "task_type_encoded": self._encode_task_type(task_type),
                    "duration": float(duration),
                }
            ]
        )
        prediction = self.model.predict(input_frame)[0]
        return float(max(0.0, min(100.0, prediction)))

    def predict_batch(self, tasks: Iterable[dict]) -> List[float]:
        """Predict productivity for multiple tasks."""
        return [
            self.predict(
                hour_of_day=task["hour_of_day"],
                task_type=task["task_type"],
                duration=task["duration"],
            )
            for task in tasks
        ]

    def save_model(self, model_path: Optional[str] = None) -> None:
        """Persist the trained model and task-type mapping."""
        target_path = model_path or self.model_path
        if not target_path:
            raise ValueError("A model path is required to save the model.")

        payload = {
            "model": self.model,
            "task_type_mapping": self.task_type_mapping,
            "is_trained": self.is_trained,
        }
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(payload, target_path)

    def load_model(self, model_path: Optional[str] = None) -> None:
        """Load a previously trained model from disk."""
        target_path = model_path or self.model_path
        if not target_path:
            raise ValueError("A model path is required to load the model.")

        payload = joblib.load(target_path)
        self.model = payload["model"]
        self.task_type_mapping = payload["task_type_mapping"]
        self.is_trained = payload["is_trained"]
        self.model_path = target_path
