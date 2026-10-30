"""Phase F13.3 — Duration Quality Gate.

Provides deterministic, defensible data-quality validation for personal task duration
observations used in DurationRatioModel training and learning readiness assessment.

Design Principles:
1. Never silently rewrite historical records in the database.
2. Never delete historical records from the database.
3. Exclude invalid or unmonitored observations from model training and readiness counts.
4. Expose explicit, structured exclusion reasons for transparency.
5. Maintain user data isolation.
6. Guardrails:
   - MIN_PLAUSIBLE_DURATION_MINUTES = 1.0 (sub-60s completions for tasks estimated >= 5m are rapid test artifacts).
   - MAX_PLAUSIBLE_DURATION_MINUTES = 960.0 (16 hours maximum single-session continuous waking work).
   - MAX_DURATION_RATIO_RUNAWAY = 10.0 (actual / estimate > 10x AND actual > 360m / 6h indicates abandoned session).
   - MIN_DURATION_RATIO_ARTIFACT = 0.02 (actual / estimate < 0.02 for estimate >= 15m indicates rapid artifact).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DurationExclusionReason(str, Enum):
    NON_FINITE_DURATION = "NON_FINITE_DURATION"
    NON_POSITIVE_DURATION = "NON_POSITIVE_DURATION"
    ZERO_OR_NEGATIVE_DURATION = "ZERO_OR_NEGATIVE_DURATION"
    TASK_NOT_COMPLETED = "TASK_NOT_COMPLETED"
    MISSING_TIMESTAMPS = "MISSING_TIMESTAMPS"
    EXCESSIVE_WALL_CLOCK_DURATION_OVERNIGHT = "EXCESSIVE_WALL_CLOCK_DURATION_OVERNIGHT"
    EXTREME_DURATION_RATIO_RUNAWAY = "EXTREME_DURATION_RATIO_RUNAWAY"
    SUB_MINIMAL_AUTOMATION_ARTIFACT = "SUB_MINIMAL_AUTOMATION_ARTIFACT"
    MICRO_RATIO_ARTIFACT = "MICRO_RATIO_ARTIFACT"


MIN_PLAUSIBLE_DURATION_MINUTES = 1.0
MAX_PLAUSIBLE_DURATION_MINUTES = 960.0  # 16 hours continuous waking work threshold
MAX_DURATION_RATIO_RUNAWAY = 10.0
MIN_RATIO_RUNAWAY_MINUTES = 360.0  # 6 hours
MIN_DURATION_RATIO_ARTIFACT = 0.02


@dataclass(frozen=True)
class DurationQualityAssessment:
    """Immutable result of a duration quality evaluation."""

    is_eligible: bool
    code: Optional[str]
    exclusion_reason: Optional[str]
    actual_duration_minutes: float
    estimated_duration_minutes: Optional[float]
    duration_ratio: Optional[float]

    def to_dict(self) -> dict[str, str | float | bool | None]:
        return {
            "is_eligible": self.is_eligible,
            "code": self.code,
            "exclusion_reason": self.exclusion_reason,
            "actual_duration_minutes": self.actual_duration_minutes,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "duration_ratio": round(self.duration_ratio, 6) if self.duration_ratio is not None else None,
        }


class DurationQualityGate:
    """Audits duration observations against physical human work and session continuity constraints."""

    @classmethod
    def assess(
        cls,
        actual_duration_minutes: float,
        estimated_duration_minutes: Optional[float] = None,
        has_completed_status: bool = True,
        has_timestamps: bool = True,
    ) -> DurationQualityAssessment:
        """Evaluate duration plausibility for model training."""

        if not has_completed_status:
            return DurationQualityAssessment(
                is_eligible=False,
                code=DurationExclusionReason.TASK_NOT_COMPLETED,
                exclusion_reason="Task lifecycle status is not completed.",
                actual_duration_minutes=actual_duration_minutes,
                estimated_duration_minutes=estimated_duration_minutes,
                duration_ratio=None,
            )

        if not has_timestamps:
            return DurationQualityAssessment(
                is_eligible=False,
                code=DurationExclusionReason.MISSING_TIMESTAMPS,
                exclusion_reason="Task lacks required start or completed timestamp.",
                actual_duration_minutes=actual_duration_minutes,
                estimated_duration_minutes=estimated_duration_minutes,
                duration_ratio=None,
            )

        if not math.isfinite(actual_duration_minutes):
            return DurationQualityAssessment(
                is_eligible=False,
                code=DurationExclusionReason.NON_FINITE_DURATION,
                exclusion_reason=f"Actual duration {actual_duration_minutes} is not a finite number.",
                actual_duration_minutes=actual_duration_minutes,
                estimated_duration_minutes=estimated_duration_minutes,
                duration_ratio=None,
            )

        if actual_duration_minutes <= 0.0:
            return DurationQualityAssessment(
                is_eligible=False,
                code=DurationExclusionReason.ZERO_OR_NEGATIVE_DURATION,
                exclusion_reason=f"Actual duration {actual_duration_minutes}m must be strictly positive.",
                actual_duration_minutes=actual_duration_minutes,
                estimated_duration_minutes=estimated_duration_minutes,
                duration_ratio=None,
            )

        ratio = (
            actual_duration_minutes / estimated_duration_minutes
            if estimated_duration_minutes is not None and estimated_duration_minutes > 0.0
            else None
        )

        # 1. Multi-day / overnight unmonitored task check (> 16 hours continuous)
        if actual_duration_minutes > MAX_PLAUSIBLE_DURATION_MINUTES:
            hours = actual_duration_minutes / 60.0
            return DurationQualityAssessment(
                is_eligible=False,
                code=DurationExclusionReason.EXCESSIVE_WALL_CLOCK_DURATION_OVERNIGHT,
                exclusion_reason=(
                    f"Actual duration of {actual_duration_minutes:.1f} minutes ({hours:.1f} hours) "
                    f"exceeds maximum single-session continuous threshold of {MAX_PLAUSIBLE_DURATION_MINUTES:.1f}m (16h); "
                    f"unmonitored overnight or multi-day elapsed interval."
                ),
                actual_duration_minutes=actual_duration_minutes,
                estimated_duration_minutes=estimated_duration_minutes,
                duration_ratio=ratio,
            )

        # 2. Runaway ratio (> 10x estimate and > 6 hours)
        if (
            ratio is not None
            and ratio > MAX_DURATION_RATIO_RUNAWAY
            and actual_duration_minutes > MIN_RATIO_RUNAWAY_MINUTES
        ):
            return DurationQualityAssessment(
                is_eligible=False,
                code=DurationExclusionReason.EXTREME_DURATION_RATIO_RUNAWAY,
                exclusion_reason=(
                    f"Actual duration {actual_duration_minutes:.1f}m is {ratio:.1f}x estimated duration "
                    f"({estimated_duration_minutes}m) and exceeds {MIN_RATIO_RUNAWAY_MINUTES}m; unmonitored runaway session."
                ),
                actual_duration_minutes=actual_duration_minutes,
                estimated_duration_minutes=estimated_duration_minutes,
                duration_ratio=ratio,
            )

        # 3. Sub-minute rapid automation artifact (< 1.0 min for tasks estimated >= 5.0 min)
        if actual_duration_minutes < MIN_PLAUSIBLE_DURATION_MINUTES:
            if estimated_duration_minutes is None or estimated_duration_minutes >= 5.0:
                sec = actual_duration_minutes * 60.0
                return DurationQualityAssessment(
                    is_eligible=False,
                    code=DurationExclusionReason.SUB_MINIMAL_AUTOMATION_ARTIFACT,
                    exclusion_reason=(
                        f"Actual duration of {actual_duration_minutes:.2f} minutes ({sec:.1f}s) for task estimated at "
                        f"{estimated_duration_minutes}m represents rapid UI automation artifact, not plausible human work."
                    ),
                    actual_duration_minutes=actual_duration_minutes,
                    estimated_duration_minutes=estimated_duration_minutes,
                    duration_ratio=ratio,
                )

        # 4. Extreme micro-ratio (< 0.02 of estimate when estimate >= 15 min)
        if (
            ratio is not None
            and estimated_duration_minutes is not None
            and estimated_duration_minutes >= 15.0
            and ratio < MIN_DURATION_RATIO_ARTIFACT
        ):
            return DurationQualityAssessment(
                is_eligible=False,
                code=DurationExclusionReason.MICRO_RATIO_ARTIFACT,
                exclusion_reason=(
                    f"Duration ratio {ratio:.4f} is under {MIN_DURATION_RATIO_ARTIFACT} for a "
                    f"{estimated_duration_minutes}m task; rapid completion artifact."
                ),
                actual_duration_minutes=actual_duration_minutes,
                estimated_duration_minutes=estimated_duration_minutes,
                duration_ratio=ratio,
            )

        # Passed all checks: valid, plausible human duration observation
        return DurationQualityAssessment(
            is_eligible=True,
            code=None,
            exclusion_reason=None,
            actual_duration_minutes=actual_duration_minutes,
            estimated_duration_minutes=estimated_duration_minutes,
            duration_ratio=ratio,
        )

    # Convenient alias
    assess_duration = assess
