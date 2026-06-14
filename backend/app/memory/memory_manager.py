from __future__ import annotations

import logging
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoryRecord:
    """In-memory performance record for one completed AI brain cycle."""

    timestamp: datetime
    day_score: float
    productivity_score: float
    priority_score: float
    energy_alignment_score: float
    stress_penalty: float
    forecast_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """Store recent scheduling performance history in RAM only."""

    def __init__(self, max_records: int = 1000) -> None:
        """
        Initialize the bounded in-memory record store.

        Args:
            max_records: Maximum number of records retained in memory.
        """
        if max_records <= 0:
            raise ValueError("max_records must be greater than zero.")
        self.max_records = min(max_records, 1000)
        self._records: Deque[MemoryRecord] = deque(maxlen=self.max_records)
        logger.info("MemoryManager initialized with max_records=%s.", self.max_records)

    def store_cycle_result(self, result: Dict[str, Any]) -> MemoryRecord:
        """
        Store a completed AIBrain cycle result.

        Args:
            result: AIBrain result containing evaluation and forecast_score.

        Returns:
            The MemoryRecord created from the cycle result.
        """
        if not isinstance(result, dict):
            raise TypeError("result must be a dictionary.")

        evaluation = result.get("evaluation") or {}
        if not isinstance(evaluation, dict):
            raise TypeError("result['evaluation'] must be a dictionary when provided.")

        metadata = {
            "context": result.get("context"),
            "schedule": result.get("schedule"),
        }
        extra_metadata = result.get("metadata")
        if isinstance(extra_metadata, dict):
            metadata.update(extra_metadata)

        record = MemoryRecord(
            timestamp=datetime.utcnow(),
            day_score=self._to_float(evaluation.get("total_score")),
            productivity_score=self._to_float(evaluation.get("productivity_score")),
            priority_score=self._to_float(evaluation.get("priority_score")),
            energy_alignment_score=self._to_float(
                evaluation.get("energy_alignment_score", evaluation.get("energy_alignment"))
            ),
            stress_penalty=self._to_float(evaluation.get("stress_penalty")),
            forecast_score=self._to_float(result.get("forecast_score")),
            metadata=metadata,
        )
        self._records.append(record)
        logger.info(
            "Stored memory record: day_score=%.3f forecast_score=%.3f records=%s.",
            record.day_score,
            record.forecast_score,
            len(self._records),
        )
        return record

    def store_memory(self, description: str, metadata: Optional[Dict[str, Any]] = None) -> MemoryRecord:
        """
        Store a cycle result from AIBrain's memory hook format.

        Args:
            description: Human-readable memory event description.
            metadata: Serialized cycle result or event metadata.

        Returns:
            The MemoryRecord created from the metadata.
        """
        payload = metadata or {}
        if not isinstance(payload, dict):
            payload = {"metadata": {"description": description, "payload": payload}}
        payload.setdefault("metadata", {})
        if isinstance(payload["metadata"], dict):
            payload["metadata"].setdefault("description", description)
        return self.store_cycle_result(payload)

    def get_recent_records(self, limit: int = 30) -> List[MemoryRecord]:
        """
        Return the most recent memory records.

        Args:
            limit: Maximum number of records to return.

        Returns:
            Records ordered from oldest to newest within the selected window.
        """
        if limit <= 0:
            return []
        records = list(self._records)
        return records[-limit:]

    def get_average_score(self) -> float:
        """
        Return the average stored day score.

        Returns:
            Mean day score, or 0.0 when no records exist.
        """
        if not self._records:
            return 0.0
        return float(statistics.mean(record.day_score for record in self._records))

    def get_score_trend(self) -> str:
        """
        Classify the recent day-score trend.

        Returns:
            One of: no_data, stable, improving, declining.
        """
        if len(self._records) < 2:
            return "no_data"

        recent_records = self.get_recent_records(limit=min(10, len(self._records)))
        midpoint = len(recent_records) // 2
        first_window = recent_records[:midpoint]
        second_window = recent_records[midpoint:]

        if not first_window or not second_window:
            return "no_data"

        first_average = statistics.mean(record.day_score for record in first_window)
        second_average = statistics.mean(record.day_score for record in second_window)
        delta = second_average - first_average

        if delta > 0.05:
            return "improving"
        if delta < -0.05:
            return "declining"
        return "stable"

    def get_system_summary(self) -> Dict[str, Any]:
        """
        Summarize stored performance history.

        Returns:
            Dictionary containing record count, averages, latest scores, and trend.
        """
        if not self._records:
            return {
                "record_count": 0,
                "average_day_score": 0.0,
                "average_productivity_score": 0.0,
                "average_priority_score": 0.0,
                "average_energy_alignment_score": 0.0,
                "average_stress_penalty": 0.0,
                "average_forecast_score": 0.0,
                "score_trend": "no_data",
                "latest_record": None,
            }

        latest = self._records[-1]
        return {
            "record_count": len(self._records),
            "average_day_score": self.get_average_score(),
            "average_productivity_score": statistics.mean(
                record.productivity_score for record in self._records
            ),
            "average_priority_score": statistics.mean(record.priority_score for record in self._records),
            "average_energy_alignment_score": statistics.mean(
                record.energy_alignment_score for record in self._records
            ),
            "average_stress_penalty": statistics.mean(record.stress_penalty for record in self._records),
            "average_forecast_score": statistics.mean(record.forecast_score for record in self._records),
            "score_trend": self.get_score_trend(),
            "latest_record": latest,
        }

    def clear(self) -> None:
        """Remove all stored memory records."""
        self._records.clear()
        logger.info("MemoryManager records cleared.")

    def _to_float(self, value: Any) -> float:
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning("Unable to convert value to float: %r", value)
            return 0.0
