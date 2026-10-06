from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.optimization_input_contract import adapt_task_for_optimization
from backend.app.domain.prediction_matrix import build_prediction_matrix, validate_prediction_matrix
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
from backend.app.services.task_lifecycle_service import TaskLifecycleService
from backend.scripts.seed_optimization_demo_data import (
    DEMO_SOURCE,
    DEMO_USER_ID,
    _serialize_task,
    seed_demo_tasks,
    validate_demo_environment,
)


def _database(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'demo.sqlite').as_posix()}", future=True)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False, future=True)


def test_demo_environment_requires_explicit_mode_and_rejects_production(tmp_path):
    app_db = tmp_path / "app.sqlite"
    demo_db = tmp_path / "demo.sqlite"
    kwargs = {
        "configured_database_url": f"sqlite:///{app_db.as_posix()}",
        "default_database_path": app_db,
        "demo_database_path": demo_db,
    }
    with pytest.raises(RuntimeError, match="QUANTUM_LIFE_DATA_MODE"):
        validate_demo_environment({}, **kwargs)
    with pytest.raises(RuntimeError, match="production"):
        validate_demo_environment(
            {"QUANTUM_LIFE_DATA_MODE": "DEVELOPMENT/DEMO", "APP_ENV": "production"}, **kwargs
        )
    validate_demo_environment({"QUANTUM_LIFE_DATA_MODE": "DEVELOPMENT/DEMO"}, **kwargs)
    other_app_db = tmp_path / "separately-configured-app.sqlite"
    validate_demo_environment(
        {"QUANTUM_LIFE_DATA_MODE": "DEVELOPMENT/DEMO"},
        **{**kwargs, "configured_database_url": f"sqlite:///{other_app_db.as_posix()}"},
    )
    with pytest.raises(RuntimeError, match="configured application database"):
        validate_demo_environment(
            {"QUANTUM_LIFE_DATA_MODE": "DEVELOPMENT/DEMO"},
            **{**kwargs, "configured_database_url": f"sqlite:///{demo_db.as_posix()}"},
        )
    with pytest.raises(RuntimeError, match="non-SQLite"):
        validate_demo_environment(
            {"QUANTUM_LIFE_DATA_MODE": "DEVELOPMENT/DEMO"},
            **{**kwargs, "configured_database_url": "postgresql://user:secret@host/database"},
        )


def test_demo_seeding_is_idempotent_and_outcomes_are_lifecycle_generated(tmp_path):
    engine, factory = _database(tmp_path)
    try:
        with factory() as session:
            lifecycle = TaskLifecycleService(session)
            sentinel = lifecycle.create_task(
                user_id=42,
                title="unrelated pre-existing row",
                task_type="other",
                priority=2,
                estimated_duration=20,
                estimated_duration_unit="minutes",
                estimated_duration_source="test_sentinel",
                created_at=datetime(2026, 9, 1),
            )
            sentinel_snapshot = (sentinel.id, sentinel.title, sentinel.actual_duration, sentinel.lifecycle_state)
            first = seed_demo_tasks(session, now=datetime(2026, 9, 20, tzinfo=timezone.utc))
            second = seed_demo_tasks(session, now=datetime(2026, 9, 20, tzinfo=timezone.utc))
            history = session.query(Task).filter(Task.user_id == DEMO_USER_ID, Task.title.like("%HISTORY%")).all()
            candidates = session.query(Task).filter(Task.user_id == DEMO_USER_ID, Task.title.like("%CANDIDATE%")).all()
            assert first["created_history"] == 10
            assert first["completed_via_lifecycle"] == 10
            assert first["created_candidates"] == 2
            assert second["created_history"] == second["completed_via_lifecycle"] == second["created_candidates"] == 0
            assert len(history) == 10 and len(candidates) == 2
            for task in history:
                assert task.completed is True and task.lifecycle_state == "completed"
                assert task.outcome_valid is True
                assert task.estimated_duration_unit == "minutes"
                assert task.estimated_duration_source == DEMO_SOURCE
                assert task.actual_duration == (task.end_time - task.start_time).total_seconds() / 60
            for task in candidates:
                assert task.lifecycle_state == "created" and task.completed is False
                assert task.actual_duration is None and task.start_time is None
                assert task.estimated_duration_unit == "minutes"
                assert task.estimated_duration_source == DEMO_SOURCE
            unchanged = session.get(Task, sentinel.id)
            assert (unchanged.id, unchanged.title, unchanged.actual_duration, unchanged.lifecycle_state) == sentinel_snapshot
    finally:
        engine.dispose()


def test_existing_trainer_builds_versioned_model_and_complete_demo_matrix(tmp_path):
    engine, factory = _database(tmp_path)
    artifacts = tmp_path / "demo-models"
    try:
        with factory() as session:
            seed_demo_tasks(session, now=datetime(2026, 9, 20, tzinfo=timezone.utc))
            behavior = BehaviorIntelligenceEngine(session, model_directory=str(artifacts))
            raw = behavior.collect_behavior_data(DEMO_USER_ID, days_back=90)
            frame = behavior._build_training_frame()
            assert len(raw) == len(frame) == 10
            metrics = behavior.train_productivity_model()
            model = behavior.productivity_model
            assert model is not None and model.is_trained
            assert model.model_path and (artifacts / Path(model.model_path).name).is_file()
            assert model.metadata["model_version"] == "productivity-rf-v1"
            assert model.metadata["feature_schema_version"] == "productivity-features-v1"
            assert model.metadata["duration_unit"] == "hours"
            assert model.metadata["training_sample_count"] == 10
            assert model.metadata["target_semantics"] == "heuristic_derived_productivity_proxy_not_observed_ground_truth"
            assert "validation_mae" in metrics

            candidates = session.query(Task).filter(
                Task.user_id == DEMO_USER_ID, Task.title.like("%CANDIDATE%")
            ).order_by(Task.id).all()
            inputs = tuple(
                adapt_task_for_optimization(
                    _serialize_task(task),
                    estimated_duration_unit=task.estimated_duration_unit,
                    duration_source=task.estimated_duration_source,
                )
                for task in candidates
            )
            matrix = build_prediction_matrix(
                PredictionEngine(), behavior, inputs, range(6, 23), development_demo=True
            )
            assert matrix.mode == "DEVELOPMENT/DEMO"
            assert len(matrix.cells) == 2 * 17
            assert all(cell.status.value == "TRAINED_MODEL" for cell in matrix.cells)
            assert all(cell.history_count == 10 and cell.model_version == "productivity-rf-v1" for cell in matrix.cells)
            assert all(cell.duration_input.source == DEMO_SOURCE for cell in matrix.cells)
            with pytest.raises(ValueError, match="cannot be labeled as production"):
                validate_prediction_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
            with pytest.raises(ValueError, match="explicit non-production optimizer opt-in"):
                ClassicalOptimizer().optimize(matrix)
    finally:
        engine.dispose()
