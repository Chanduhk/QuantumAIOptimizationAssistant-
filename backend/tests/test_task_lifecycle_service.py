from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.db import get_db
from backend.app.ml.datasets import TaskDataExtractor
from backend.app.models.base import Base
from backend.app.models.behavior_data import BehaviorData as _BehaviorData
from backend.app.models.task import Task
from backend.app.services.auth_service import CSRF_COOKIE
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


def create_started_task(service: TaskLifecycleService) -> Task:
    task = service.create_task(
        user_id=1,
        title="private validation task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=BASE,
    )
    return service.start_task(task_id=task.id, user_id=1, started_at=BASE + timedelta(minutes=10))


def test_create_task_records_prediction_time_fields_only():
    service = TaskLifecycleService(memory_session())

    task = service.create_task(
        user_id=1,
        title="private validation task",
        task_type="focus",
        priority=4,
        estimated_duration=45.0,
        created_at=BASE,
    )

    assert task.created_at == BASE
    assert task.lifecycle_state == "created"
    assert task.completed is False
    assert task.actual_duration is None
    assert task.end_time is None
    assert task.outcome_valid is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"user_id": 0}, "user_id"),
        ({"title": ""}, "title"),
        ({"task_type": ""}, "task_type"),
        ({"priority": 0}, "priority"),
        ({"priority": 6}, "priority"),
        ({"estimated_duration": 0.0}, "estimated_duration"),
        ({"estimated_duration": -1.0}, "estimated_duration"),
        ({"estimated_duration": float("nan")}, "finite"),
        ({"estimated_duration": float("inf")}, "finite"),
    ],
)
def test_create_task_rejects_invalid_prediction_time_values(kwargs, message):
    service = TaskLifecycleService(memory_session())
    values = {
        "user_id": 1,
        "title": "Task",
        "task_type": "focus",
        "priority": 3,
        "estimated_duration": 60.0,
        "created_at": BASE,
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=message):
        service.create_task(**values)


def test_start_task_records_start_time_and_rejects_duplicate_start():
    service = TaskLifecycleService(memory_session())
    task = service.create_task(
        user_id=1,
        title="Task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=BASE,
    )

    started = service.start_task(task_id=task.id, user_id=1, started_at=BASE + timedelta(minutes=5))

    assert started.start_time == BASE + timedelta(minutes=5)
    assert started.lifecycle_state == "started"
    with pytest.raises(ValueError, match="already been started"):
        service.start_task(task_id=task.id, user_id=1, started_at=BASE + timedelta(minutes=6))


def test_start_before_creation_is_rejected():
    service = TaskLifecycleService(memory_session())
    task = service.create_task(
        user_id=1,
        title="Task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=BASE,
    )

    with pytest.raises(ValueError, match="before created_at"):
        service.start_task(task_id=task.id, user_id=1, started_at=BASE - timedelta(minutes=1))


def test_complete_task_derives_actual_duration_and_sets_outcome_fields():
    session = memory_session()
    service = TaskLifecycleService(session)
    task = create_started_task(service)

    completed = service.complete_task(
        task_id=task.id,
        user_id=1,
        completed_at=BASE + timedelta(minutes=70),
    )

    assert completed.actual_duration == 60.0
    assert completed.end_time == BASE + timedelta(minutes=70)
    assert completed.completed is True
    assert completed.lifecycle_state == "completed"
    assert completed.outcome_valid is True


def test_complete_task_accepts_matching_actual_duration():
    service = TaskLifecycleService(memory_session())
    task = create_started_task(service)

    completed = service.complete_task(
        task_id=task.id,
        user_id=1,
        completed_at=BASE + timedelta(minutes=70),
        actual_duration=60.0,
    )

    assert completed.actual_duration == 60.0


def test_complete_task_rejects_conflicting_actual_duration():
    service = TaskLifecycleService(memory_session())
    task = create_started_task(service)

    with pytest.raises(ValueError, match="conflicts"):
        service.complete_task(
            task_id=task.id,
            user_id=1,
            completed_at=BASE + timedelta(minutes=70),
            actual_duration=59.0,
        )


def test_complete_before_start_is_rejected():
    service = TaskLifecycleService(memory_session())
    task = service.create_task(
        user_id=1,
        title="Task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=BASE,
    )

    with pytest.raises(ValueError, match="started before completion"):
        service.complete_task(task_id=task.id, user_id=1, completed_at=BASE + timedelta(minutes=10))


def test_complete_at_or_before_start_time_is_rejected():
    service = TaskLifecycleService(memory_session())
    task = create_started_task(service)

    with pytest.raises(ValueError, match="after start_time"):
        service.complete_task(task_id=task.id, user_id=1, completed_at=BASE + timedelta(minutes=10))


def test_duplicate_completion_is_rejected():
    service = TaskLifecycleService(memory_session())
    task = create_started_task(service)
    service.complete_task(task_id=task.id, user_id=1, completed_at=BASE + timedelta(minutes=70))

    with pytest.raises(ValueError, match="already been completed"):
        service.complete_task(task_id=task.id, user_id=1, completed_at=BASE + timedelta(minutes=80))


def test_timezone_aware_timestamps_are_normalized_to_utc_naive():
    service = TaskLifecycleService(memory_session())
    aware = datetime(2026, 1, 1, 14, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    task = service.create_task(
        user_id=1,
        title="Task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=aware,
    )

    assert task.created_at == BASE
    assert task.created_at.tzinfo is None


def test_created_started_completed_flow_is_f42_compatible():
    session = memory_session()
    service = TaskLifecycleService(session)
    task = create_started_task(service)
    service.complete_task(task_id=task.id, user_id=1, completed_at=BASE + timedelta(minutes=70))

    extraction = TaskDataExtractor(session).extract(user_id=1)
    row = extraction.dataset_build.rows[0]

    assert extraction.report.eligible_records == 1
    assert row.prediction_timestamp == BASE
    assert row.features["time_since_task_created_minutes"] == 0.0
    assert row.target["duration_ratio"] == 1.0
    assert "actual_duration" not in row.features
    assert "completed" not in row.features


def test_incomplete_task_is_not_dataset_eligible():
    session = memory_session()
    service = TaskLifecycleService(session)
    service.create_task(
        user_id=1,
        title="Task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=BASE,
    )

    extraction = TaskDataExtractor(session).extract(user_id=1)

    assert extraction.report.eligible_records == 0
    assert extraction.dataset_build.rows == ()
    assert any("task.start_time must be a datetime" in reason for reason in extraction.report.rejection_reason_counts)


def test_multiple_users_are_isolated_for_extraction():
    session = memory_session()
    service = TaskLifecycleService(session)
    first = create_started_task(service)
    service.complete_task(task_id=first.id, user_id=1, completed_at=BASE + timedelta(minutes=70))
    second = service.create_task(
        user_id=2,
        title="Task",
        task_type="admin",
        priority=2,
        estimated_duration=30.0,
        created_at=BASE,
    )
    service.start_task(task_id=second.id, user_id=2, started_at=BASE + timedelta(minutes=5))
    service.complete_task(task_id=second.id, user_id=2, completed_at=BASE + timedelta(minutes=35))

    extraction = TaskDataExtractor(session).extract(user_id=2)

    assert extraction.report.users_represented == ("2",)
    assert len(extraction.dataset_build.rows) == 1
    assert extraction.dataset_build.rows[0].user_id == "2"


def test_lifecycle_flow_is_deterministic_with_explicit_timestamps():
    session = memory_session()
    service = TaskLifecycleService(session)
    task = create_started_task(service)
    service.complete_task(task_id=task.id, user_id=1, completed_at=BASE + timedelta(minutes=70))

    first = TaskDataExtractor(session).extract(user_id=1)
    second = TaskDataExtractor(session).extract(user_id=1)

    assert first.signature() == second.signature()


def test_service_rejects_missing_task_and_wrong_user():
    service = TaskLifecycleService(memory_session())

    with pytest.raises(ValueError, match="task not found"):
        service.get_task(task_id=1)

    task = service.create_task(
        user_id=1,
        title="Task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=BASE,
    )
    with pytest.raises(ValueError, match="task not found"):
        service.start_task(task_id=task.id, user_id=2, started_at=BASE)


def test_old_schema_is_extended_without_resetting_existing_rows():
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE tasks ("
                "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title VARCHAR(255) NOT NULL, "
                "task_type VARCHAR(100) NOT NULL, priority INTEGER NOT NULL, "
                "estimated_duration FLOAT, actual_duration FLOAT, start_time DATETIME, "
                "end_time DATETIME, completed BOOLEAN NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks (id, user_id, title, task_type, priority, estimated_duration, completed) "
                "VALUES (1, 1, 'existing', 'focus', 3, 60.0, 0)"
            )
        )
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = Session()

    TaskLifecycleService(session)
    columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
    count = session.execute(text("SELECT COUNT(*) FROM tasks")).scalar_one()

    assert {"created_at", "lifecycle_state", "outcome_valid", "estimated_duration_unit", "estimated_duration_source"}.issubset(columns)
    assert count == 1
    legacy = session.execute(text("SELECT estimated_duration_unit, estimated_duration_source FROM tasks WHERE id = 1")).one()
    assert legacy == (None, None)


def test_api_lifecycle_flow_uses_isolated_test_database():
    session = memory_session()

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": "lifecycle-test@example.com", "password": "test-only password 123"},
        )
        assert registration.status_code == 201
        user_id = registration.json()["user"]["id"]
        assert client.get("/api/v1/auth/me").json()["id"] == user_id

        csrf_token = client.cookies.get(CSRF_COOKIE)
        assert csrf_token
        headers = {"X-CSRF-Token": csrf_token}

        create_response = client.post(
            "/api/v1/tasks",
            headers=headers,
            json={
                "user_id": user_id,
                "title": "private api task",
                "task_type": "focus",
                "priority": 3,
                "estimated_duration": 60.0,
                "created_at": BASE.isoformat(),
            },
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["result"]["task"]["id"]

        start_response = client.post(
            f"/api/v1/tasks/{task_id}/start",
            headers=headers,
            json={"started_at": (BASE + timedelta(minutes=5)).isoformat()},
        )
        assert start_response.status_code == 200

        # Duplicate start on already-started task returns 409 conflict
        dup_start = client.post(
            f"/api/v1/tasks/{task_id}/start",
            headers=headers,
            json={"started_at": (BASE + timedelta(minutes=6)).isoformat()},
        )
        assert dup_start.status_code == 409
        assert "already been started" in dup_start.json()["detail"]

        complete_response = client.post(
            f"/api/v1/tasks/{task_id}/complete",
            headers=headers,
            json={"completed_at": (BASE + timedelta(minutes=65)).isoformat()},
        )
        assert complete_response.status_code == 200
        completed_task = complete_response.json()["result"]["task"]
        assert completed_task["completed"] is True
        assert completed_task["actual_duration"] == 60.0

        readiness = client.get(f"/api/v1/tasks/ml-dataset/readiness?user_id={user_id}")
        assert readiness.status_code == 200
        report = readiness.json()["result"]["adapter_report"]
        assert report["eligible_records"] == 1
        assert report["dataset_row_count"] == 1

        # Starting an already-completed task returns 409 conflict
        comp_start = client.post(
            f"/api/v1/tasks/{task_id}/start",
            headers=headers,
            json={"started_at": (BASE + timedelta(minutes=70)).isoformat()},
        )
        assert comp_start.status_code == 409
        assert "completed task cannot be started" in comp_start.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_serialize_task_normalizes_effective_lifecycle_state():
    session = memory_session()
    service = TaskLifecycleService(session=session, clock=lambda: BASE)
    task = service.create_task(
        user_id=1,
        title="Sample Task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=BASE,
    )

    # Initially created
    serialized = service.serialize_task(task)
    assert serialized["lifecycle_state"] == "created"

    # Even if lifecycle_state is manually 'created', if start_time is set, serialize returns 'started'
    task.start_time = BASE + timedelta(minutes=10)
    task.lifecycle_state = "created"
    serialized_started = service.serialize_task(task)
    assert serialized_started["lifecycle_state"] == "started"

    # If completed is True, serialize returns 'completed'
    task.completed = True
    serialized_completed = service.serialize_task(task)
    assert serialized_completed["lifecycle_state"] == "completed"


def test_get_all_tasks_and_get_task_self_heals_inconsistent_lifecycle_state():
    session = memory_session()
    service = TaskLifecycleService(session=session, clock=lambda: BASE)
    task = service.create_task(
        user_id=1,
        title="Sample Task",
        task_type="focus",
        priority=3,
        estimated_duration=60.0,
        created_at=BASE,
    )

    # Simulate inconsistent DB row from proposal scheduling
    task.start_time = BASE + timedelta(hours=1)
    task.end_time = BASE + timedelta(hours=2)
    task.lifecycle_state = "created"
    session.commit()

    # get_task self-heals
    fetched = service.get_task(task_id=task.id)
    assert fetched.lifecycle_state == "started"

    # get_all_tasks self-heals
    tasks = service.get_all_tasks(user_id=1)
    assert tasks[0].lifecycle_state == "started"
