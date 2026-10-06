"""Seed and exercise an isolated, lifecycle-generated optimization demo.

Run from the repository root with QUANTUM_LIFE_DATA_MODE=DEVELOPMENT/DEMO and
the required --confirm-development-demo flag. The script never connects to
the configured application database; it uses backend/behavior_engine_demo.db
and a demo-only model artifact directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.domain.assignment_qubo_ising import AssignmentQuboIsingBuilder
from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.hybrid_comparison import HybridComparator
from backend.app.domain.optimization_input_contract import adapt_task_for_optimization
from backend.app.domain.prediction_matrix import build_prediction_matrix
from backend.app.domain.qaoa_solver import AssignmentQAOASolver
from backend.app.domain.quantum_suitability import QuantumSuitabilityAnalyzer
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.models.behavior_data import BehaviorData  # register model metadata
from backend.app.models.task import Task
from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
from backend.app.services.task_lifecycle_service import TaskLifecycleService


ROOT = Path(__file__).resolve().parents[2]
DEMO_DATABASE = ROOT / "backend" / "behavior_engine_demo.db"
DEMO_MODEL_DIRECTORY = ROOT / "backend" / "artifacts" / "productivity_models" / "development_demo"
DEMO_USER_ID = 960_016
DEMO_SOURCE = "f96_development_demo:seed_v1"
DEMO_PREFIX = "DEV-DEMO F9.6"
HISTORY: tuple[dict[str, Any], ...] = (
    {"type": "coding", "priority": 5, "estimate": 35, "actual": 42, "hour": 7},
    {"type": "research", "priority": 4, "estimate": 55, "actual": 48, "hour": 9},
    {"type": "writing", "priority": 3, "estimate": 75, "actual": 86, "hour": 11},
    {"type": "meeting", "priority": 2, "estimate": 45, "actual": 51, "hour": 13},
    {"type": "admin", "priority": 2, "estimate": 30, "actual": 26, "hour": 15},
    {"type": "coding", "priority": 5, "estimate": 95, "actual": 108, "hour": 8},
    {"type": "research", "priority": 4, "estimate": 110, "actual": 97, "hour": 10},
    {"type": "writing", "priority": 3, "estimate": 65, "actual": 73, "hour": 12},
    {"type": "coding", "priority": 4, "estimate": 120, "actual": 101, "hour": 14},
    {"type": "other", "priority": 1, "estimate": 50, "actual": 58, "hour": 16},
)
CANDIDATES: tuple[dict[str, Any], ...] = (
    {"type": "coding", "priority": 5, "estimate": 70},
    {"type": "research", "priority": 4, "estimate": 105},
)


def validate_demo_environment(
    environ: dict[str, str],
    *,
    configured_database_url: str,
    default_database_path: Path,
    demo_database_path: Path,
) -> None:
    """Fail closed unless demo mode and an isolated local SQLite target are clear."""
    if environ.get("QUANTUM_LIFE_DATA_MODE", "").strip().upper() != "DEVELOPMENT/DEMO":
        raise RuntimeError("Set QUANTUM_LIFE_DATA_MODE=DEVELOPMENT/DEMO to enable demo seeding.")
    production_markers = {"production", "prod", "live"}
    for key in ("APP_ENV", "ENVIRONMENT", "DEPLOYMENT_ENV", "QUANTUM_LIFE_ENV"):
        if environ.get(key, "").strip().lower() in production_markers:
            raise RuntimeError(f"Refusing demo seeding because {key} marks this environment as production.")
    try:
        parsed = make_url(configured_database_url)
    except Exception:
        raise RuntimeError("Refusing demo seeding because the configured database cannot be classified.") from None
    if parsed.get_backend_name() != "sqlite" or not parsed.database:
        raise RuntimeError("Refusing demo seeding with a non-SQLite configured database; no database was opened.")
    configured_database_path = Path(parsed.database).resolve()
    if configured_database_path == demo_database_path.resolve():
        raise RuntimeError("Demo database must be separate from the configured application database.")
    if default_database_path.resolve() == demo_database_path.resolve():
        raise RuntimeError("Demo database must be physically separate from the configured application database.")
    # Any other local SQLite database is left unopened; all writes target only
    # the fixed demo path. This permits a separately configured local app DB
    # without treating it as seed input or silently changing its contents.


def _database_fingerprint(path: Path) -> tuple[int | None, str | None]:
    """Read-only row count and byte digest for proving the original DB is unchanged."""
    if not path.exists():
        return None, None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] if "tasks" in tables else 0
    except sqlite3.Error:
        return None, digest
    return int(count), digest


def _task_title(kind: str, index: int) -> str:
    return f"{DEMO_PREFIX} {kind} {index:02d}"


def seed_demo_tasks(session: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Create, start, and complete the fixed demo history through lifecycle APIs."""
    reference = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if reference.tzinfo is not None:
        reference = reference.astimezone(timezone.utc).replace(tzinfo=None)
    lifecycle = TaskLifecycleService(session)
    rows = session.query(Task).filter(Task.user_id == DEMO_USER_ID).all()
    by_title = {task.title: task for task in rows}
    created = completed = candidate_created = 0
    anchor = reference - timedelta(days=len(HISTORY) + 1)

    for index, spec in enumerate(HISTORY, start=1):
        title = _task_title("HISTORY", index)
        task = by_title.get(title)
        start = (anchor + timedelta(days=index)).replace(hour=spec["hour"], minute=0, second=0, microsecond=0)
        if task is None:
            task = lifecycle.create_task(
                user_id=DEMO_USER_ID,
                title=title,
                task_type=spec["type"],
                priority=spec["priority"],
                estimated_duration=spec["estimate"],
                estimated_duration_unit="minutes",
                estimated_duration_source=DEMO_SOURCE,
                created_at=start - timedelta(minutes=30),
            )
            created += 1
        _verify_seed_task(task, spec, expected_state="history")
        if task.lifecycle_state == "created":
            task = lifecycle.start_task(task_id=task.id, user_id=DEMO_USER_ID, started_at=start)
        if task.lifecycle_state == "started":
            started = task.start_time
            if started is None:
                raise RuntimeError(f"Demo history task {task.id} has no lifecycle start timestamp.")
            lifecycle.complete_task(
                task_id=task.id,
                user_id=DEMO_USER_ID,
                completed_at=started + timedelta(minutes=spec["actual"]),
            )
            completed += 1
        else:
            _verify_completed_outcome(task)

    for index, spec in enumerate(CANDIDATES, start=1):
        title = _task_title("CANDIDATE", index)
        task = by_title.get(title)
        if task is None:
            task = lifecycle.create_task(
                user_id=DEMO_USER_ID,
                title=title,
                task_type=spec["type"],
                priority=spec["priority"],
                estimated_duration=spec["estimate"],
                estimated_duration_unit="minutes",
                estimated_duration_source=DEMO_SOURCE,
                created_at=reference - timedelta(minutes=5 * index),
            )
            candidate_created += 1
        _verify_seed_task(task, spec, expected_state="candidate")

    return {
        "created_history": created,
        "completed_via_lifecycle": completed,
        "created_candidates": candidate_created,
        "history_tasks": len(HISTORY),
        "planning_candidates": len(CANDIDATES),
        "total_demo_tasks": len(HISTORY) + len(CANDIDATES),
    }


def _verify_seed_task(task: Task, spec: dict[str, Any], *, expected_state: str) -> None:
    if (
        task.user_id != DEMO_USER_ID
        or task.estimated_duration != spec["estimate"]
        or task.estimated_duration_unit != "minutes"
        or task.estimated_duration_source != DEMO_SOURCE
        or task.task_type != spec["type"]
        or task.priority != spec["priority"]
    ):
        raise RuntimeError(f"Existing namespaced demo task {task.id} conflicts with the seed contract; leaving it untouched.")
    if expected_state == "candidate" and (task.completed or task.lifecycle_state != "created"):
        raise RuntimeError(f"Demo candidate {task.id} is no longer a created planning task; leaving it untouched.")
    if expected_state == "history" and task.lifecycle_state not in {"created", "started", "completed"}:
        raise RuntimeError(f"Demo history task {task.id} has an unsupported lifecycle state; leaving it untouched.")
    if expected_state == "history" and task.start_time is not None and task.start_time.hour != spec["hour"]:
        raise RuntimeError(f"Demo history task {task.id} start hour conflicts with the versioned seed; leaving it untouched.")
    if expected_state == "history" and task.lifecycle_state == "completed":
        _verify_completed_outcome(task)
        if abs(float(task.actual_duration) - float(spec["actual"])) > 1e-6:
            raise RuntimeError(f"Demo history task {task.id} outcome conflicts with the versioned seed; leaving it untouched.")


def _verify_completed_outcome(task: Task) -> None:
    if (
        not task.completed
        or task.lifecycle_state != "completed"
        or task.outcome_valid is not True
        or task.start_time is None
        or task.end_time is None
        or task.actual_duration is None
    ):
        raise RuntimeError(f"Completed demo task {task.id} has incomplete lifecycle outcome data; leaving it untouched.")
    expected = (task.end_time - task.start_time).total_seconds() / 60.0
    if abs(float(task.actual_duration) - expected) > 1e-6:
        raise RuntimeError(f"Completed demo task {task.id} actual duration does not match lifecycle timestamps.")


def _training_rejections(raw_tasks: list[dict[str, Any]], eligible_count: int) -> dict[str, int]:
    reasons: Counter[str] = Counter()
    for row in raw_tasks:
        if row.get("lifecycle_state") != "completed":
            reasons["not_completed"] += 1
        elif row.get("outcome_valid") is not True:
            reasons["invalid_outcome"] += 1
        elif row.get("estimated_duration_unit") not in {"minutes", "hours"}:
            reasons["unknown_estimate_unit"] += 1
        elif row.get("estimated_duration") is None or row.get("actual_duration") is None:
            reasons["missing_estimate_or_actual_outcome"] += 1
    rejected = max(0, len(raw_tasks) - eligible_count)
    if rejected > sum(reasons.values()):
        reasons["other_training_validation"] += rejected - sum(reasons.values())
    return dict(sorted(reasons.items()))


def _serialize_task(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "user_id": task.user_id,
        "title": task.title,
        "task_type": task.task_type,
        "priority": task.priority,
        "estimated_duration": task.estimated_duration,
        "estimated_duration_unit": task.estimated_duration_unit,
        "estimated_duration_source": task.estimated_duration_source,
        "actual_duration": task.actual_duration,
        "lifecycle_state": task.lifecycle_state,
        "completed": bool(task.completed),
        "outcome_valid": task.outcome_valid,
    }


def run_demo_readiness(
    *,
    demo_database_path: Path = DEMO_DATABASE,
    model_directory: Path = DEMO_MODEL_DIRECTORY,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Train and validate the demo matrix, then advance only through passed gates."""
    demo_database_path = demo_database_path.resolve()
    if demo_database_path == (ROOT / "backend" / "behavior_engine.db").resolve():
        raise RuntimeError("The demo database path resolves to the application database; refusing to continue.")
    database_url = f"sqlite:///{demo_database_path.as_posix()}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False}, future=True)
    from backend.app.models.base import Base
    from backend.app.services.task_lifecycle_service import ensure_task_lifecycle_schema_for_bind

    Base.metadata.create_all(bind=engine)
    ensure_task_lifecycle_schema_for_bind(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    report: dict[str, Any] = {
        "seed_status": "BLOCKED",
        "demo_tasks": 0,
        "eligible_training_count": 0,
        "rejected_count": 0,
        "rejected_reasons": {},
        "model_artifact_status": "NOT_RUN",
        "model_version": None,
        "feature_schema_version": None,
        "validation_metrics": None,
        "prediction_matrix_status": "NOT_RUN",
        "matrix_mode": "DEVELOPMENT/DEMO",
        "nontriviality_status": "NOT_RUN",
        "classical_optimization_status": "NOT_RUN",
        "qubo_ising_status": "NOT_RUN",
        "quantum_suitability_status": "NOT_RUN",
        "qaoa_status": "NOT_RUN",
        "hybrid_status": "NOT_RUN",
        "executive_cognitive_brain_status": "NOT_RUN",
        "remaining_blocker": None,
        "tests_note": "Automated tests are reported separately from this data run.",
    }
    try:
        with factory() as session:
            counts = seed_demo_tasks(session, now=now)
            report["seed_status"] = "IDEMPOTENT_DEMO_SEEDED"
            report["demo_tasks"] = counts["total_demo_tasks"]
            report["new_history_tasks"] = counts["created_history"]
            report["newly_completed_via_lifecycle"] = counts["completed_via_lifecycle"]
            report["new_planning_candidates"] = counts["created_candidates"]

            behavior = BehaviorIntelligenceEngine(session, model_directory=str(model_directory.resolve()))
            raw = behavior.collect_behavior_data(DEMO_USER_ID, days_back=90)
            frame = behavior._build_training_frame()
            report["eligible_training_count"] = len(frame)
            raw_records = raw.to_dict(orient="records") if not raw.empty else []
            report["rejected_reasons"] = _training_rejections(raw_records, len(frame))
            report["rejected_count"] = max(0, len(raw_records) - len(frame))
            if len(frame) < 5:
                report["model_artifact_status"] = "NOT_CREATED_INSUFFICIENT_ELIGIBLE_DATA"
                report["remaining_blocker"] = f"Existing trainer requires 5 eligible completed examples; found {len(frame)}."
                return report

            model = behavior.productivity_model
            metadata = model.metadata if model is not None and isinstance(model.metadata, dict) else {}
            artifact_parent = Path(model.model_path).resolve().parent if model is not None and model.model_path else None
            reusable_artifact = bool(
                model is not None
                and model.is_trained
                and model.compatibility_status == "OPTIMIZATION_COMPATIBLE"
                and metadata.get("model_version") == model.MODEL_VERSION
                and metadata.get("feature_schema_version") == model.FEATURE_SCHEMA_VERSION
                and metadata.get("target_schema_version") == model.TARGET_SCHEMA_VERSION
                and metadata.get("training_sample_count") == len(frame)
                and metadata.get("dataset_schema_version") == model.DATASET_SCHEMA_VERSION
                and metadata.get("duration_unit") == "hours"
                and artifact_parent == model_directory.resolve()
            )
            if reusable_artifact:
                metrics = metadata.get("validation_metrics", {})
                report["model_artifact_status"] = "REUSED_VALIDATED_VERSIONED_DEMO_ARTIFACT"
            else:
                metrics = behavior.train_productivity_model()
                model = behavior.productivity_model
                metadata = model.metadata if model is not None and isinstance(model.metadata, dict) else {}
                report["model_artifact_status"] = "TRAINED_VERSIONED_DEMO_ARTIFACT"
            report["model_artifact_path"] = str(model.model_path) if model is not None else None
            report["model_version"] = metadata.get("model_version")
            report["feature_schema_version"] = metadata.get("feature_schema_version")
            report["target_schema_version"] = metadata.get("target_schema_version")
            report["training_sample_count"] = metadata.get("training_sample_count")
            report["target_semantics"] = metadata.get("target_semantics")
            report["validation_metrics"] = metadata.get("validation_metrics", metrics)

            demo_rows = session.query(Task).filter(Task.user_id == DEMO_USER_ID, Task.title.like(f"{DEMO_PREFIX}%"), Task.completed.is_(False)).order_by(Task.id.asc()).all()
            candidate_rows = [task for task in demo_rows if task.lifecycle_state == "created"]
            inputs = tuple(
                adapt_task_for_optimization(
                    _serialize_task(task),
                    estimated_duration_unit=task.estimated_duration_unit,
                    duration_source=task.estimated_duration_source,
                )
                for task in candidate_rows
            )
            actions = tuple(RLScheduler().available_actions)
            matrix = build_prediction_matrix(
                PredictionEngine(), behavior, inputs, actions, development_demo=True
            )
            report["prediction_matrix_status"] = "READY_DEVELOPMENT_DEMO" if len(matrix.cells) == len(inputs) * len(actions) else "INVALID"
            report["matrix_dimensions"] = {"tasks": len(matrix.task_ids), "candidate_hours": len(matrix.candidate_hours), "cells": len(matrix.cells)}
            report["matrix_model_version"] = matrix.model_version
            report["nontriviality_status"] = matrix.nontriviality
            report["assignment_contrast"] = matrix.assignment_contrast
            if matrix.nontriviality != "PASS":
                report["remaining_blocker"] = "Real lifecycle-derived demo predictions do not establish assignment interaction; optimizer and quantum stages were not run."
                return report

            optimizer = ClassicalOptimizer(allow_test_matrices=True)
            classical = optimizer.optimize(matrix)
            report["classical_optimization_status"] = "FEASIBLE_DEMO_CANDIDATE"
            report["classical_objective"] = classical.total_objective
            builder = AssignmentQuboIsingBuilder(allow_test_matrices=True)
            formulation = builder.build(matrix)
            report["qubo_ising_status"] = "BUILT_DEMO_ONLY"
            report["qubo_variable_count"] = len(formulation.variable_mapping)
            suitability = QuantumSuitabilityAnalyzer().assess(
                matrix, classical, formulation, allow_test_mode=True
            )
            report["quantum_suitability_status"] = suitability.status
            report["quantum_suitability_reasons"] = list(suitability.reasons)
            report["quantum_variable_count"] = suitability.variable_count
            if suitability.status != "SUITABLE":
                report["qaoa_status"] = "NOT_RUN_GATE_" + suitability.status
                report["hybrid_status"] = "NOT_RUN_NO_QUANTUM_CANDIDATE"
                report["executive_cognitive_brain_status"] = "NOT_RUN_NO_HYBRID_COMPARISON"
                report["remaining_blocker"] = "; ".join(suitability.reasons)
                return report

            quantum = AssignmentQAOASolver(allow_test_mode=True).solve(formulation, matrix)
            report["qaoa_status"] = quantum.status
            if quantum.status != "CANDIDATE":
                report["remaining_blocker"] = quantum.reason or f"QAOA returned {quantum.status}."
                return report
            comparison = HybridComparator().compare(
                matrix, classical, quantum, formulation=formulation, allow_test_mode=True
            )
            report["hybrid_status"] = comparison.status
            if comparison.status != "COMPARED":
                report["remaining_blocker"] = "; ".join(comparison.reasons)
                return report
            evidence = comparison.to_dict()
            tasks_for_executive = [_serialize_task(task) for task in candidate_rows]
            executive = ExecutiveCognitiveBrain().execute_planning_request(
                tasks_for_executive,
                user_id=DEMO_USER_ID,
                behavior_patterns={},
                optimization_evidence=evidence,
            )
            report["executive_cognitive_brain_status"] = "RECEIVED_DEMO_COMPARISON_EVIDENCE"
            report["executive_recommendation"] = executive.get("recommended_plan")
            return report
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-development-demo", action="store_true", help="confirm isolated development/demo data generation")
    args = parser.parse_args(argv)
    if not args.confirm_development_demo:
        parser.error("--confirm-development-demo is required")
    try:
        from backend.app.database.db import DEFAULT_SQLITE_PATH, get_database_url

        validate_demo_environment(
            dict(os.environ),
            configured_database_url=get_database_url(),
            default_database_path=DEFAULT_SQLITE_PATH,
            demo_database_path=DEMO_DATABASE,
        )
        configured_url = get_database_url()
        configured_path = Path(make_url(configured_url).database).resolve()
        protected_paths = {DEFAULT_SQLITE_PATH.resolve(), configured_path}
        original_before = {path: _database_fingerprint(path) for path in protected_paths}
        report = run_demo_readiness()
        original_after = {path: _database_fingerprint(path) for path in protected_paths}
        original_unchanged = original_before == original_after
        report["original_app_database_unchanged"] = original_unchanged
        report["protected_database_task_rows"] = {
            str(path): {"before": original_before[path][0], "after": original_after[path][0]}
            for path in sorted(protected_paths)
        }
        report["demo_database"] = str(DEMO_DATABASE)
        report["model_artifact_directory"] = str(DEMO_MODEL_DIRECTORY)
        print(json.dumps(report, indent=2, default=str))
        if not original_unchanged:
            print("ERROR: original application database fingerprint changed", file=sys.stderr)
            return 3
        return 0 if report.get("seed_status") == "IDEMPOTENT_DEMO_SEEDED" else 2
    except Exception as exc:
        # Do not expose configured URLs, environment values, or credential data.
        print(json.dumps({"status": "BLOCKED", "reason": f"{type(exc).__name__}: {exc}"}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
