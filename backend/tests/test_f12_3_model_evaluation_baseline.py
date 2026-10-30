from __future__ import annotations

import math
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.ml.datasets.models import DatasetRow
from backend.app.ml.datasets.splitter import TemporalDatasetSplitter
from backend.app.ml.datasets.task_database_adapter import TaskDataExtractor
from backend.app.ml.duration_model import DurationRatioBaselineRegressor
from backend.app.ml.model_registry import (
    InMemoryModelStore,
    ModelRegistry,
    ModelStatus,
)
from backend.app.ml.readiness import (
    MINIMUM_TRAINING_ROWS,
    NOT_READY_INSUFFICIENT_DATA,
    NOT_READY_NO_DATA,
    READY_FOR_TRAINING,
    assess_duration_model_readiness,
)
from backend.app.models.base import Base
from backend.app.services.task_lifecycle_service import (
    TaskLifecycleService,
    ensure_task_lifecycle_schema,
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


# =========================================================================
# STAGE 2: MODEL PROMOTION SAFETY (BETTER, WORSE, EQUAL, MISSING, INCOMPATIBLE)
# =========================================================================

def test_promote_better_regression_candidate_succeeds():
    """Candidate with strictly lower MAE improves on production and is promoted."""
    registry = ModelRegistry(store=InMemoryModelStore())

    # 1. Register production model v1 (MAE = 0.25, RMSE = 0.30)
    v1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV1"},
        metrics={
            "mae": 0.25,
            "rmse": 0.30,
            "mape": 15.0,
            "directional_bias": 0.05,
            "sample_count": 20,
            "target_schema_version": "duration_ratio_v0.1",
            "evaluation_protocol": "chronological_temporal_holdout",
        },
    )
    promoted_v1 = registry.promote_model("duration-ratio-ridge", v1.version)
    assert promoted_v1.status == ModelStatus.PRODUCTION
    assert promoted_v1.version == 1

    # 2. Register candidate v2 with lower error (MAE = 0.18, RMSE = 0.22)
    v2 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV2"},
        metrics={
            "mae": 0.18,
            "rmse": 0.22,
            "mape": 11.0,
            "directional_bias": 0.02,
            "sample_count": 20,
            "target_schema_version": "duration_ratio_v0.1",
            "evaluation_protocol": "chronological_temporal_holdout",
        },
    )

    # 3. Promote candidate v2 -> succeeds
    promoted_v2 = registry.promote_model("duration-ratio-ridge", v2.version)
    assert promoted_v2.status == ModelStatus.PRODUCTION
    assert promoted_v2.version == 2

    current = registry.get_latest_model("duration-ratio-ridge")
    assert current is not None
    assert current.metadata.version == 2


def test_promote_worse_regression_candidate_rejected_and_preserves_production():
    """Candidate with higher MAE is rejected and current production model is preserved."""
    registry = ModelRegistry(store=InMemoryModelStore())

    # 1. Production model v1 (MAE = 0.20)
    v1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV1"},
        metrics={
            "mae": 0.20,
            "rmse": 0.25,
            "directional_bias": 0.01,
            "sample_count": 20,
            "target_schema_version": "duration_ratio_v0.1",
        },
    )
    registry.promote_model("duration-ratio-ridge", v1.version)

    # 2. Candidate v2 with worse MAE (0.28)
    v2 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV2_Worse"},
        metrics={
            "mae": 0.28,
            "rmse": 0.35,
            "directional_bias": 0.04,
            "sample_count": 20,
            "target_schema_version": "duration_ratio_v0.1",
        },
    )

    # 3. Promotion rejected with clear error
    with pytest.raises(ValueError, match="Candidate model is inferior: candidate MAE \\(0.2800\\) > production MAE \\(0.2000\\)"):
        registry.promote_model("duration-ratio-ridge", v2.version)

    # Production remains v1
    current = registry.get_latest_model("duration-ratio-ridge")
    assert current is not None
    assert current.metadata.version == 1
    assert current.metadata.status == ModelStatus.PRODUCTION


def test_promote_equal_regression_candidate_rejected_and_preserves_production():
    """Candidate with equal error metrics does not improve on approved production model."""
    registry = ModelRegistry(store=InMemoryModelStore())

    v1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV1"},
        metrics={
            "mae": 0.20,
            "rmse": 0.25,
            "directional_bias": 0.02,
            "sample_count": 20,
            "target_schema_version": "duration_ratio_v0.1",
        },
    )
    registry.promote_model("duration-ratio-ridge", v1.version)

    # Candidate with identical performance
    v2 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV2_Identical"},
        metrics={
            "mae": 0.20,
            "rmse": 0.25,
            "directional_bias": 0.02,
            "sample_count": 20,
            "target_schema_version": "duration_ratio_v0.1",
        },
    )

    with pytest.raises(ValueError, match="does not improve on approved production model"):
        registry.promote_model("duration-ratio-ridge", v2.version)

    current = registry.get_latest_model("duration-ratio-ridge")
    assert current is not None
    assert current.metadata.version == 1


def test_promote_missing_metrics_candidate_rejected():
    """Candidate with missing evaluation metrics is rejected."""
    registry = ModelRegistry(store=InMemoryModelStore())

    v1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV1"},
        metrics={},
    )

    with pytest.raises(ValueError, match="missing evaluation metrics"):
        registry.promote_model("duration-ratio-ridge", v1.version)


def test_promote_incompatible_target_candidate_rejected():
    """Candidate evaluating different target definition than production is rejected."""
    registry = ModelRegistry(store=InMemoryModelStore())

    v1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV1"},
        metrics={
            "mae": 0.20,
            "rmse": 0.25,
            "target_schema_version": "duration_ratio_v0.1",
        },
    )
    registry.promote_model("duration-ratio-ridge", v1.version)

    # Candidate trained on different target definition
    v2 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeV2_Incompatible"},
        metrics={
            "mae": 0.15,
            "rmse": 0.20,
            "target_schema_version": "raw_minutes_unscaled_v0.1",
        },
    )

    with pytest.raises(ValueError, match="Incompatible target definitions"):
        registry.promote_model("duration-ratio-ridge", v2.version)

    current = registry.get_latest_model("duration-ratio-ridge")
    assert current is not None
    assert current.metadata.version == 1


def test_promote_incompatible_evaluation_types_rejected():
    """Cannot compare regression candidate against classification/score production model."""
    registry = ModelRegistry(store=InMemoryModelStore())

    v1 = registry.register_model(
        "generic-model",
        model_object={"name": "ClassifierV1"},
        metrics={"accuracy_score": 0.85},
    )
    registry.promote_model("generic-model", v1.version)

    # Incompatible regression candidate for same family
    v2 = registry.register_model(
        "generic-model",
        model_object={"name": "RegressorV2"},
        metrics={"mae": 0.15, "rmse": 0.20},
    )

    with pytest.raises(ValueError, match="Incompatible model evaluation types"):
        registry.promote_model("generic-model", v2.version)


def test_promote_invalid_regression_metrics_rejected():
    """Candidates with negative MAE, NaN, or extreme directional bias are rejected."""
    registry = ModelRegistry(store=InMemoryModelStore())

    # Negative MAE
    v1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "Bad1"},
        metrics={"mae": -0.15, "rmse": 0.20},
    )
    with pytest.raises(ValueError, match="invalid MAE"):
        registry.promote_model("duration-ratio-ridge", v1.version)

    # Extreme directional bias (> 1.5)
    v2 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "Bad2"},
        metrics={"mae": 0.20, "rmse": 0.25, "directional_bias": 2.8},
    )
    with pytest.raises(ValueError, match="exceeds allowable safety threshold"):
        registry.promote_model("duration-ratio-ridge", v2.version)


def test_promote_insufficient_evaluation_samples_rejected():
    """Candidate with zero evaluation samples cannot be promoted."""
    registry = ModelRegistry(store=InMemoryModelStore())

    v1 = registry.register_model(
        "duration-ratio-ridge",
        model_object={"name": "RidgeNoEval"},
        metrics={"mae": 0.15, "rmse": 0.20, "sample_count": 0},
    )
    with pytest.raises(ValueError, match="insufficient evaluation data"):
        registry.promote_model("duration-ratio-ridge", v1.version)


# =========================================================================
# STAGE 4: EVALUATION READINESS (TRAINING & EVALUATION PARTITION SIZES)
# =========================================================================

def test_readiness_requires_both_usable_train_and_val_partitions(memory_db):
    """
    Reaching total row count alone does not suffice:
    The chronological training partition must have >= MINIMUM_TRAINING_ROWS (10)
    AND the evaluation partition must have >= 1 row.
    """
    service = TaskLifecycleService(memory_db)
    base_time = datetime(2026, 10, 11, 8, 0, 0)

    # Create 11 completed tasks: 70% of 11 = 7 training rows (< 10)
    for i in range(11):
        t = service.create_task(
            user_id=1,
            title=f"Task {i}",
            task_type="coding",
            priority=3,
            estimated_duration=30.0,
            estimated_duration_unit="minutes",
            created_at=base_time + timedelta(hours=i),
        )
        service.start_task(task_id=t.id, user_id=1, started_at=base_time + timedelta(hours=i, minutes=5))
        service.complete_task(
            task_id=t.id,
            user_id=1,
            completed_at=base_time + timedelta(hours=i, minutes=35),
            actual_duration=30.0,
        )

    # Assess duration readiness: total rows is 11 (>= 10), but train partition is only 7!
    readiness = assess_duration_model_readiness(memory_db, user_id=1)
    assert readiness.status == NOT_READY_INSUFFICIENT_DATA
    assert any("insufficient_training_partition" in reason for reason in readiness.blocking_reasons)
    assert readiness.details["train_partition_size"] < MINIMUM_TRAINING_ROWS
    assert readiness.details["total_usable_rows"] == 11
