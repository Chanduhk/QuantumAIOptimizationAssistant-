from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any, Mapping

from backend.app.ml.datasets.events import (
    CanonicalEventHistory,
    EventHistoryBuilder,
    EventType,
    RawTaskEvent,
)
from backend.app.ml.datasets.leakage import LeakageGuard
from backend.app.ml.datasets.models import (
    DataQualityIssue,
    DatasetMetadata,
    DatasetRow,
    PredictionSnapshot,
)


SCHEMA_VERSION = "duration_dataset_schema_v0.1"
FEATURE_VERSION = "duration_features_v0.1"
LABEL_VERSION = "duration_ratio_v0.1"
DATASET_VERSION = "duration_ratio_dataset_v0.1"


@dataclass(frozen=True)
class DatasetBuildResult:
    """Immutable output of deterministic F.3 dataset construction."""

    rows: tuple[DatasetRow, ...]
    rejected: tuple[DataQualityIssue, ...]
    metadata: DatasetMetadata

    def signature(self) -> tuple[Any, ...]:
        """Return deterministic signature for reproducibility checks."""

        return (
            tuple(row.signature() for row in self.rows),
            tuple((issue.severity, issue.code, issue.message, issue.task_id, issue.event_id) for issue in self.rejected),
            self.metadata.dataset_version,
            self.metadata.valid_row_count,
            self.metadata.rejected_row_count,
        )


class DurationDatasetBuilder:
    """Build leakage-safe duration-ratio supervised dataset rows from task events."""

    def __init__(self, *, leakage_guard: LeakageGuard | None = None) -> None:
        self.history_builder = EventHistoryBuilder()
        self.leakage_guard = leakage_guard or LeakageGuard()

    def build(self, events: tuple[RawTaskEvent, ...]) -> DatasetBuildResult:
        """Build valid rows, rejected issues, and metadata from raw events."""

        histories = self.history_builder.build(events)
        rejected: list[DataQualityIssue] = []
        rows: list[DatasetRow] = []
        completed_prior: list[tuple[CanonicalEventHistory, float, datetime]] = []

        for history in sorted(histories, key=lambda item: (self._prediction_timestamp(item) or datetime.max, item.task_id)):
            if any(issue.severity == "ERROR" for issue in history.issues):
                rejected.extend(history.issues)
                continue
            try:
                snapshot = self._snapshot(history, completed_prior)
                features, feature_provenance = self._features(snapshot)
                self.leakage_guard.validate_features(features)
                self.leakage_guard.validate_provenance(feature_provenance)
                ratio, outcome_timestamp = self._duration_ratio(history)
                if outcome_timestamp <= snapshot.prediction_timestamp:
                    raise ValueError("outcome occurs before or at prediction timestamp.")
                row = DatasetRow(
                    example_id=f"duration-ratio-{history.user_id}-{history.task_id}",
                    task_id=history.task_id,
                    user_id=history.user_id,
                    prediction_timestamp=snapshot.prediction_timestamp,
                    features=features,
                    target={"duration_ratio": ratio},
                    provenance={
                        "feature_provenance": tuple(sorted(feature_provenance.items())),
                        "label_source": "task_completed_outcome",
                        "actual_duration_used_only_for_label": True,
                    },
                    dataset_version=DATASET_VERSION,
                    schema_version=SCHEMA_VERSION,
                    feature_version=FEATURE_VERSION,
                    label_version=LABEL_VERSION,
                )
                rows.append(row)
                completed_prior.append((history, ratio, outcome_timestamp))
            except ValueError as exc:
                rejected.append(DataQualityIssue("QUARANTINE", "ROW_REJECTED", str(exc), history.task_id))

        rows = sorted(rows, key=lambda row: (row.prediction_timestamp, row.example_id))
        metadata = self._metadata(events, rows, rejected)
        return DatasetBuildResult(rows=tuple(rows), rejected=tuple(rejected), metadata=metadata)

    def _snapshot(
        self,
        history: CanonicalEventHistory,
        completed_prior: list[tuple[CanonicalEventHistory, float, datetime]],
    ) -> PredictionSnapshot:
        prediction_timestamp = self._prediction_timestamp(history)
        if prediction_timestamp is None:
            raise ValueError("missing prediction timestamp from created/scheduled event.")
        task_state = self._task_state_at_prediction(history, prediction_timestamp)
        historical = self._historical_context(
            user_id=history.user_id,
            task_type=str(task_state.get("task_type", "unknown")),
            prediction_timestamp=prediction_timestamp,
            completed_prior=completed_prior,
        )
        return PredictionSnapshot(
            task_id=history.task_id,
            user_id=history.user_id,
            prediction_timestamp=prediction_timestamp,
            task_state=task_state,
            historical_context=historical,
        )

    def _features(self, snapshot: PredictionSnapshot) -> tuple[Mapping[str, Any], Mapping[str, str]]:
        state = snapshot.task_state
        estimated = self._positive_float(state.get("estimated_duration_minutes"), "estimated_duration_minutes")
        priority = int(state.get("priority", 3))
        if priority < 1 or priority > 5:
            raise ValueError("priority must be between 1 and 5.")
        task_type = str(state.get("task_type", "general")).strip().lower() or "general"
        scheduled_start = state.get("scheduled_start_timestamp")
        features: dict[str, Any] = {
            "estimated_duration_minutes": estimated,
            "priority": priority,
            "task_type": task_type,
            "prediction_hour": snapshot.prediction_timestamp.hour,
            "prediction_day_of_week": snapshot.prediction_timestamp.weekday(),
            "time_since_task_created_minutes": self._minutes_between(state.get("created_timestamp"), snapshot.prediction_timestamp),
            "scheduled_start_hour": scheduled_start.hour if isinstance(scheduled_start, datetime) else snapshot.prediction_timestamp.hour,
            "hours_until_scheduled_start": (
                round((scheduled_start - snapshot.prediction_timestamp).total_seconds() / 3600.0, 4)
                if isinstance(scheduled_start, datetime)
                else 0.0
            ),
            **snapshot.historical_context,
        }
        provenance = {key: "available_at_prediction_time" for key in features}
        return features, provenance

    def _historical_context(
        self,
        *,
        user_id: str,
        task_type: str,
        prediction_timestamp: datetime,
        completed_prior: list[tuple[CanonicalEventHistory, float, datetime]],
    ) -> dict[str, Any]:
        eligible = [
            (history, ratio, outcome_time)
            for history, ratio, outcome_time in completed_prior
            if history.user_id == user_id and outcome_time < prediction_timestamp
        ]
        ratios = [ratio for _, ratio, _ in eligible]
        same_type = [
            ratio
            for history, ratio, outcome_time in eligible
            if str(self._task_state_at_prediction(history, self._prediction_timestamp(history) or outcome_time).get("task_type", "")).lower()
            == task_type
        ]
        return {
            "prior_completed_task_count": len(eligible),
            "prior_duration_ratio_mean": round(sum(ratios) / len(ratios), 6) if ratios else 1.0,
            "prior_duration_ratio_median": round(float(median(ratios)), 6) if ratios else 1.0,
            "prior_same_type_duration_ratio_mean": round(sum(same_type) / len(same_type), 6) if same_type else 1.0,
        }

    def _duration_ratio(self, history: CanonicalEventHistory) -> tuple[float, datetime]:
        completed = self._first_event(history, EventType.TASK_COMPLETED)
        if completed is None:
            raise ValueError("missing completed outcome.")
        estimated = self._positive_float(self._task_state_at_prediction(history, self._prediction_timestamp(history) or completed.timestamp).get("estimated_duration_minutes"), "estimated_duration_minutes")
        actual = completed.payload.get("actual_duration_minutes")
        if actual is None:
            actual = self._actual_duration_from_timestamps(history, completed)
        actual_minutes = self._non_negative_float(actual, "actual_duration_minutes")
        if actual_minutes <= 0:
            raise ValueError("actual_duration_minutes must be positive for duration_ratio.")
        ratio = actual_minutes / estimated
        if not math.isfinite(ratio):
            raise ValueError("duration_ratio must be finite.")
        return round(ratio, 8), completed.timestamp

    def _actual_duration_from_timestamps(self, history: CanonicalEventHistory, completed: RawTaskEvent) -> float:
        started = self._first_event(history, EventType.TASK_STARTED)
        if started is None:
            raise ValueError("missing actual duration and task_started event.")
        if completed.timestamp <= started.timestamp:
            raise ValueError("completed timestamp must be after started timestamp.")
        paused_minutes = self._paused_minutes(history)
        return max(0.0, (completed.timestamp - started.timestamp).total_seconds() / 60.0 - paused_minutes)

    @staticmethod
    def _paused_minutes(history: CanonicalEventHistory) -> float:
        paused_at: datetime | None = None
        total = 0.0
        for event in history.events:
            if event.event_type is EventType.TASK_PAUSED:
                paused_at = event.timestamp
            elif event.event_type is EventType.TASK_RESUMED and paused_at is not None:
                total += max(0.0, (event.timestamp - paused_at).total_seconds() / 60.0)
                paused_at = None
        return total

    @staticmethod
    def _prediction_timestamp(history: CanonicalEventHistory) -> datetime | None:
        for event_type in (EventType.TASK_SCHEDULED, EventType.TASK_CREATED, EventType.TASK_RESCHEDULED):
            event = DurationDatasetBuilder._first_event(history, event_type)
            if event is not None:
                return event.timestamp
        return None

    @staticmethod
    def _task_state_at_prediction(history: CanonicalEventHistory, prediction_timestamp: datetime) -> dict[str, Any]:
        state: dict[str, Any] = {"task_type": "general", "priority": 3}
        for event in history.events:
            if event.timestamp > prediction_timestamp:
                continue
            if event.event_type in {EventType.TASK_CREATED, EventType.TASK_SCHEDULED, EventType.TASK_RESCHEDULED}:
                if "created_timestamp" not in state and event.event_type is EventType.TASK_CREATED:
                    state["created_timestamp"] = event.timestamp
                for key in ("estimated_duration_minutes", "priority", "task_type", "goal_id", "dependency_count"):
                    if key in event.payload:
                        state[key] = event.payload[key]
                if "scheduled_start_timestamp" in event.payload:
                    scheduled = event.payload["scheduled_start_timestamp"]
                    if not isinstance(scheduled, datetime):
                        raise ValueError("scheduled_start_timestamp must be a datetime.")
                    state["scheduled_start_timestamp"] = scheduled
        if "created_timestamp" not in state:
            state["created_timestamp"] = prediction_timestamp
        return state

    @staticmethod
    def _first_event(history: CanonicalEventHistory, event_type: EventType) -> RawTaskEvent | None:
        for event in history.events:
            if event.event_type is event_type:
                return event
        return None

    @staticmethod
    def _minutes_between(start: object, end: datetime) -> float:
        if not isinstance(start, datetime):
            return 0.0
        return round(max(0.0, (end - start).total_seconds() / 60.0), 4)

    @staticmethod
    def _positive_float(value: object, field_name: str) -> float:
        number = DurationDatasetBuilder._non_negative_float(value, field_name)
        if number <= 0:
            raise ValueError(f"{field_name} must be positive.")
        return number

    @staticmethod
    def _non_negative_float(value: object, field_name: str) -> float:
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

    @staticmethod
    def _metadata(
        events: tuple[RawTaskEvent, ...],
        rows: list[DatasetRow],
        rejected: list[DataQualityIssue],
    ) -> DatasetMetadata:
        timestamps = [event.timestamp for event in events]
        return DatasetMetadata(
            dataset_version=DATASET_VERSION,
            schema_version=SCHEMA_VERSION,
            feature_version=FEATURE_VERSION,
            label_version=LABEL_VERSION,
            creation_timestamp="deterministic_from_source_events",
            source_period_start=min(timestamps) if timestamps else None,
            source_period_end=max(timestamps) if timestamps else None,
            raw_event_count=len(events),
            valid_event_count=len(events) - sum(1 for issue in rejected if issue.event_id),
            invalid_event_count=sum(1 for issue in rejected if issue.event_id),
            row_count=len(rows),
            valid_row_count=len(rows),
            rejected_row_count=len(rejected),
        )
