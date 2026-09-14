from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from backend.app.ml.datasets import (
    DatasetReporter,
    DurationDatasetBuilder,
    EventType,
    LeakageGuard,
    RawTaskEvent,
    TemporalDatasetSplitter,
)


BASE = datetime(2026, 1, 1, 8, 0, 0)


def event(
    event_id: str,
    task_id: str,
    event_type: EventType,
    minutes: int,
    payload: dict[str, object] | None = None,
    user_id: str = "user-1",
) -> RawTaskEvent:
    return RawTaskEvent(
        event_id=event_id,
        task_id=task_id,
        user_id=user_id,
        event_type=event_type,
        timestamp=BASE + timedelta(minutes=minutes),
        payload=payload or {},
    )


def completed_task(
    task_id: str,
    start_minute: int,
    estimate: float,
    actual: float,
    task_type: str = "focus",
    priority: int = 3,
) -> tuple[RawTaskEvent, ...]:
    return (
        event(
            f"{task_id}-created",
            task_id,
            EventType.TASK_CREATED,
            start_minute,
            {
                "estimated_duration_minutes": estimate,
                "priority": priority,
                "task_type": task_type,
            },
        ),
        event(f"{task_id}-started", task_id, EventType.TASK_STARTED, start_minute + 5),
        event(
            f"{task_id}-completed",
            task_id,
            EventType.TASK_COMPLETED,
            start_minute + 5 + int(actual),
            {"actual_duration_minutes": actual},
        ),
    )


def demo_events() -> tuple[RawTaskEvent, ...]:
    """F.3 SYNTHETIC TEST FIXTURE -- NOT REAL TRAINING DATA."""

    return (
        *completed_task("task-a", 0, 60.0, 90.0, "focus", 4),
        *completed_task("task-b", 120, 30.0, 30.0, "admin", 2),
        *completed_task("task-c", 240, 45.0, 30.0, "focus", 5),
        *completed_task("task-d", 360, 50.0, 75.0, "focus", 3),
        *completed_task("task-e", 480, 40.0, 20.0, "admin", 1),
    )


def build_demo():
    return DurationDatasetBuilder().build(demo_events())


def test_valid_event_is_immutable_and_payload_is_nested_immutable():
    raw = event(
        "event-1",
        "task-1",
        EventType.TASK_CREATED,
        0,
        {"estimated_duration_minutes": 30, "priority": 3, "nested": {"source": "test"}},
    )

    with pytest.raises(FrozenInstanceError):
        raw.event_id = "other"
    with pytest.raises(TypeError):
        raw.payload["new"] = "blocked"
    with pytest.raises(TypeError):
        raw.payload["nested"]["source"] = "blocked"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"event_id": ""}, "event_id"),
        ({"timestamp": "bad"}, "timestamp"),
        ({"event_type": "unknown"}, "event_type"),
    ],
)
def test_invalid_raw_event_identity_timestamp_and_type(kwargs, message):
    base = {
        "event_id": "event-1",
        "task_id": "task-1",
        "user_id": "user-1",
        "event_type": EventType.TASK_CREATED,
        "timestamp": BASE,
        "payload": {"estimated_duration_minutes": 30},
    }
    base.update(kwargs)
    with pytest.raises(ValueError, match=message):
        RawTaskEvent(**base)


@pytest.mark.parametrize(
    "payload",
    [
        {"estimated_duration_minutes": 0},
        {"estimated_duration_minutes": -1},
        {"estimated_duration_minutes": float("nan")},
        {"estimated_duration_minutes": float("inf")},
        {"priority": 0},
        {"priority": 6},
    ],
)
def test_invalid_created_payload_values_are_rejected(payload):
    with pytest.raises(ValueError):
        event("event-1", "task-1", EventType.TASK_CREATED, 0, payload)


@pytest.mark.parametrize("actual", [-1, float("nan"), float("inf")])
def test_invalid_completed_actual_duration_is_rejected(actual):
    with pytest.raises(ValueError):
        event("event-1", "task-1", EventType.TASK_COMPLETED, 10, {"actual_duration_minutes": actual})


def test_duplicate_event_ids_are_rejected():
    events = (
        event("dup", "task-1", EventType.TASK_CREATED, 0, {"estimated_duration_minutes": 30}),
        event("dup", "task-1", EventType.TASK_COMPLETED, 40, {"actual_duration_minutes": 30}),
    )

    with pytest.raises(ValueError, match="duplicate event_id"):
        DurationDatasetBuilder().build(events)


def test_impossible_chronology_is_quarantined():
    events = (
        event("done", "task-1", EventType.TASK_COMPLETED, 10, {"actual_duration_minutes": 10}),
        event("late", "task-1", EventType.TASK_STARTED, 20),
    )

    result = DurationDatasetBuilder().build(events)

    assert result.rows == ()
    assert any(issue.code == "EVENT_AFTER_TERMINAL" for issue in result.rejected)


def test_valid_completed_task_generates_duration_ratio_label():
    result = DurationDatasetBuilder().build(completed_task("task-1", 0, 60.0, 90.0))

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.target == {"duration_ratio": 1.5}
    assert row.features["estimated_duration_minutes"] == 60.0
    assert "actual_duration_minutes" not in row.features
    assert "duration_ratio" not in row.features


def test_actual_duration_is_label_only_not_feature():
    row = build_demo().rows[0]

    assert row.provenance["actual_duration_used_only_for_label"] is True
    assert all("actual_duration" not in feature for feature in row.features)


def test_task_without_completed_outcome_is_rejected_not_labeled():
    events = (
        event("created", "task-1", EventType.TASK_CREATED, 0, {"estimated_duration_minutes": 30}),
        event("started", "task-1", EventType.TASK_STARTED, 5),
    )

    result = DurationDatasetBuilder().build(events)

    assert result.rows == ()
    assert any("missing completed outcome" in issue.message for issue in result.rejected)


def test_cancelled_task_is_not_converted_to_training_row():
    events = (
        event("created", "task-1", EventType.TASK_CREATED, 0, {"estimated_duration_minutes": 30}),
        event("cancelled", "task-1", EventType.TASK_CANCELLED, 10),
    )

    result = DurationDatasetBuilder().build(events)

    assert result.rows == ()
    assert any("missing completed outcome" in issue.message for issue in result.rejected)


def test_zero_actual_duration_is_rejected_for_label_quality():
    events = (
        event("created", "task-1", EventType.TASK_CREATED, 0, {"estimated_duration_minutes": 30}),
        event("completed", "task-1", EventType.TASK_COMPLETED, 10, {"actual_duration_minutes": 0}),
    )

    result = DurationDatasetBuilder().build(events)

    assert result.rows == ()
    assert any("actual_duration_minutes must be positive" in issue.message for issue in result.rejected)


def test_actual_duration_can_be_computed_from_timestamps_and_pauses():
    events = (
        event("created", "task-1", EventType.TASK_CREATED, 0, {"estimated_duration_minutes": 100}),
        event("started", "task-1", EventType.TASK_STARTED, 10),
        event("paused", "task-1", EventType.TASK_PAUSED, 30),
        event("resumed", "task-1", EventType.TASK_RESUMED, 40),
        event("completed", "task-1", EventType.TASK_COMPLETED, 70),
    )

    result = DurationDatasetBuilder().build(events)

    assert result.rows[0].target["duration_ratio"] == 0.5


def test_first_task_has_neutral_historical_features():
    row = build_demo().rows[0]

    assert row.features["prior_completed_task_count"] == 0
    assert row.features["prior_duration_ratio_mean"] == 1.0
    assert row.features["prior_duration_ratio_median"] == 1.0


def test_historical_features_use_only_outcomes_known_before_prediction():
    result = DurationDatasetBuilder().build(
        (
            *completed_task("future-outcome", 0, 60.0, 60.0),
            *completed_task("predicted-before-future-completes", 30, 30.0, 30.0),
            *completed_task("after-future-completes", 120, 30.0, 60.0),
        )
    )
    rows_by_task = {row.task_id: row for row in result.rows}

    assert rows_by_task["predicted-before-future-completes"].features["prior_completed_task_count"] == 0
    assert rows_by_task["after-future-completes"].features["prior_completed_task_count"] == 2


def test_same_type_historical_feature_is_type_specific():
    rows = {row.task_id: row for row in build_demo().rows}

    assert rows["task-c"].features["prior_same_type_duration_ratio_mean"] == 1.5
    assert rows["task-e"].features["prior_same_type_duration_ratio_mean"] == 1.0


def test_leakage_guard_rejects_forbidden_feature_names():
    guard = LeakageGuard()

    for feature_name in ("actual_duration_minutes", "completion_timestamp", "future_workload", "target", "duration_ratio"):
        with pytest.raises(ValueError):
            guard.validate_features({feature_name: 1.0})


def test_leakage_guard_rejects_unavailable_provenance():
    with pytest.raises(ValueError, match="invalid prediction-time provenance"):
        LeakageGuard().validate_provenance({"feature": "after_prediction_time"})


def test_dataset_row_rejects_target_in_features():
    result = build_demo()
    row = result.rows[0]
    with pytest.raises(ValueError, match="features cannot contain"):
        row.__class__(
            example_id="bad",
            task_id=row.task_id,
            user_id=row.user_id,
            prediction_timestamp=row.prediction_timestamp,
            features={"duration_ratio": 1.0},
            target={"duration_ratio": 1.0},
            provenance={},
            dataset_version=row.dataset_version,
            schema_version=row.schema_version,
            feature_version=row.feature_version,
            label_version=row.label_version,
        )


def test_dataset_row_rejects_invalid_target():
    row = build_demo().rows[0]
    with pytest.raises(ValueError):
        row.__class__(
            example_id="bad",
            task_id=row.task_id,
            user_id=row.user_id,
            prediction_timestamp=row.prediction_timestamp,
            features={"safe": 1.0},
            target={"duration_ratio": float("inf")},
            provenance={},
            dataset_version=row.dataset_version,
            schema_version=row.schema_version,
            feature_version=row.feature_version,
            label_version=row.label_version,
        )


def test_dataset_row_is_immutable():
    row = build_demo().rows[0]

    with pytest.raises(FrozenInstanceError):
        row.task_id = "other"
    with pytest.raises(TypeError):
        row.features["new"] = 1


def test_dataset_builder_is_deterministic_for_identical_input():
    first = build_demo()
    second = DurationDatasetBuilder().build(tuple(reversed(demo_events())))

    assert first.signature() == second.signature()


def test_temporal_split_is_chronological_and_non_overlapping():
    rows = build_demo().rows
    split = TemporalDatasetSplitter().split(rows, train_fraction=0.6, validation_fraction=0.2)

    assert len(split.train) == 3
    assert len(split.validation) == 1
    assert len(split.test) == 1
    assert split.train[-1].prediction_timestamp <= split.validation[0].prediction_timestamp
    assert split.validation[-1].prediction_timestamp <= split.test[0].prediction_timestamp
    assert len(set(split.signature()[0]) & set(split.signature()[1]) & set(split.signature()[2])) == 0


def test_temporal_split_is_deterministic_with_unsorted_rows():
    rows = tuple(reversed(build_demo().rows))
    splitter = TemporalDatasetSplitter()

    assert splitter.split(rows).signature() == splitter.split(tuple(reversed(rows))).signature()


def test_temporal_split_handles_insufficient_data_without_future_shuffle():
    rows = build_demo().rows[:2]
    split = TemporalDatasetSplitter().split(rows)

    assert split.train == rows
    assert split.validation == ()
    assert split.test == ()


def test_dataset_report_contains_quality_and_no_model_metrics():
    build = build_demo()
    split = TemporalDatasetSplitter().split(build.rows)
    report = DatasetReporter().report(build, split)

    assert report.summary["valid_examples"] == 5
    assert report.leakage_checks["actual_duration_absent_from_features"] is True
    assert report.split_sizes["train"] + report.split_sizes["validation"] + report.split_sizes["test"] == 5
    assert "rmse" not in report.summary
    with pytest.raises(TypeError):
        report.summary["new"] = 1


def test_dataset_metadata_counts_rejections():
    events = (
        *completed_task("valid", 0, 30.0, 30.0),
        event("created", "invalid", EventType.TASK_CREATED, 60, {"estimated_duration_minutes": 30}),
    )

    result = DurationDatasetBuilder().build(events)

    assert result.metadata.valid_row_count == 1
    assert result.metadata.rejected_row_count == 1


def test_invalid_pause_resume_order_is_rejected():
    events = (
        event("created", "task-1", EventType.TASK_CREATED, 0, {"estimated_duration_minutes": 30}),
        event("paused", "task-1", EventType.TASK_PAUSED, 5),
        event("completed", "task-1", EventType.TASK_COMPLETED, 40, {"actual_duration_minutes": 30}),
    )

    result = DurationDatasetBuilder().build(events)

    assert result.rows == ()
    assert any(issue.code == "INVALID_PAUSE" for issue in result.rejected)


def test_optional_context_missing_uses_safe_defaults():
    row = DurationDatasetBuilder().build(
        (
            event("created", "task-1", EventType.TASK_CREATED, 0, {"estimated_duration_minutes": 30}),
            event("completed", "task-1", EventType.TASK_COMPLETED, 45, {"actual_duration_minutes": 30}),
        )
    ).rows[0]

    assert row.features["priority"] == 3
    assert row.features["task_type"] == "general"
    assert row.features["hours_until_scheduled_start"] == 0.0


def test_scheduled_start_features_are_prediction_time_safe():
    scheduled = BASE + timedelta(hours=3)
    row = DurationDatasetBuilder().build(
        (
            event(
                "created",
                "task-1",
                EventType.TASK_CREATED,
                0,
                {"estimated_duration_minutes": 60, "scheduled_start_timestamp": scheduled},
            ),
            event("completed", "task-1", EventType.TASK_COMPLETED, 120, {"actual_duration_minutes": 90}),
        )
    ).rows[0]

    assert row.features["scheduled_start_hour"] == scheduled.hour
    assert row.features["hours_until_scheduled_start"] == 3.0


def test_duplicate_terminal_outcomes_are_rejected():
    events = (
        event("created", "task-1", EventType.TASK_CREATED, 0, {"estimated_duration_minutes": 30}),
        event("completed-1", "task-1", EventType.TASK_COMPLETED, 30, {"actual_duration_minutes": 30}),
        event("completed-2", "task-1", EventType.TASK_COMPLETED, 40, {"actual_duration_minutes": 40}),
    )

    result = DurationDatasetBuilder().build(events)

    assert result.rows == ()
    assert any(issue.code == "DUPLICATE_TERMINAL" for issue in result.rejected)

