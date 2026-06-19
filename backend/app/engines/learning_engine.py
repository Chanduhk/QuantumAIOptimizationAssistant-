from __future__ import annotations

import math
from typing import Any, Dict

from backend.app.ai_rl import RLScheduler
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine


class LearningEngine:
    """Autonomous learning loop for retraining models and updating RL policy."""

    def detect_model_drift(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        user_id: int,
        days_back: int = 90,
    ) -> Dict[str, Any]:
        self._validate_behavior_engine(behavior_engine)
        self._validate_user_id(user_id)
        self._validate_days_back(days_back)
        tasks = behavior_engine.collect_behavior_data(user_id=user_id, days_back=days_back)
        self._validate_task_history(tasks)

        feature_frame = behavior_engine.extract_features()
        productivity_scores = self._extract_productivity_scores(
            feature_frame,
            require_min_records=2,
        )
        recent_scores = productivity_scores[-min(10, len(productivity_scores)) :]
        recent_average = self._finite_number(
            sum(recent_scores) / len(recent_scores),
            field_name="recent_average_productivity",
        )
        historical_average = self._finite_number(
            sum(productivity_scores) / len(productivity_scores),
            field_name="historical_average_productivity",
        )
        drift_score = abs(recent_average - historical_average)
        drift_score = self._finite_number(drift_score, field_name="drift_score")

        result = {
            "user_id": user_id,
            "drift_score": round(drift_score, 4),
            "recent_average_productivity": round(recent_average, 2),
            "historical_average_productivity": round(historical_average, 2),
            "drift_detected": drift_score >= 7.5,
        }
        self._validate_drift_output(result)
        return result

    def retrain_productivity_model(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        user_id: int,
        days_back: int = 90,
    ) -> Dict[str, Any]:
        self._validate_behavior_engine(behavior_engine)
        self._validate_user_id(user_id)
        self._validate_days_back(days_back)
        tasks = behavior_engine.collect_behavior_data(user_id=user_id, days_back=days_back)
        self._validate_task_history(tasks)

        feature_frame = behavior_engine.extract_features()
        self._extract_productivity_scores(feature_frame, require_min_records=1)
        metrics = behavior_engine.train_productivity_model()
        patterns = behavior_engine.get_user_patterns()

        result = {
            "metrics": metrics,
            "patterns": patterns,
            "report": behavior_engine.generate_report(),
        }
        self._validate_retraining_output(result)
        return result

    def update_rl_policy(
        self,
        rl_scheduler: RLScheduler,
        tasks: list[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        episodes: int = 25,
    ) -> Dict[str, Any]:
        self._validate_rl_scheduler(rl_scheduler)
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
        if not isinstance(episodes, int) or isinstance(episodes, bool) or episodes <= 0:
            raise ValueError("episodes must be greater than zero.")
        if behavior_patterns is None:
            behavior_patterns = {}
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        result = rl_scheduler.train_agent(tasks, behavior_patterns, episodes=episodes)
        self._validate_rl_output(result)
        return result

    def update_model(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        rl_scheduler: RLScheduler,
        user_id: int,
        days_back: int = 90,
    ) -> Dict[str, Any]:
        self._validate_behavior_engine(behavior_engine)
        self._validate_rl_scheduler(rl_scheduler)
        self._validate_user_id(user_id)
        self._validate_days_back(days_back)
        drift = self.detect_model_drift(
            behavior_engine,
            user_id=user_id,
            days_back=days_back,
        )
        self._validate_drift_output(drift)
        retraining_output = self.retrain_productivity_model(
            behavior_engine,
            user_id=user_id,
            days_back=days_back,
        )
        self._validate_retraining_output(retraining_output)
        feature_records = self._feature_records(behavior_engine)
        rl_update = self.update_rl_policy(
            rl_scheduler,
            feature_records,
            retraining_output["patterns"],
        )
        self._validate_rl_output(rl_update)

        return {
            "drift": drift,
            "retraining": retraining_output,
            "rl_policy_update": rl_update,
        }

    def _validate_behavior_engine(self, behavior_engine: BehaviorIntelligenceEngine) -> None:
        required_methods = (
            "collect_behavior_data",
            "extract_features",
            "train_productivity_model",
            "get_user_patterns",
            "generate_report",
        )
        if behavior_engine is None:
            raise ValueError("behavior_engine is required.")
        missing = [
            method
            for method in required_methods
            if not callable(getattr(behavior_engine, method, None))
        ]
        if missing:
            raise ValueError(f"behavior_engine missing required methods: {missing}.")

    def _validate_rl_scheduler(self, rl_scheduler: RLScheduler) -> None:
        if rl_scheduler is None or not callable(getattr(rl_scheduler, "train_agent", None)):
            raise ValueError("rl_scheduler must provide train_agent.")

    def _validate_user_id(self, user_id: int) -> None:
        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            raise ValueError("user_id must be a positive integer.")

    def _validate_days_back(self, days_back: int) -> None:
        if not isinstance(days_back, int) or isinstance(days_back, bool) or days_back <= 0:
            raise ValueError("days_back must be greater than zero.")

    def _validate_task_history(self, tasks: Any) -> None:
        if tasks is None:
            raise ValueError("Task history cannot be None.")
        if not hasattr(tasks, "empty") or not hasattr(tasks, "columns"):
            raise ValueError("Task history must be a DataFrame-like object.")
        if tasks.empty:
            raise ValueError("No completed tasks found for the user.")

    def _extract_productivity_scores(
        self,
        feature_frame: Any,
        *,
        require_min_records: int,
    ) -> list[float]:
        if feature_frame is None:
            raise ValueError("Feature frame cannot be None.")
        if not hasattr(feature_frame, "empty") or not hasattr(feature_frame, "columns"):
            raise ValueError("Feature frame must be a DataFrame-like object.")
        if feature_frame.empty:
            raise ValueError("Feature frame cannot be empty.")
        if "productivity_score" not in feature_frame.columns:
            raise ValueError("Feature frame missing productivity_score.")

        scores = [
            self._finite_number(value, field_name="productivity_score")
            for value in feature_frame["productivity_score"].tolist()
        ]
        if len(scores) < require_min_records:
            raise ValueError("Insufficient productivity history for analysis.")
        return scores

    def _feature_records(self, behavior_engine: BehaviorIntelligenceEngine) -> list[Dict[str, Any]]:
        feature_frame = getattr(behavior_engine, "behavior_data_df", None)
        self._extract_productivity_scores(feature_frame, require_min_records=1)
        if not callable(getattr(feature_frame, "to_dict", None)):
            raise ValueError("Feature frame cannot be converted to records.")
        records = feature_frame.to_dict(orient="records")
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise ValueError("Feature records must be a list of dictionaries.")
        return records

    def _validate_drift_output(self, output: Dict[str, Any]) -> None:
        if not isinstance(output, dict):
            raise ValueError("Drift output must be a dictionary.")
        for key in ("drift_score", "recent_average_productivity", "historical_average_productivity"):
            self._finite_number(output.get(key), field_name=key)
        if not isinstance(output.get("drift_detected"), bool):
            raise ValueError("drift_detected must be a boolean.")

    def _validate_retraining_output(self, output: Dict[str, Any]) -> None:
        if not isinstance(output, dict):
            raise ValueError("Retraining output must be a dictionary.")
        metrics = output.get("metrics")
        patterns = output.get("patterns")
        report = output.get("report")
        if not isinstance(metrics, dict) or not metrics:
            raise ValueError("Training metrics must be a non-empty dictionary.")
        for value in metrics.values():
            if isinstance(value, bool):
                raise ValueError("training metrics must be numeric.")
            self._finite_number(value, field_name="training metrics")
        if not isinstance(patterns, dict):
            raise ValueError("Behavior patterns must be a dictionary.")
        if report is None or not isinstance(report, (str, dict)):
            raise ValueError("Behavior report must be a string or dictionary.")

    def _validate_rl_output(self, output: Dict[str, Any]) -> None:
        if not isinstance(output, dict) or not output:
            raise ValueError("RL output must be a non-empty dictionary.")
        self._validate_numeric_payload(output, field_name="RL output")

    def _validate_numeric_payload(self, payload: Any, *, field_name: str) -> None:
        if isinstance(payload, dict):
            for value in payload.values():
                self._validate_numeric_payload(value, field_name=field_name)
            return
        if isinstance(payload, list):
            for value in payload:
                self._validate_numeric_payload(value, field_name=field_name)
            return
        if isinstance(payload, bool) or payload is None:
            return
        if isinstance(payload, (int, float)):
            self._finite_number(payload, field_name=field_name)

    def _finite_number(self, value: Any, *, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return number
