from __future__ import annotations

from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.ai_models.productivity_model import ProductivityModel
from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.ml.datasets.builder import DurationDatasetBuilder
from backend.app.ml.datasets.leakage import LeakageGuard
from backend.app.ml.datasets.models import DatasetRow
from backend.app.ml.datasets.splitter import DatasetSplit, TemporalDatasetSplitter
from backend.app.ml.duration_model import (
    FEATURE_NAMES,
    DurationRatioBaselineRegressor,
    EvaluationReport,
)
from backend.app.ml.model_registry import InMemoryModelStore, ModelRegistry, ModelStatus
from backend.app.ml.readiness import (
    NOT_READY_INSUFFICIENT_DATA,
    NOT_READY_INSUFFICIENT_EPISODES,
    NOT_READY_NO_DATA,
    NOT_READY_NO_GROUND_TRUTH_LABELS,
    READY_FOR_TRAINING,
    assess_duration_model_readiness,
    assess_full_ml_system_readiness,
    assess_productivity_model_readiness,
    assess_rl_scheduler_readiness,
)
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.task_lifecycle_service import TaskLifecycleService, ensure_task_lifecycle_schema


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_task_lifecycle_schema_for_bind = None
    from backend.app.services.task_lifecycle_service import ensure_task_lifecycle_schema
    Session = sessionmaker(bind=engine)
    session = Session()
    ensure_task_lifecycle_schema(session)
    yield session
    session.close()


def test_user_feedback_collection_on_task_completion(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 8, 10, 0, 0)

    task = service.create_task(
        user_id=1,
        title="Deep Work",
        task_type="coding",
        priority=4,
        estimated_duration=60.0,
        estimated_duration_unit="minutes",
        created_at=now,
    )

    service.start_task(task_id=task.id, started_at=now + timedelta(minutes=5))

    completed = service.complete_task(
        task_id=task.id,
        completed_at=now + timedelta(minutes=65),
        actual_duration=60.0,
        focus_rating=4.5,
        energy_rating=4.0,
        productivity_rating=5.0,
        feedback_notes="Felt highly productive and uninterrupted.",
    )

    assert completed.completed is True
    assert completed.focus_rating == 4.5
    assert completed.energy_rating == 4.0
    assert completed.productivity_rating == 5.0
    assert completed.feedback_notes == "Felt highly productive and uninterrupted."
    assert completed.feedback_submitted_at is not None

    serialized = service.serialize_task(completed)
    assert serialized["focus_rating"] == 4.5
    assert serialized["productivity_rating"] == 5.0


def test_record_feedback_post_completion(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 8, 10, 0, 0)

    task = service.create_task(
        user_id=1,
        title="Admin Work",
        task_type="admin",
        priority=2,
        estimated_duration=30.0,
        estimated_duration_unit="minutes",
        created_at=now,
    )
    service.start_task(task_id=task.id, started_at=now + timedelta(minutes=2))
    service.complete_task(task_id=task.id, completed_at=now + timedelta(minutes=32))

    updated = service.record_feedback(
        task_id=task.id,
        focus_rating=3.0,
        energy_rating=2.5,
        productivity_rating=3.5,
        feedback_notes="A bit sluggish after lunch.",
    )

    assert updated.focus_rating == 3.0
    assert updated.energy_rating == 2.5
    assert updated.productivity_rating == 3.5


def test_feedback_rating_bounds_validation(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 8, 10, 0, 0)

    task = service.create_task(
        user_id=1,
        title="Writing",
        task_type="writing",
        priority=3,
        estimated_duration=45.0,
        created_at=now,
    )
    service.start_task(task_id=task.id, started_at=now)
    service.complete_task(task_id=task.id, completed_at=now + timedelta(minutes=45))

    with pytest.raises(ValueError, match="focus_rating must be between 1.0 and 5.0"):
        service.record_feedback(
            task_id=task.id,
            focus_rating=6.0,
            energy_rating=3.0,
            productivity_rating=4.0,
        )

    with pytest.raises(ValueError, match="productivity_rating must be between 1.0 and 5.0"):
        service.record_feedback(
            task_id=task.id,
            focus_rating=4.0,
            energy_rating=3.0,
            productivity_rating=0.5,
        )


def test_feedback_rejected_on_incomplete_task(memory_db):
    service = TaskLifecycleService(memory_db)
    task = service.create_task(
        user_id=1,
        title="Incomplete",
        task_type="writing",
        priority=3,
        estimated_duration=45.0,
    )

    with pytest.raises(ValueError, match="Feedback can only be recorded for completed tasks"):
        service.record_feedback(
            task_id=task.id,
            focus_rating=4.0,
            energy_rating=4.0,
            productivity_rating=4.0,
        )


def test_ml_readiness_assessment_empty_database(memory_db):
    report = assess_full_ml_system_readiness(memory_db)
    assert report.database_task_count == 0
    assert report.eligible_dataset_rows == 0
    assert report.components["DurationRatioModel"].status == NOT_READY_NO_DATA
    assert report.components["ProductivityModel"].status == NOT_READY_NO_DATA
    assert report.components["RLScheduler"].status == NOT_READY_INSUFFICIENT_EPISODES


def test_ml_readiness_insufficient_data_and_heuristic_proxy(memory_db):
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 8, 10, 0, 0)
    task = service.create_task(
        user_id=1,
        title="Task 1",
        task_type="coding",
        priority=4,
        estimated_duration=60.0,
        estimated_duration_unit="minutes",
        created_at=now,
    )
    service.start_task(task_id=task.id, started_at=now)
    service.complete_task(task_id=task.id, completed_at=now + timedelta(minutes=60))

    report = assess_full_ml_system_readiness(memory_db)
    assert report.database_task_count == 1
    assert report.eligible_dataset_rows == 1
    assert report.components["DurationRatioModel"].status == NOT_READY_INSUFFICIENT_DATA
    assert report.components["ProductivityModel"].status == NOT_READY_NO_GROUND_TRUTH_LABELS
    assert report.components["RLScheduler"].status == NOT_READY_INSUFFICIENT_EPISODES


def test_duration_model_refuses_training_on_insufficient_samples():
    regressor = DurationRatioBaselineRegressor()
    empty_split = DatasetSplit(train=(), validation=(), test=())

    with pytest.raises(ValueError, match="Cannot train duration model: 0 training rows is below"):
        regressor.train_on_split(empty_split)


def test_duration_model_training_and_evaluation_on_synthetic_split():
    base_time = datetime(2026, 10, 1, 9, 0, 0)
    train_rows = []
    for i in range(12):
        row = DatasetRow(
            example_id=f"train-{i}",
            task_id=f"t-{i}",
            user_id="1",
            prediction_timestamp=base_time + timedelta(hours=i),
            features={
                "estimated_duration_minutes": 60.0 + (i * 5),
                "priority": (i % 5) + 1,
                "task_type": "coding" if i % 2 == 0 else "research",
                "prediction_hour": 9 + (i % 8),
                "prediction_day_of_week": (i % 7),
                "time_since_task_created_minutes": 10.0,
                "scheduled_start_hour": 9 + (i % 8),
                "hours_until_scheduled_start": 0.5,
                "prior_completed_task_count": i,
                "prior_duration_ratio_mean": 1.05,
                "prior_duration_ratio_median": 1.0,
                "prior_same_type_duration_ratio_mean": 1.02,
            },
            target={"duration_ratio": 1.0 + (0.05 * (i % 3))},
            provenance={"label_source": "test"},
            dataset_version="v0.1",
            schema_version="v0.1",
            feature_version="v0.1",
            label_version="v0.1",
        )
        train_rows.append(row)

    val_rows = [
        DatasetRow(
            example_id="val-1",
            task_id="t-val",
            user_id="1",
            prediction_timestamp=base_time + timedelta(hours=20),
            features=train_rows[0].features,
            target={"duration_ratio": 1.1},
            provenance={"label_source": "test"},
            dataset_version="v0.1",
            schema_version="v0.1",
            feature_version="v0.1",
            label_version="v0.1",
        )
    ]

    split = DatasetSplit(train=tuple(train_rows), validation=tuple(val_rows), test=())
    regressor = DurationRatioBaselineRegressor()
    report = regressor.train_on_split(split)

    assert regressor.is_trained is True
    assert isinstance(report, EvaluationReport)
    assert report.sample_count == 1
    assert report.train_sample_count == 12
    assert report.feature_count == 12
    assert report.mae >= 0.0
    assert report.rmse >= 0.0
    assert regressor.metadata is not None
    assert regressor.metadata["train_sample_count"] == 12


def test_model_registry_blocks_synthetic_and_demo_model_promotion():
    store = InMemoryModelStore()
    registry = ModelRegistry(store=store)

    fake_model = object()
    staging_meta = registry.register_model(
        model_name="productivity_model",
        model_object=fake_model,
        metrics={
            "accuracy_score": 0.85,
            "demo_only": True,
            "no_real_training_samples_available": True,
        },
    )

    with pytest.raises(ValueError, match="Model trained on synthetic or demo data cannot be promoted"):
        registry.promote_model("productivity_model", staging_meta.version)


def test_model_registry_blocks_negative_score_promotion():
    store = InMemoryModelStore()
    registry = ModelRegistry(store=store)

    fake_model = object()
    staging_meta = registry.register_model(
        model_name="duration_model",
        model_object=fake_model,
        metrics={"accuracy_score": -0.2},
    )

    with pytest.raises(ValueError, match="Model with negative accuracy/validation score cannot be promoted"):
        registry.promote_model("duration_model", staging_meta.version)


def test_productivity_and_rl_models_expose_unready_status():
    prod_model = ProductivityModel()
    assert prod_model.readiness_status == NOT_READY_NO_GROUND_TRUTH_LABELS

    rl_scheduler = RLScheduler()
    assert rl_scheduler.readiness_status == NOT_READY_INSUFFICIENT_EPISODES
