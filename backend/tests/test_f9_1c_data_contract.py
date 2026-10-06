from __future__ import annotations

import ast
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.domain.optimization_input_contract import (
    DurationUnit,
    OptimizationInputError,
    adapt_task_for_optimization,
    classify_legacy_duration,
    normalize_duration,
    validate_unique_task_ids,
)
from backend.app.domain.prediction_provenance import PredictionResult, PredictionStatus
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.models.base import Base
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
from backend.app.services.task_lifecycle_service import TaskLifecycleService


def test_normalizes_minutes_to_hours_and_preserves_provenance() -> None:
    duration = normalize_duration(90, DurationUnit.MINUTES, "new_task_form_minutes")

    assert duration.original_value == 90.0
    assert duration.original_unit is DurationUnit.MINUTES
    assert duration.normalized_hours == 1.5
    assert duration.source == "new_task_form_minutes"
    assert duration.conversion_applied == "minutes_to_hours_divide_by_60"
    assert duration.optimizer_eligible is True


def test_normalizes_hours_to_hours() -> None:
    duration = normalize_duration(1.25, "hours", "explicit_internal_hours")

    assert duration.normalized_hours == 1.25
    assert duration.conversion_applied == "identity_hours"


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), -float("inf"), "60"])
def test_rejects_non_positive_or_non_finite_durations(value: object) -> None:
    with pytest.raises(OptimizationInputError):
        normalize_duration(value, "minutes", "test_input")


def test_rejects_unknown_duration_unit() -> None:
    with pytest.raises(OptimizationInputError, match="unknown-unit"):
        normalize_duration(60, "unknown", "legacy_task")


def test_classifies_legacy_duration_without_changing_raw_value() -> None:
    legacy = {"estimated_duration": 60.0}
    raw_before = dict(legacy)

    classified = classify_legacy_duration(legacy["estimated_duration"])

    assert legacy == raw_before
    assert classified.original_value == 60.0
    assert classified.original_unit is DurationUnit.UNKNOWN
    assert classified.optimizer_eligible is False


def test_optimizer_adapter_rejects_unknown_legacy_estimate() -> None:
    with pytest.raises(OptimizationInputError) as error:
        adapt_task_for_optimization(
            {
                "id": 1,
                "task_type": "study",
                "priority": 3,
                "estimated_duration": 60.0,
                "lifecycle_state": "created",
                "completed": False,
            },
            estimated_duration_unit=None,
            duration_source=None,
        )

    assert error.value.code == "LEGACY_UNTYPED_DURATION"


def test_optimizer_adapter_does_not_substitute_actual_duration() -> None:
    with pytest.raises(OptimizationInputError) as error:
        adapt_task_for_optimization(
            {
                "id": 1,
                "task_type": "study",
                "priority": 3,
                "estimated_duration": None,
                "actual_duration": 45.0,
                "lifecycle_state": "created",
                "completed": False,
            },
            estimated_duration_unit="minutes",
            duration_source="new_task_form_minutes",
        )

    assert error.value.code == "MISSING_ESTIMATE"


def test_optimizer_adapter_marks_legacy_model_feature_unit_unverified() -> None:
    task = adapt_task_for_optimization(
        {
            "id": 1,
            "task_type": "study",
            "priority": 3,
            "estimated_duration": 60.0,
            "lifecycle_state": "created",
            "completed": False,
            "outcome_valid": None,
        },
        estimated_duration_unit="minutes",
        duration_source="new_task_form_minutes",
    )

    assert task.estimated_duration.normalized_hours == 1.0
    assert task.prediction_eligibility.value == "MODEL_FEATURE_UNIT_UNVERIFIED"


def test_optimizer_adapter_rejects_invalid_task_identity_and_duplicate_ids() -> None:
    raw = {
        "id": 1,
        "task_type": "study",
        "priority": 3,
        "estimated_duration": 60.0,
        "lifecycle_state": "created",
        "completed": False,
    }
    first = adapt_task_for_optimization(
        raw, estimated_duration_unit="minutes", duration_source="explicit_test_input"
    )
    duplicate = adapt_task_for_optimization(
        {**raw, "id": 1}, estimated_duration_unit="minutes", duration_source="explicit_test_input"
    )
    with pytest.raises(OptimizationInputError) as error:
        validate_unique_task_ids([first, duplicate])
    assert error.value.code == "DUPLICATE_TASK_ID"

    with pytest.raises(OptimizationInputError) as error:
        adapt_task_for_optimization(
            {**raw, "id": None}, estimated_duration_unit="minutes", duration_source="explicit_test_input"
        )
    assert error.value.code == "INVALID_TASK_ID"


@pytest.mark.parametrize(
    ("state", "completed", "code"),
    [
        ("started", False, "STARTED_TASK_NOT_SUPPORTED"),
        ("completed", True, "COMPLETED_TASK_NOT_ELIGIBLE"),
        ("created", True, "COMPLETED_TASK_NOT_ELIGIBLE"),
    ],
)
def test_optimizer_adapter_rejects_started_and_completed_tasks(state: str, completed: bool, code: str) -> None:
    with pytest.raises(OptimizationInputError) as error:
        adapt_task_for_optimization(
            {
                "id": 7,
                "task_type": "study",
                "priority": 3,
                "estimated_duration": 60.0,
                "lifecycle_state": state,
                "completed": completed,
            },
            estimated_duration_unit="minutes",
            duration_source="explicit_test_input",
        )
    assert error.value.code == code


def test_lifecycle_stores_actual_duration_as_elapsed_minutes() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    service = TaskLifecycleService(session)
    created = datetime(2026, 2, 1, 9, 0, 0)
    task = service.create_task(
        user_id=1,
        title="contract test",
        task_type="study",
        priority=3,
        estimated_duration=60.0,
        created_at=created,
    )
    service.start_task(task_id=task.id, started_at=created)

    completed = service.complete_task(task_id=task.id, completed_at=created + timedelta(minutes=90))

    assert completed.actual_duration == 90.0
    session.close()
    engine.dispose()


class _FakeProductivityModel:
    def __init__(self, *, trained: bool, history_shape: tuple[int, int] | None = None, value: float = 80.0) -> None:
        self.is_trained = trained
        self.training_data_shape = history_shape
        self.value = value
        self.calls: list[dict[str, object]] = []

    def predict(self, hour: int, task_type: str, duration: float) -> float:
        self.calls.append({"hour": hour, "task_type": task_type, "duration": duration})
        return self.value


def _prediction(engine: BehaviorIntelligenceEngine):
    return PredictionEngine().predict_task_hour_with_provenance(
        engine,
        task_id=3,
        candidate_start_hour=10,
        task_type="study",
        duration=normalize_duration(60, "minutes", "explicit_task_estimate"),
    )


def test_cold_start_prediction_is_explicit_heuristic_provenance() -> None:
    behavior = BehaviorIntelligenceEngine(session=None)
    behavior.productivity_model = _FakeProductivityModel(trained=False)
    behavior.behavior_data_df = pd.DataFrame()
    result = _prediction(behavior)

    assert result.status is PredictionStatus.COLD_START_HEURISTIC
    assert result.prediction_source is PredictionStatus.COLD_START_HEURISTIC
    assert result.model_trained is False
    assert result.history_count == 0
    assert result.fallback_used is True
    assert result.model_version is None
    assert result.optimizer_eligibility == "COLD_START_NOT_ELIGIBLE"
    assert result.value == 85.0  # existing hour-only fallback at hour 10
    assert result.model_version_status == "MODEL_VERSION_NOT_AVAILABLE"


def test_trained_prediction_reports_available_training_count_but_is_not_optimizer_safe() -> None:
    behavior = BehaviorIntelligenceEngine(session=None)
    model = _FakeProductivityModel(trained=True, history_shape=None, value=83.5)
    behavior.productivity_model = model
    result = _prediction(behavior)

    assert result.status is PredictionStatus.TRAINED_MODEL
    assert result.model_trained is True
    assert result.history_count is None
    assert result.history_count_status == "UNAVAILABLE"
    assert result.model_version is None
    assert result.model_version_status == "MODEL_VERSION_NOT_AVAILABLE"
    assert result.optimizer_eligibility == "MODEL_FEATURE_UNIT_UNVERIFIED"
    assert model.calls == [{"hour": 10, "task_type": "study", "duration": 1.0}]


def test_history_count_and_model_version_remain_unavailable_when_absent() -> None:
    behavior = BehaviorIntelligenceEngine(session=None)
    behavior.productivity_model = _FakeProductivityModel(trained=True, history_shape=None)
    result = _prediction(behavior)

    assert result.history_count is None
    assert result.history_count_status == "UNAVAILABLE"
    assert result.model_version is None


def test_prediction_contract_rejects_inconsistent_provenance() -> None:
    duration = normalize_duration(60, "minutes", "explicit_test_input")
    with pytest.raises(ValueError, match="cold-start provenance"):
        PredictionResult(
            task_id=3,
            candidate_start_hour=10,
            value=80.0,
            score_unit="productivity_points",
            prediction_source=PredictionStatus.COLD_START_HEURISTIC,
            model_trained=True,
            history_count=1,
            history_count_status="AVAILABLE",
            model_version=None,
            model_version_status="MODEL_VERSION_NOT_AVAILABLE",
            fallback_used=True,
            duration_input=duration,
            validity=True,
            status=PredictionStatus.COLD_START_HEURISTIC,
            optimizer_eligibility="COLD_START_HEURISTIC",
        )


def test_prediction_engine_marks_invalid_inputs_without_fabricating_score() -> None:
    behavior = BehaviorIntelligenceEngine(session=None)
    result = PredictionEngine().predict_task_hour_with_provenance(
        behavior,
        task_id=3,
        candidate_start_hour=10,
        task_type="",
        duration=normalize_duration(60, "minutes", "explicit_test_input"),
    )

    assert result.status is PredictionStatus.INVALID_INPUT
    assert result.value is None
    assert result.validity is False
    assert result.model_version is None


def test_invalid_prediction_value_is_not_reported_as_valid() -> None:
    with pytest.raises(ValueError, match="unavailable or invalid"):
        PredictionResult(
            task_id=3,
            candidate_start_hour=10,
            value=80.0,
            score_unit="productivity_points",
            prediction_source=PredictionStatus.INVALID_INPUT,
            model_trained=None,
            history_count=None,
            history_count_status="UNAVAILABLE",
            model_version=None,
            model_version_status="MODEL_VERSION_NOT_AVAILABLE",
            fallback_used=False,
            duration_input=None,
            validity=True,
            status=PredictionStatus.INVALID_INPUT,
            optimizer_eligibility="INVALID_INPUT",
        )


def test_task_api_legacy_estimated_duration_field_remains_unchanged() -> None:
    source = Path(__file__).parents[1].joinpath("main.py").read_text(encoding="utf-8-sig")
    module = ast.parse(source)
    task_request = next(
        node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "TaskCreateRequest"
    )
    fields = {
        node.target.id
        for node in task_request.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    route_paths = {
        decorator.args[0].value
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr in {"get", "post"}
        and decorator.args
        and isinstance(decorator.args[0], ast.Constant)
    }
    assert "estimated_duration" in fields
    assert "estimated_duration_unit" in fields
    assert "actual_duration" not in fields
    assert "/api/v1/tasks" in route_paths
    assert "/api/v1/tasks/{task_id}" in route_paths
