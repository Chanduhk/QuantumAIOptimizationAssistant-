from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy.orm import Session

from backend.app.ml.datasets.models import _freeze_mapping
from backend.app.ml.datasets.task_database_adapter import TaskDataExtractor
from backend.app.models.task import Task


ACTUAL_DURATION_TOLERANCE_MINUTES = 1e-6


@dataclass(frozen=True)
class TaskCollectionReport:
    """Immutable report describing whether real Task rows can supply F.3 datasets."""

    total_task_records: int
    completed_records: int
    incomplete_records: int
    lifecycle_valid_records: int
    lifecycle_invalid_records: int
    f3_eligible_records: int
    f3_rejected_records: int
    f3_dataset_rows: int
    valid_actual_duration_records: int
    missing_estimate_records: int
    missing_created_at_records: int
    missing_start_time_records: int
    missing_end_time_records: int
    invalid_duration_records: int
    users_represented: tuple[str, ...]
    task_types_represented: tuple[str, ...]
    rejection_reason_counts: Mapping[str, int]
    lifecycle_issue_counts: Mapping[str, int]
    no_real_training_samples_available: bool

    def __post_init__(self) -> None:
        for field_name in (
            "total_task_records",
            "completed_records",
            "incomplete_records",
            "lifecycle_valid_records",
            "lifecycle_invalid_records",
            "f3_eligible_records",
            "f3_rejected_records",
            "f3_dataset_rows",
            "valid_actual_duration_records",
            "missing_estimate_records",
            "missing_created_at_records",
            "missing_start_time_records",
            "missing_end_time_records",
            "invalid_duration_records",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")
        for field_name in ("users_represented", "task_types_represented"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                raise ValueError(f"{field_name} must be a tuple.")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"{field_name} must contain non-empty strings.")
        object.__setattr__(self, "rejection_reason_counts", _freeze_mapping(self.rejection_reason_counts, "rejection_reason_counts"))
        object.__setattr__(self, "lifecycle_issue_counts", _freeze_mapping(self.lifecycle_issue_counts, "lifecycle_issue_counts"))
        if not isinstance(self.no_real_training_samples_available, bool):
            raise ValueError("no_real_training_samples_available must be boolean.")

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-friendly collection status."""

        return {
            "total_task_records": self.total_task_records,
            "completed_records": self.completed_records,
            "incomplete_records": self.incomplete_records,
            "lifecycle_valid_records": self.lifecycle_valid_records,
            "lifecycle_invalid_records": self.lifecycle_invalid_records,
            "f3_eligible_records": self.f3_eligible_records,
            "f3_rejected_records": self.f3_rejected_records,
            "f3_dataset_rows": self.f3_dataset_rows,
            "valid_actual_duration_records": self.valid_actual_duration_records,
            "missing_estimate_records": self.missing_estimate_records,
            "missing_created_at_records": self.missing_created_at_records,
            "missing_start_time_records": self.missing_start_time_records,
            "missing_end_time_records": self.missing_end_time_records,
            "invalid_duration_records": self.invalid_duration_records,
            "users_represented": self.users_represented,
            "task_types_represented": self.task_types_represented,
            "rejection_reason_counts": dict(self.rejection_reason_counts),
            "lifecycle_issue_counts": dict(self.lifecycle_issue_counts),
            "no_real_training_samples_available": self.no_real_training_samples_available,
        }


class TaskCollectionReporter:
    """Inspect stored Task rows without mutating them or generating synthetic data."""

    def __init__(self, session: Session, *, extractor: TaskDataExtractor | None = None) -> None:
        if session is None:
            raise ValueError("session is required.")
        self.session = session
        self.extractor = extractor or TaskDataExtractor(session)

    def report(self, *, user_id: int | None = None) -> TaskCollectionReport:
        """Return lifecycle and F.3 eligibility status for real Task rows."""

        if user_id is not None and (not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0):
            raise ValueError("user_id must be a positive integer.")
        query = self.session.query(Task)
        if user_id is not None:
            query = query.filter(Task.user_id == user_id)
        records = tuple(query.order_by(Task.user_id.asc(), Task.id.asc()).all())
        extraction = self.extractor.extract(user_id=user_id)

        issue_counts: dict[str, int] = {}
        users: set[str] = set()
        task_types: set[str] = set()
        completed_records = 0
        incomplete_records = 0
        lifecycle_valid = 0
        valid_actual_duration = 0
        missing_estimate = 0
        missing_created = 0
        missing_start = 0
        missing_end = 0
        invalid_duration = 0

        for task in records:
            if task.user_id is not None:
                users.add(str(task.user_id))
            if isinstance(task.task_type, str) and task.task_type.strip():
                task_types.add(task.task_type.strip().lower())
            if bool(task.completed):
                completed_records += 1
            else:
                incomplete_records += 1

            issues = self._lifecycle_issues(task)
            for issue in issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            if not issues and bool(task.completed):
                lifecycle_valid += 1
            if "missing_estimated_duration" in issues:
                missing_estimate += 1
            if "missing_created_at" in issues:
                missing_created += 1
            if "missing_start_time" in issues:
                missing_start += 1
            if "missing_end_time" in issues:
                missing_end += 1
            if any(issue in issues for issue in ("invalid_actual_duration", "actual_duration_conflict", "invalid_temporal_order")):
                invalid_duration += 1
            if self._has_valid_actual_duration(task):
                valid_actual_duration += 1

        return TaskCollectionReport(
            total_task_records=len(records),
            completed_records=completed_records,
            incomplete_records=incomplete_records,
            lifecycle_valid_records=lifecycle_valid,
            lifecycle_invalid_records=len(records) - lifecycle_valid,
            f3_eligible_records=extraction.report.eligible_records,
            f3_rejected_records=extraction.report.rejected_records,
            f3_dataset_rows=extraction.report.dataset_row_count,
            valid_actual_duration_records=valid_actual_duration,
            missing_estimate_records=missing_estimate,
            missing_created_at_records=missing_created,
            missing_start_time_records=missing_start,
            missing_end_time_records=missing_end,
            invalid_duration_records=invalid_duration,
            users_represented=tuple(sorted(users)),
            task_types_represented=tuple(sorted(task_types)),
            rejection_reason_counts=extraction.report.rejection_reason_counts,
            lifecycle_issue_counts=issue_counts,
            no_real_training_samples_available=extraction.report.no_real_training_samples_available,
        )

    def _lifecycle_issues(self, task: Task) -> tuple[str, ...]:
        issues: list[str] = []
        estimate = self._finite_number(getattr(task, "estimated_duration", None))
        if estimate is None or estimate <= 0:
            issues.append("missing_estimated_duration")
        created_at = getattr(task, "created_at", None)
        start_time = getattr(task, "start_time", None)
        end_time = getattr(task, "end_time", None)
        if not isinstance(created_at, datetime):
            issues.append("missing_created_at")
        if not isinstance(start_time, datetime):
            issues.append("missing_start_time")
        if bool(getattr(task, "completed", False)):
            if not isinstance(end_time, datetime):
                issues.append("missing_end_time")
            if getattr(task, "outcome_valid", None) is not True:
                issues.append("missing_valid_outcome")
        else:
            return tuple(sorted(set(issues)))

        if isinstance(created_at, datetime) and isinstance(start_time, datetime) and start_time < created_at:
            issues.append("invalid_temporal_order")
        if isinstance(start_time, datetime) and isinstance(end_time, datetime):
            if end_time <= start_time:
                issues.append("invalid_temporal_order")
            else:
                actual = self._finite_number(getattr(task, "actual_duration", None))
                derived = (end_time - start_time).total_seconds() / 60.0
                if actual is None or actual <= 0:
                    issues.append("invalid_actual_duration")
                elif abs(actual - derived) > ACTUAL_DURATION_TOLERANCE_MINUTES:
                    issues.append("actual_duration_conflict")
        return tuple(sorted(set(issues)))

    def _has_valid_actual_duration(self, task: Task) -> bool:
        start_time = getattr(task, "start_time", None)
        end_time = getattr(task, "end_time", None)
        actual = self._finite_number(getattr(task, "actual_duration", None))
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            return False
        if end_time <= start_time or actual is None or actual <= 0:
            return False
        derived = (end_time - start_time).total_seconds() / 60.0
        return abs(actual - derived) <= ACTUAL_DURATION_TOLERANCE_MINUTES

    @staticmethod
    def _finite_number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        return number
