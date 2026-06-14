from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from backend.app.domain.day_model import Day
from backend.app.domain.strategic_compression import (
    compute_overload_index,
    get_compression_status,
)

logger = logging.getLogger(__name__)


@dataclass
class ContextState:
    """Read-only snapshot of the current planning system state."""

    timestamp: datetime
    available_hours: float
    total_task_hours: float
    overload_score: float
    task_count: int
    high_priority_count: int
    average_priority: float
    sleep_hours: float
    compression_active: bool
    fatigue_status: str
    predicted_risk_level: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextBuilder:
    """Build unified state snapshots from the existing Day and task models."""

    def __init__(
        self,
        *,
        fatigue_engine: Optional[Any] = None,
        forecast_engine: Optional[Any] = None,
        planning_horizon: int = 5,
    ) -> None:
        self.fatigue_engine = fatigue_engine
        self.forecast_engine = forecast_engine
        self.planning_horizon = planning_horizon
        self._last_snapshot: Optional[ContextState] = None

    def build(self, day: Day) -> ContextState:
        """Create a read-only ContextState from an existing Day instance."""
        logger.info("Building context state from Day.")
        self._validate_day(day)

        tasks = list(getattr(day, "tasks", []))
        task_count = len(tasks)
        total_task_hours = float(day.total_task_hours())
        available_hours = float(day.available_hours)
        overload_score = float(day.overload_score())
        priorities = [float(getattr(task, "priority", 0.0)) for task in tasks]
        high_priority_count = sum(1 for priority in priorities if priority >= 8.0)
        average_priority = sum(priorities) / task_count if task_count else 0.0
        compression_status = get_compression_status(tasks)
        compression_active = bool(compression_status.get("compression_active", False))
        fatigue_status = self._resolve_fatigue_status(day)
        predicted_risk_level = self._predict_risk_level(
            overload_score=overload_score,
            sleep_hours=float(day.sleep_hours),
            high_priority_count=high_priority_count,
            task_count=task_count,
            compression_active=compression_active,
        )

        metadata: Dict[str, Any] = {
            "active_task_count": int(compression_status.get("active_tasks", task_count)),
            "active_task_hours": float(compression_status.get("active_hours", total_task_hours)),
            "deferred_task_count": sum(1 for task in tasks if bool(getattr(task, "deferred", False))),
            "penalized_task_count": int(compression_status.get("penalized_tasks", 0)),
            "penalized_task_hours": float(compression_status.get("penalized_hours", 0.0)),
            "overload_index": compute_overload_index(
                tasks,
                capacity_per_day=available_hours,
                planning_horizon=self.planning_horizon,
            ),
            "planning_horizon": self.planning_horizon,
        }

        snapshot = ContextState(
            timestamp=datetime.utcnow(),
            available_hours=available_hours,
            total_task_hours=total_task_hours,
            overload_score=overload_score,
            task_count=task_count,
            high_priority_count=high_priority_count,
            average_priority=average_priority,
            sleep_hours=float(day.sleep_hours),
            compression_active=compression_active,
            fatigue_status=fatigue_status,
            predicted_risk_level=predicted_risk_level,
            metadata=metadata,
        )
        self._last_snapshot = snapshot
        logger.info(
            "Context state built: tasks=%s overload=%.3f risk=%s",
            task_count,
            overload_score,
            predicted_risk_level,
        )
        return snapshot

    def build_from_forecast(self, day: Day) -> ContextState:
        """Build context enriched with non-mutating forecast-engine status metadata."""
        logger.info("Building context state with forecast metadata.")
        snapshot = self.build(day)
        forecast_engine = self.forecast_engine
        if forecast_engine is not None:
            snapshot.metadata.update(self._extract_forecast_metadata(forecast_engine))
            forecast_fatigue = self._extract_fatigue_status(forecast_engine)
            if forecast_fatigue:
                snapshot.fatigue_status = forecast_fatigue
        self._last_snapshot = snapshot
        return snapshot

    def get_system_snapshot(self) -> ContextState:
        """Return the most recently built ContextState."""
        if self._last_snapshot is None:
            logger.error("System snapshot requested before context was built.")
            raise ValueError("No system snapshot is available. Call build(day) first.")
        logger.info("Returning last system snapshot.")
        return self._last_snapshot

    def _validate_day(self, day: Day) -> None:
        if not isinstance(day, Day):
            raise TypeError("ContextBuilder requires an existing Day instance.")
        if float(day.available_hours) <= 0:
            raise ValueError("Day.available_hours must be greater than zero.")

    def _resolve_fatigue_status(self, day: Day) -> str:
        for source in (self.fatigue_engine, self.forecast_engine, day):
            status = self._extract_fatigue_status(source)
            if status:
                return status
        if float(day.sleep_hours) < 6.0:
            return "sleep_restricted"
        if float(day.sleep_hours) >= 7.0:
            return "stable"
        return "watch"

    def _extract_fatigue_status(self, source: Optional[Any]) -> Optional[str]:
        if source is None:
            return None
        fatigue_engine = getattr(source, "fatigue_engine", source)
        status_method = getattr(fatigue_engine, "get_status_report", None)
        if callable(status_method):
            try:
                return str(status_method())
            except Exception as exc:
                logger.warning("Unable to read fatigue status: %s", exc)
        return None

    def _extract_forecast_metadata(self, forecast_engine: Any) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        for attribute in ("day_scores", "entropy_values", "csi_values", "penalty_values"):
            value = getattr(forecast_engine, attribute, None)
            if value is not None:
                metadata[attribute] = list(value)
        config = getattr(forecast_engine, "config", None)
        if config is not None:
            forecast_config = getattr(config, "forecast", None)
            if forecast_config is not None:
                metadata["forecast_days"] = getattr(forecast_config, "num_days", None)
                metadata["forecast_risk_weight"] = getattr(forecast_config, "risk_weight", None)
        return metadata

    def _predict_risk_level(
        self,
        *,
        overload_score: float,
        sleep_hours: float,
        high_priority_count: int,
        task_count: int,
        compression_active: bool,
    ) -> str:
        risk_points = 0
        if overload_score >= 1.5:
            risk_points += 3
        elif overload_score > 1.0:
            risk_points += 2
        if sleep_hours < 6.0:
            risk_points += 2
        elif sleep_hours < 7.0:
            risk_points += 1
        if compression_active:
            risk_points += 1
        if task_count and high_priority_count / task_count >= 0.5:
            risk_points += 1

        if risk_points >= 5:
            return "critical"
        if risk_points >= 3:
            return "high"
        if risk_points >= 1:
            return "moderate"
        return "low"
