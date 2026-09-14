from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.db import get_db
from backend.app.ml.datasets import TaskCollectionReporter, TaskDataExtractor
from backend.app.models.base import Base
from backend.app.models.behavior_data import BehaviorData as _BehaviorData
from backend.app.models.task import Task
from backend.app.services.task_lifecycle_service import TaskLifecycleService
from backend.main import app


BASE = datetime(2026, 1, 1, 9, 0, 0)


def memory_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    return Session()


def complete_task(
    service: TaskLifecycleService,
    *,
    user_id: int = 1,
    task_type: str = "focus",
    estimate: float = 60.0,
    actual_minutes: float = 60.0,
    created_offset: int = 0,
    start_offset: int = 5,
) -> Task:
    task = service.create_task(
        user_id=user_id,
        title="private validation task",
        task_type=task_type,
        priority=3,
        estimated_duration=estimate,
        created_at=BASE + timedelta(minutes=created_offset),
    )
    service.start_task(task_id=task.id, user_id=user_id, started_at=BASE + timedelta(minutes=start_offset))
    return service.complete_task(
        task_id=task.id,
        user_id=user_id,
        completed_at=BASE + timedelta(minutes=start_offset + actual_minutes),
    )


def test_collection_report_empty_database_reports_no_real_samples():
    report = TaskCollectionReporter(memory_session()).report()

    assert report.total_task_records == 0
    assert report.completed_records == 0
    assert report.f3_eligible_records == 0
    assert report.f3_dataset_rows == 0
    assert report.no_real_training_samples_available is True


def test_real_application_lifecycle_produces_collection_valid_record():
    session = memory_session()
    service = TaskLifecycleService(session)
    complete_task(service)

    report = TaskCollectionReporter(session).report(user_id=1)

    assert report.total_task_records == 1
    assert report.completed_records == 1
    assert report.lifecycle_valid_records == 1
    assert report.f3_eligible_records == 1
    assert report.f3_dataset_rows == 1
    assert report.valid_actual_duration_records == 1
    assert report.users_represented == ("1",)
    assert report.task_types_represented == ("focus",)


def test_collection_report_counts_incomplete_record_without_fabrication():
    session = memory_session()
    service = TaskLifecycleService(session)
    service.create_task(
        user_id=1,
        title="private pending task",
        task_type="admin",
        priority=2,
        estimated_duration=30.0,
        created_at=BASE,
    )

    report = TaskCollectionReporter(session).report(user_id=1)

    assert report.incomplete_records == 1
    assert report.completed_records == 0
    assert report.f3_eligible_records == 0
    assert report.missing_start_time_records == 1
    assert report.missing_end_time_records == 0


def test_invalid_historical_row_is_reported_not_repaired():
    session = memory_session()
    session.add(
        Task(
            user_id=1,
            title="legacy bad task",
            task_type="focus",
            priority=3,
            estimated_duration=60.0,
            created_at=BASE + timedelta(hours=1),
            start_time=BASE,
            end_time=BASE + timedelta(minutes=30),
            actual_duration=30.0,
            completed=True,
            lifecycle_state="completed",
            outcome_valid=True,
        )
    )
    session.commit()

    report = TaskCollectionReporter(session).report()

    assert report.lifecycle_valid_records == 0
    assert report.lifecycle_issue_counts["invalid_temporal_order"] == 1
    assert report.f3_eligible_records == 0


def test_conflicting_duration_is_reported_and_excluded():
    session = memory_session()
    session.add(
        Task(
            user_id=1,
            title="legacy conflict",
            task_type="focus",
            priority=3,
            estimated_duration=60.0,
            created_at=BASE,
            start_time=BASE + timedelta(minutes=5),
            end_time=BASE + timedelta(minutes=65),
            actual_duration=30.0,
            completed=True,
            lifecycle_state="completed",
            outcome_valid=True,
        )
    )
    session.commit()

    report = TaskCollectionReporter(session).report()

    assert report.invalid_duration_records == 1
    assert report.lifecycle_issue_counts["actual_duration_conflict"] == 1
    assert report.f3_eligible_records == 0


def test_valid_completed_task_reaches_f3_without_outcome_feature_leakage():
    session = memory_session()
    service = TaskLifecycleService(session)
    complete_task(service, actual_minutes=90.0, estimate=60.0)

    extraction = TaskDataExtractor(session).extract(user_id=1)
    row = extraction.dataset_build.rows[0]

    assert row.target["duration_ratio"] == 1.5
    forbidden = {"actual_duration", "actual_duration_minutes", "completed", "end_time", "completion_time"}
    assert forbidden.isdisjoint(set(row.features))
    assert "private validation task" not in str(row.to_dict())


def test_future_completed_task_does_not_influence_earlier_history():
    session = memory_session()
    service = TaskLifecycleService(session)
    complete_task(service, actual_minutes=120.0, created_offset=0, start_offset=5)
    complete_task(service, actual_minutes=30.0, created_offset=20, start_offset=25)
    complete_task(service, actual_minutes=60.0, created_offset=180, start_offset=185)

    rows = {row.task_id: row for row in TaskDataExtractor(session).extract(user_id=1).dataset_build.rows}

    assert rows["2"].features["prior_completed_task_count"] == 0
    assert rows["3"].features["prior_completed_task_count"] == 2


def test_multiple_users_and_task_types_are_reported_separately():
    session = memory_session()
    service = TaskLifecycleService(session)
    complete_task(service, user_id=1, task_type="focus")
    complete_task(service, user_id=2, task_type="admin", created_offset=120, start_offset=125)

    report = TaskCollectionReporter(session).report()

    assert report.users_represented == ("1", "2")
    assert report.task_types_represented == ("admin", "focus")
    assert report.f3_dataset_rows == 2


def test_collection_report_is_deterministic_for_repeated_reads():
    session = memory_session()
    service = TaskLifecycleService(session)
    complete_task(service)

    first = TaskCollectionReporter(session).report().to_dict()
    second = TaskCollectionReporter(session).report().to_dict()

    assert first == second


def test_collection_status_api_uses_actual_lifecycle_flow_with_isolated_database():
    session = memory_session()

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/v1/tasks",
            json={
                "user_id": 1,
                "title": "private api validation task",
                "task_type": "focus",
                "priority": 3,
                "estimated_duration": 60.0,
                "created_at": BASE.isoformat(),
            },
        )
        task_id = create_response.json()["result"]["task"]["id"]
        assert create_response.status_code == 200

        start_response = client.post(
            f"/api/v1/tasks/{task_id}/start",
            json={"user_id": 1, "started_at": (BASE + timedelta(minutes=5)).isoformat()},
        )
        assert start_response.status_code == 200

        complete_response = client.post(
            f"/api/v1/tasks/{task_id}/complete",
            json={"user_id": 1, "completed_at": (BASE + timedelta(minutes=65)).isoformat()},
        )
        assert complete_response.status_code == 200

        status_response = client.get("/api/v1/tasks/data-collection/status?user_id=1")
        readiness_response = client.get("/api/v1/tasks/ml-dataset/readiness?user_id=1")
        status_report = status_response.json()["result"]["collection_report"]
        readiness_result = readiness_response.json()["result"]

        assert status_response.status_code == 200
        assert readiness_response.status_code == 200
        assert status_report["lifecycle_valid_records"] == 1
        assert status_report["f3_dataset_rows"] == 1
        assert readiness_result["adapter_report"]["dataset_row_count"] == 1
        assert readiness_result["collection_report"]["f3_dataset_rows"] == 1
    finally:
        app.dependency_overrides.clear()


def test_api_rejects_invalid_lifecycle_transition_without_dataset_row():
    session = memory_session()

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/v1/tasks",
            json={
                "user_id": 1,
                "title": "private api validation task",
                "task_type": "focus",
                "priority": 3,
                "estimated_duration": 60.0,
                "created_at": BASE.isoformat(),
            },
        )
        task_id = create_response.json()["result"]["task"]["id"]
        complete_response = client.post(
            f"/api/v1/tasks/{task_id}/complete",
            json={"user_id": 1, "completed_at": (BASE + timedelta(minutes=65)).isoformat()},
        )
        report = TaskCollectionReporter(session).report(user_id=1)

        assert complete_response.status_code == 400
        assert report.f3_dataset_rows == 0
    finally:
        app.dependency_overrides.clear()


def test_collection_report_does_not_use_behavior_data_fields():
    session = memory_session()
    service = TaskLifecycleService(session)
    task = complete_task(service)
    session.add(
        _BehaviorData(
            user_id=1,
            task_id=task.id,
            hour_of_day=9,
            task_type="focus",
            duration=999.0,
            focus_score=1.0,
            energy_level=1.0,
            completion_time=999.0,
            productivity_score=999.0,
        )
    )
    session.commit()

    row = TaskDataExtractor(session).extract(user_id=1).dataset_build.rows[0]

    assert row.target["duration_ratio"] == 1.0
    assert "productivity_score" not in row.features
    assert "duration" not in row.features
