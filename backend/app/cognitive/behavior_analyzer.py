from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BehaviorProfile:
    """Statistical behavior profile derived from historical memory records."""

    average_day_score: float
    average_productivity_score: float
    average_priority_score: float
    average_energy_alignment_score: float
    average_stress_penalty: float
    consistency_score: float
    burnout_risk: float
    productivity_trend: str
    performance_category: str
    recommended_daily_capacity: float
    metadata: dict = field(default_factory=dict)


class BehaviorAnalyzer:
    """Analyze user performance patterns from MemoryManager records."""

    def __init__(self, memory_manager: Any) -> None:
        """
        Store a reference to the memory manager.

        Args:
            memory_manager: Object compatible with MemoryManager.get_recent_records().
        """
        self.memory_manager = memory_manager

    def analyze(self) -> BehaviorProfile:
        """
        Build a BehaviorProfile from available memory records.

        Returns:
            BehaviorProfile containing aggregate performance, consistency,
            burnout risk, productivity trend, category, and capacity guidance.
        """
        records = self._get_records()
        if not records:
            logger.info("No memory records available for behavior analysis.")
            return BehaviorProfile(
                average_day_score=0.0,
                average_productivity_score=0.0,
                average_priority_score=0.0,
                average_energy_alignment_score=0.0,
                average_stress_penalty=0.0,
                consistency_score=0.0,
                burnout_risk=0.0,
                productivity_trend="insufficient_data",
                performance_category="low",
                recommended_daily_capacity=4.0,
                metadata={
                    "record_count": 0,
                    "analysis_method": "statistical_memory_record_analysis",
                },
            )

        average_day_score = self._mean(records, "day_score")
        average_productivity_score = self._mean(records, "productivity_score")
        average_priority_score = self._mean(records, "priority_score")
        average_energy_alignment_score = self._mean(records, "energy_alignment_score")
        average_stress_penalty = self._mean(records, "stress_penalty")
        consistency_score = self._calculate_consistency(records)
        burnout_risk = self._calculate_burnout_risk(
            stress_penalty=average_stress_penalty,
            average_day_score=average_day_score,
        )
        productivity_trend = self._calculate_productivity_trend(records)
        performance_category = self._calculate_performance_category(average_day_score)
        recommended_daily_capacity = self._recommended_capacity(
            average_day_score=average_day_score,
            stress_penalty=average_stress_penalty,
        )

        profile = BehaviorProfile(
            average_day_score=average_day_score,
            average_productivity_score=average_productivity_score,
            average_priority_score=average_priority_score,
            average_energy_alignment_score=average_energy_alignment_score,
            average_stress_penalty=average_stress_penalty,
            consistency_score=consistency_score,
            burnout_risk=burnout_risk,
            productivity_trend=productivity_trend,
            performance_category=performance_category,
            recommended_daily_capacity=recommended_daily_capacity,
            metadata={
                "record_count": len(records),
                "analysis_method": "statistical_memory_record_analysis",
                "latest_day_score": self._safe_float(getattr(records[-1], "day_score", 0.0)),
                "day_score_variance": self._variance(records, "day_score"),
            },
        )
        logger.info(
            "Behavior profile generated: records=%s average_day_score=%.3f trend=%s category=%s.",
            len(records),
            profile.average_day_score,
            profile.productivity_trend,
            profile.performance_category,
        )
        return profile

    def _calculate_consistency(self, records: Optional[List[Any]] = None) -> float:
        """
        Calculate normalized consistency from day-score variance.

        Higher consistency means lower variance. Scores are normalized to 0.0-1.0.
        """
        source_records = records if records is not None else self._get_records()
        scores = [self._safe_float(getattr(record, "day_score", 0.0)) for record in source_records]
        if not scores:
            return 0.0
        if len(scores) == 1:
            return 1.0

        variance = statistics.pvariance(scores)
        normalized_variance = self._clamp(variance / 0.25)
        return round(1.0 - normalized_variance, 4)

    def _calculate_burnout_risk(self, stress_penalty: float, average_day_score: float) -> float:
        """
        Calculate burnout risk from stress pressure and low performance.

        High stress combined with low average day score produces higher risk.
        """
        stress_component = self._clamp(stress_penalty)
        low_score_component = self._clamp(1.0 - average_day_score)
        risk = (0.65 * stress_component) + (0.35 * low_score_component)
        return round(self._clamp(risk), 4)

    def _calculate_productivity_trend(self, records: Optional[List[Any]] = None) -> str:
        """
        Calculate productivity trend from recent day scores.

        Returns:
            improving, stable, declining, or insufficient_data.
        """
        source_records = records if records is not None else self._get_records()
        if len(source_records) < 3:
            return "insufficient_data"

        recent_records = source_records[-min(10, len(source_records)) :]
        midpoint = len(recent_records) // 2
        first_window = recent_records[:midpoint]
        second_window = recent_records[midpoint:]
        if not first_window or not second_window:
            return "insufficient_data"

        first_average = statistics.mean(
            self._safe_float(getattr(record, "day_score", 0.0)) for record in first_window
        )
        second_average = statistics.mean(
            self._safe_float(getattr(record, "day_score", 0.0)) for record in second_window
        )
        delta = second_average - first_average

        if delta > 0.05:
            return "improving"
        if delta < -0.05:
            return "declining"
        return "stable"

    def _calculate_performance_category(self, average_day_score: float) -> str:
        """
        Categorize performance from average day score.

        Returns:
            elite, high, moderate, or low.
        """
        score = self._clamp(average_day_score)
        if score >= 0.85:
            return "elite"
        if score >= 0.70:
            return "high"
        if score >= 0.50:
            return "moderate"
        return "low"

    def _recommended_capacity(self, average_day_score: float, stress_penalty: float) -> float:
        """
        Recommend daily capacity in hours from score and stress.

        Returns:
            Capacity bounded between 4.0 and 10.0 hours.
        """
        score = self._clamp(average_day_score)
        stress = self._clamp(stress_penalty)
        capacity = 4.0 + (score * 6.0) - (stress * 2.0)
        return round(self._clamp(capacity, minimum=4.0, maximum=10.0), 2)

    def _get_records(self) -> List[Any]:
        """Return all recent records from the memory manager without raising."""
        if self.memory_manager is None:
            return []

        get_recent_records = getattr(self.memory_manager, "get_recent_records", None)
        if callable(get_recent_records):
            try:
                records = get_recent_records(limit=1000)
                return list(records or [])
            except Exception as exc:
                logger.warning("Unable to read memory records: %s", exc)
                return []

        records = getattr(self.memory_manager, "_records", None)
        if records is None:
            return []
        try:
            return list(records)
        except TypeError:
            logger.warning("Memory manager records are not iterable.")
            return []

    def _mean(self, records: List[Any], field_name: str) -> float:
        """Return a safe mean for a numeric MemoryRecord field."""
        if not records:
            return 0.0
        values = [self._safe_float(getattr(record, field_name, 0.0)) for record in records]
        return round(float(statistics.mean(values)), 4)

    def _variance(self, records: List[Any], field_name: str) -> float:
        """Return population variance for a numeric MemoryRecord field."""
        if len(records) < 2:
            return 0.0
        values = [self._safe_float(getattr(record, field_name, 0.0)) for record in records]
        return round(float(statistics.pvariance(values)), 6)

    def _safe_float(self, value: Any) -> float:
        """Convert a value to a finite float, returning 0.0 on invalid input."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(number):
            return 0.0
        return number

    def _clamp(self, value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        """Clamp a numeric value to an inclusive range."""
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        safe_value = self._safe_float(value)
        return max(minimum, min(maximum, safe_value))
