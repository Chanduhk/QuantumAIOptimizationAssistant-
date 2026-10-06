"""Safe internal data contracts for future scheduling optimization.

These types do not alter the public Task API or reinterpret persisted values.
Only explicitly unit-tagged estimates can be normalized for optimizer input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class DurationUnit(str, Enum):
    MINUTES = "minutes"
    HOURS = "hours"
    UNKNOWN = "unknown"


class DurationProvenanceStatus(str, Enum):
    KNOWN_UNIT = "KNOWN_UNIT"
    UNKNOWN_UNIT = "UNKNOWN_UNIT"


class OptimizationInputError(ValueError):
    """Invalid or unsupported data at the optimizer input boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LegacyUntypedDuration:
    """A preserved raw legacy value whose unit cannot be established."""

    original_value: Any
    source: str = "Task.estimated_duration"
    original_unit: DurationUnit = DurationUnit.UNKNOWN
    provenance_status: DurationProvenanceStatus = DurationProvenanceStatus.UNKNOWN_UNIT

    @property
    def optimizer_eligible(self) -> bool:
        return False


def classify_legacy_duration(value: Any, source: str = "Task.estimated_duration") -> LegacyUntypedDuration:
    """Retain an existing raw value while marking its unit explicitly unknown."""

    if not isinstance(source, str) or not source.strip():
        raise OptimizationInputError("INVALID_DURATION_SOURCE", "legacy duration source must be explicit and non-empty.")
    return LegacyUntypedDuration(original_value=value, source=source.strip())


@dataclass(frozen=True)
class DurationValue:
    """An explicitly sourced duration normalized to hours."""

    original_value: float
    original_unit: DurationUnit
    source: str
    normalized_hours: float
    conversion_applied: str
    provenance_status: DurationProvenanceStatus = DurationProvenanceStatus.KNOWN_UNIT

    def __post_init__(self) -> None:
        if (
            isinstance(self.original_value, bool)
            or not isinstance(self.original_value, (int, float))
            or not math.isfinite(float(self.original_value))
            or self.original_value <= 0
        ):
            raise ValueError("original duration must be finite and positive.")
        if self.original_unit not in {DurationUnit.MINUTES, DurationUnit.HOURS}:
            raise ValueError("normalized duration requires an explicit supported unit.")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("normalized duration requires source provenance.")
        expected = self.original_value / 60.0 if self.original_unit is DurationUnit.MINUTES else self.original_value
        if (
            isinstance(self.normalized_hours, bool)
            or not isinstance(self.normalized_hours, (int, float))
            or not math.isfinite(float(self.normalized_hours))
            or self.normalized_hours <= 0
            or self.normalized_hours != expected
        ):
            raise ValueError("normalized_hours does not match the original value and unit.")
        expected_conversion = "minutes_to_hours_divide_by_60" if self.original_unit is DurationUnit.MINUTES else "identity_hours"
        if self.conversion_applied != expected_conversion:
            raise ValueError("conversion_applied does not match the unit conversion.")
        if self.provenance_status is not DurationProvenanceStatus.KNOWN_UNIT:
            raise ValueError("DurationValue must carry known-unit provenance.")

    @property
    def optimizer_eligible(self) -> bool:
        return self.provenance_status is DurationProvenanceStatus.KNOWN_UNIT


def normalize_duration(value: Any, unit: DurationUnit | str, source: str) -> DurationValue:
    """Normalize an explicitly unit-tagged positive finite value to hours."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OptimizationInputError("INVALID_DURATION", "duration must be a numeric value.")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise OptimizationInputError("INVALID_DURATION", "duration must be finite.")
    if numeric_value <= 0:
        raise OptimizationInputError("INVALID_DURATION", "duration must be greater than zero.")
    if not isinstance(source, str) or not source.strip():
        raise OptimizationInputError("INVALID_DURATION_SOURCE", "duration source must be explicit and non-empty.")
    try:
        parsed_unit = unit if isinstance(unit, DurationUnit) else DurationUnit(str(unit).lower())
    except ValueError:
        raise OptimizationInputError("UNKNOWN_DURATION_UNIT", "duration unit must be 'minutes' or 'hours'.") from None
    if parsed_unit is DurationUnit.UNKNOWN:
        raise OptimizationInputError("UNKNOWN_DURATION_UNIT", "unknown-unit durations are not optimizer eligible.")

    if parsed_unit is DurationUnit.MINUTES:
        hours = numeric_value / 60.0
        conversion = "minutes_to_hours_divide_by_60"
    else:
        hours = numeric_value
        conversion = "identity_hours"
    if not math.isfinite(hours) or hours <= 0:
        raise OptimizationInputError("INVALID_NORMALIZED_DURATION", "normalized duration must be finite and positive.")
    return DurationValue(
        original_value=numeric_value,
        original_unit=parsed_unit,
        source=source.strip(),
        normalized_hours=hours,
        conversion_applied=conversion,
    )


class PredictionEligibility(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    MODEL_FEATURE_UNIT_UNVERIFIED = "MODEL_FEATURE_UNIT_UNVERIFIED"


@dataclass(frozen=True)
class OptimizationTaskInput:
    task_id: int | str
    task_type: str
    priority: int
    estimated_duration: DurationValue
    lifecycle_state: str
    completed: bool
    outcome_valid: bool | None
    prediction_eligibility: PredictionEligibility


def adapt_task_for_optimization(
    task: Any,
    *,
    estimated_duration_unit: DurationUnit | str | None,
    duration_source: str | None,
) -> OptimizationTaskInput:
    """Build an optimizer-facing task without inferring units or using outcomes."""

    def read(name: str, default: Any = None) -> Any:
        if isinstance(task, Mapping):
            return task.get(name, default)
        return getattr(task, name, default)

    task_id = read("id", read("task_id"))
    if isinstance(task_id, bool) or not isinstance(task_id, (int, str)) or not str(task_id).strip():
        raise OptimizationInputError("INVALID_TASK_ID", "task ID must be a non-empty stable integer or string.")
    if isinstance(task_id, int) and task_id <= 0:
        raise OptimizationInputError("INVALID_TASK_ID", "integer task ID must be positive.")

    task_type = read("task_type")
    if not isinstance(task_type, str) or not task_type.strip():
        raise OptimizationInputError("INVALID_TASK_TYPE", "task_type must be a non-empty string.")
    priority = read("priority")
    if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 5:
        raise OptimizationInputError("INVALID_PRIORITY", "priority must be an integer from 1 to 5.")

    completed = read("completed")
    if not isinstance(completed, bool):
        raise OptimizationInputError("INVALID_LIFECYCLE_STATE", "completed must be an explicit boolean.")
    lifecycle_state = read("lifecycle_state")
    if not isinstance(lifecycle_state, str) or not lifecycle_state.strip():
        raise OptimizationInputError("INVALID_LIFECYCLE_STATE", "lifecycle_state must be explicit.")
    lifecycle_state = lifecycle_state.strip().lower()
    if completed or lifecycle_state == "completed":
        raise OptimizationInputError("COMPLETED_TASK_NOT_ELIGIBLE", "completed tasks are excluded from planning optimization.")
    if lifecycle_state == "started":
        raise OptimizationInputError("STARTED_TASK_NOT_SUPPORTED", "started tasks lack a remaining-duration contract.")
    if lifecycle_state != "created":
        raise OptimizationInputError("INVALID_LIFECYCLE_STATE", "only created tasks are currently supported.")

    outcome_valid = read("outcome_valid")
    if outcome_valid is not None and not isinstance(outcome_valid, bool):
        raise OptimizationInputError("INVALID_OUTCOME_STATE", "outcome_valid must be boolean or None.")

    estimate = read("estimated_duration")
    if estimate is None:
        raise OptimizationInputError("MISSING_ESTIMATE", "an explicit estimated_duration is required; actual_duration is outcome-only.")
    if estimated_duration_unit is None:
        raise OptimizationInputError(
            "LEGACY_UNTYPED_DURATION",
            "legacy estimated_duration has unknown units and is not optimizer eligible.",
        )
    if duration_source is None:
        raise OptimizationInputError("INVALID_DURATION_SOURCE", "explicit duration source is required.")
    duration = normalize_duration(estimate, estimated_duration_unit, duration_source)

    # Duration provenance may be established while ProductivityModel's
    # training feature unit remains unverified. Do not overstate eligibility.
    return OptimizationTaskInput(
        task_id=task_id,
        task_type=task_type.strip(),
        priority=priority,
        estimated_duration=duration,
        lifecycle_state=lifecycle_state,
        completed=False,
        outcome_valid=outcome_valid,
        prediction_eligibility=PredictionEligibility.MODEL_FEATURE_UNIT_UNVERIFIED,
    )


def validate_unique_task_ids(tasks: Iterable[OptimizationTaskInput]) -> tuple[OptimizationTaskInput, ...]:
    """Return tasks in input order or reject duplicate stable identities."""

    result = tuple(tasks)
    ids = [str(task.task_id) for task in result]
    if len(ids) != len(set(ids)):
        raise OptimizationInputError("DUPLICATE_TASK_ID", "task IDs must be unique within an optimization problem.")
    return result
