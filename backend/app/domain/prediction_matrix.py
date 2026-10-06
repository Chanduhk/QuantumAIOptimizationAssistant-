"""Validated production, development/demo, and synthetic test matrices."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Sequence

from backend.app.domain.optimization_input_contract import OptimizationTaskInput
from backend.app.domain.prediction_provenance import PredictionResult, PredictionStatus
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine


@dataclass(frozen=True)
class SyntheticTestPredictionCell:
    """Algorithm-test score with no claim of model provenance or user data."""

    task_id: int | str
    candidate_start_hour: int
    value: float
    score_unit: str = "productivity_points"
    provenance_label: str = "TEST/SYNTHETIC"


@dataclass(frozen=True)
class PredictionMatrix:
    task_ids: tuple[int | str, ...]
    candidate_hours: tuple[int, ...]
    cells: tuple[PredictionResult | SyntheticTestPredictionCell, ...]
    model_version: str | None
    feature_schema_version: str | None
    target_schema_version: str | None
    nontriviality: str
    assignment_contrast: float | None
    mode: str = "PRODUCTION"

    @property
    def optimizer_eligible(self) -> bool:
        return self.mode == "PRODUCTION" and self.nontriviality == "PASS"

    def score(self, task_id: int | str, candidate_hour: int) -> float:
        for cell in self.cells:
            if cell.task_id == task_id and cell.candidate_start_hour == candidate_hour:
                return float(cell.value)
        raise KeyError((task_id, candidate_hour))


def build_prediction_matrix(
    prediction_engine: PredictionEngine,
    behavior_engine: BehaviorIntelligenceEngine,
    tasks: Sequence[OptimizationTaskInput],
    candidate_hours: Iterable[int],
    *,
    development_demo: bool = False,
) -> PredictionMatrix:
    """Evaluate every task/hour pair using a compatible trained model only."""
    task_tuple = tuple(tasks)
    hours = tuple(candidate_hours)
    if not task_tuple or any(not isinstance(task, OptimizationTaskInput) for task in task_tuple):
        raise ValueError("tasks must be non-empty OptimizationTaskInput records")
    _validate_problem_dimensions(tuple(task.task_id for task in task_tuple), hours)
    if any(
        task.completed
        or task.lifecycle_state != "created"
        or not task.estimated_duration.optimizer_eligible
        for task in task_tuple
    ):
        raise ValueError("tasks must be eligible created-task inputs with explicit duration provenance")

    cells = tuple(
        prediction_engine.predict_task_hour_with_provenance(
            behavior_engine,
            task_id=task.task_id,
            candidate_start_hour=hour,
            task_type=task.task_type,
            duration=task.estimated_duration,
        )
        for task in sorted(task_tuple, key=lambda item: str(item.task_id))
        for hour in sorted(hours)
    )
    if development_demo:
        if any(not task.estimated_duration.source.startswith("f96_development_demo:") for task in task_tuple):
            raise ValueError("development/demo matrix requires explicitly namespaced demo task estimates")
        return validate_development_demo_matrix(cells, tuple(task.task_id for task in task_tuple), hours)
    return validate_prediction_matrix(cells, tuple(task.task_id for task in task_tuple), hours)


def validate_prediction_matrix(
    predictions: Iterable[PredictionResult],
    task_ids: Sequence[int | str],
    candidate_hours: Sequence[int],
    *,
    epsilon: float = 1e-9,
    development_demo: bool = False,
) -> PredictionMatrix:
    """Validate a complete production matrix and measure assignment interaction."""
    tasks = tuple(task_ids)
    hours = tuple(candidate_hours)
    _validate_problem_dimensions(tasks, hours)
    if isinstance(epsilon, bool) or not isinstance(epsilon, (int, float)) or not math.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("epsilon must be positive and finite")

    cells = tuple(predictions)
    if len(cells) != len(tasks) * len(hours):
        raise ValueError("prediction matrix is incomplete")
    by_pair: dict[tuple[int | str, int], PredictionResult] = {}
    demo_cells = [
        cell for cell in cells
        if isinstance(cell, PredictionResult)
        and cell.duration_input is not None
        and cell.duration_input.source.startswith("f96_development_demo:")
    ]
    if demo_cells and (not development_demo or len(demo_cells) != len(cells)):
        raise ValueError("development/demo predictions cannot be labeled as production or mixed with other provenance")
    if development_demo and len(demo_cells) != len(cells):
        raise ValueError("development/demo matrix requires explicitly namespaced duration provenance")
    for cell in cells:
        if not isinstance(cell, PredictionResult):
            raise ValueError("production matrix cells require PredictionResult provenance")
        pair = (cell.task_id, cell.candidate_start_hour)
        if pair in by_pair:
            raise ValueError("prediction matrix contains duplicate task/hour cells")
        if cell.status is not PredictionStatus.TRAINED_MODEL or not cell.validity:
            raise ValueError("only valid trained-model predictions may enter a production optimizer matrix")
        if cell.model_trained is not True or cell.fallback_used:
            raise ValueError("production matrix requires a trained model and no fallback prediction")
        if cell.history_count_status != "AVAILABLE" or cell.history_count is None or cell.history_count < 5:
            raise ValueError("production matrix requires at least 5 verified training samples")
        if cell.optimizer_eligibility != "ELIGIBLE_HEURISTIC_PROXY":
            raise ValueError("prediction is not eligible under the model provenance contract")
        if cell.value is None or not math.isfinite(float(cell.value)):
            raise ValueError("prediction value must be finite")
        if cell.duration_input is None or not cell.duration_input.optimizer_eligible:
            raise ValueError("prediction duration provenance is required")
        if not cell.model_version or not cell.feature_schema_version or not cell.target_schema_version:
            raise ValueError("versioned model and schema provenance is required")
        if cell.model_version_status != "AVAILABLE":
            raise ValueError("model version provenance is unavailable")
        by_pair[pair] = cell
    expected = {(task_id, hour) for task_id in tasks for hour in hours}
    if set(by_pair) != expected:
        raise ValueError("prediction matrix task/hour identities do not match the requested domain")

    versions = {(c.model_version, c.feature_schema_version, c.target_schema_version) for c in cells}
    if len(versions) != 1:
        raise ValueError("prediction matrix mixes model or schema versions")
    if len({cell.history_count for cell in cells}) != 1:
        raise ValueError("prediction matrix mixes training sample evidence")
    version, feature_schema, target_schema = next(iter(versions))
    nontriviality, contrast = _assignment_interaction(by_pair, tasks, hours, epsilon)
    return PredictionMatrix(
        task_ids=tasks,
        candidate_hours=hours,
        cells=tuple(sorted(cells, key=lambda c: (str(c.task_id), c.candidate_start_hour))),
        model_version=str(version),
        feature_schema_version=str(feature_schema),
        target_schema_version=str(target_schema),
        nontriviality=nontriviality,
        assignment_contrast=contrast,
        mode="DEVELOPMENT/DEMO" if development_demo else "PRODUCTION",
    )


def create_synthetic_test_matrix(
    task_ids: Sequence[int | str],
    candidate_hours: Sequence[int],
    scores: Iterable[tuple[int | str, int, float]],
) -> PredictionMatrix:
    """Construct a matrix explicitly labeled TEST/SYNTHETIC for solver tests."""
    tasks = tuple(task_ids)
    hours = tuple(candidate_hours)
    _validate_problem_dimensions(tasks, hours)
    cells = tuple(
        SyntheticTestPredictionCell(task_id, hour, _test_score(score))
        for task_id, hour, score in scores
    )
    return validate_synthetic_test_matrix(cells, tasks, hours)


def validate_synthetic_test_matrix(
    predictions: Iterable[SyntheticTestPredictionCell],
    task_ids: Sequence[int | str],
    candidate_hours: Sequence[int],
    *,
    epsilon: float = 1e-9,
) -> PredictionMatrix:
    """Validate mechanics-only test scores; never marks them production eligible."""
    tasks = tuple(task_ids)
    hours = tuple(candidate_hours)
    _validate_problem_dimensions(tasks, hours)
    if isinstance(epsilon, bool) or not isinstance(epsilon, (int, float)) or not math.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("epsilon must be positive and finite")
    cells = tuple(predictions)
    if len(cells) != len(tasks) * len(hours):
        raise ValueError("prediction matrix is incomplete")
    by_pair: dict[tuple[int | str, int], SyntheticTestPredictionCell] = {}
    for cell in cells:
        if not isinstance(cell, SyntheticTestPredictionCell) or cell.provenance_label != "TEST/SYNTHETIC":
            raise ValueError("test matrix cells must be explicitly marked TEST/SYNTHETIC")
        if cell.score_unit != "productivity_points":
            raise ValueError("test score unit must be productivity_points")
        _test_score(cell.value)
        pair = (cell.task_id, cell.candidate_start_hour)
        if pair in by_pair:
            raise ValueError("prediction matrix contains duplicate task/hour cells")
        by_pair[pair] = cell
    expected = {(task_id, hour) for task_id in tasks for hour in hours}
    if set(by_pair) != expected:
        raise ValueError("prediction matrix task/hour identities do not match the requested domain")
    nontriviality, contrast = _assignment_interaction(by_pair, tasks, hours, epsilon)
    return PredictionMatrix(
        task_ids=tasks,
        candidate_hours=hours,
        cells=tuple(sorted(cells, key=lambda c: (str(c.task_id), c.candidate_start_hour))),
        model_version=None,
        feature_schema_version=None,
        target_schema_version=None,
        nontriviality=nontriviality,
        assignment_contrast=contrast,
        mode="TEST/SYNTHETIC",
    )


def validate_development_demo_matrix(
    predictions: Iterable[PredictionResult],
    task_ids: Sequence[int | str],
    candidate_hours: Sequence[int],
    *,
    epsilon: float = 1e-9,
) -> PredictionMatrix:
    """Validate real model predictions sourced only from the isolated demo namespace.

    This reuses the strict trained-model production-cell checks but preserves a
    distinct mode so demo evidence cannot be mislabeled as production or as
    synthetic solver fixtures.
    """
    from dataclasses import replace

    matrix = validate_prediction_matrix(
        predictions, task_ids, candidate_hours, epsilon=epsilon, development_demo=True
    )
    if any(
        cell.duration_input is None
        or not cell.duration_input.source.startswith("f96_development_demo:")
        for cell in matrix.cells
        if isinstance(cell, PredictionResult)
    ):
        raise ValueError("development/demo predictions require namespaced duration provenance")
    return matrix


def _validate_problem_dimensions(task_ids: tuple[int | str, ...], hours: tuple[int, ...]) -> None:
    if not task_ids or len(set(task_ids)) != len(task_ids):
        raise ValueError("task IDs must be non-empty and unique")
    if any(isinstance(task_id, bool) or not isinstance(task_id, (int, str)) or not str(task_id).strip() for task_id in task_ids):
        raise ValueError("task IDs must be non-empty strings or integers")
    if any(isinstance(task_id, int) and task_id <= 0 for task_id in task_ids):
        raise ValueError("integer task IDs must be positive")
    if not hours or len(set(hours)) != len(hours):
        raise ValueError("candidate hours must be non-empty and unique")
    if any(isinstance(hour, bool) or not isinstance(hour, int) or not 6 <= hour <= 22 for hour in hours):
        raise ValueError("candidate hours must be integer actions in the range 6..22")
    if len(task_ids) > len(hours):
        raise ValueError("task count cannot exceed candidate-hour count")


def _test_score(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("prediction score must be finite")
    if not 0.0 <= float(value) <= 100.0:
        raise ValueError("prediction score must be within 0..100")
    return float(value)


def _assignment_interaction(by_pair, tasks, hours, epsilon: float) -> tuple[str, float | None]:
    for task_a, task_b in combinations(tasks, 2):
        for hour_a, hour_b in combinations(hours, 2):
            delta = (
                float(by_pair[(task_a, hour_a)].value)
                + float(by_pair[(task_b, hour_b)].value)
                - float(by_pair[(task_a, hour_b)].value)
                - float(by_pair[(task_b, hour_a)].value)
            )
            if abs(delta) > epsilon:
                return "PASS", delta
    return "NOT_PROVEN", None
