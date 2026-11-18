from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.learning.autonomous_learning import (
    AutomaticLearningCoordinator,
    LearningState,
    reset_learning_coordinator,
)
from backend.app.ml.model_registry import InMemoryModelStore, ModelRegistry, ModelStatus
from backend.app.ml.readiness import MINIMUM_TRAINING_ROWS
from backend.app.ml.training_controller import (
    TrainingController,
    TrainingJobStatus,
    TrainingJobType,
)
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.models.auth import User
from backend.app.services.task_lifecycle_service import (
    TaskLifecycleService,
    clear_task_event_listeners,
    ensure_task_lifecycle_schema,
)


@pytest.fixture
def session_factory(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"timeout": 30.0},
    )
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine)
    seed_session = SessionFactory()
    ensure_task_lifecycle_schema(seed_session)

    # Seed users
    now = datetime.now(timezone.utc)
    u1 = User(id=1, email="u1@example.com", password_hash="pw", is_active=True, created_at=now)
    u2 = User(id=2, email="u2@example.com", password_hash="pw", is_active=True, created_at=now)
    seed_session.add_all([u1, u2])
    seed_session.commit()
    seed_session.close()

    return SessionFactory


@pytest.fixture
def test_setup(tmp_path, session_factory):
    clear_task_event_listeners()
    reset_learning_coordinator()

    registry = ModelRegistry(store=InMemoryModelStore())
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    controller = TrainingController(
        registry=registry,
        artifacts_dir=artifacts_dir,
    )

    coordinator = AutomaticLearningCoordinator(
        training_controller=controller,
        db_session_factory=session_factory,
    )
    coordinator.initialize()

    yield {
        "controller": controller,
        "coordinator": coordinator,
        "session_factory": session_factory,
        "registry": registry,
        "artifacts_dir": artifacts_dir,
    }

    clear_task_event_listeners()
    reset_learning_coordinator()


def _create_and_complete_task(
    service: TaskLifecycleService,
    user_id: int,
    idx: int,
    duration: float = 30.0,
    feedback: bool = False,
):
    base_time = datetime(2026, 11, 1, 10, 0, 0) + timedelta(hours=idx)
    t = service.create_task(
        user_id=user_id,
        title=f"Task {idx}",
        task_type="coding",
        priority=3,
        estimated_duration=duration,
        created_at=base_time,
    )
    start_time = base_time + timedelta(minutes=5)
    end_time = start_time + timedelta(minutes=duration)
    service.start_task(task_id=t.id, user_id=user_id, started_at=start_time)

    if feedback:
        return service.complete_task(
            task_id=t.id,
            user_id=user_id,
            completed_at=end_time,
            actual_duration=duration,
            focus_rating=4.0,
            energy_rating=4.0,
            productivity_rating=5.0,
        )
    return service.complete_task(
        task_id=t.id,
        user_id=user_id,
        completed_at=end_time,
        actual_duration=duration,
    )


def test_task_completion_triggers_automatic_readiness_check(test_setup):
    """When a task is completed, an event is dispatched and the coordinator runs readiness check."""
    session = test_setup["session_factory"]()
    coordinator = test_setup["coordinator"]
    service = TaskLifecycleService(session)

    try:
        task = _create_and_complete_task(service, user_id=1, idx=0, duration=25.0)

        time.sleep(0.5)

        status = coordinator.get_learning_status(user_id=1)
        assert status["learning_mode"] == "automatic"
        assert status["last_event"] is not None
        assert status["last_event"]["event_name"] == "task_completed"
        assert status["last_event"]["task_id"] == task.id
        assert status["last_event"]["user_id"] == 1
        assert status["current_state"] in ("waiting_for_sufficient_data", "idle")
        assert "Waiting for training threshold" in (status["last_verdict"] or "")
    finally:
        session.close()


def test_feedback_event_triggers_automatic_readiness_check(test_setup):
    """Submitting feedback dispatches feedback_recorded and checks productivity readiness."""
    session = test_setup["session_factory"]()
    coordinator = test_setup["coordinator"]
    service = TaskLifecycleService(session)

    try:
        task = _create_and_complete_task(service, user_id=1, idx=1, duration=30.0)

        service.record_feedback(
            task_id=task.id,
            user_id=1,
            focus_rating=4.0,
            energy_rating=4.0,
            productivity_rating=5.0,
        )

        time.sleep(0.5)

        status = coordinator.get_learning_status(user_id=1)
        assert status["last_event"] is not None
        assert status["last_event"]["event_name"] == "feedback_recorded"
        assert status["last_event"]["user_id"] == 1
    finally:
        session.close()


def test_no_training_below_readiness_threshold(test_setup):
    """Below 10 eligible samples, no training job is queued and status honestly reflects waiting."""
    session = test_setup["session_factory"]()
    coordinator = test_setup["coordinator"]
    controller = test_setup["controller"]
    service = TaskLifecycleService(session)

    try:
        for i in range(3):
            _create_and_complete_task(service, user_id=1, idx=i, duration=20.0 + i)

        time.sleep(0.5)

        assert len(controller._history) == 0
        assert controller._active_job is None
        status = coordinator.get_learning_status(user_id=1)
        assert status["current_state"] == "waiting_for_sufficient_data"
    finally:
        session.close()


def test_automatic_training_triggered_when_threshold_reached(test_setup):
    """When valid tasks reach the training threshold, training is automatically launched asynchronously."""
    session = test_setup["session_factory"]()
    coordinator = test_setup["coordinator"]
    controller = test_setup["controller"]
    service = TaskLifecycleService(session)

    try:
        # Create 15 completed tasks so chronological train partition reaches >= 10
        for i in range(15):
            _create_and_complete_task(service, user_id=1, idx=i, duration=25.0 + (i % 5))

        # Wait for the automatic background training to complete
        for _ in range(40):
            time.sleep(0.2)
            if len(controller._history) > 0:
                break

        assert len(controller._history) >= 1
        last_job = controller._history[-1]
        assert last_job.job_type == TrainingJobType.PERSONALIZED
        assert "automatic_continuous_learning_user_1" in last_job.triggered_by
        assert last_job.result_summary["personalized"]["status"] == "TRAINED"
    finally:
        session.close()


def test_training_deduplication_skips_identical_fingerprint(test_setup):
    """Repeated events on the same data state do not trigger duplicate training."""
    session = test_setup["session_factory"]()
    coordinator = test_setup["coordinator"]
    controller = test_setup["controller"]
    service = TaskLifecycleService(session)

    try:
        for i in range(15):
            _create_and_complete_task(service, user_id=1, idx=i, duration=30.0)

        for _ in range(40):
            time.sleep(0.2)
            if len(controller._history) > 0:
                break

        initial_job_count = len(controller._history)
        assert initial_job_count >= 1

        # Simulate another event on the same user without adding new data
        coordinator.on_task_event("task_completed", 999, 1)
        time.sleep(0.5)

        # Job count must not increase
        assert len(controller._history) == initial_job_count
        status = coordinator.get_learning_status(user_id=1)
        assert "already trained" in (status["last_verdict"] or "")
    finally:
        session.close()


def test_user_isolation_in_automatic_learning(test_setup):
    """Events for user 1 do not assess or train models for user 2."""
    session = test_setup["session_factory"]()
    coordinator = test_setup["coordinator"]
    controller = test_setup["controller"]
    service = TaskLifecycleService(session)

    try:
        for i in range(10):
            _create_and_complete_task(service, user_id=1, idx=i, duration=30.0)

        for _ in range(30):
            time.sleep(0.2)
            if len(controller._history) > 0:
                break

        # User 2 status must remain 0 samples and waiting
        u2_status = coordinator.get_learning_status(user_id=2)
        assert u2_status["per_model_readiness"]["DurationRatioModel"]["eligible_samples"] == 0
        assert u2_status["per_model_readiness"]["DurationRatioModel"]["ready"] is False
    finally:
        session.close()


def test_stale_job_recovery(test_setup):
    """Stale jobs left in RUNNING or QUEUED are safely recovered on startup."""
    controller = test_setup["controller"]

    from backend.app.ml.training_controller import TrainingJobRecord
    stale_job = TrainingJobRecord(
        job_id="stale-123",
        job_type=TrainingJobType.PERSONALIZED,
        status=TrainingJobStatus.RUNNING,
        triggered_by="crashed_process",
    )
    controller._active_job = stale_job

    recovered_count = controller.recover_stale_jobs()
    assert recovered_count == 1
    assert stale_job.status == TrainingJobStatus.FAILED
    assert "interrupted" in (stale_job.error_message or "")
    assert controller._active_job is None
