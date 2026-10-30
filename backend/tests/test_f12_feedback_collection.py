from __future__ import annotations

from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.task_lifecycle_service import (
    TaskLifecycleService,
    ensure_task_lifecycle_schema,
)
from backend.app.ml.readiness import (
    assess_full_ml_system_readiness,
    assess_productivity_model_readiness,
    assess_duration_model_readiness,
    NOT_READY_NO_GROUND_TRUTH_LABELS,
    NOT_READY_INSUFFICIENT_DATA,
    READY_FOR_TRAINING,
)


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ensure_task_lifecycle_schema(session)
    yield session
    session.close()


def test_valid_feedback_recording(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 11, 10, 0, 0)

    task = service.create_task(
        user_id=1,
        title="Deep Neural Optimization",
        task_type="coding",
        priority=4,
        estimated_duration=90.0,
        estimated_duration_unit="minutes",
        created_at=now,
    )
    service.start_task(task_id=task.id, user_id=1, started_at=now + timedelta(minutes=5))
    service.complete_task(task_id=task.id, user_id=1, completed_at=now + timedelta(minutes=95))

    updated = service.record_feedback(
        task_id=task.id,
        user_id=1,
        focus_rating=4.5,
        energy_rating=4.0,
        productivity_rating=5.0,
        feedback_notes="Excellent uninterrupted focus block.",
        submitted_at=now + timedelta(minutes=96),
    )

    assert updated.focus_rating == 4.5
    assert updated.energy_rating == 4.0
    assert updated.productivity_rating == 5.0
    assert updated.feedback_notes == "Excellent uninterrupted focus block."
    assert updated.feedback_submitted_at == now + timedelta(minutes=96)


def test_invalid_ratings_rejected(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 11, 10, 0, 0)

    task = service.create_task(
        user_id=1,
        title="Testing Validation",
        task_type="admin",
        priority=2,
        estimated_duration=30.0,
        created_at=now,
    )
    service.start_task(task_id=task.id, user_id=1, started_at=now)
    service.complete_task(task_id=task.id, user_id=1, completed_at=now + timedelta(minutes=30))

    # Reject rating < 1.0
    with pytest.raises(ValueError, match="focus_rating must be between 1.0 and 5.0"):
        service.record_feedback(
            task_id=task.id,
            user_id=1,
            focus_rating=0.5,
            energy_rating=3.0,
            productivity_rating=3.0,
        )

    # Reject rating > 5.0
    with pytest.raises(ValueError, match="productivity_rating must be between 1.0 and 5.0"):
        service.record_feedback(
            task_id=task.id,
            user_id=1,
            focus_rating=4.0,
            energy_rating=3.0,
            productivity_rating=5.5,
        )

    # Reject non-numeric rating
    with pytest.raises(ValueError, match="energy_rating must be numeric"):
        service.record_feedback(
            task_id=task.id,
            user_id=1,
            focus_rating=4.0,
            energy_rating=True,  # bool should be rejected
            productivity_rating=4.0,
        )


def test_feedback_requires_completed_task(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 11, 10, 0, 0)

    task = service.create_task(
        user_id=1,
        title="Unfinished Task",
        task_type="writing",
        priority=3,
        estimated_duration=45.0,
        created_at=now,
    )

    with pytest.raises(ValueError, match="Feedback can only be recorded for completed tasks"):
        service.record_feedback(
            task_id=task.id,
            user_id=1,
            focus_rating=3.0,
            energy_rating=3.0,
            productivity_rating=3.0,
        )


def test_user_isolation_for_feedback(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 11, 10, 0, 0)

    # User 1 creates and completes task
    task = service.create_task(
        user_id=1,
        title="User 1 Task",
        task_type="coding",
        priority=3,
        estimated_duration=60.0,
        created_at=now,
    )
    service.start_task(task_id=task.id, user_id=1, started_at=now)
    service.complete_task(task_id=task.id, user_id=1, completed_at=now + timedelta(minutes=60))

    # User 2 attempts to submit feedback for User 1's task
    with pytest.raises(ValueError, match="task not found"):
        service.record_feedback(
            task_id=task.id,
            user_id=2,  # different user
            focus_rating=4.0,
            energy_rating=4.0,
            productivity_rating=4.0,
        )


def test_duplicate_feedback_updates_cleanly(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 11, 10, 0, 0)

    task = service.create_task(
        user_id=1,
        title="Re-rate Task",
        task_type="research",
        priority=3,
        estimated_duration=45.0,
        created_at=now,
    )
    service.start_task(task_id=task.id, user_id=1, started_at=now)
    service.complete_task(task_id=task.id, user_id=1, completed_at=now + timedelta(minutes=45))

    # Initial rating
    service.record_feedback(
        task_id=task.id,
        user_id=1,
        focus_rating=3.0,
        energy_rating=3.0,
        productivity_rating=3.0,
        feedback_notes="Average session",
    )

    # User updates their rating later
    updated = service.record_feedback(
        task_id=task.id,
        user_id=1,
        focus_rating=4.0,
        energy_rating=3.5,
        productivity_rating=4.5,
        feedback_notes="Realized I accomplished more than I thought",
    )

    assert updated.focus_rating == 4.0
    assert updated.energy_rating == 3.5
    assert updated.productivity_rating == 4.5
    assert updated.feedback_notes == "Realized I accomplished more than I thought"


def test_real_data_integrity_lifecycle_flow(memory_db):
    """
    End-to-End Test (Section 18):
    Complete task -> actual duration recorded -> user enters rating ->
    feedback persisted -> dataset eligibility updates -> readiness reflects the new genuine record.
    """
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 11, 9, 0, 0)

    # Initial state: 0 tasks, no ground truth labels
    initial_readiness = assess_full_ml_system_readiness(memory_db)
    assert initial_readiness.database_task_count == 0
    assert initial_readiness.eligible_dataset_rows == 0
    assert initial_readiness.components["ProductivityModel"].status == "NOT_READY_NO_DATA"

    # 1. Create task with explicit minutes
    task = service.create_task(
        user_id=10,
        title="Real ML Lifecycle Task",
        task_type="coding",
        priority=4,
        estimated_duration=60.0,
        estimated_duration_unit="minutes",
        created_at=now,
    )

    # 2. Start task
    service.start_task(task_id=task.id, user_id=10, started_at=now + timedelta(minutes=5))

    # 3. Complete task -> actual duration recorded
    completed = service.complete_task(
        task_id=task.id,
        user_id=10,
        completed_at=now + timedelta(minutes=75),
        actual_duration=70.0,
    )
    assert completed.actual_duration == 70.0
    assert completed.outcome_valid is True

    # 4. Check readiness BEFORE feedback: Duration has 1 row, Productivity has 0 rated rows
    mid_readiness = assess_full_ml_system_readiness(memory_db, user_id=10)
    assert mid_readiness.eligible_dataset_rows == 1
    assert mid_readiness.components["ProductivityModel"].status == NOT_READY_NO_GROUND_TRUTH_LABELS
    assert mid_readiness.components["ProductivityModel"].eligible_samples == 0

    # 5. User enters genuine rating -> feedback persisted
    rated = service.record_feedback(
        task_id=task.id,
        user_id=10,
        focus_rating=4.5,
        energy_rating=4.0,
        productivity_rating=5.0,
        feedback_notes="Productive flow block",
    )
    assert rated.focus_rating == 4.5
    assert rated.productivity_rating == 5.0

    # 6. Check readiness AFTER feedback: ProductivityModel now reflects 1 genuine user rating!
    final_readiness = assess_full_ml_system_readiness(memory_db, user_id=10)
    assert final_readiness.database_task_count == 1
    assert final_readiness.eligible_dataset_rows == 1
    assert final_readiness.components["ProductivityModel"].eligible_samples == 1
    # Still requires 9 more (10 minimum) - honestly reported!
    assert final_readiness.components["ProductivityModel"].required_samples == 10
    assert final_readiness.components["ProductivityModel"].status in (
        NOT_READY_NO_GROUND_TRUTH_LABELS,
        NOT_READY_INSUFFICIENT_DATA,
    )
