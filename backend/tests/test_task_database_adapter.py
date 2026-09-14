from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ml.datasets import EventType, TaskDataExtractor
from backend.app.models.base import Base
from backend.app.models.task import Task


BASE = datetime(2026, 1, 1, 9, 0, 0)


def make_task(
    task_id: int,
    *,
    user_id: int = 1,
    task_type: str = "focus",
    priority: int = 3,
    estimate: float | None = 60.0,
    actual: float | None = 60.0,
    start_offset: int | None = 0,
    end_offset: int | None = 60,
    completed: bool = True,
) -> Task:
    return Task(
        id=task_id,
        user_id=user_id,
        title=f"private-title-{task_id}",
        task_type=task_type,
        priority=priority,
        estimated_duration=estimate,
        actual_duration=actual,
        start_time=None if start_offset is None else BASE + timedelta(minutes=start_offset),
        end_time=None if end_offset is None else BASE + timedelta(minutes=end_offset),
        completed=completed,
    )


def memory_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    return Session()


def extract(records):
    return TaskDataExtractor(memory_session()).extract_from_records(tuple(records))


def test_empty_database_reports_zero_without_fabricating_events():
    session = memory_session()

    result = TaskDataExtractor(session).extract()

    assert result.report.total_database_records == 0
    assert result.report.eligible_records == 0
    assert result.report.rejected_records == 0
    assert result.report.generated_event_count == 0
    assert result.dataset_build.rows == ()
    assert result.report.no_real_training_samples_available is True


def test_valid_completed_task_maps_to_f3_events_and_dataset_row():
    result = extract([make_task(1, estimate=60.0, actual=90.0, end_offset=90)])

    assert result.report.eligible_records == 1
    assert [event.event_type for event in result.events] == [
        EventType.TASK_CREATED,
        EventType.TASK_STARTED,
        EventType.TASK_COMPLETED,
    ]
    row = result.dataset_build.rows[0]
    assert row.task_id == "1"
    assert row.user_id == "1"
    assert row.prediction_timestamp == BASE
    assert row.features["estimated_duration_minutes"] == 60.0
    assert row.features["task_type"] == "focus"
    assert row.target["duration_ratio"] == 1.5


def test_task_title_is_not_exposed_in_events_or_features():
    result = extract([make_task(1)])

    serialized_events = str(tuple(event.payload for event in result.events))
    assert "private-title" not in serialized_events
    assert "title" not in result.dataset_build.rows[0].features


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"estimate": None}, "task.estimated_duration must be numeric"),
        ({"estimate": 0.0}, "task.estimated_duration must be positive"),
        ({"estimate": -1.0}, "task.estimated_duration cannot be negative"),
        ({"start_offset": None}, "task.start_time must be a datetime"),
        ({"end_offset": None}, "task.end_time must be a datetime"),
        ({"completed": False}, "task is incomplete"),
        ({"task_type": ""}, "task.task_type must be a non-empty string"),
        ({"priority": 0}, "task.priority must be a positive integer"),
        ({"priority": 6}, "task.priority must be between 1 and 5"),
    ],
)
def test_invalid_task_records_are_reported(kwargs, expected):
    result = extract([make_task(1, **kwargs)])

    assert result.dataset_build.rows == ()
    assert result.report.eligible_records == 0
    assert any(expected in reason for reason in result.report.rejection_reason_counts)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_estimated_duration_is_rejected(value):
    result = extract([make_task(1, estimate=value)])

    assert any("task.estimated_duration must be finite" in reason for reason in result.report.rejection_reason_counts)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_actual_duration_is_rejected(value):
    result = extract([make_task(1, actual=value)])

    assert any("task.actual_duration must be finite" in reason for reason in result.report.rejection_reason_counts)


def test_negative_actual_duration_is_rejected():
    result = extract([make_task(1, actual=-1.0)])

    assert "task.actual_duration cannot be negative." in result.report.rejection_reason_counts


def test_zero_actual_duration_is_rejected():
    result = extract([make_task(1, actual=0.0, end_offset=0)])

    assert "task.end_time must be after task.start_time." in result.report.rejection_reason_counts


def test_impossible_timestamps_are_rejected():
    result = extract([make_task(1, actual=60.0, start_offset=60, end_offset=30)])

    assert "task.end_time must be after task.start_time." in result.report.rejection_reason_counts


def test_actual_duration_can_be_derived_from_start_end_when_missing():
    result = extract([make_task(1, estimate=60.0, actual=None, start_offset=0, end_offset=75)])

    assert result.dataset_build.rows[0].target["duration_ratio"] == 1.25
    completed = [event for event in result.events if event.event_type is EventType.TASK_COMPLETED][0]
    assert completed.payload["source"] == "task_orm_start_end_derived_duration"


def test_conflicting_stored_and_derived_duration_is_rejected():
    result = extract([make_task(1, estimate=60.0, actual=50.0, start_offset=0, end_offset=60)])

    assert "task.actual_duration conflicts with duration derived from start_time/end_time." in result.report.rejection_reason_counts


def test_duplicate_task_ids_are_rejected_deterministically():
    result = extract([make_task(1), make_task(1, user_id=2)])

    assert result.report.eligible_records == 1
    assert "duplicate task id" in result.report.rejection_reason_counts


def test_multiple_users_are_represented_without_cross_user_history():
    result = extract(
        [
            make_task(1, user_id=1, actual=60.0),
            make_task(2, user_id=2, actual=120.0, end_offset=120),
        ]
    )

    rows = {row.user_id: row for row in result.dataset_build.rows}
    assert result.report.users_represented == ("1", "2")
    assert rows["1"].features["prior_completed_task_count"] == 0
    assert rows["2"].features["prior_completed_task_count"] == 0


def test_ordering_and_signature_are_deterministic():
    records = [
        make_task(2, start_offset=120, end_offset=180),
        make_task(1, start_offset=0, end_offset=60),
    ]

    first = extract(records)
    second = extract(tuple(reversed(records)))

    assert [event.task_id for event in first.events] == ["1", "1", "1", "2", "2", "2"]
    assert first.signature() == second.signature()


def test_later_completed_task_does_not_affect_earlier_features():
    result = extract(
        [
            make_task(1, start_offset=0, end_offset=100, actual=100),
            make_task(2, start_offset=10, end_offset=40, actual=30),
            make_task(3, start_offset=120, end_offset=180, actual=60),
        ]
    )
    rows = {row.task_id: row for row in result.dataset_build.rows}

    assert rows["2"].features["prior_completed_task_count"] == 0
    assert rows["3"].features["prior_completed_task_count"] == 2


def test_leakage_fields_are_absent_from_prediction_features():
    result = extract([make_task(1, actual=90.0, end_offset=90)])
    row = result.dataset_build.rows[0]

    forbidden_exact = {
        "actual_duration",
        "actual_duration_minutes",
        "end_time",
        "completed",
        "completion_time",
        "productivity_score",
    }
    assert forbidden_exact.isdisjoint(set(row.features))


def test_behavior_data_fields_are_not_used_as_prediction_features():
    result = extract([make_task(1)])
    features = result.dataset_build.rows[0].features

    assert "duration" not in features
    assert "completion_time" not in features
    assert "productivity_score" not in features


def test_report_contains_eligibility_and_dataset_counts():
    result = extract([make_task(1), make_task(2, estimate=None)])

    assert result.report.total_database_records == 2
    assert result.report.eligible_records == 1
    assert result.report.rejected_records == 1
    assert result.report.generated_event_count == 3
    assert result.report.dataset_row_count == 1
    assert result.report.label_available_records == 1
    assert result.report.feature_available_records == 1


def test_report_is_immutable_and_json_friendly():
    result = extract([make_task(1)])

    with pytest.raises(FrozenInstanceError):
        result.report.eligible_records = 99
    with pytest.raises(TypeError):
        result.report.rejection_reason_counts["new"] = 1
    assert result.report.to_dict()["eligible_records"] == 1


def test_extract_reads_from_sqlalchemy_session():
    session = memory_session()
    session.add(make_task(1))
    session.add(make_task(2, user_id=2, start_offset=120, end_offset=180))
    session.commit()

    result = TaskDataExtractor(session).extract()

    assert result.report.total_database_records == 2
    assert result.report.eligible_records == 2
    assert len(result.dataset_build.rows) == 2


def test_extract_can_filter_by_user_id():
    session = memory_session()
    session.add(make_task(1, user_id=1))
    session.add(make_task(2, user_id=2))
    session.commit()

    result = TaskDataExtractor(session).extract(user_id=2)

    assert result.report.total_database_records == 1
    assert result.report.users_represented == ("2",)


def test_extract_rejects_invalid_user_filter():
    with pytest.raises(ValueError, match="user_id"):
        TaskDataExtractor(memory_session()).extract(user_id=0)


def test_f3_raw_event_contract_compatibility():
    result = extract([make_task(1, estimate=45.0, actual=45.0, end_offset=45)])

    assert all(event.schema_version == "task_event_v0.1" for event in result.events)
    assert result.events[0].payload["estimated_duration_minutes"] == 45.0
    assert result.events[-1].payload["actual_duration_minutes"] == 45.0
    assert result.dataset_build.rows[0].target["duration_ratio"] == 1.0
