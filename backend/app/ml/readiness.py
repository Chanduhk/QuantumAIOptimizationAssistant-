from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional
from sqlalchemy.orm import Session

from backend.app.ml.datasets.quality_audit import DatasetQualityAuditor
from backend.app.ml.datasets.task_collection_report import TaskCollectionReporter
from backend.app.ml.datasets.task_database_adapter import TaskDataExtractor
from backend.app.models.task import Task


# Readiness Tiers
NOT_READY_NO_DATA = "NOT_READY_NO_DATA"
NOT_READY_INSUFFICIENT_DATA = "NOT_READY_INSUFFICIENT_DATA"
NOT_READY_INVALID_DATA = "NOT_READY_INVALID_DATA"
NOT_READY_NO_GROUND_TRUTH_LABELS = "NOT_READY_NO_GROUND_TRUTH_LABELS"
NOT_READY_INSUFFICIENT_EPISODES = "NOT_READY_INSUFFICIENT_EPISODES"
READY_FOR_TRAINING = "READY_FOR_TRAINING"
READY_FOR_EVALUATION = "READY_FOR_EVALUATION"
PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
PRODUCTION = "PRODUCTION"

# Thresholds with documented rationale
MINIMUM_AUDITABLE_ROWS = 3  # Minimum required for basic descriptive statistics
MINIMUM_TRAINING_ROWS = 10  # Minimum required for 70/15/15 chronological temporal train/val/test split
MINIMUM_EVALUATION_ROWS = 20  # Minimum required for statistical stability of MAE/RMSE
MINIMUM_PRODUCTION_CANDIDATE_ROWS = 50  # Minimum required for generalization across task types
MINIMUM_RL_EPISODES = 25  # Minimum episodes required before claiming RL policy convergence


@dataclass(frozen=True)
class ComponentReadiness:
    """Readiness assessment for one ML/AI component."""

    component_name: str
    model_type: str
    status: str
    eligible_samples: int
    required_samples: int
    ground_truth_label_source: str
    blocking_reasons: tuple[str, ...]
    data_collection_actions: tuple[str, ...]
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        cleaned_details: Dict[str, Any] = {}
        for k, v in self.details.items():
            if isinstance(v, (Mapping, dict)):
                cleaned_details[k] = dict(v)
            else:
                cleaned_details[k] = v
        return {
            "component_name": self.component_name,
            "model_type": self.model_type,
            "status": self.status,
            "eligible_samples": self.eligible_samples,
            "required_samples": self.required_samples,
            "ground_truth_label_source": self.ground_truth_label_source,
            "blocking_reasons": list(self.blocking_reasons),
            "data_collection_actions": list(self.data_collection_actions),
            "details": cleaned_details,
        }


@dataclass(frozen=True)
class SystemMLReadinessReport:
    """System-wide readiness assessment across all predictive/learning components."""

    overall_status: str
    audit_timestamp: str
    database_task_count: int
    eligible_dataset_rows: int
    components: Mapping[str, ComponentReadiness]
    summary: str
    next_steps: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "audit_timestamp": self.audit_timestamp,
            "database_task_count": self.database_task_count,
            "eligible_dataset_rows": self.eligible_dataset_rows,
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "summary": self.summary,
            "next_steps": list(self.next_steps),
        }


def assess_duration_model_readiness(session: Session, *, user_id: Optional[int] = None) -> ComponentReadiness:
    """Assess readiness of the proposed duration-ratio regression model."""
    extractor = TaskDataExtractor(session)
    extraction = extractor.extract(user_id=user_id)
    collection = TaskCollectionReporter(session).report(user_id=user_id)
    quality = DatasetQualityAuditor().audit_extraction(extraction, collection_report=collection)

    row_count = len(extraction.dataset_build.rows)
    train_count = len(extraction.dataset_split.train)
    val_count = len(extraction.dataset_split.validation or extraction.dataset_split.test)
    blocking: List[str] = list(quality.blocking_reasons)
    actions: List[str] = []

    if collection.total_task_records == 0:
        status = NOT_READY_NO_DATA
        blocking.append("database_has_no_tasks")
        actions.append("Create tasks through TaskLifecycleService with explicit estimated_duration and unit='minutes'")
    elif quality.issues:
        status = NOT_READY_INVALID_DATA
        blocking.extend(quality.issues)
        actions.append("Resolve data quality anomalies or timestamp ordering violations")
    else:
        status = READY_FOR_TRAINING
        if row_count < MINIMUM_EVALUATION_ROWS:
            status = NOT_READY_INSUFFICIENT_DATA
            blocking.append(f"insufficient_samples_{row_count}_below_minimum_{MINIMUM_EVALUATION_ROWS}")
            actions.append(f"Execute and complete at least {MINIMUM_EVALUATION_ROWS - row_count} more verified tasks")
        if train_count < MINIMUM_TRAINING_ROWS:
            status = NOT_READY_INSUFFICIENT_DATA
            blocking.append(f"insufficient_training_partition_{train_count}_below_{MINIMUM_TRAINING_ROWS}")
            actions.append(f"Execute and complete more verified tasks so chronological training partition reaches at least {MINIMUM_TRAINING_ROWS} (currently {train_count})")
        if val_count < 1:
            status = NOT_READY_INSUFFICIENT_DATA
            blocking.append("empty_evaluation_partition")
            actions.append("Execute and complete additional verified tasks to establish a separate chronological evaluation partition")

    return ComponentReadiness(
        component_name="DurationRatioModel",
        model_type="Duration-ratio baseline regression (Ridge / Random Forest)",
        status=status,
        eligible_samples=row_count,
        required_samples=MINIMUM_EVALUATION_ROWS,
        ground_truth_label_source="actual_duration_minutes / estimated_duration_minutes (empirical lifecycle timestamps)",
        blocking_reasons=tuple(sorted(set(blocking))),
        data_collection_actions=tuple(actions),
        details={
            "f3_eligible_records": extraction.report.eligible_records,
            "f3_rejected_records": extraction.report.rejected_records,
            "rejection_reasons": dict(extraction.report.rejection_reason_counts),
            "leakage_status": quality.leakage_status,
            "train_partition_size": train_count,
            "evaluation_partition_size": val_count,
            "total_usable_rows": row_count,
        },
    )


def assess_productivity_model_readiness(session: Session, *, user_id: Optional[int] = None) -> ComponentReadiness:
    """Assess readiness of the ProductivityModel."""
    query = session.query(Task).filter(Task.completed.is_(True))
    if user_id is not None:
        query = query.filter(Task.user_id == user_id)
    completed_tasks = query.all()

    # Ground truth feedback requires genuine user ratings, not heuristic formula
    rated_tasks = [t for t in completed_tasks if t.productivity_rating is not None and 1.0 <= t.productivity_rating <= 5.0]
    rated_count = len(rated_tasks)

    blocking = []
    actions = []

    if len(completed_tasks) == 0:
        status = NOT_READY_NO_DATA
        blocking.append("no_completed_tasks_recorded")
        actions.append("Complete tasks to begin accumulating behavioral data")
    elif rated_count == 0:
        status = NOT_READY_NO_GROUND_TRUTH_LABELS
        blocking.append("target_is_heuristic_proxy_no_observed_ground_truth_labels")
        actions.append("Submit post-task feedback ratings (1-5) via POST /api/v1/tasks/{id}/feedback")
        actions.append(f"Collect at least {MINIMUM_TRAINING_ROWS} user-rated completed tasks")
    elif rated_count < MINIMUM_TRAINING_ROWS:
        status = NOT_READY_INSUFFICIENT_DATA
        blocking.append(f"insufficient_genuine_labels_{rated_count}_below_minimum_{MINIMUM_TRAINING_ROWS}")
        actions.append("Submit post-task feedback ratings (1-5) via POST /api/v1/tasks/{id}/feedback")
        actions.append(f"Collect at least {MINIMUM_TRAINING_ROWS - rated_count} more user-rated completed tasks")
    else:
        status = READY_FOR_TRAINING

    return ComponentReadiness(
        component_name="ProductivityModel",
        model_type="RandomForestRegressor (productivity-rf-v1)",
        status=status,
        eligible_samples=rated_count,
        required_samples=MINIMUM_TRAINING_ROWS,
        ground_truth_label_source="user_productivity_rating (1.0 to 5.0 self-report)",
        blocking_reasons=tuple(sorted(set(blocking))),
        data_collection_actions=tuple(actions),
        details={
            "total_completed_tasks": len(completed_tasks),
            "user_rated_tasks": rated_count,
            "demo_model_status": "DEMO_ONLY (trained on synthetic data)",
            "current_production_target_semantics": (
                "heuristic_derived_productivity_proxy_not_observed_ground_truth"
                if rated_count == 0
                else "genuine_user_self_report_ratings_active"
            ),
        },
    )


def assess_rl_scheduler_readiness(session: Session, *, user_id: Optional[int] = None) -> ComponentReadiness:
    """Assess readiness of the RLScheduler."""
    query = session.query(Task).filter(
        Task.completed.is_(True),
        Task.start_time.is_not(None),
        Task.end_time.is_not(None),
    )
    if user_id is not None:
        query = query.filter(Task.user_id == user_id)

    from backend.app.ml.datasets.duration_quality_gate import DurationQualityGate

    valid_episodes = []
    for t in query.all():
        if t.start_time is None or t.end_time is None or t.end_time <= t.start_time:
            continue
        actual_min = t.actual_duration
        if actual_min is None:
            actual_min = (t.end_time - t.start_time).total_seconds() / 60.0
        gate_res = DurationQualityGate.assess(actual_min, t.estimated_duration)
        if not gate_res.is_eligible:
            continue
        valid_episodes.append(t)

    sample_count = len(valid_episodes)

    blocking = []
    actions = []

    if sample_count < MINIMUM_RL_EPISODES:
        status = NOT_READY_INSUFFICIENT_EPISODES
        blocking.append(f"insufficient_schedule_adherence_episodes_{sample_count}_below_{MINIMUM_RL_EPISODES}")
        actions.append("Execute tasks according to scheduled time slots to generate schedule adherence signals")
    else:
        status = READY_FOR_TRAINING

    return ComponentReadiness(
        component_name="RLScheduler",
        model_type="Tabular Q-Learning (Q-table)",
        status=status,
        eligible_samples=sample_count,
        required_samples=MINIMUM_RL_EPISODES,
        ground_truth_label_source="Schedule adherence reward R = f(start_time - scheduled_hour, energy, priority)",
        blocking_reasons=tuple(blocking),
        data_collection_actions=tuple(actions),
        details={
            "q_table_status": "UNINITIALIZED_ZERO_POLICY",
            "episodes_observed": sample_count,
        },
    )


def assess_full_ml_system_readiness(session: Session, *, user_id: Optional[int] = None) -> SystemMLReadinessReport:
    """Generate comprehensive deterministic readiness assessment across the entire AI/ML surface."""
    duration_readiness = assess_duration_model_readiness(session, user_id=user_id)
    productivity_readiness = assess_productivity_model_readiness(session, user_id=user_id)
    rl_readiness = assess_rl_scheduler_readiness(session, user_id=user_id)

    components = {
        "DurationRatioModel": duration_readiness,
        "ProductivityModel": productivity_readiness,
        "RLScheduler": rl_readiness,
    }

    total_query = session.query(Task)
    if user_id is not None:
        total_query = total_query.filter(Task.user_id == user_id)
    total_tasks = total_query.count()
    eligible_rows = duration_readiness.eligible_samples

    # Overall system readiness defaults to lowest common readiness for training
    if any(c.status in {NOT_READY_NO_DATA, NOT_READY_INSUFFICIENT_DATA} for c in components.values()):
        overall = NOT_READY_INSUFFICIENT_DATA
    elif any(c.status == NOT_READY_NO_GROUND_TRUTH_LABELS for c in components.values()):
        overall = NOT_READY_NO_GROUND_TRUTH_LABELS
    elif all(c.status == READY_FOR_TRAINING for c in components.values()):
        overall = READY_FOR_TRAINING
    else:
        overall = NOT_READY_INSUFFICIENT_DATA

    next_steps = [
        "Continue normal task execution: ensure tasks specify explicit duration units ('minutes')",
        "Record task start and completion timestamps via TaskLifecycleService",
        "Submit user feedback ratings (focus, energy, productivity) upon task completion",
        "Audit dataset readiness periodically via GET /api/v1/ml/readiness",
    ]

    summary = (
        f"ML Foundation Audit: {total_tasks} total tasks in database, {eligible_rows} eligible duration training rows. "
        f"DurationModel status: {duration_readiness.status}. "
        f"ProductivityModel status: {productivity_readiness.status} (heuristic proxy target). "
        f"RLScheduler status: {rl_readiness.status}."
    )

    return SystemMLReadinessReport(
        overall_status=overall,
        audit_timestamp=datetime.utcnow().isoformat() + "Z",
        database_task_count=total_tasks,
        eligible_dataset_rows=eligible_rows,
        components=components,
        summary=summary,
        next_steps=tuple(next_steps),
    )
