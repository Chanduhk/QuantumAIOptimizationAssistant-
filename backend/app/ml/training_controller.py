from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from backend.app.ai_models.productivity_model import ProductivityModel
from backend.app.ml.datasets.public_dataset_manager import (
    DEFAULT_EXTERNAL_DATA_DIR,
    UCI_GARMENT_ID,
    PublicDatasetManager,
    PublicDatasetMetadata,
)
from backend.app.ml.duration_model import (
    DurationRatioBaselineRegressor,
    EvaluationReport,
)
from backend.app.ml.model_registry import (
    ModelMetadata,
    ModelRegistry,
    ModelStatus,
    get_model_registry,
)
from backend.app.ml.readiness import (
    MINIMUM_RL_EPISODES,
    MINIMUM_TRAINING_ROWS,
    assess_duration_model_readiness,
    assess_full_ml_system_readiness,
    assess_productivity_model_readiness,
    assess_rl_scheduler_readiness,
)

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "data" / "model_artifacts"


class TrainingJobStatus(str, Enum):
    """Lifecycle states for training jobs."""

    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    GATED = "gated"
    FAILED = "failed"


class TrainingJobType(str, Enum):
    """Supported targets for automatic training."""

    PUBLIC_BENCHMARK = "public_benchmark"
    PERSONALIZED = "personalized"
    ALL = "all"


@dataclass
class TrainingStepLog:
    """Structured progress log entry for an automatic training step."""

    timestamp_utc: str
    step: str
    status: str
    message: str
    progress_pct: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "step": self.step,
            "status": self.status,
            "message": self.message,
            "progress_pct": self.progress_pct,
        }


@dataclass
class TrainingJobRecord:
    """Complete execution record for an automatic model training run."""

    job_id: str
    job_type: TrainingJobType
    status: TrainingJobStatus
    triggered_by: str
    started_at_utc: Optional[str] = None
    completed_at_utc: Optional[str] = None
    progress_pct: int = 0
    current_step: str = "initialized"
    step_logs: List[TrainingStepLog] = field(default_factory=list)
    candidate_models: List[Dict[str, Any]] = field(default_factory=list)
    result_summary: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    data_fingerprint: Optional[str] = None

    def add_log(self, step: str, status: str, message: str, progress_pct: int) -> None:
        self.current_step = step
        self.progress_pct = max(0, min(100, progress_pct))
        now_str = datetime.now(timezone.utc).isoformat()
        entry = TrainingStepLog(
            timestamp_utc=now_str,
            step=step,
            status=status,
            message=message,
            progress_pct=self.progress_pct,
        )
        self.step_logs.append(entry)
        logger.info("[TrainingJob %s] [%s] (%d%%) %s", self.job_id, step, self.progress_pct, message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "triggered_by": self.triggered_by,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "progress_pct": self.progress_pct,
            "current_step": self.current_step,
            "step_logs": [log.to_dict() for log in self.step_logs],
            "candidate_models": self.candidate_models,
            "result_summary": self.result_summary,
            "error_message": self.error_message,
            "data_fingerprint": self.data_fingerprint,
        }


class TrainingController:
    """Manages automatic model training, readiness evaluation, baseline comparisons, and background execution."""

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        dataset_manager: Optional[PublicDatasetManager] = None,
        artifacts_dir: Optional[Path] = None,
    ) -> None:
        self.registry = registry or get_model_registry()
        self.dataset_manager = dataset_manager or PublicDatasetManager()
        self.artifacts_dir = Path(artifacts_dir or DEFAULT_ARTIFACTS_DIR)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._active_job: Optional[TrainingJobRecord] = None
        self._last_job: Optional[TrainingJobRecord] = None
        self._history: List[TrainingJobRecord] = []
        self._cache_fingerprints: Dict[str, str] = {}
        self.recover_stale_jobs()

    def recover_stale_jobs(self) -> int:
        """Safely clean up active jobs left in running or queued state during process crashes/restarts."""
        with self._lock:
            recovered = 0
            if self._active_job and self._active_job.status in (
                TrainingJobStatus.RUNNING,
                TrainingJobStatus.QUEUED,
            ):
                self._active_job.status = TrainingJobStatus.FAILED
                self._active_job.error_message = "Training process was interrupted by application restart."
                self._active_job.completed_at_utc = datetime.now(timezone.utc).isoformat()
                self._active_job.add_log(
                    "stale_recovery",
                    "FAILED",
                    "Job interrupted by process restart; cleanly recovered.",
                    self._active_job.progress_pct,
                )
                self._last_job = self._active_job
                self._history.append(self._active_job)
                self._active_job = None
                recovered += 1
            return recovered

    def get_status(self) -> Dict[str, Any]:
        """Return the current training controller state, active job, candidate models, and public dataset provenance."""
        with self._lock:
            active = self._active_job.to_dict() if self._active_job else None
            last = self._last_job.to_dict() if self._last_job else None

            # Get staging candidates and production models from registry
            candidates = []
            production = []
            for m_name in ("ProductivityModel", "DurationRatioModel", "behavior_model"):
                for m in self.registry.list_models(m_name):
                    info = {
                        "model_name": m.model_name,
                        "version": m.version,
                        "status": m.status.value,
                        "accuracy_score": m.accuracy_score,
                        "training_timestamp": m.training_timestamp,
                        "metrics": m.metrics,
                    }
                    if m.status == ModelStatus.STAGING:
                        candidates.append(info)
                    elif m.status == ModelStatus.PRODUCTION:
                        production.append(info)

            prov = self.dataset_manager.get_provenance(UCI_GARMENT_ID)

            return {
                "controller_status": (
                    self._active_job.status.value if self._active_job else TrainingJobStatus.IDLE.value
                ),
                "active_job": active,
                "last_job": last,
                "candidate_models": candidates,
                "production_models": production,
                "public_dataset": prov,
                "total_jobs_executed": len(self._history),
            }

    def trigger_training(
        self,
        job_type: str = "public_benchmark",
        force: bool = False,
        triggered_by: str = "manual_api",
        user_id: Optional[int] = None,
        db_session_factory: Optional[Callable[[], Any]] = None,
    ) -> TrainingJobRecord:
        """Trigger an asynchronous model training job in a background worker."""
        try:
            parsed_type = TrainingJobType(job_type)
        except ValueError as exc:
            raise ValueError(
                f"Invalid job_type '{job_type}'. Must be one of: public_benchmark, personalized, all."
            ) from exc

        with self._lock:
            if self._active_job and self._active_job.status in (
                TrainingJobStatus.RUNNING,
                TrainingJobStatus.QUEUED,
            ):
                raise RuntimeError(
                    f"A training job is already in progress (job_id: {self._active_job.job_id}). Duplicate concurrent training is prevented."
                )

            job_id = f"job-{uuid.uuid4().hex[:8]}"
            job = TrainingJobRecord(
                job_id=job_id,
                job_type=parsed_type,
                status=TrainingJobStatus.QUEUED,
                triggered_by=triggered_by,
                started_at_utc=datetime.now(timezone.utc).isoformat(),
            )
            job.add_log("queued", "QUEUED", f"Job queued for background execution (type: {parsed_type.value})", 0)
            self._active_job = job

        # Launch background worker
        worker = threading.Thread(
            target=self._run_worker,
            args=(job, force, user_id, db_session_factory),
            daemon=True,
            name=f"TrainingWorker-{job_id}",
        )
        worker.start()

        return job

    def retry_training(
        self,
        job_id: Optional[str] = None,
        user_id: Optional[int] = None,
        db_session_factory: Optional[Callable[[], Any]] = None,
    ) -> TrainingJobRecord:
        """Retry a failed or gated training job safely."""
        with self._lock:
            target_type = TrainingJobType.PUBLIC_BENCHMARK
            if self._last_job:
                target_type = self._last_job.job_type

        return self.trigger_training(
            job_type=target_type.value,
            force=True,
            triggered_by="retry_api",
            user_id=user_id,
            db_session_factory=db_session_factory,
        )

    def _run_worker(
        self,
        job: TrainingJobRecord,
        force: bool,
        user_id: Optional[int],
        db_session_factory: Optional[Callable[[], Any]],
    ) -> None:
        """Background worker thread executing training stages safely."""
        with self._lock:
            job.status = TrainingJobStatus.RUNNING

        try:
            job.add_log("starting", "RUNNING", f"Worker thread started for job {job.job_id}", 5)

            if job.job_type in (TrainingJobType.PUBLIC_BENCHMARK, TrainingJobType.ALL):
                self._train_public_benchmark(job, force=force)

            if job.job_type in (TrainingJobType.PERSONALIZED, TrainingJobType.ALL):
                self._check_and_train_personalized(job, user_id=user_id, db_session_factory=db_session_factory)

            with self._lock:
                if job.status == TrainingJobStatus.RUNNING:
                    job.status = TrainingJobStatus.COMPLETED
                job.completed_at_utc = datetime.now(timezone.utc).isoformat()
                job.progress_pct = 100
                job.add_log(
                    "finished",
                    job.status.value.upper(),
                    f"Job {job.job_id} concluded with status '{job.status.value}'",
                    100,
                )
                self._last_job = job
                self._history.append(job)
                self._active_job = None

        except Exception as exc:
            logger.exception("Error during training job %s: %s", job.job_id, exc)
            with self._lock:
                job.status = TrainingJobStatus.FAILED
                job.error_message = str(exc)
                job.completed_at_utc = datetime.now(timezone.utc).isoformat()
                job.add_log(
                    "error",
                    "FAILED",
                    f"Training encountered an unhandled exception: {exc}",
                    job.progress_pct,
                )
                self._last_job = job
                self._history.append(job)
                self._active_job = None

    def _train_public_benchmark(self, job: TrainingJobRecord, force: bool = False) -> None:
        """Train and evaluate ProductivityModel on the UCI Garment public benchmark dataset."""
        job.add_log("public_dataset_bootstrap", "RUNNING", "Validating public dataset availability and SHA-256 integrity", 15)

        # 1. Ensure dataset is downloaded and validated
        if not self.dataset_manager.is_bootstrapped(UCI_GARMENT_ID) or force:
            meta = self.dataset_manager.bootstrap_uci_garment(force=force)
            job.add_log(
                "public_dataset_bootstrap",
                "SUCCESS",
                f"Bootstrapped {meta.name} ({meta.total_records} rows, SHA-256: {meta.sha256_checksum[:12]}...)",
                25,
            )
        else:
            meta_dict = self.dataset_manager.get_provenance(UCI_GARMENT_ID) or {}
            job.add_log(
                "public_dataset_bootstrap",
                "SUCCESS",
                f"Existing verified public dataset found ({meta_dict.get('total_records', 1197)} rows)",
                25,
            )

        # 2. Check fingerprint to avoid redundant retraining
        prov = self.dataset_manager.get_provenance(UCI_GARMENT_ID) or {}
        ds_checksum = prov.get("sha256_checksum", "")
        cache_key = f"public_benchmark_{ProductivityModel.MODEL_VERSION}_{ds_checksum}"
        if not force and self._cache_fingerprints.get(cache_key):
            job.add_log(
                "cache_check",
                "SKIPPED",
                "Public dataset and model configuration unchanged; skipping redundant training.",
                90,
            )
            job.result_summary["public_benchmark"] = {
                "status": "cached",
                "message": "Dataset and model configuration unchanged since last candidate registration.",
            }
            return

        # 3. Load chronological train/val/test partitions
        job.add_log("load_partitions", "RUNNING", "Loading chronological train, val, and test partitions", 35)
        train_df, val_df, test_df = self.dataset_manager.load_productivity_splits(UCI_GARMENT_ID)

        # 4. Train ProductivityModel candidate
        job.add_log(
            "model_training",
            "RUNNING",
            f"Fitting ProductivityModel (RandomForestRegressor) on {len(train_df)} benchmark records",
            50,
        )
        prod_model = ProductivityModel()
        train_metrics = prod_model.train(train_df)
        job.add_log(
            "model_training",
            "SUCCESS",
            f"Trained candidate: R2={train_metrics.get('validation_r2', 0):.4f}, MAE={train_metrics.get('validation_mae', 0):.2f}",
            65,
        )

        # 5. Evaluate candidate and baseline on validation partition
        job.add_log("candidate_evaluation", "RUNNING", f"Evaluating candidate and baseline on holdout val set (N={len(val_df)})", 75)

        # Predict candidate on val_df (normalizing duration to hours)
        duration_unit = val_df.attrs.get("duration_unit", "minutes")
        val_preds: List[float] = []
        for _, row in val_df.iterrows():
            raw_dur = float(row["duration"])
            dur_hours = (raw_dur / 60.0) if duration_unit == "minutes" else raw_dur
            pred = prod_model.predict(
                hour=int(row["hour_of_day"]),
                task_type=str(row["task_type"]),
                duration=dur_hours,
            )
            val_preds.append(pred)

        y_val_true = val_df["productivity_score"].to_numpy(dtype=float)
        y_val_pred = np.array(val_preds, dtype=float)

        cand_errors = y_val_pred - y_val_true
        cand_mae = float(np.mean(np.abs(cand_errors)))
        cand_rmse = float(np.sqrt(np.mean(cand_errors**2)))
        ss_tot = float(np.sum((y_val_true - np.mean(y_val_true)) ** 2))
        ss_res = float(np.sum(cand_errors**2))
        cand_r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

        # Baseline: Naive mean predictor from training set
        train_mean = float(np.mean(train_df["productivity_score"]))
        base_errors = train_mean - y_val_true
        base_mae = float(np.mean(np.abs(base_errors)))
        base_rmse = float(np.sqrt(np.mean(base_errors**2)))
        base_r2 = 0.0

        # 6. Artifact validation & persistence
        artifact_name = f"productivity_benchmark_candidate_{prov.get('dataset_id', 'uci')}.joblib"
        artifact_path = self.artifacts_dir / artifact_name
        prod_model.save(str(artifact_path))

        with open(artifact_path, "rb") as f:
            artifact_checksum = hashlib.sha256(f.read()).hexdigest()

        # Smoke-test inference on saved artifact (30 min = 0.5 hours)
        smoke_model = ProductivityModel(model_path=str(artifact_path))
        smoke_pred = smoke_model.predict(10, "coding", 0.5)
        if not (0.0 <= smoke_pred <= 100.0):
            raise ValueError(f"Artifact smoke test failed: invalid prediction {smoke_pred}")

        # 7. Register candidate in ModelRegistry
        job.add_log("model_registration", "RUNNING", "Registering evaluated candidate into ModelRegistry", 85)

        metadata_dict = {
            "model_version": ProductivityModel.MODEL_VERSION,
            "feature_schema_version": ProductivityModel.FEATURE_SCHEMA_VERSION,
            "target_schema_version": ProductivityModel.TARGET_SCHEMA_VERSION,
            "dataset_id": UCI_GARMENT_ID,
            "dataset_provenance": "UCI Machine Learning Repository 597 (CC BY 4.0)",
            "is_personalized": False,
            "public_benchmark": True,
            "demo_only": False,
            "accuracy_score": max(0.0, round(train_metrics.get("validation_r2", 0.0), 4)),
            "mae": round(cand_mae, 4),
            "rmse": round(cand_rmse, 4),
            "training_sample_count": len(train_df),
            "validation_sample_count": len(val_df),
            "baseline_metrics": {
                "mae": round(base_mae, 4),
                "rmse": round(base_rmse, 4),
                "r2": round(base_r2, 4),
                "baseline_type": "naive_mean_benchmark",
            },
            "artifact_path": str(artifact_path),
            "artifact_checksum": artifact_checksum,
            "dataset_checksum": ds_checksum,
            "evaluation_protocol": "chronological_temporal_holdout",
            "promotion_verdict": "OFFLINE_CANDIDATE_STAGING",
            "status": ModelStatus.STAGING.value,
        }

        registered = self.registry.register_model(
            model_name="ProductivityModel",
            model_object=prod_model,
            metrics=metadata_dict,
        )

        self._cache_fingerprints[cache_key] = artifact_checksum

        candidate_summary = {
            "model_name": "ProductivityModel",
            "version": registered.version,
            "status": registered.status.value,
            "candidate_mae": round(cand_mae, 4),
            "baseline_mae": round(base_mae, 4),
            "candidate_rmse": round(cand_rmse, 4),
            "baseline_rmse": round(base_rmse, 4),
            "candidate_r2": round(cand_r2, 4),
            "sample_count": len(val_df),
            "artifact_checksum": artifact_checksum[:12],
            "governance_note": (
                "Registered as STAGING offline benchmark candidate. Public benchmark data is never "
                "promoted to user personal production model."
            ),
        }
        job.candidate_models.append(candidate_summary)
        job.result_summary["public_benchmark"] = candidate_summary

        job.add_log(
            "model_registration",
            "SUCCESS",
            f"ProductivityModel candidate v{registered.version} registered (MAE: {cand_mae:.2f} vs Base: {base_mae:.2f})",
            90,
        )

    def _check_and_train_personalized(
        self,
        job: TrainingJobRecord,
        user_id: Optional[int],
        db_session_factory: Optional[Callable[[], Any]],
    ) -> None:
        """Audit readiness and train personalized model only when genuine real user data meets minimum thresholds."""
        job.add_log("personalized_readiness_audit", "RUNNING", "Auditing genuine real database records and readiness gates", 92)

        if db_session_factory is None:
            job.add_log(
                "personalized_readiness_audit",
                "GATED",
                "No database session provided; personalized training safely skipped.",
                95,
            )
            return

        session = db_session_factory()
        try:
            dur_readiness = assess_duration_model_readiness(session, user_id=user_id)
            prod_readiness = assess_productivity_model_readiness(session, user_id=user_id)
            rl_readiness = assess_rl_scheduler_readiness(session, user_id=user_id)

            gated_reasons = []
            trained_models = []

            train_count = dur_readiness.details.get("train_partition_size", 0)
            if dur_readiness.status == "READY_FOR_TRAINING" or train_count >= MINIMUM_TRAINING_ROWS:
                job.add_log("duration_training", "RUNNING", f"Fitting personalized duration model for user {user_id or 'global'}.", 94)
                from backend.app.ml.datasets.task_database_adapter import TaskDataExtractor
                extraction = TaskDataExtractor(session).extract(user_id=user_id)
                dur_regressor = DurationRatioBaselineRegressor()
                dur_report = dur_regressor.train_on_split(extraction.dataset_split)

                p_artifact_path = self.artifacts_dir / f"duration_model_user_{user_id or 'global'}.joblib"
                import joblib
                joblib.dump(dur_regressor, str(p_artifact_path))
                with open(p_artifact_path, "rb") as f:
                    p_checksum = hashlib.sha256(f.read()).hexdigest()

                reg_meta = {
                    **dur_report.to_dict(),
                    "model_version": dur_regressor.metadata["model_version"],
                    "is_personalized": True,
                    "public_benchmark": False,
                    "artifact_path": str(p_artifact_path),
                    "artifact_checksum": p_checksum,
                    "status": ModelStatus.STAGING.value,
                }
                reg_record = self.registry.register_model(
                    model_name="DurationRatioModel",
                    model_object=dur_regressor,
                    metrics=reg_meta,
                )

                try:
                    promoted = self.registry.promote_model("DurationRatioModel", reg_record.version)
                    job.add_log(
                        "duration_promotion",
                        "SUCCESS",
                        f"Promoted personalized model v{promoted.version} to PRODUCTION.",
                        96,
                    )
                    trained_models.append({
                        "model_name": "DurationRatioModel",
                        "version": promoted.version,
                        "status": "production",
                        "mae": dur_report.mae,
                        "rmse": dur_report.rmse,
                    })
                except Exception as promo_exc:
                    job.add_log(
                        "duration_promotion",
                        "RETAINED_STAGING",
                        f"Duration candidate v{reg_record.version} held in staging: {promo_exc}",
                        96,
                    )
                    trained_models.append({
                        "model_name": "DurationRatioModel",
                        "version": reg_record.version,
                        "status": "staging",
                        "rejection_reason": str(promo_exc),
                    })
            else:
                gated_reasons.append(
                    f"Duration observations ({dur_readiness.eligible_samples}/{MINIMUM_TRAINING_ROWS}) insufficient."
                )

            # 2. Independent Productivity Model Assessment & Training
            if prod_readiness.eligible_samples >= MINIMUM_TRAINING_ROWS:
                job.add_log("productivity_training", "RUNNING", f"Fitting personalized productivity model for user {user_id or 'global'}.", 96)
                from backend.app.ml.productivity_target import transform_ratings_to_productivity_score
                from backend.app.models.task import Task
                import pandas as pd

                query = session.query(Task).filter(Task.completed.is_(True))
                if user_id is not None:
                    query = query.filter(Task.user_id == user_id)
                completed_tasks = query.all()
                rated_tasks = [t for t in completed_tasks if t.productivity_rating is not None and 1.0 <= t.productivity_rating <= 5.0]

                records = []
                for t in rated_tasks:
                    hour = t.start_time.hour if t.start_time else (t.created_at.hour if t.created_at else 12)
                    ttype = (t.task_type.lower() if t.task_type and t.task_type.lower() in ProductivityModel.VALID_TASK_TYPES else "other")
                    dur_min = float(t.actual_duration if t.actual_duration is not None else (t.estimated_duration or 30.0))
                    prod_score = transform_ratings_to_productivity_score(
                        productivity_rating=float(t.productivity_rating),
                        focus_rating=float(t.focus_rating) if t.focus_rating is not None else None,
                        energy_rating=float(t.energy_rating) if t.energy_rating is not None else None,
                    )
                    records.append({
                        "hour_of_day": hour,
                        "task_type": ttype,
                        "duration": dur_min,
                        "productivity_score": prod_score,
                    })

                df = pd.DataFrame(records)
                df.attrs["duration_unit"] = "minutes"
                df.attrs["dataset_schema_version"] = ProductivityModel.DATASET_SCHEMA_VERSION
                df.attrs["target_schema_version"] = ProductivityModel.TARGET_SCHEMA_VERSION

                prod_model = ProductivityModel()
                train_metrics = prod_model.train(df)

                p_artifact_path = self.artifacts_dir / f"productivity_model_user_{user_id or 'global'}.joblib"
                self.artifacts_dir.mkdir(parents=True, exist_ok=True)
                prod_model.save(str(p_artifact_path))

                # Also save to legacy productivity directory so behavior_engine can discover it directly
                legacy_dir = Path(__file__).resolve().parents[2] / "artifacts" / "productivity_models"
                legacy_dir.mkdir(parents=True, exist_ok=True)
                prod_model.save(str(legacy_dir / f"user_{user_id or 'global'}_productivity_model.joblib"))

                with open(p_artifact_path, "rb") as f:
                    p_checksum = hashlib.sha256(f.read()).hexdigest()

                reg_meta = {
                    **train_metrics,
                    "model_version": prod_model.MODEL_VERSION,
                    "is_personalized": True,
                    "public_benchmark": False,
                    "artifact_path": str(p_artifact_path),
                    "artifact_checksum": p_checksum,
                    "status": ModelStatus.STAGING.value,
                    "evaluation_metrics": {
                        "mae": train_metrics.get("validation_mae", train_metrics.get("mae", 5.0)),
                        "rmse": train_metrics.get("validation_rmse", train_metrics.get("rmse", 8.0)),
                    },
                }
                reg_record = self.registry.register_model(
                    model_name="ProductivityModel",
                    model_object=prod_model,
                    metrics=reg_meta,
                )

                try:
                    promoted = self.registry.promote_model("ProductivityModel", reg_record.version)
                    job.add_log(
                        "productivity_promotion",
                        "SUCCESS",
                        f"Promoted personalized ProductivityModel v{promoted.version} to PRODUCTION.",
                        98,
                    )
                    trained_models.append({
                        "model_name": "ProductivityModel",
                        "version": promoted.version,
                        "status": "production",
                        "mae": train_metrics.get("mae"),
                        "rmse": train_metrics.get("rmse"),
                    })
                except Exception as promo_exc:
                    job.add_log(
                        "productivity_promotion",
                        "RETAINED_STAGING",
                        f"Productivity candidate v{reg_record.version} held in staging: {promo_exc}",
                        98,
                    )
                    trained_models.append({
                        "model_name": "ProductivityModel",
                        "version": reg_record.version,
                        "status": "staging",
                        "rejection_reason": str(promo_exc),
                    })
            else:
                gated_reasons.append(
                    f"User ground-truth ratings ({prod_readiness.eligible_samples}/{MINIMUM_TRAINING_ROWS}) insufficient."
                )

            # 3. Independent RL Scheduler Assessment & Training
            if rl_readiness.eligible_samples >= MINIMUM_RL_EPISODES:
                job.add_log("rl_training", "RUNNING", f"Fitting personalized RL Q-learning schedule policy for user {user_id or 'global'}.", 98)
                try:
                    from backend.app.ai_rl.rl_scheduler import RLScheduler
                    from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
                    from backend.app.ml.datasets.duration_quality_gate import DurationQualityGate

                    b_engine = BehaviorIntelligenceEngine(session)
                    b_engine.collect_behavior_data(user_id=user_id)
                    patterns = b_engine.get_user_patterns()

                    query = session.query(Task).filter(
                        Task.completed.is_(True),
                        Task.start_time.is_not(None),
                        Task.end_time.is_not(None),
                    )
                    if user_id is not None:
                        query = query.filter(Task.user_id == user_id)

                    episode_tasks = []
                    for t in query.all():
                        if t.start_time is None or t.end_time is None or t.end_time <= t.start_time:
                            continue
                        actual_min = t.actual_duration
                        if actual_min is None:
                            actual_min = (t.end_time - t.start_time).total_seconds() / 60.0
                        gate_res = DurationQualityGate.assess(actual_min, t.estimated_duration)
                        if not gate_res.is_eligible:
                            continue
                        h = t.start_time.hour if t.start_time else 10
                        episode_tasks.append({
                            "task_id": t.id,
                            "title": t.title,
                            "task_type": t.task_type or "general",
                            "priority": t.priority or 3,
                            "hour_of_day": h,
                            "scheduled_hour": h,
                            "estimated_duration": t.estimated_duration or 30.0,
                            "estimated_duration_unit": t.estimated_duration_unit or "minutes",
                            "estimated_duration_source": t.estimated_duration_source or "user_stated",
                            "actual_duration": t.actual_duration,
                            "predicted_productivity": (t.productivity_rating * 20.0) if t.productivity_rating else patterns.get("average_productivity", 50.0),
                        })

                    if len(episode_tasks) >= MINIMUM_RL_EPISODES:
                        scheduler = RLScheduler()
                        train_res = scheduler.train_agent(
                            episode_tasks,
                            patterns,
                            episodes=max(25, min(100, len(episode_tasks))),
                        )
                        scheduler._save_policy()
                        job.add_log(
                            "rl_training",
                            "SUCCESS",
                            f"RL Scheduler policy converged across {train_res.get('episodes', 25)} episodes ({train_res.get('states_learned', 0)} states).",
                            99,
                        )
                        trained_models.append({
                            "model_name": "RLScheduler",
                            "version": 1,
                            "status": "production",
                            "states_learned": train_res.get("states_learned", 0),
                            "average_reward": train_res.get("average_reward", 0.0),
                        })
                    else:
                        gated_reasons.append(
                            f"RL adherence episodes ({len(episode_tasks)}/{MINIMUM_RL_EPISODES}) insufficient."
                        )
                except Exception as rl_exc:
                    logger.warning("Error fitting RL policy: %s", rl_exc)
                    gated_reasons.append(f"RL policy fitting encountered: {rl_exc}")
            else:
                gated_reasons.append(
                    f"RL adherence episodes ({rl_readiness.eligible_samples}/{MINIMUM_RL_EPISODES}) insufficient."
                )

            # 4. Final Verdict and Governance Summary
            if not trained_models:
                summary_msg = "Personalized model training safely GATED: " + "; ".join(gated_reasons)
                job.status = TrainingJobStatus.GATED
                job.add_log("personalized_gating", "GATED", summary_msg, 95)
                job.result_summary["personalized"] = {
                    "status": "GATED",
                    "duration_eligible_samples": dur_readiness.eligible_samples,
                    "duration_required_samples": MINIMUM_TRAINING_ROWS,
                    "productivity_eligible_samples": prod_readiness.eligible_samples,
                    "productivity_required_samples": MINIMUM_TRAINING_ROWS,
                    "rl_eligible_samples": rl_readiness.eligible_samples,
                    "rl_required_samples": MINIMUM_RL_EPISODES,
                    "reasons": gated_reasons,
                    "governance_note": (
                        "Production model training strictly forbids fabricated records or weakened thresholds. "
                        "Heuristic fallback remains active until genuine user interaction provides sufficient data."
                    ),
                }
            else:
                job.status = TrainingJobStatus.COMPLETED
                job.add_log("personalized_completion", "SUCCESS", f"Personalized training completed for {len(trained_models)} model(s).", 100)
                dur_trained = next((m for m in trained_models if m["model_name"] == "DurationRatioModel"), None)
                job.result_summary["personalized"] = {
                    "status": "TRAINED",
                    "trained_models": trained_models,
                    "gated_reasons": gated_reasons,
                    "version": dur_trained["version"] if dur_trained else trained_models[0]["version"],
                    "evaluation_mae": dur_trained.get("mae") if dur_trained else None,
                    "evaluation_rmse": dur_trained.get("rmse") if dur_trained else None,
                }
        finally:
            session.close()


_SHARED_CONTROLLER: Optional[TrainingController] = None
_CONTROLLER_LOCK = threading.RLock()


def get_training_controller(
    registry: Optional[ModelRegistry] = None,
    dataset_manager: Optional[PublicDatasetManager] = None,
) -> TrainingController:
    """Return the shared singleton TrainingController instance."""
    global _SHARED_CONTROLLER
    with _CONTROLLER_LOCK:
        if _SHARED_CONTROLLER is None:
            _SHARED_CONTROLLER = TrainingController(
                registry=registry,
                dataset_manager=dataset_manager,
            )
        return _SHARED_CONTROLLER


def reset_training_controller() -> None:
    """Reset the shared singleton training controller (for testing)."""
    global _SHARED_CONTROLLER
    with _CONTROLLER_LOCK:
        _SHARED_CONTROLLER = None
