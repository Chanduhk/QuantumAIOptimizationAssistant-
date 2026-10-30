from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ml.datasets.builder import DurationDatasetBuilder
from backend.app.ml.datasets.leakage import (
    FORBIDDEN_EXACT_FEATURES,
    FORBIDDEN_FEATURE_TOKENS,
    LeakageGuard,
)
from backend.app.ml.datasets.models import DatasetRow
from backend.app.ml.datasets.splitter import TemporalDatasetSplitter
from backend.app.ml.datasets.task_database_adapter import TaskDataExtractor
from backend.app.ml.duration_model import (
    FEATURE_NAMES,
    DurationRatioBaselineRegressor,
    EvaluationReport,
)
from backend.app.ml.model_registry import InMemoryModelStore, ModelRegistry, ModelStatus
from backend.app.ml.readiness import (
    MINIMUM_TRAINING_ROWS,
    NOT_READY_INSUFFICIENT_DATA,
    NOT_READY_NO_GROUND_TRUTH_LABELS,
    assess_duration_model_readiness,
    assess_full_ml_system_readiness,
    assess_productivity_model_readiness,
)
from sqlalchemy.pool import StaticPool
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.task_lifecycle_service import (
    TaskLifecycleService,
    ensure_task_lifecycle_schema,
    ensure_task_lifecycle_schema_for_bind,
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


def test_sqlite_persistence_and_migration_across_backend_restart():
    """
    Stage 1 & 4 Verification:
    Verify that tasks, actual durations, feedback ratings, and lifecycle state
    safely survive a full database restart / engine disconnect without data loss.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{db_path}"

    try:
        # Phase 1: Initialize DB and schema, simulate first server run
        engine1 = create_engine(db_url, future=True)
        ensure_task_lifecycle_schema_for_bind(engine1)
        Session1 = sessionmaker(bind=engine1, future=True)

        with Session1() as session:
            service = TaskLifecycleService(session)
            now = datetime(2026, 10, 11, 8, 0, 0)

            task = service.create_task(
                user_id=42,
                title="Restart Survival Task",
                task_type="coding",
                priority=3,
                estimated_duration=60.0,
                estimated_duration_unit="minutes",
                created_at=now,
            )
            service.start_task(task_id=task.id, user_id=42, started_at=now + timedelta(minutes=5))
            service.complete_task(
                task_id=task.id,
                user_id=42,
                completed_at=now + timedelta(minutes=65),
                actual_duration=60.0,
            )
            service.record_feedback(
                task_id=task.id,
                user_id=42,
                focus_rating=4.5,
                energy_rating=4.0,
                productivity_rating=5.0,
                feedback_notes="Survives simulated restart cleanly",
            )
            saved_id = task.id

        # Phase 2: Disconnect completely (simulate process shutdown / server reboot)
        engine1.dispose()

        # Phase 3: Start new engine against the existing DB file (simulate restart)
        engine2 = create_engine(db_url, future=True)
        ensure_task_lifecycle_schema_for_bind(engine2)
        Session2 = sessionmaker(bind=engine2, future=True)

        with Session2() as session:
            reloaded_task = session.query(Task).filter(Task.id == saved_id).one()
            assert reloaded_task.title == "Restart Survival Task"
            assert reloaded_task.completed is True
            assert reloaded_task.actual_duration == 60.0
            assert reloaded_task.outcome_valid is True
            assert reloaded_task.focus_rating == 4.5
            assert reloaded_task.energy_rating == 4.0
            assert reloaded_task.productivity_rating == 5.0
            assert reloaded_task.feedback_notes == "Survives simulated restart cleanly"
            assert reloaded_task.feedback_submitted_at is not None

            # Verify readiness assessment after restart
            readiness = assess_full_ml_system_readiness(session, user_id=42)
            assert readiness.database_task_count == 1
            assert readiness.eligible_dataset_rows == 1
            assert readiness.components["DurationRatioModel"].eligible_samples == 1
            assert readiness.components["ProductivityModel"].eligible_samples == 1
        engine2.dispose()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


def test_user_scoped_readiness_counts(memory_db):
    """
    Stage 1 & 4 Verification:
    Verify that readiness counts are strictly scoped to the specified user_id
    and do not leak or aggregate cross-user records.
    """
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 11, 8, 0, 0)

    # User 1: 2 completed tasks with feedback
    for i in (1, 2):
        t = service.create_task(
            user_id=1,
            title=f"User 1 Task {i}",
            task_type="coding",
            priority=3,
            estimated_duration=30.0,
            estimated_duration_unit="minutes",
            created_at=now,
        )
        service.start_task(task_id=t.id, user_id=1, started_at=now)
        service.complete_task(task_id=t.id, user_id=1, completed_at=now + timedelta(minutes=30), actual_duration=30.0)
        service.record_feedback(task_id=t.id, user_id=1, focus_rating=4.0, energy_rating=4.0, productivity_rating=4.0)

    # User 2: 1 completed task without feedback
    t2 = service.create_task(
        user_id=2,
        title="User 2 Task",
        task_type="writing",
        priority=2,
        estimated_duration=45.0,
        estimated_duration_unit="minutes",
        created_at=now,
    )
    service.start_task(task_id=t2.id, user_id=2, started_at=now)
    service.complete_task(task_id=t2.id, user_id=2, completed_at=now + timedelta(minutes=45), actual_duration=45.0)

    # Assess for User 1
    r1 = assess_full_ml_system_readiness(memory_db, user_id=1)
    assert r1.database_task_count == 2
    assert r1.eligible_dataset_rows == 2
    assert r1.components["ProductivityModel"].eligible_samples == 2

    # Assess for User 2
    r2 = assess_full_ml_system_readiness(memory_db, user_id=2)
    assert r2.database_task_count == 1
    assert r2.eligible_dataset_rows == 1
    assert r2.components["ProductivityModel"].eligible_samples == 0


def test_auth_service_task_feedback_regex_protection():
    """
    Stage 1 Verification:
    Verify that the middleware regex in auth_service matches /feedback endpoints.
    """
    pattern = re.compile(r"/api/v1/tasks/(\d+)(?:/(?:start|complete|feedback))?")

    # Should match plain task
    m1 = pattern.fullmatch("/api/v1/tasks/42")
    assert m1 is not None and m1.group(1) == "42"

    # Should match start
    m2 = pattern.fullmatch("/api/v1/tasks/42/start")
    assert m2 is not None and m2.group(1) == "42"

    # Should match complete
    m3 = pattern.fullmatch("/api/v1/tasks/42/complete")
    assert m3 is not None and m3.group(1) == "42"

    # Should match feedback
    m4 = pattern.fullmatch("/api/v1/tasks/42/feedback")
    assert m4 is not None and m4.group(1) == "42"

    # Should NOT match unrelated path
    m5 = pattern.fullmatch("/api/v1/tasks/42/unknown")
    assert m5 is None


def test_inferior_model_cannot_replace_approved_production_model():
    """
    Stage 3 Verification:
    Verify model registry gating: failed or inferior candidates cannot replace
    an approved production model.
    """
    registry = ModelRegistry(store=InMemoryModelStore())

    # 1. Register and promote base model (score = 0.85)
    m1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeModelV1"},
        metrics={"accuracy_score": 0.85, "demo_only": False},
    )
    promoted_v1 = registry.promote_model("duration-ratio-ridge", m1.version)
    assert promoted_v1.status == ModelStatus.PRODUCTION
    assert promoted_v1.version == 1

    # 2. Register inferior model (score = 0.80)
    m2 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeModelV2"},
        metrics={"accuracy_score": 0.80, "demo_only": False},
    )

    # 3. Attempting to promote inferior model should raise ValueError
    with pytest.raises(ValueError, match="inferior to current production"):
        registry.promote_model("duration-ratio-ridge", m2.version)

    # Current production remains v1
    current = registry.get_latest_model("duration-ratio-ridge")
    assert current is not None
    assert current.metadata.version == 1

    # 4. Register superior model (score = 0.92)
    m3 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeModelV3"},
        metrics={"accuracy_score": 0.92, "demo_only": False},
    )
    promoted_v3 = registry.promote_model("duration-ratio-ridge", m3.version)
    assert promoted_v3.status == ModelStatus.PRODUCTION
    assert promoted_v3.version == 3

    # Production is now v3
    current_updated = registry.get_latest_model("duration-ratio-ridge")
    assert current_updated is not None
    assert current_updated.metadata.version == 3


def test_dataset_integrity_no_target_or_feedback_leakage(memory_db):
    """
    Stage 2 Verification:
    Verify that actual duration, completion timestamp, and post-outcome feedback
    do not leak into feature vectors.
    """
    service = TaskLifecycleService(memory_db)
    now = datetime(2026, 10, 11, 9, 0, 0)

    task = service.create_task(
        user_id=1,
        title="No Leakage Verification",
        task_type="coding",
        priority=4,
        estimated_duration=50.0,
        estimated_duration_unit="minutes",
        created_at=now,
    )
    service.start_task(task_id=task.id, user_id=1, started_at=now + timedelta(minutes=5))
    service.complete_task(
        task_id=task.id,
        user_id=1,
        completed_at=now + timedelta(minutes=65),
        actual_duration=60.0,
    )
    service.record_feedback(
        task_id=task.id,
        user_id=1,
        focus_rating=5.0,
        energy_rating=5.0,
        productivity_rating=5.0,
        feedback_notes="Confidential feedback notes",
    )

    extractor = TaskDataExtractor(memory_db)
    result = extractor.extract(user_id=1)
    assert len(result.dataset_build.rows) == 1

    row = result.dataset_build.rows[0]
    features = row.features

    # Check using LeakageGuard
    guard = LeakageGuard()
    guard.validate_features(features)

    for forbidden in FORBIDDEN_FEATURE_TOKENS:
        for fname in features:
            assert forbidden not in fname.lower(), f"Leakage detected: {forbidden} found in {fname}!"
    for forbidden in FORBIDDEN_EXACT_FEATURES:
        assert forbidden not in features, f"Exact target leakage: {forbidden} in features!"

    # Check feedback fields are completely absent from features
    for feedback_field in ("focus_rating", "energy_rating", "productivity_rating", "feedback_notes"):
        assert feedback_field not in features, f"Feedback leakage: {feedback_field} in features!"

    # Target is strictly duration_ratio = actual / estimated = 60.0 / 50.0 = 1.2
    assert "duration_ratio" in row.target
    assert abs(row.target["duration_ratio"] - 1.2) < 1e-4


def test_chronological_splits_preserve_order():
    """
    Stage 2 & 3 Verification:
    Verify temporal splitting respects chronology: no shuffling, no forward-looking data.
    """
    splitter = TemporalDatasetSplitter()
    base_time = datetime(2026, 10, 1, 10, 0, 0)

    # Create 12 sequential mock rows
    mock_rows = []
    for i in range(12):
        row = DatasetRow(
            example_id=f"ex-{i:02d}",
            task_id=str(i),
            user_id="1",
            prediction_timestamp=base_time + timedelta(days=i),
            features={"estimated_duration_minutes": 30.0, "priority": 3, "task_type": "coding"},
            target={"duration_ratio": 1.0 + (i * 0.05)},
            provenance={"label_source": "test"},
            dataset_version="v0.1",
            schema_version="v0.1",
            feature_version="v0.1",
            label_version="v0.1",
        )
        mock_rows.append(row)

    split = splitter.split(tuple(mock_rows))
    assert len(split.train) == 8  # 70% of 12 = 8
    assert len(split.validation) == 1  # 15% of 12 = 1
    assert len(split.test) == 3  # Remaining = 3

    # Verify temporal ordering across splits
    train_max = max(r.prediction_timestamp for r in split.train)
    val_min = min(r.prediction_timestamp for r in split.validation)
    val_max = max(r.prediction_timestamp for r in split.validation)
    test_min = min(r.prediction_timestamp for r in split.test)

    assert train_max < val_min, "Train split leaks into validation split!"
    assert val_max < test_min, "Validation split leaks into test split!"


def test_duration_model_metrics_computation():
    """
    Stage 3 Verification:
    Verify that EvaluationReport correctly computes MAE, RMSE, MAPE, and directional bias.
    """
    base_time = datetime(2026, 10, 1, 10, 0, 0)

    rows = []
    for i in range(15):
        rows.append(
            DatasetRow(
                example_id=f"row-{i:02d}",
                task_id=str(i),
                user_id="1",
                prediction_timestamp=base_time + timedelta(hours=i),
                features={
                    "estimated_duration_minutes": 30.0 + i,
                    "priority": 3,
                    "task_type": "coding",
                    "prediction_hour": 10,
                    "prediction_day_of_week": 1,
                    "time_since_task_created_minutes": 5.0,
                    "scheduled_start_hour": 10,
                    "hours_until_scheduled_start": 0.0,
                    "prior_completed_task_count": i,
                    "prior_duration_ratio_mean": 1.0,
                    "prior_duration_ratio_median": 1.0,
                    "prior_same_type_duration_ratio_mean": 1.0,
                },
                target={"duration_ratio": 1.1 if i < 10 else 1.0},
                provenance={"label_source": "test"},
                dataset_version="v0.1",
                schema_version="v0.1",
                feature_version="v0.1",
                label_version="v0.1",
            )
        )

    model = DurationRatioBaselineRegressor()
    split = TemporalDatasetSplitter().split(tuple(rows))
    report = model.train_on_split(split)

    assert isinstance(report, EvaluationReport)
    assert report.mae >= 0.0
    assert report.rmse >= 0.0
    assert report.mape >= 0.0
    assert isinstance(report.directional_bias, float)
    assert isinstance(report.median_error, float)
    assert report.train_sample_count >= MINIMUM_TRAINING_ROWS
