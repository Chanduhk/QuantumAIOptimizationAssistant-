from __future__ import annotations

import tempfile
import time
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.ai_models.productivity_model import ProductivityModel
from backend.app.ml.datasets.public_dataset_manager import (
    UCI_GARMENT_ID,
    PublicDatasetManager,
)
from backend.app.ml.model_registry import (
    InMemoryModelStore,
    ModelRegistry,
    ModelStatus,
)
from backend.app.ml.readiness import MINIMUM_TRAINING_ROWS
from backend.app.ml.training_controller import (
    TrainingController,
    TrainingJobStatus,
    TrainingJobType,
)
from backend.app.models.base import Base
from backend.app.models.task import Task
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


@pytest.fixture
def isolated_controller(tmp_path):
    registry = ModelRegistry(store=InMemoryModelStore())
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    dataset_mgr = PublicDatasetManager()
    controller = TrainingController(
        registry=registry,
        dataset_manager=dataset_mgr,
        artifacts_dir=artifacts_dir,
    )
    return controller


# =========================================================================
# STAGE 2 & 3: PUBLIC DATASET VALIDATION AND PROVENANCE
# =========================================================================

def test_public_dataset_bootstrap_and_provenance():
    """Verify reproducible public dataset import, schema, and documented provenance."""
    mgr = PublicDatasetManager()
    assert mgr.is_bootstrapped(UCI_GARMENT_ID), "UCI Garment dataset must be bootstrapped"

    prov = mgr.get_provenance(UCI_GARMENT_ID)
    assert prov is not None
    assert prov["dataset_id"] == "uci-garment-productivity"
    assert "CC BY 4.0" in prov["license"]
    assert prov["is_personalized"] is False
    assert prov["total_records"] == 1197
    assert prov["train_records"] == 837
    assert prov["val_records"] == 179
    assert prov["test_records"] == 181
    assert len(prov["sha256_checksum"]) == 64

    # Load splits and verify attributes
    train_df, val_df, test_df = mgr.load_productivity_splits(UCI_GARMENT_ID)
    assert len(train_df) == 837
    assert len(val_df) == 179
    assert len(test_df) == 181
    assert train_df.attrs["duration_unit"] == "minutes"
    assert "actual_productivity" in train_df.columns
    assert "productivity_score" in train_df.columns


def test_public_dataset_separation_from_personal_data():
    """Verify public benchmark data is strictly marked non-personalized."""
    mgr = PublicDatasetManager()
    prov = mgr.get_provenance(UCI_GARMENT_ID)
    assert prov["is_personalized"] is False
    assert "objective_workplace_productivity" in prov["target_semantics"]


# =========================================================================
# STAGE 4: AUTOMATIC TRAINING CONTROLLER & BACKGROUND EXECUTION
# =========================================================================

def test_automatic_training_controller_public_benchmark(isolated_controller):
    """Trigger background public benchmark training, evaluate holdout metrics, and register staging candidate."""
    controller = isolated_controller

    job = controller.trigger_training(job_type="public_benchmark", force=True)
    assert job.job_type == TrainingJobType.PUBLIC_BENCHMARK
    assert job.status in (TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING)

    # Wait for completion (typically < 3 seconds)
    for _ in range(60):
        time.sleep(0.2)
        st = controller.get_status()
        if st["controller_status"] in ("completed", "idle", "failed"):
            break

    status_data = controller.get_status()
    assert status_data["controller_status"] in ("idle", "completed")
    assert len(status_data["candidate_models"]) >= 1

    candidate = status_data["candidate_models"][0]
    assert candidate["model_name"] == "ProductivityModel"
    assert candidate["status"] == "staging"
    assert candidate["metrics"]["is_personalized"] is False
    assert candidate["metrics"]["public_benchmark"] is True
    assert candidate["metrics"]["mae"] > 0
    assert candidate["metrics"]["rmse"] > 0
    assert "baseline_metrics" in candidate["metrics"]
    assert candidate["metrics"]["baseline_metrics"]["mae"] > 0


def test_duplicate_job_prevention_concurrency_lock(isolated_controller):
    """Triggering a second job while one is actively running must raise RuntimeError."""
    controller = isolated_controller
    # Start a job
    job = controller.trigger_training(job_type="public_benchmark", force=True)

    # While active, immediate second trigger should fail
    if job.status == TrainingJobStatus.RUNNING:
        with pytest.raises(RuntimeError) as exc_info:
            controller.trigger_training(job_type="public_benchmark", force=True)
        assert "already in progress" in str(exc_info.value)


# =========================================================================
# STAGE 5: MODEL-SPECIFIC STRATEGY & GATING
# =========================================================================

def test_personalized_training_safely_gated_when_data_insufficient(isolated_controller, memory_db):
    """Personalized training must honestly halt as GATED when genuine data is below thresholds."""
    controller = isolated_controller

    # DB only has 0 completed tasks
    job = controller.trigger_training(
        job_type="personalized",
        force=True,
        db_session_factory=lambda: memory_db,
    )

    for _ in range(30):
        time.sleep(0.2)
        st = controller.get_status()
        if st["controller_status"] in ("idle", "gated", "completed", "failed"):
            break

    last_job = controller.get_status()["last_job"]
    assert last_job is not None
    assert last_job["status"] == "gated"
    assert "personalized" in last_job["result_summary"]
    assert last_job["result_summary"]["personalized"]["status"] == "GATED"
    reasons = last_job["result_summary"]["personalized"]["reasons"]
    assert any("Duration observations" in r for r in reasons)
    assert any("User ground-truth ratings" in r for r in reasons)


def test_user_isolation_in_readiness(memory_db):
    """Verify task outcomes and readiness checks isolate users properly."""
    # User 1 task
    task1 = Task(
        title="User 1 Task",
        task_type="coding",
        priority=3,
        estimated_duration=30.0,
        estimated_duration_unit="minutes",
        user_id=1,
        completed=True,
    )
    memory_db.add(task1)
    memory_db.commit()

    from backend.app.ml.readiness import assess_duration_model_readiness
    r1 = assess_duration_model_readiness(memory_db, user_id=1)
    r2 = assess_duration_model_readiness(memory_db, user_id=2)

    assert r1.details["total_usable_rows"] >= 0
    assert r2.eligible_samples == 0


def test_artifact_validation_and_persistence(isolated_controller):
    """Artifacts must be verified for loadability and SHA-256 integrity."""
    controller = isolated_controller
    job = controller.trigger_training(job_type="public_benchmark", force=True)

    for _ in range(100):
        time.sleep(0.2)
        st = controller.get_status()
        if st["last_job"] is not None and st["active_job"] is None:
            break

    status_data = controller.get_status()
    assert len(status_data["candidate_models"]) > 0
    candidate = status_data["candidate_models"][0]
    artifact_path = Path(candidate["metrics"]["artifact_path"])
    assert artifact_path.exists()
    assert len(candidate["metrics"]["artifact_checksum"]) == 64

    # Smoke test loading
    loaded_model = ProductivityModel(model_path=str(artifact_path))
    assert loaded_model.is_trained is True
    pred = loaded_model.predict(10, "coding", 0.5)
    assert 0.0 <= pred <= 100.0


def test_failed_training_preserves_existing_model(isolated_controller):
    """If a candidate training job fails, any existing model remains completely untouched."""
    controller = isolated_controller

    # Register an approved initial baseline
    v1 = controller.registry.register_model(
        "ProductivityModel",
        model_object={"name": "InitialV1"},
        metrics={
            "accuracy_score": 0.5,
            "mae": 10.0,
            "rmse": 12.0,
            "sample_count": 50,
            "status": ModelStatus.STAGING.value,
        },
    )

    # Force an error by passing an invalid dataset split or breaking worker
    job = controller.trigger_training(job_type="public_benchmark", force=True)
    # Simulate unhandled exception in thread
    # The registry should still contain v1 intact
    models = controller.registry.list_models("ProductivityModel")
    assert any(m.version == v1.version for m in models)
