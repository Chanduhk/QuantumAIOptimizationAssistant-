from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from backend.app.domain.optimization_input_contract import normalize_duration
from backend.app.ml.datasets.builder import DatasetBuildResult, DurationDatasetBuilder
from backend.app.ml.datasets.events import EventType, RawTaskEvent
from backend.app.ml.datasets.models import DataQualityIssue, _datetime, _freeze_mapping, _safe_text
from backend.app.ml.datasets.report import DatasetReport, DatasetReporter
from backend.app.ml.datasets.splitter import DatasetSplit, TemporalDatasetSplitter
from backend.app.models.behavior_data import BehaviorData as _BehaviorData
from backend.app.models.task import Task
from backend.app.ml.datasets.duration_quality_gate import DurationQualityGate


DERIVED_DURATION_TOLERANCE_MINUTES = 1e-6
NO_REAL_TRAINING_SAMPLES_LIMITATION = "no real training samples available"


@dataclass(frozen=True)
class TaskAdapterReport:
    """Immutable eligibility report for Task ORM to F.3 event extraction."""

    total_database_records: int
    eligible_records: int
    rejected_records: int
    rejection_reason_counts: Mapping[str, int]
    users_represented: tuple[str, ...]
    earliest_source_timestamp: datetime | None
    latest_source_timestamp: datetime | None
    label_available_records: int
    feature_available_records: int
    generated_event_count: int
    dataset_row_count: int
    adapter_signature: tuple[Any, ...]
    dataset_signature: tuple[Any, ...] | None
    limitations: tuple[str, ...]
    no_real_training_samples_available: bool

    def __post_init__(self) -> None:
        for field_name in (
            "total_database_records",
            "eligible_records",
            "rejected_records",
            "label_available_records",
            "feature_available_records",
            "generated_event_count",
            "dataset_row_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")
        object.__setattr__(self, "rejection_reason_counts", _freeze_mapping(self.rejection_reason_counts, "rejection_reason_counts"))
        for field_name in ("earliest_source_timestamp", "latest_source_timestamp"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _datetime(value, field_name))
        if not isinstance(self.users_represented, tuple):
            raise ValueError("users_represented must be a tuple.")
        object.__setattr__(self, "users_represented", tuple(_safe_text(str(user), "user_id") for user in self.users_represented))
        if not isinstance(self.adapter_signature, tuple):
            raise ValueError("adapter_signature must be a tuple.")
        if self.dataset_signature is not None and not isinstance(self.dataset_signature, tuple):
            raise ValueError("dataset_signature must be a tuple when supplied.")
        if not isinstance(self.limitations, tuple):
            raise ValueError("limitations must be a tuple.")
        object.__setattr__(self, "limitations", tuple(_safe_text(str(item), "limitation") for item in self.limitations))
        if not isinstance(self.no_real_training_samples_available, bool):
            raise ValueError("no_real_training_samples_available must be boolean.")

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-friendly report representation."""

        return {
            "total_database_records": self.total_database_records,
            "eligible_records": self.eligible_records,
            "rejected_records": self.rejected_records,
            "rejection_reason_counts": dict(self.rejection_reason_counts),
            "users_represented": self.users_represented,
            "earliest_source_timestamp": None
            if self.earliest_source_timestamp is None
            else self.earliest_source_timestamp.isoformat(),
            "latest_source_timestamp": None
            if self.latest_source_timestamp is None
            else self.latest_source_timestamp.isoformat(),
            "label_available_records": self.label_available_records,
            "feature_available_records": self.feature_available_records,
            "generated_event_count": self.generated_event_count,
            "dataset_row_count": self.dataset_row_count,
            "adapter_signature": self.adapter_signature,
            "dataset_signature": self.dataset_signature,
            "limitations": self.limitations,
            "no_real_training_samples_available": self.no_real_training_samples_available,
        }


@dataclass(frozen=True)
class TaskExtractionResult:
    """Immutable output of read-only Task extraction and F.3 dataset adaptation."""

    events: tuple[RawTaskEvent, ...]
    rejected: tuple[DataQualityIssue, ...]
    report: TaskAdapterReport
    dataset_build: DatasetBuildResult
    dataset_report: DatasetReport
    dataset_split: DatasetSplit

    def signature(self) -> tuple[Any, ...]:
        """Return a deterministic signature for repeated extraction checks."""

        return (
            tuple((event.event_id, event.task_id, event.user_id, event.event_type.value, event.timestamp.isoformat()) for event in self.events),
            tuple((issue.severity, issue.code, issue.task_id, issue.message) for issue in self.rejected),
            self.report.adapter_signature,
            self.dataset_build.signature(),
            self.dataset_split.signature(),
        )


class TaskDataExtractor:
    """Read Task records and adapt eligible completed tasks into F.3 RawTaskEvent contracts."""

    def __init__(
        self,
        session: Session,
        *,
        dataset_builder: DurationDatasetBuilder | None = None,
        splitter: TemporalDatasetSplitter | None = None,
        reporter: DatasetReporter | None = None,
    ) -> None:
        if session is None:
            raise ValueError("session is required.")
        self.session = session
        self.dataset_builder = dataset_builder or DurationDatasetBuilder()
        self.splitter = splitter or TemporalDatasetSplitter()
        self.reporter = reporter or DatasetReporter()

    def extract(self, *, user_id: int | None = None) -> TaskExtractionResult:
        """Read Task rows from the current SQLAlchemy session and return F.3-compatible output."""

        if user_id is not None:
            self._positive_int(user_id, "user_id")
        query = self.session.query(Task)
        if user_id is not None:
            query = query.filter(Task.user_id == user_id)
        records = query.order_by(Task.user_id.asc(), Task.id.asc()).all()
        return self.extract_from_records(records)

    def extract_from_records(self, records: Iterable[Task]) -> TaskExtractionResult:
        """Adapt provided Task-like records without mutating them."""

        ordered_records = tuple(sorted(records, key=self._record_order_key))
        events: list[RawTaskEvent] = []
        rejected: list[DataQualityIssue] = []
        seen_task_ids: set[str] = set()
        source_timestamps: list[datetime] = []
        eligible_users: set[str] = set()
        label_available = 0
        feature_available = 0

        for record in ordered_records:
            task_key = self._task_key(record)
            if task_key in seen_task_ids:
                rejected.append(self._issue("DUPLICATE_TASK_ID", "duplicate task id", task_key))
                continue
            seen_task_ids.add(task_key)
            try:
                adapted_events, timestamps = self._adapt_record(record)
                events.extend(adapted_events)
                source_timestamps.extend(timestamps)
                eligible_users.add(str(record.user_id))
                label_available += 1
                feature_available += 1
            except ValueError as exc:
                rejected.append(self._issue("TASK_REJECTED", str(exc), task_key))
                for timestamp in (getattr(record, "start_time", None), getattr(record, "end_time", None)):
                    if isinstance(timestamp, datetime):
                        source_timestamps.append(timestamp)

        event_tuple = tuple(sorted(events, key=lambda event: (event.timestamp, event.user_id, event.task_id, event.event_id)))
        dataset_build = self.dataset_builder.build(event_tuple)
        dataset_split = self.splitter.split(dataset_build.rows)
        dataset_report = self.reporter.report(dataset_build, dataset_split)
        all_rejected = tuple(sorted([*rejected, *dataset_build.rejected], key=lambda issue: (issue.code, issue.task_id or "", issue.message)))
        report = self._report(
            records=ordered_records,
            events=event_tuple,
            rejected=all_rejected,
            source_timestamps=source_timestamps,
            users=eligible_users,
            label_available=label_available,
            feature_available=feature_available,
            dataset_build=dataset_build,
        )
        return TaskExtractionResult(
            events=event_tuple,
            rejected=all_rejected,
            report=report,
            dataset_build=dataset_build,
            dataset_report=dataset_report,
            dataset_split=dataset_split,
        )

    def _adapt_record(self, task: Task) -> tuple[tuple[RawTaskEvent, ...], tuple[datetime, ...]]:
        task_id = str(self._positive_int(getattr(task, "id", None), "task.id"))
        user_id = str(self._positive_int(getattr(task, "user_id", None), "task.user_id"))
        task_type = _safe_text(str(getattr(task, "task_type", "")), "task.task_type")
        priority = self._priority(getattr(task, "priority", None))
        raw_estimate = self._positive_float(getattr(task, "estimated_duration", None), "task.estimated_duration")
        estimate_unit = getattr(task, "estimated_duration_unit", None)
        estimate_source = getattr(task, "estimated_duration_source", None)
        if estimate_unit not in {"minutes", "hours"} or not isinstance(estimate_source, str) or not estimate_source.strip():
            raise ValueError("task.estimated_duration unit/source is unknown; legacy estimate is ineligible.")
        normalized_estimate = normalize_duration(raw_estimate, estimate_unit, estimate_source)
        estimate = normalized_estimate.normalized_hours * 60.0
        start_time = _datetime(getattr(task, "start_time", None), "task.start_time")
        created_at = getattr(task, "created_at", None)
        prediction_time = created_at if isinstance(created_at, datetime) else start_time
        if start_time < prediction_time:
            raise ValueError("task.start_time cannot be before task.created_at.")
        end_time = _datetime(getattr(task, "end_time", None), "task.end_time")
        if not bool(getattr(task, "completed", False)):
            raise ValueError("task is incomplete.")
        if end_time <= start_time:
            raise ValueError("task.end_time must be after task.start_time.")

        derived_duration = (end_time - start_time).total_seconds() / 60.0
        stored_actual = getattr(task, "actual_duration", None)
        actual_duration = derived_duration if stored_actual is None else self._non_negative_float(stored_actual, "task.actual_duration")
        if stored_actual is not None and abs(actual_duration - derived_duration) > DERIVED_DURATION_TOLERANCE_MINUTES:
            raise ValueError("task.actual_duration conflicts with duration derived from start_time/end_time.")
        if actual_duration <= 0:
            raise ValueError("task.actual_duration must be positive.")

        quality_assessment = DurationQualityGate.assess(
            actual_duration_minutes=actual_duration,
            estimated_duration_minutes=estimate,
        )
        if not quality_assessment.is_eligible:
            raise ValueError(f"duration quality anomaly: {quality_assessment.exclusion_reason}")

        events = (
            RawTaskEvent(
                event_id=f"task-{task_id}-created",
                task_id=task_id,
                user_id=user_id,
                event_type=EventType.TASK_CREATED,
                timestamp=prediction_time,
                payload={
                    "estimated_duration_minutes": estimate,
                    "priority": priority,
                    "task_type": task_type,
                    "source": "task_orm_created_at" if isinstance(created_at, datetime) else "task_orm_start_time_conservative_prediction_boundary",
                },
            ),
            RawTaskEvent(
                event_id=f"task-{task_id}-started",
                task_id=task_id,
                user_id=user_id,
                event_type=EventType.TASK_STARTED,
                timestamp=start_time,
                payload={"source": "task_orm_start_time"},
            ),
            RawTaskEvent(
                event_id=f"task-{task_id}-completed",
                task_id=task_id,
                user_id=user_id,
                event_type=EventType.TASK_COMPLETED,
                timestamp=end_time,
                payload={
                    "actual_duration_minutes": actual_duration,
                    "source": "task_orm_actual_duration" if stored_actual is not None else "task_orm_start_end_derived_duration",
                },
            ),
        )
        return events, (prediction_time, start_time, end_time)

    @staticmethod
    def _report(
        *,
        records: tuple[Task, ...],
        events: tuple[RawTaskEvent, ...],
        rejected: tuple[DataQualityIssue, ...],
        source_timestamps: list[datetime],
        users: set[str],
        label_available: int,
        feature_available: int,
        dataset_build: DatasetBuildResult,
    ) -> TaskAdapterReport:
        reason_counts: dict[str, int] = {}
        for issue in rejected:
            reason_counts[issue.message] = reason_counts.get(issue.message, 0) + 1
        limitations = (
            "legacy records without created_at use task.start_time as conservative prediction boundary",
            "pause/resume history is unavailable in Task ORM",
            "BehaviorData post-outcome fields are not used as prediction features",
        )
        if not dataset_build.rows:
            limitations = (*limitations, NO_REAL_TRAINING_SAMPLES_LIMITATION)
        adapter_signature = (
            len(records),
            tuple((event.event_id, event.timestamp.isoformat()) for event in events),
            tuple(sorted(reason_counts.items())),
            dataset_build.signature(),
        )
        return TaskAdapterReport(
            total_database_records=len(records),
            eligible_records=len(events) // 3,
            rejected_records=len(rejected),
            rejection_reason_counts=reason_counts,
            users_represented=tuple(sorted(users)),
            earliest_source_timestamp=min(source_timestamps) if source_timestamps else None,
            latest_source_timestamp=max(source_timestamps) if source_timestamps else None,
            label_available_records=label_available,
            feature_available_records=feature_available,
            generated_event_count=len(events),
            dataset_row_count=len(dataset_build.rows),
            adapter_signature=adapter_signature,
            dataset_signature=dataset_build.signature(),
            limitations=limitations,
            no_real_training_samples_available=not dataset_build.rows,
        )

    @staticmethod
    def _record_order_key(record: Task) -> tuple[int, datetime, int]:
        user_id = getattr(record, "user_id", 0) or 0
        start = getattr(record, "start_time", None)
        task_id = getattr(record, "id", 0) or 0
        return (int(user_id), start if isinstance(start, datetime) else datetime.max, int(task_id))

    @staticmethod
    def _task_key(record: Task) -> str:
        value = getattr(record, "id", None)
        return "missing-task-id" if value is None else str(value)

    @staticmethod
    def _issue(code: str, message: str, task_id: str) -> DataQualityIssue:
        return DataQualityIssue("QUARANTINE", code, message, task_id=task_id)

    @staticmethod
    def _positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer.")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a positive integer.") from None
        if number <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
        return number

    @staticmethod
    def _priority(value: Any) -> int:
        priority = TaskDataExtractor._positive_int(value, "task.priority")
        if priority > 5:
            raise ValueError("task.priority must be between 1 and 5.")
        return priority

    @staticmethod
    def _positive_float(value: Any, field_name: str) -> float:
        number = TaskDataExtractor._non_negative_float(value, field_name)
        if number <= 0:
            raise ValueError(f"{field_name} must be positive.")
        return number

    @staticmethod
    def _non_negative_float(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be numeric.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        if number < 0:
            raise ValueError(f"{field_name} cannot be negative.")
        return number
