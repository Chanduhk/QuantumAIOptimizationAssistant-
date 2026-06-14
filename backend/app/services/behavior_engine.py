from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.ai_models.productivity_model import ProductivityModel
from backend.app.models.behavior_data import BehaviorData
from backend.app.models.task import Task


class BehaviorIntelligenceEngine:
    """Analyze task history, derive behavioral features, and train user models."""

    def __init__(self, session: Session, model_directory: Optional[str] = None) -> None:
        self.session = session
        self.model_directory = Path(
            model_directory
            or Path(__file__).resolve().parents[2] / "artifacts" / "productivity_models"
        )
        self.active_user_id: Optional[int] = None
        self.productivity_model: Optional[ProductivityModel] = None
        self.raw_tasks_df = pd.DataFrame()
        self.behavior_data_df = pd.DataFrame()
        self.user_patterns: Dict[str, Any] = {}

    def _get_model_path(self, user_id: int) -> Path:
        return self.model_directory / f"user_{user_id}_productivity_model.joblib"

    def _set_active_user(self, user_id: int) -> None:
        self.active_user_id = user_id
        self.productivity_model = ProductivityModel(model_path=str(self._get_model_path(user_id)))

    def collect_behavior_data(self, user_id: int, days_back: int = 90) -> pd.DataFrame:
        """Load completed task history for a user."""
        self._set_active_user(user_id)
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        tasks = (
            self.session.query(Task)
            .filter(Task.user_id == user_id, Task.completed.is_(True))
            .filter(Task.start_time.is_not(None), Task.end_time.is_not(None))
            .filter(Task.start_time >= cutoff)
            .order_by(Task.start_time.asc())
            .all()
        )

        self.raw_tasks_df = pd.DataFrame(
            [
                {
                    "id": task.id,
                    "user_id": task.user_id,
                    "title": task.title,
                    "task_type": task.task_type,
                    "priority": task.priority,
                    "estimated_duration": task.estimated_duration,
                    "actual_duration": task.actual_duration,
                    "start_time": task.start_time,
                    "end_time": task.end_time,
                    "completed": task.completed,
                }
                for task in tasks
            ]
        )
        return self.raw_tasks_df

    def extract_features(self) -> pd.DataFrame:
        """Convert raw task history into normalized behavioral features."""
        if self.raw_tasks_df.empty:
            raise ValueError("No task history available. Call collect_behavior_data first.")

        frame = self.raw_tasks_df.copy()
        required_columns = {
            "id",
            "user_id",
            "task_type",
            "priority",
            "estimated_duration",
            "actual_duration",
            "start_time",
            "end_time",
        }
        missing_columns = required_columns - set(frame.columns)
        if missing_columns:
            raise ValueError(f"Missing required task history columns: {sorted(missing_columns)}")

        frame["start_time"] = pd.to_datetime(frame["start_time"])
        frame["end_time"] = pd.to_datetime(frame["end_time"])
        frame["hour_of_day"] = frame["start_time"].dt.hour.astype(int)
        frame["duration"] = frame["actual_duration"].fillna(frame["estimated_duration"]).fillna(0.0)
        frame["duration"] = frame["duration"].clip(lower=1.0)

        estimated = frame["estimated_duration"].fillna(frame["duration"]).clip(lower=1.0)
        frame["completion_time"] = (frame["duration"] / estimated).clip(lower=0.25, upper=3.0)

        # Heuristic scoring provides stable labels for supervised training.
        priority_component = frame["priority"].fillna(3).clip(lower=1, upper=5) * 8.0
        duration_efficiency = (1.2 - (frame["completion_time"] - 1.0).abs()).clip(lower=0.2) * 35.0
        time_focus = (1.0 - ((frame["hour_of_day"] - 10).abs() / 12.0)).clip(lower=0.1) * 35.0
        energy_curve = (1.0 - ((frame["hour_of_day"] - 14).abs() / 14.0)).clip(lower=0.15) * 100.0

        frame["focus_score"] = (priority_component + duration_efficiency + time_focus).clip(0, 100)
        frame["energy_level"] = energy_curve.clip(0, 100)
        frame["productivity_score"] = (
            0.45 * frame["focus_score"]
            + 0.35 * frame["energy_level"]
            + 0.20 * (100.0 / frame["completion_time"])
        ).clip(0, 100)

        behavior_columns = [
            "user_id",
            "id",
            "hour_of_day",
            "task_type",
            "duration",
            "focus_score",
            "energy_level",
            "completion_time",
            "productivity_score",
        ]
        self.behavior_data_df = (
            frame[behavior_columns].rename(columns={"id": "task_id"}).reset_index(drop=True)
        )
        return self.behavior_data_df

    def _sync_behavior_rows(self) -> None:
        """Store the derived rows for later analytics and traceability."""
        if self.behavior_data_df.empty:
            return

        task_ids = self.behavior_data_df["task_id"].tolist()
        self.session.query(BehaviorData).filter(BehaviorData.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )

        records = [
            BehaviorData(
                user_id=int(row.user_id),
                task_id=int(row.task_id),
                hour_of_day=int(row.hour_of_day),
                task_type=str(row.task_type),
                duration=float(row.duration),
                focus_score=float(row.focus_score),
                energy_level=float(row.energy_level),
                completion_time=float(row.completion_time),
                productivity_score=float(row.productivity_score),
            )
            for row in self.behavior_data_df.itertuples(index=False)
        ]
        self.session.add_all(records)
        self.session.commit()

    def train_productivity_model(self) -> Dict[str, float]:
        """Train and persist the productivity model for the active user."""
        if self.productivity_model is None or self.active_user_id is None:
            raise ValueError("No active user selected. Call collect_behavior_data first.")
        if self.behavior_data_df.empty:
            self.extract_features()

        self._sync_behavior_rows()
        metrics = self.productivity_model.train(self.behavior_data_df)
        metrics["user_id"] = float(self.active_user_id)
        return metrics

    def get_user_patterns(self) -> Dict[str, Any]:
        """Summarize recurring productivity patterns for the active user."""
        if self.behavior_data_df.empty:
            self.extract_features()

        grouped_hours = self.behavior_data_df.groupby("hour_of_day")["productivity_score"].mean()
        grouped_tasks = self.behavior_data_df.groupby("task_type")["productivity_score"].mean()
        duration_by_task = self.behavior_data_df.groupby("task_type")["duration"].mean()

        self.user_patterns = {
            "user_id": self.active_user_id,
            "tasks_analyzed": int(len(self.behavior_data_df)),
            "average_productivity": round(float(self.behavior_data_df["productivity_score"].mean()), 2),
            "average_focus_score": round(float(self.behavior_data_df["focus_score"].mean()), 2),
            "average_energy_level": round(float(self.behavior_data_df["energy_level"].mean()), 2),
            "average_completion_time": round(float(self.behavior_data_df["completion_time"].mean()), 2),
            "best_focus_hours": grouped_hours.sort_values(ascending=False).head(3).index.astype(int).tolist(),
            "preferred_task_types": grouped_tasks.sort_values(ascending=False).head(3).index.astype(str).tolist(),
            "hourly_productivity": {
                int(hour): round(float(score), 2)
                for hour, score in grouped_hours.sort_index().items()
            },
            "productivity_by_task_type": {
                str(task_type): round(float(score), 2)
                for task_type, score in grouped_tasks.sort_values(ascending=False).items()
            },
            "average_duration_by_task_type": {
                str(task_type): round(float(duration), 2)
                for task_type, duration in duration_by_task.sort_values(ascending=False).items()
            },
        }
        return self.user_patterns

    def predict_task_productivity(self, hour_of_day: int, task_type: str, duration: float) -> float:
        """Predict productivity for a planned task for the active user."""
        if self.productivity_model is None:
            raise ValueError("No active user selected. Call collect_behavior_data first.")

        if not self.productivity_model.is_trained:
            if self.behavior_data_df.empty:
                raise ValueError("No training data available for the active user.")
            self.train_productivity_model()

        return self.productivity_model.predict(hour_of_day, task_type, duration)

    def generate_report(self) -> str:
        """Generate a concise human-readable report."""
        patterns = self.get_user_patterns()
        best_hours = ", ".join(str(hour) for hour in patterns["best_focus_hours"]) or "n/a"
        preferred_types = ", ".join(patterns["preferred_task_types"]) or "n/a"

        return "\n".join(
            [
                "Quantum Life AI Behavior Report",
                f"User ID: {patterns['user_id']}",
                f"Tasks analyzed: {patterns['tasks_analyzed']}",
                f"Average productivity score: {patterns['average_productivity']}",
                f"Average focus score: {patterns['average_focus_score']}",
                f"Average energy level: {patterns['average_energy_level']}",
                f"Average completion time ratio: {patterns['average_completion_time']}",
                f"Best focus hours: {best_hours}",
                f"Preferred task types: {preferred_types}",
            ]
        )
