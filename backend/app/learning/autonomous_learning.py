from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timezone
from enum import Enum
from statistics import mean, pstdev
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.core.engine_registry import EngineRegistry
from backend.app.core.events import EventBus
from backend.app.ml import FeatureStore, ModelRegistry
from backend.app.ml.model_registry import InMemoryModelStore, ModelMetadata
from backend.app.monitoring import AIMonitor

LEARNING_STARTED = "LEARNING_STARTED"
MODEL_TRAINED = "MODEL_TRAINED"
MODEL_PROMOTED = "MODEL_PROMOTED"
MODEL_UPDATED = "MODEL_UPDATED"

_SHARED_FEATURE_STORE = FeatureStore()
_SHARED_MODEL_STORE = InMemoryModelStore()
_SHARED_EVENT_BUS = EventBus()


class AutonomousLearningLoop:
    """Continuous learning workflow for behavior-aware productivity models."""

    def __init__(
        self,
        session: Session,
        *,
        days_back: int = 90,
        engine_registry: Optional[EngineRegistry] = None,
        feature_store: Optional[FeatureStore] = None,
        model_registry: Optional[ModelRegistry] = None,
        event_bus: Optional[EventBus] = None,
        monitor: Optional[AIMonitor] = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.engine_registry = engine_registry
        self.feature_store = feature_store or _SHARED_FEATURE_STORE
        self.event_bus = event_bus or _SHARED_EVENT_BUS
        self.monitor = monitor or AIMonitor()
        self.model_registry = model_registry or ModelRegistry(
            store=_SHARED_MODEL_STORE,
            monitor=self.monitor,
        )
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    async def initialize_learning_loop(self) -> None:
        """Initialize engine dependencies using the shared engine registry."""
        if self._initialized:
            return

        self.engine_registry = self.engine_registry or EngineRegistry(self.session)
        self.behavior_engine = self.engine_registry.get_behavior_engine()
        self.learning_engine = self.engine_registry.get_learning_engine()
        self.prediction_engine = self.engine_registry.get_prediction_engine()
        self._initialized = True

    async def collect_behavior_data(self, user_id: int) -> Dict[str, Any]:
        """Collect task outcomes and derived productivity features for a user."""
        await self.initialize_learning_loop()
        started = perf_counter()

        raw_tasks = self.behavior_engine.collect_behavior_data(
            user_id=user_id,
            days_back=self.days_back,
        )
        if raw_tasks.empty:
            raise ValueError("No completed tasks found for the user.")

        behavior_frame = self.behavior_engine.extract_features()
        behavior_patterns = self.behavior_engine.get_user_patterns()

        merged_frame = raw_tasks.merge(
            behavior_frame,
            left_on="id",
            right_on="task_id",
            how="left",
        )
        merged_frame["duration_delta"] = (
            merged_frame["actual_duration"].fillna(merged_frame["estimated_duration"]).fillna(0.0)
            - merged_frame["estimated_duration"].fillna(0.0)
        )

        records = merged_frame.to_dict(orient="records")
        payload = {
            "raw_tasks": raw_tasks,
            "behavior_frame": behavior_frame,
            "behavior_patterns": behavior_patterns,
            "records": records,
        }

        self.monitor.log_engine_execution(
            "AutonomousLearningLoop:CollectBehaviorData",
            perf_counter() - started,
        )
        return payload

    async def detect_behavior_drift(self, user_id: int) -> Dict[str, Any]:
        """Compare recent productivity behavior with stored historical features."""
        await self.initialize_learning_loop()
        started = perf_counter()

        drift_report = self.learning_engine.detect_model_drift(
            self.behavior_engine,
            user_id=user_id,
            days_back=self.days_back,
        )
        current_patterns = self.behavior_engine.get_user_patterns()
        historical_features = self.feature_store.get_all_features(user_id)

        historical_productivity = float(
            historical_features.get("historical_average_productivity")
            or historical_features.get("average_productivity")
            or current_patterns.get("average_productivity", 0.0)
        )
        historical_focus_score = float(
            historical_features.get("historical_average_focus_score")
            or historical_features.get("average_focus_score")
            or current_patterns.get("average_focus_score", 0.0)
        )

        productivity_shift = abs(float(current_patterns.get("average_productivity", 0.0)) - historical_productivity)
        focus_shift = abs(float(current_patterns.get("average_focus_score", 0.0)) - historical_focus_score)
        combined_drift_score = round(
            max(float(drift_report["drift_score"]), (productivity_shift * 0.7) + (focus_shift * 0.3)),
            4,
        )

        drift_payload = {
            **drift_report,
            "feature_store_baseline_productivity": round(historical_productivity, 2),
            "feature_store_baseline_focus_score": round(historical_focus_score, 2),
            "productivity_shift": round(productivity_shift, 4),
            "focus_shift": round(focus_shift, 4),
            "drift_score": combined_drift_score,
            "drift_detected": combined_drift_score >= 7.5,
        }

        self.monitor.log_training_metrics("AutonomousLearningLoop:Drift", drift_payload)
        self.monitor.log_engine_execution(
            "AutonomousLearningLoop:DetectBehaviorDrift",
            perf_counter() - started,
        )
        return drift_payload

    async def retrain_models(self, user_id: int) -> Dict[str, Any]:
        """Retrain the productivity model using fresh behavior and feature context."""
        await self.initialize_learning_loop()
        started = perf_counter()

        feature_snapshot = self.feature_store.get_all_features(user_id)
        retraining_output = self.learning_engine.retrain_productivity_model(
            self.behavior_engine,
            user_id=user_id,
            days_back=self.days_back,
        )
        trained_model = self.behavior_engine.productivity_model
        if trained_model is None:
            raise ValueError("Productivity model training did not produce a model instance.")

        response = {
            "model": trained_model,
            "training_metrics": retraining_output["metrics"],
            "patterns": retraining_output["patterns"],
            "report": retraining_output["report"],
            "feature_snapshot": feature_snapshot,
        }

        self.monitor.log_engine_execution(
            "AutonomousLearningLoop:RetrainModels",
            perf_counter() - started,
        )
        return response

    async def evaluate_model(
        self,
        model: Any,
        validation_data: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Evaluate model quality on validation behavior records."""
        await self.initialize_learning_loop()
        started = perf_counter()

        if validation_data.empty:
            raise ValueError("validation_data is required for model evaluation.")

        validation_frame = validation_data.copy()
        sample_count = max(1, min(len(validation_frame), max(1, int(round(len(validation_frame) * 0.2)))))
        validation_frame = validation_frame.tail(sample_count)

        predictions = [
            float(
                model.predict(
                    hour_of_day=int(row.hour_of_day),
                    task_type=str(row.task_type),
                    duration=float(row.duration),
                )
            )
            for row in validation_frame.itertuples(index=False)
        ]
        actual_values = [float(value) for value in validation_frame["productivity_score"].tolist()]
        absolute_errors = [abs(actual - predicted) for actual, predicted in zip(actual_values, predictions)]
        mae = mean(absolute_errors) if absolute_errors else 0.0
        error_rate = min(mae / 100.0, 1.0)
        confidence_score = max(0.0, 1.0 - min((pstdev(absolute_errors) if len(absolute_errors) > 1 else mae) / 100.0, 1.0))
        prediction_accuracy = max(0.0, 1.0 - error_rate)

        metrics = {
            "accuracy_score": round(prediction_accuracy, 4),
            "prediction_accuracy": round(prediction_accuracy, 4),
            "error_rate": round(error_rate, 4),
            "confidence_score": round(confidence_score, 4),
            "validation_samples": len(validation_frame),
        }

        self.monitor.log_training_metrics("AutonomousLearningLoop:Evaluation", metrics)
        self.monitor.log_engine_execution(
            "AutonomousLearningLoop:EvaluateModel",
            perf_counter() - started,
        )
        return metrics

    async def update_model_registry(
        self,
        user_id: int,
        model: Any,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Register a trained model and promote it if it improves production quality."""
        await self.initialize_learning_loop()
        started = perf_counter()

        model_name = self._model_name(user_id)
        current_production = self.model_registry.get_latest_model(model_name)
        previous_accuracy = (
            float(current_production.metadata.accuracy_score)
            if current_production is not None
            else 0.0
        )

        registered_metadata = self.model_registry.register_model(
            model_name=model_name,
            model_object=model,
            metrics={
                **metrics,
                "training_timestamp": datetime.utcnow().isoformat(),
                "status": "staging",
            },
        )

        promoted_metadata: Optional[ModelMetadata] = None
        accuracy_improvement = round(float(registered_metadata.accuracy_score) - previous_accuracy, 4)
        should_promote = current_production is None or registered_metadata.accuracy_score > previous_accuracy
        if should_promote:
            promoted_metadata = self.model_registry.promote_model(model_name, registered_metadata.version)
            await self._emit_event(
                MODEL_PROMOTED,
                {
                    "user_id": user_id,
                    "model_name": model_name,
                    "version": promoted_metadata.version,
                    "accuracy_score": promoted_metadata.accuracy_score,
                },
            )

        self.monitor.log_engine_execution(
            "AutonomousLearningLoop:UpdateModelRegistry",
            perf_counter() - started,
        )
        return {
            "registered_model": registered_metadata,
            "promoted_model": promoted_metadata,
            "accuracy_improvement": accuracy_improvement,
            "production_updated": should_promote,
        }

    async def update_prediction_engine(self, user_id: int) -> Dict[str, Any]:
        """Reload the latest production model into the active prediction path."""
        await self.initialize_learning_loop()
        started = perf_counter()

        model_name = self._model_name(user_id)
        latest_record = self.model_registry.get_latest_model(model_name)
        if latest_record is None:
            raise ValueError(f"No production model available for '{model_name}'.")

        self.behavior_engine.active_user_id = user_id
        self.behavior_engine.productivity_model = latest_record.model_object
        setattr(self.prediction_engine, "latest_model_metadata", latest_record.metadata)

        payload = {
            "model_name": latest_record.metadata.model_name,
            "version": latest_record.metadata.version,
            "status": latest_record.metadata.status.value,
        }
        self.monitor.log_engine_execution(
            "AutonomousLearningLoop:UpdatePredictionEngine",
            perf_counter() - started,
        )
        return payload

    async def run_learning_cycle(self, user_id: int) -> Dict[str, Any]:
        """Execute one full autonomous learning cycle for a user."""
        await self.initialize_learning_loop()
        cycle_started = perf_counter()

        try:
            await self._emit_event(
                LEARNING_STARTED,
                {
                    "user_id": user_id,
                    "started_at": datetime.utcnow().isoformat(),
                },
            )

            behavior_payload = await self.collect_behavior_data(user_id)
            drift_report = await self.detect_behavior_drift(user_id)
            retraining_output = await self.retrain_models(user_id)
            await self._emit_event(
                MODEL_TRAINED,
                {
                    "user_id": user_id,
                    "model_name": self._model_name(user_id),
                    "training_metrics": retraining_output["training_metrics"],
                },
            )

            evaluation_metrics = await self.evaluate_model(
                retraining_output["model"],
                behavior_payload["behavior_frame"],
            )
            registry_update = await self.update_model_registry(
                user_id=user_id,
                model=retraining_output["model"],
                metrics={
                    **retraining_output["training_metrics"],
                    **evaluation_metrics,
                },
            )
            prediction_update = await self.update_prediction_engine(user_id)
            await self._emit_event(
                MODEL_UPDATED,
                {
                    "user_id": user_id,
                    "model_name": prediction_update["model_name"],
                    "version": prediction_update["version"],
                },
            )

            self._update_feature_store_baseline(
                user_id=user_id,
                behavior_patterns=retraining_output["patterns"],
                drift_report=drift_report,
                evaluation_metrics=evaluation_metrics,
            )

            cycle_duration = perf_counter() - cycle_started
            self.monitor.log_engine_execution("AutonomousLearningLoop", cycle_duration)
            self.monitor.log_training_metrics(
                "AutonomousLearningLoop",
                {
                    "user_id": user_id,
                    "cycle_duration_seconds": round(cycle_duration, 4),
                    "drift_score": drift_report["drift_score"],
                    "accuracy_score": evaluation_metrics["accuracy_score"],
                    "accuracy_improvement": registry_update["accuracy_improvement"],
                },
            )

            promoted_model = registry_update["promoted_model"] or registry_update["registered_model"]
            return {
                "status": "learning completed",
                "new_model_version": f"v{promoted_model.version}",
                "accuracy_improvement": registry_update["accuracy_improvement"],
                "drift_score": drift_report["drift_score"],
                "model_promoted": registry_update["production_updated"],
            }
        except Exception as exc:
            self.logger.exception("Learning cycle failed for user %s", user_id)
            raise ValueError(f"Learning cycle failed: {exc}") from exc

    async def _emit_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        await self.event_bus.publish_event(event_name, payload)
        self.monitor.log_event(event_name)

    def _update_feature_store_baseline(
        self,
        *,
        user_id: int,
        behavior_patterns: Dict[str, Any],
        drift_report: Dict[str, Any],
        evaluation_metrics: Dict[str, Any],
    ) -> None:
        baseline = {
            "historical_average_productivity": behavior_patterns.get("average_productivity", 0.0),
            "historical_average_focus_score": behavior_patterns.get("average_focus_score", 0.0),
            "historical_average_energy_level": behavior_patterns.get("average_energy_level", 0.0),
            "best_focus_hours": behavior_patterns.get("best_focus_hours", []),
            "preferred_task_types": behavior_patterns.get("preferred_task_types", []),
            "latest_drift_score": drift_report.get("drift_score", 0.0),
            "latest_accuracy_score": evaluation_metrics.get("accuracy_score", 0.0),
            "last_learning_cycle": datetime.utcnow().isoformat(),
        }
        self.feature_store.store_features(user_id, baseline)

    def _model_name(self, user_id: int) -> str:
        return f"productivity_model_user_{user_id}"


class LearningState(str, Enum):
    IDLE = "idle"
    DATA_PENDING = "data_pending"
    CHECKING_READINESS = "checking_readiness"
    WAITING_FOR_DATA = "waiting_for_sufficient_data"
    QUEUED = "queued"
    TRAINING = "training"
    EVALUATING = "evaluating"
    PROMOTED = "promoted"
    CANDIDATE_REJECTED = "candidate_rejected"
    FAILED = "failed"


class AutomaticLearningCoordinator:
    """Event-driven coordinator that automatically checks model readiness,
    governs decoupled candidate training, evaluates metrics, and enforces
    safe model promotion without manual user intervention.
    """

    def __init__(
        self,
        *,
        training_controller=None,
        db_session_factory=None,
    ) -> None:
        self._controller = training_controller
        self._db_session_factory = db_session_factory
        self._lock = threading.RLock()
        self._state = LearningState.IDLE
        self._pending_users: set[int] = set()
        self._evaluating_users: set[int] = set()
        self._user_fingerprints: dict[int, str] = {}
        self._last_event: Optional[Dict[str, Any]] = None
        self._last_check_timestamp: Optional[str] = None
        self._last_training_timestamp: Optional[str] = None
        self._last_verdict: Optional[str] = None
        self._initialized = False
        self._worker_thread: Optional[threading.Thread] = None

    def initialize(self, db_session_factory: Optional[Callable[[], Session]] = None) -> None:
        """Initialize event subscriptions and recover stale jobs."""
        with self._lock:
            if db_session_factory is not None:
                self._db_session_factory = db_session_factory
            if self._controller is None:
                from backend.app.ml.training_controller import get_training_controller
                self._controller = get_training_controller()

            # Clean up interrupted jobs from previous server run
            if self._controller is not None:
                self._controller.recover_stale_jobs()

            from backend.app.services.task_lifecycle_service import register_task_event_listener
            register_task_event_listener(self.on_task_event)
            self._initialized = True
            logging.getLogger(__name__).info("AutomaticLearningCoordinator initialized and subscribed to TaskLifecycleService events.")
            # Trigger background evaluation of existing database records
            threading.Thread(target=self.evaluate_existing_users, daemon=True, name="AutomaticLearningStartupSweep").start()

    def evaluate_existing_users(self) -> None:
        """Scan existing database users for training readiness on startup."""
        if self._db_session_factory is None:
            return
        session = self._db_session_factory()
        try:
            from backend.app.models.task import Task
            user_ids = [
                u_id for (u_id,) in session.query(Task.user_id).filter(Task.completed.is_(True)).distinct().all()
            ]
            with self._lock:
                for uid in user_ids:
                    self._pending_users.add(uid)
                if self._pending_users:
                    self._state = LearningState.DATA_PENDING
                    if self._worker_thread is None or not self._worker_thread.is_alive():
                        self._worker_thread = threading.Thread(
                            target=self._run_event_processor,
                            daemon=True,
                            name="AutomaticLearningWorker",
                        )
                        self._worker_thread.start()
        except Exception as exc:
            logging.getLogger(__name__).warning("Could not evaluate existing users on startup: %s", exc)
        finally:
            session.close()

    def on_task_event(self, event_name: str, task_id: int, user_id: int) -> None:
        """Handle incoming lifecycle events asynchronously without blocking the calling thread."""
        with self._lock:
            self._last_event = {
                "event_name": event_name,
                "task_id": task_id,
                "user_id": user_id,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            self._state = LearningState.DATA_PENDING
            self._pending_users.add(user_id)

            # Spawn or ensure background processor thread is running
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_thread = threading.Thread(
                    target=self._run_event_processor,
                    daemon=True,
                    name="AutomaticLearningWorker",
                )
                self._worker_thread.start()

    def _run_event_processor(self) -> None:
        """Background worker loop draining pending users and assessing readiness."""
        while True:
            user_id: Optional[int] = None
            with self._lock:
                if not self._pending_users:
                    if self._state == LearningState.DATA_PENDING:
                        self._state = LearningState.IDLE
                    break
                user_id = self._pending_users.pop()
                self._evaluating_users.add(user_id)
                self._state = LearningState.CHECKING_READINESS

            try:
                self._evaluate_and_train_user(user_id)
            except Exception as exc:
                logging.getLogger(__name__).exception("Error in AutomaticLearningCoordinator for user %s: %s", user_id, exc)
                with self._lock:
                    self._state = LearningState.FAILED
                    self._last_verdict = f"Error during automated assessment: {exc}"
            finally:
                with self._lock:
                    self._evaluating_users.discard(user_id)

    def _evaluate_and_train_user(self, user_id: int) -> None:
        """Assess readiness for user, check data fingerprint, and trigger training if eligible."""
        if self._db_session_factory is None:
            with self._lock:
                self._last_verdict = "No database session factory configured for automatic learning."
                self._state = LearningState.IDLE
            return

        from backend.app.ml.readiness import (
            MINIMUM_TRAINING_ROWS,
            MINIMUM_RL_EPISODES,
            assess_duration_model_readiness,
            assess_productivity_model_readiness,
            assess_rl_scheduler_readiness,
        )

        session = self._db_session_factory()
        try:
            dur = assess_duration_model_readiness(session, user_id=user_id)
            prod = assess_productivity_model_readiness(session, user_id=user_id)
            rl = assess_rl_scheduler_readiness(session, user_id=user_id)

            now_str = datetime.now(timezone.utc).isoformat()
            with self._lock:
                self._last_check_timestamp = now_str

            # Compute data fingerprint for deduplication
            fingerprint_payload = f"u:{user_id}:d:{dur.eligible_samples}:p:{prod.eligible_samples}:r:{rl.eligible_samples}"
            fingerprint = hashlib.sha256(fingerprint_payload.encode()).hexdigest()

            train_count = dur.details.get("train_partition_size", 0)
            dur_ready = dur.status == "READY_FOR_TRAINING" or train_count >= MINIMUM_TRAINING_ROWS
            prod_ready = prod.eligible_samples >= MINIMUM_TRAINING_ROWS
            rl_ready = rl.eligible_samples >= MINIMUM_RL_EPISODES

            if not (dur_ready or prod_ready or rl_ready):
                with self._lock:
                    self._state = LearningState.WAITING_FOR_DATA
                    self._last_verdict = (
                        f"Data accumulating: Duration ({dur.eligible_samples}/{MINIMUM_TRAINING_ROWS}), "
                        f"Productivity ({prod.eligible_samples}/{MINIMUM_TRAINING_ROWS}), "
                        f"RL ({rl.eligible_samples}/{MINIMUM_RL_EPISODES}). Waiting for training threshold."
                    )
                return

            # Check if this exact data state was already trained
            with self._lock:
                if self._user_fingerprints.get(user_id) == fingerprint:
                    self._state = LearningState.IDLE
                    self._last_verdict = f"Identical dataset fingerprint ({fingerprint[:12]}) already trained; skipping redundant run."
                    return
                self._user_fingerprints[user_id] = fingerprint
                self._state = LearningState.QUEUED
                self._last_verdict = "Training threshold satisfied! Triggering automatic training."

            # Trigger training through controller
            if self._controller is not None:
                try:
                    job = self._controller.trigger_training(
                        job_type="personalized",
                        force=False,
                        triggered_by=f"automatic_continuous_learning_user_{user_id}",
                        user_id=user_id,
                        db_session_factory=self._db_session_factory,
                    )
                    with self._lock:
                        self._last_training_timestamp = now_str
                        self._state = LearningState.TRAINING
                        self._last_verdict = f"Automatic training job {job.job_id} launched for user {user_id}."
                except RuntimeError as rexc:
                    # Concurrency lock prevented duplicate run; acceptable
                    with self._lock:
                        self._last_verdict = f"Training already active: {rexc}"
        finally:
            session.close()

    def get_learning_status(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Return the current continuous learning state and transparent readiness report."""
        with self._lock:
            readiness_data = {}
            if self._db_session_factory is not None:
                try:
                    from backend.app.ml.readiness import (
                        MINIMUM_TRAINING_ROWS,
                        MINIMUM_RL_EPISODES,
                        assess_duration_model_readiness,
                        assess_productivity_model_readiness,
                        assess_rl_scheduler_readiness,
                    )
                    sess = self._db_session_factory()
                    try:
                        dur = assess_duration_model_readiness(sess, user_id=user_id)
                        prod = assess_productivity_model_readiness(sess, user_id=user_id)
                        rl = assess_rl_scheduler_readiness(sess, user_id=user_id)
                        readiness_data = {
                            "DurationRatioModel": {
                                "status": dur.status,
                                "eligible_samples": dur.eligible_samples,
                                "required_samples": MINIMUM_TRAINING_ROWS,
                                "ready": dur.eligible_samples >= MINIMUM_TRAINING_ROWS,
                                "next_requirement": f"Accumulate {max(0, MINIMUM_TRAINING_ROWS - dur.eligible_samples)} more completed tasks with actual duration.",
                            },
                            "ProductivityModel": {
                                "status": prod.status,
                                "eligible_samples": prod.eligible_samples,
                                "required_samples": MINIMUM_TRAINING_ROWS,
                                "ready": prod.eligible_samples >= MINIMUM_TRAINING_ROWS,
                                "next_requirement": f"Submit {max(0, MINIMUM_TRAINING_ROWS - prod.eligible_samples)} more ratings (1-5) via task feedback.",
                            },
                            "RLScheduler": {
                                "status": rl.status,
                                "eligible_samples": rl.eligible_samples,
                                "required_samples": MINIMUM_RL_EPISODES,
                                "ready": rl.eligible_samples >= MINIMUM_RL_EPISODES,
                                "next_requirement": f"Accumulate {max(0, MINIMUM_RL_EPISODES - rl.eligible_samples)} more schedule adherence episodes.",
                            },
                        }
                    finally:
                        sess.close()
                except Exception:
                    pass

            return {
                "learning_mode": "automatic",
                "current_state": self._state.value,
                "initialized": self._initialized,
                "last_event": self._last_event,
                "last_check_timestamp": self._last_check_timestamp,
                "last_training_timestamp": self._last_training_timestamp,
                "last_verdict": self._last_verdict or "Autonomous continuous learning active. Collecting eligible outcomes.",
                "governance": {
                    "automatic_continuous_learning": True,
                    "manual_training_required": False,
                    "user_isolated": True,
                    "decoupled_models": True,
                    "synthetic_promotion_forbidden": True,
                },
                "per_model_readiness": readiness_data,
            }


_SHARED_LEARNING_COORDINATOR: Optional[AutomaticLearningCoordinator] = None
_COORDINATOR_LOCK = threading.RLock()


def get_learning_coordinator() -> AutomaticLearningCoordinator:
    """Return the shared singleton AutomaticLearningCoordinator instance."""
    global _SHARED_LEARNING_COORDINATOR
    with _COORDINATOR_LOCK:
        if _SHARED_LEARNING_COORDINATOR is None:
            _SHARED_LEARNING_COORDINATOR = AutomaticLearningCoordinator()
        return _SHARED_LEARNING_COORDINATOR


def reset_learning_coordinator() -> None:
    """Reset the singleton coordinator (for isolated test environments)."""
    global _SHARED_LEARNING_COORDINATOR
    with _COORDINATOR_LOCK:
        _SHARED_LEARNING_COORDINATOR = None
