from __future__ import annotations

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
        if days_back <= 0:
            raise ValueError("days_back must be greater than zero.")
        tasks = behavior_engine.collect_behavior_data(user_id=user_id, days_back=days_back)
        if tasks.empty:
            raise ValueError("No completed tasks found for the user.")

        feature_frame = behavior_engine.extract_features()
        recent_average = float(feature_frame["productivity_score"].tail(min(10, len(feature_frame))).mean())
        historical_average = float(feature_frame["productivity_score"].mean())
        drift_score = abs(recent_average - historical_average)

        return {
            "user_id": user_id,
            "drift_score": round(drift_score, 4),
            "recent_average_productivity": round(recent_average, 2),
            "historical_average_productivity": round(historical_average, 2),
            "drift_detected": drift_score >= 7.5,
        }

    def retrain_productivity_model(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        user_id: int,
        days_back: int = 90,
    ) -> Dict[str, Any]:
        if days_back <= 0:
            raise ValueError("days_back must be greater than zero.")
        tasks = behavior_engine.collect_behavior_data(user_id=user_id, days_back=days_back)
        if tasks.empty:
            raise ValueError("No completed tasks found for the user.")

        behavior_engine.extract_features()
        metrics = behavior_engine.train_productivity_model()
        patterns = behavior_engine.get_user_patterns()

        return {
            "metrics": metrics,
            "patterns": patterns,
            "report": behavior_engine.generate_report(),
        }

    def update_rl_policy(
        self,
        rl_scheduler: RLScheduler,
        tasks: list[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        episodes: int = 25,
    ) -> Dict[str, Any]:
        if tasks is None:
            raise ValueError("tasks must be a list of dictionaries.")
        if episodes <= 0:
            raise ValueError("episodes must be greater than zero.")
        if behavior_patterns is None:
            behavior_patterns = {}
        return rl_scheduler.train_agent(tasks, behavior_patterns, episodes=episodes)

    def update_model(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        rl_scheduler: RLScheduler,
        user_id: int,
        days_back: int = 90,
    ) -> Dict[str, Any]:
        drift = self.detect_model_drift(
            behavior_engine,
            user_id=user_id,
            days_back=days_back,
        )
        retraining_output = self.retrain_productivity_model(
            behavior_engine,
            user_id=user_id,
            days_back=days_back,
        )
        feature_records = behavior_engine.behavior_data_df.to_dict(orient="records")
        rl_update = self.update_rl_policy(
            rl_scheduler,
            feature_records,
            retraining_output["patterns"],
        )

        return {
            "drift": drift,
            "retraining": retraining_output,
            "rl_policy_update": rl_update,
        }
