from __future__ import annotations

import logging
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List


class AIMonitor:
    """Observability layer for AI engine execution and model behavior."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.engine_executions: List[Dict[str, Any]] = []
        self.predictions: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self.training_metrics: List[Dict[str, Any]] = []

    def log_engine_execution(self, engine_name: str, duration: float) -> None:
        """Record how long an engine took to run."""
        payload = {
            "engine_name": engine_name,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.engine_executions.append(payload)
        self.logger.info("Engine '%s' executed in %.4fs", engine_name, duration)

    def log_prediction(self, engine_name: str, prediction_value: float) -> None:
        """Record a prediction emitted by an AI engine."""
        payload = {
            "engine_name": engine_name,
            "prediction_value": prediction_value,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.predictions.append(payload)
        self.logger.info("Prediction logged for '%s': %.4f", engine_name, prediction_value)

    def log_event(self, event_name: str) -> None:
        """Record that an event was processed."""
        payload = {
            "event_name": event_name,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(payload)
        self.logger.info("Event processed: %s", event_name)

    def log_training_metrics(self, engine_name: str, metrics: Dict[str, Any]) -> None:
        """Record model training metrics for later inspection."""
        payload = {
            "engine_name": engine_name,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.training_metrics.append(payload)
        self.logger.info("Training metrics logged for '%s'", engine_name)

    def report_system_metrics(self) -> Dict[str, Any]:
        """Return a summary of current AI observability data."""
        execution_durations = [item["duration"] for item in self.engine_executions]
        prediction_values = [item["prediction_value"] for item in self.predictions]

        return {
            "engine_execution_count": len(self.engine_executions),
            "average_engine_duration": round(mean(execution_durations), 4) if execution_durations else 0.0,
            "prediction_count": len(self.predictions),
            "average_prediction_value": round(mean(prediction_values), 4) if prediction_values else 0.0,
            "event_count": len(self.events),
            "training_metric_count": len(self.training_metrics),
        }
