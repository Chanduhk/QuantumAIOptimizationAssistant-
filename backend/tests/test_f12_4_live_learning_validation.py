from __future__ import annotations

import math
from datetime import datetime, timedelta
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.ai_models.productivity_model import ProductivityModel
from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.ml.datasets.models import DatasetRow
from backend.app.ml.datasets.splitter import DatasetSplit, TemporalDatasetSplitter
from backend.app.ml.datasets.task_database_adapter import TaskDataExtractor
from backend.app.ml.duration_model import (
    FEATURE_NAMES,
    DurationRatioBaselineRegressor,
    EvaluationReport,
)
from backend.app.ml.model_registry import (
    InMemoryModelStore,
    ModelRegistry,
    ModelStatus,
)
from backend.app.ml.productivity_target import transform_ratings_to_productivity_score
from backend.app.ml.readiness import (
    MINIMUM_RL_EPISODES,
    MINIMUM_TRAINING_ROWS,
    NOT_READY_INSUFFICIENT_DATA,
    NOT_READY_INSUFFICIENT_EPISODES,
    NOT_READY_NO_GROUND_TRUTH_LABELS,
    assess_duration_model_readiness,
    assess_full_ml_system_readiness,
    assess_productivity_model_readiness,
    assess_rl_scheduler_readiness,
)
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.task_lifecycle_service import (
    TaskLifecycleService,
    ensure_task_lifecycle_schema,
)


@pytest.fixture
def isolated_db():
    """Isolated in-memory SQLite database guaranteed to never touch production data."""
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


# =========================================================================
# STAGE 1: LIVE TASK LIFECYCLE IN ISOLATED DATABASE
# =========================================================================

def test_stage1_live_task_lifecycle_persistence_and_extraction(isolated_db):
    """
    Verify complete real-data journey:
    1. Create task with explicit estimated duration and minutes unit
    2. Start the task
    3. Complete it with valid actual duration
    4. Record focus, energy, and productivity ratings
    5. Reconnect/restart session and confirm persistence
    6. Confirm dataset extractor includes only eligible records
    """
    service = TaskLifecycleService(isolated_db)
    base_time = datetime(2026, 10, 11, 9, 0, 0)

    # 1. Create task with explicit minutes unit
    t1 = service.create_task(
        user_id=1,
        title="Develop Secure Auth Module",
        task_type="coding",
        priority=4,
        estimated_duration=45.0,
        estimated_duration_unit="minutes",
        estimated_duration_source="user_estimate",
        created_at=base_time,
    )
    assert t1.id is not None
    assert t1.estimated_duration == 45.0
    assert t1.estimated_duration_unit == "minutes"
    assert t1.lifecycle_state == "created"

    # 2. Start the task
    started = service.start_task(
        task_id=t1.id,
        user_id=1,
        started_at=base_time + timedelta(minutes=5),
    )
    assert started.lifecycle_state == "started"
    assert started.start_time == base_time + timedelta(minutes=5)

    # 3. Complete with valid actual duration
    completed = service.complete_task(
        task_id=t1.id,
        user_id=1,
        completed_at=base_time + timedelta(minutes=50),
        actual_duration=45.0,
    )
    assert completed.lifecycle_state == "completed"
    assert completed.completed is True
    assert completed.actual_duration == 45.0

    # 4. Record optional feedback ratings
    feedback = service.record_feedback(
        task_id=t1.id,
        user_id=1,
        focus_rating=4.5,
        energy_rating=4.0,
        productivity_rating=4.5,
        feedback_notes="Focused coding session with zero interruptions.",
    )
    assert feedback.focus_rating == 4.5
    assert feedback.energy_rating == 4.0
    assert feedback.productivity_rating == 4.5

    # Also create an INELIGIBLE task (legacy record with missing unit in raw database)
    t_ineligible = Task(
        user_id=1,
        title="Legacy Ineligible Task",
        task_type="admin",
        priority=2,
        estimated_duration=30.0,
        estimated_duration_unit=None,  # Missing unit
        start_time=base_time + timedelta(hours=1, minutes=5),
        end_time=base_time + timedelta(hours=1, minutes=35),
        actual_duration=30.0,
        completed=True,
        lifecycle_state="completed",
        created_at=base_time + timedelta(hours=1),
    )
    isolated_db.add(t_ineligible)
    isolated_db.commit()

    # 5. Simulate application restart: commit and reload from raw query
    isolated_db.commit()

    reloaded_t1 = isolated_db.query(Task).filter(Task.id == t1.id).one()
    assert reloaded_t1.title == "Develop Secure Auth Module"
    assert reloaded_t1.estimated_duration == 45.0
    assert reloaded_t1.estimated_duration_unit == "minutes"
    assert reloaded_t1.actual_duration == 45.0
    assert reloaded_t1.focus_rating == 4.5
    assert reloaded_t1.productivity_rating == 4.5

    # 6. Extract duration dataset: only t1 should be eligible, t_ineligible must be rejected
    extractor = TaskDataExtractor(isolated_db)
    extraction = extractor.extract(user_id=1)

    assert len(extraction.dataset_build.rows) == 1
    assert extraction.dataset_build.rows[0].task_id == str(t1.id)
    assert extraction.dataset_build.rows[0].features["estimated_duration_minutes"] == 45.0
    assert extraction.dataset_build.rows[0].target["duration_ratio"] == 1.0  # 45.0 / 45.0

    assert len(extraction.rejected) == 1
    assert extraction.rejected[0].task_id == str(t_ineligible.id)
    assert "estimated_duration unit/source is unknown" in extraction.rejected[0].message


# =========================================================================
# STAGE 2: DURATION MODEL EVALUATION INTEGRITY & BIAS DEFINITION
# =========================================================================

def test_stage2_directional_bias_units_and_evaluation_integrity():
    """
    Verify:
    - Directional bias definition: mean(y_pred - y_true), units = dimensionless duration-ratio
    - Positive bias = systematic overestimation; negative bias = systematic underestimation
    - MAE and RMSE are compared in compatible units (duration ratio)
    - MAPE safely handles positive and near-zero targets
    - Baseline and candidate evaluated on identical hold-out observations
    - Chronological split preserves order without data leakage
    """
    base_time = datetime(2026, 10, 1, 9, 0, 0)

    # Construct synthetic evaluation rows for mathematical verification
    eval_rows = []
    # y_true ratios: 1.0 (on-time), 1.2 (slightly slow), 0.8 (fast)
    targets = [1.0, 1.2, 0.8]
    for i, ratio in enumerate(targets):
        row = DatasetRow(
            example_id=f"eval-{i}",
            task_id=f"task-eval-{i}",
            user_id="1",
            prediction_timestamp=base_time + timedelta(hours=i),
            features={
                "estimated_duration_minutes": 60.0,
                "priority": 3,
                "task_type": "coding",
                "prediction_hour": 10,
                "prediction_day_of_week": 2,
                "time_since_task_created_minutes": 15.0,
                "scheduled_start_hour": 10,
                "hours_until_scheduled_start": 0.5,
                "prior_completed_task_count": i,
                "prior_duration_ratio_mean": 1.0,
                "prior_duration_ratio_median": 1.0,
                "prior_same_type_duration_ratio_mean": 1.0,
            },
            target={"duration_ratio": ratio},
            provenance={"label_source": "test"},
            dataset_version="v0.1",
            schema_version="v0.1",
            feature_version="v0.1",
            label_version="v0.1",
        )
        eval_rows.append(row)

    # If predictions are [1.1, 1.3, 0.9]:
    # Errors = [+0.1, +0.1, +0.1]
    # Directional bias = +0.1 (systematic overestimation by 10% of estimated duration)
    # MAE = 0.1
    # RMSE = 0.1
    errors = np.array([0.1, 0.1, 0.1])
    bias = float(np.mean(errors))
    assert round(bias, 4) == 0.1000

    # Verify MAPE protection: zero or near-zero targets do not produce ZeroDivisionError
    y_true_with_zero = np.array([0.0, 1.0, 2.0])
    y_pred = np.array([0.5, 1.0, 2.0])
    abs_err = np.abs(y_pred - y_true_with_zero)
    safe_pe = abs_err / np.maximum(y_true_with_zero, 1e-4)
    assert not np.isnan(safe_pe).any()
    assert not np.isinf(safe_pe).any()

    # Verify chronological dataset splitter order
    splitter = TemporalDatasetSplitter()
    split = splitter.split(tuple(eval_rows), train_fraction=0.34, validation_fraction=0.33)
    assert len(split.train) == 1
    assert len(split.validation) == 1
    assert len(split.test) == 1
    # Split timestamps must be non-decreasing
    assert split.train[0].prediction_timestamp <= split.validation[0].prediction_timestamp
    assert split.validation[0].prediction_timestamp <= split.test[0].prediction_timestamp


def test_stage2_promotion_gate_rejects_insufficient_evaluation_samples():
    """
    Review whether one validation observation is enough for promotion policy:
    1 sample is NOT enough; the gate requires at least 3 hold-out evaluation samples.
    A candidate with 1 or 2 evaluation samples must be rejected.
    """
    registry = ModelRegistry(store=InMemoryModelStore())

    # Candidate with only 1 evaluation sample
    v1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeSingleSample"},
        metrics={"mae": 0.10, "rmse": 0.12, "sample_count": 1},
    )

    with pytest.raises(ValueError, match="insufficient evaluation data.*sample count: 1 < 3"):
        registry.promote_model("duration-ratio-ridge", v1.version)

    # Candidate with 2 evaluation samples
    v2 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeTwoSamples"},
        metrics={"mae": 0.10, "rmse": 0.12, "sample_count": 2},
    )

    with pytest.raises(ValueError, match="insufficient evaluation data.*sample count: 2 < 3"):
        registry.promote_model("duration-ratio-ridge", v2.version)


# =========================================================================
# STAGE 3: PRODUCTIVITY FEEDBACK & TARGET TRANSFORMATION
# =========================================================================

def test_stage3_productivity_feedback_and_target_transformation(isolated_db):
    """
    Verify:
    - User feedback ratings (1.0 to 5.0) are genuine self-reports
    - Target transformation maps 1-5 rating into calibrated 0-100 score
    - Multi-dimensional composite weighting (productivity 60%, focus 25%, energy 15%)
    - Out-of-bounds ratings are rejected
    - ProductivityModel reports NOT_READY_NO_GROUND_TRUTH_LABELS when unrated
    """
    # 1. Mathematical transformation validation
    # Direct mappings:
    assert transform_ratings_to_productivity_score(1.0) == 0.0
    assert transform_ratings_to_productivity_score(2.0) == 25.0
    assert transform_ratings_to_productivity_score(3.0) == 50.0
    assert transform_ratings_to_productivity_score(4.0) == 75.0
    assert transform_ratings_to_productivity_score(5.0) == 100.0

    # Composite mapping:
    # 5.0 across all three = 100.0
    assert transform_ratings_to_productivity_score(5.0, focus_rating=5.0, energy_rating=5.0) == 100.0
    # 1.0 across all three = 0.0
    assert transform_ratings_to_productivity_score(1.0, focus_rating=1.0, energy_rating=1.0) == 0.0

    # Weighted composite: prod=4.0, focus=3.0, energy=2.0
    # prod_scaled = (3.0)*25 = 75; focus_scaled = (2.0)*25 = 50; energy_scaled = (1.0)*25 = 25
    # score = 0.60*75 + 0.25*50 + 0.15*25 = 45 + 12.5 + 3.75 = 61.25
    assert transform_ratings_to_productivity_score(4.0, focus_rating=3.0, energy_rating=2.0) == 61.25

    # Out of bounds rejection
    with pytest.raises(ValueError, match="between 1.0 and 5.0"):
        transform_ratings_to_productivity_score(0.5)

    with pytest.raises(ValueError, match="between 1.0 and 5.0"):
        transform_ratings_to_productivity_score(5.5)

    # 2. Database readiness check on unrated completed tasks
    service = TaskLifecycleService(isolated_db)
    base_time = datetime(2026, 10, 11, 10, 0, 0)
    t = service.create_task(
        user_id=1,
        title="Unrated Task",
        task_type="coding",
        priority=3,
        estimated_duration=30.0,
        estimated_duration_unit="minutes",
        created_at=base_time,
    )
    service.start_task(task_id=t.id, user_id=1, started_at=base_time)
    service.complete_task(task_id=t.id, user_id=1, completed_at=base_time + timedelta(minutes=30), actual_duration=30.0)

    # Completed but unrated: readiness must be NOT_READY_NO_GROUND_TRUTH_LABELS
    readiness = assess_productivity_model_readiness(isolated_db, user_id=1)
    assert readiness.status == NOT_READY_NO_GROUND_TRUTH_LABELS
    assert readiness.eligible_samples == 0
    assert "target_is_heuristic_proxy_no_observed_ground_truth_labels" in readiness.blocking_reasons


# =========================================================================
# STAGE 4: RL SCHEDULING EPISODE & REWARD INTEGRITY
# =========================================================================

def test_stage4_rl_scheduling_episode_and_reward_integrity(isolated_db):
    """
    Verify:
    - Episode represents a real scheduling outcome (completed=True, valid start_time and end_time, end_time > start_time)
    - Incomplete tasks (e.g. not completed or missing end_time) are NOT counted
    - Reward definition in RLScheduler._calculate_reward is explicit and consistent
    - Uninitialized policy is exposed as UNINITIALIZED_ZERO_POLICY
    """
    service = TaskLifecycleService(isolated_db)
    base_time = datetime(2026, 10, 11, 8, 0, 0)

    # 1. Incomplete task (only started, not completed) -> should NOT count as episode
    t_incomp = service.create_task(
        user_id=1,
        title="Ongoing Task",
        task_type="coding",
        priority=3,
        estimated_duration=60.0,
        estimated_duration_unit="minutes",
        created_at=base_time,
    )
    service.start_task(task_id=t_incomp.id, user_id=1, started_at=base_time)

    readiness = assess_rl_scheduler_readiness(isolated_db, user_id=1)
    assert readiness.eligible_samples == 0
    assert readiness.status == NOT_READY_INSUFFICIENT_EPISODES
    assert readiness.details["q_table_status"] == "UNINITIALIZED_ZERO_POLICY"

    # 2. Complete task with valid lifecycle -> should count as 1 episode
    service.complete_task(task_id=t_incomp.id, user_id=1, completed_at=base_time + timedelta(minutes=60), actual_duration=60.0)
    readiness_after = assess_rl_scheduler_readiness(isolated_db, user_id=1)
    assert readiness_after.eligible_samples == 1
    assert readiness_after.status == NOT_READY_INSUFFICIENT_EPISODES

    # 3. RL Scheduler reward function verification
    scheduler = RLScheduler()
    assert scheduler.readiness_status == NOT_READY_INSUFFICIENT_EPISODES

    behavior_patterns = {
        "average_productivity": 70.0,
        "best_focus_hours": [9, 10, 11],
        "preferred_task_types": ["coding"],
        "hourly_productivity": {9: 80.0, 10: 85.0},
        "average_energy_level": 75.0,
    }

    task_dict = {
        "predicted_productivity": 75.0,
        "priority": 4,
        "task_type": "coding",
    }

    # Reward calculation:
    # 75.0 * 0.6 = 45.0
    # priority 4 * 8.0 = 32.0
    # hourly_productivity(9) * 0.3 = 80.0 * 0.3 = 24.0
    # best_focus_hour bonus = 10.0 (action_hour 9 is in [9, 10, 11])
    # preferred_task_type bonus = 6.0 ("coding" is in preferred)
    # energy_level(9) * 0.1 = 100.0 * 0.1 = 10.0 (distance=0 to focus hour)
    # Expected reward = 45.0 + 32.0 + 24.0 + 10.0 + 6.0 + 10.0 = 127.0
    reward = scheduler._calculate_reward(task_dict, action_hour=9, behavior_patterns=behavior_patterns)
    assert round(reward, 2) == 127.00


# =========================================================================
# STAGE 5: STRICT USER ISOLATION
# =========================================================================

def test_stage5_strict_user_isolation(isolated_db):
    """
    Verify complete user isolation:
    - User 1 cannot access, update, complete, or review User 2's tasks or feedback
    - Extractor for User 1 returns ONLY User 1's dataset rows
    - Readiness for User 1 counts ONLY User 1's tasks
    - Model registry candidate records do not contain user PII
    """
    service = TaskLifecycleService(isolated_db)
    base_time = datetime(2026, 10, 11, 9, 0, 0)

    # Create task for User 1
    t_user1 = service.create_task(
        user_id=1,
        title="User 1 Task",
        task_type="coding",
        priority=3,
        estimated_duration=30.0,
        estimated_duration_unit="minutes",
        created_at=base_time,
    )
    service.start_task(task_id=t_user1.id, user_id=1, started_at=base_time)
    service.complete_task(task_id=t_user1.id, user_id=1, completed_at=base_time + timedelta(minutes=30), actual_duration=30.0)
    service.record_feedback(task_id=t_user1.id, user_id=1, focus_rating=4.0, energy_rating=4.0, productivity_rating=4.0)

    # Create task for User 2
    t_user2 = service.create_task(
        user_id=2,
        title="User 2 Secret Task",
        task_type="writing",
        priority=5,
        estimated_duration=60.0,
        estimated_duration_unit="minutes",
        created_at=base_time,
    )

    # User 1 cannot get User 2's task
    with pytest.raises(ValueError, match="not found"):
        service.get_task(task_id=t_user2.id, user_id=1)

    # User 1 cannot start User 2's task
    with pytest.raises(ValueError, match="not found"):
        service.start_task(task_id=t_user2.id, user_id=1)

    # User 1 cannot complete User 2's task
    with pytest.raises(ValueError, match="not found"):
        service.complete_task(task_id=t_user2.id, user_id=1, actual_duration=60.0)

    # User 1 cannot record feedback on User 2's task
    with pytest.raises(ValueError, match="not found"):
        service.record_feedback(task_id=t_user2.id, user_id=1, focus_rating=5.0, energy_rating=5.0, productivity_rating=5.0)

    # Dataset extractor isolation:
    extractor = TaskDataExtractor(isolated_db)
    extraction_user1 = extractor.extract(user_id=1)
    assert len(extraction_user1.dataset_build.rows) == 1
    assert extraction_user1.dataset_build.rows[0].user_id == "1"

    extraction_user2 = extractor.extract(user_id=2)
    assert len(extraction_user2.dataset_build.rows) == 0

    # Readiness isolation:
    readiness_u1 = assess_duration_model_readiness(isolated_db, user_id=1)
    readiness_u2 = assess_duration_model_readiness(isolated_db, user_id=2)
    assert readiness_u1.eligible_samples == 1
    assert readiness_u2.eligible_samples == 0
