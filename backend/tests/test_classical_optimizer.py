from __future__ import annotations

from dataclasses import replace
import math

import pytest

from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.optimization_input_contract import (
    OptimizationTaskInput,
    PredictionEligibility,
    normalize_duration,
)
from backend.app.domain.prediction_matrix import (
    SyntheticTestPredictionCell,
    build_prediction_matrix,
    create_synthetic_test_matrix,
    validate_synthetic_test_matrix,
)
from backend.app.engines.optimization_engine import OptimizationEngine


def test_maximum_weight_assignment_matches_independent_reference() -> None:
    matrix = create_synthetic_test_matrix(
        ["task-a", "task-b"], [9, 10],
        [("task-a", 9, 90), ("task-a", 10, 20), ("task-b", 9, 10), ("task-b", 10, 80)],
    )
    optimizer = ClassicalOptimizer(allow_test_matrices=True)

    result = optimizer.optimize(matrix)
    reference = optimizer.reference_optimize(matrix)

    assert [(a.task_id, a.assigned_hour) for a in result.assignments] == [("task-a", 9), ("task-b", 10)]
    assert result.total_objective == pytest.approx(170)
    assert result.total_objective == pytest.approx(reference.total_objective)
    assert result.feasibility is True
    assert result.constraint_violations == ()
    assert result.mode == "TEST/SYNTHETIC"
    assert result.input_provenance["label"] == "TEST/SYNTHETIC"
    assert result.input_provenance["model_version"] is None
    assert result.solver == "deterministic_hungarian_assignment"
    assert math.isfinite(result.runtime_seconds) and result.runtime_seconds >= 0


def test_one_task_and_unequal_task_hour_counts_are_supported() -> None:
    one = create_synthetic_test_matrix(["only"], [7, 8], [("only", 7, 5), ("only", 8, 95)])
    result = ClassicalOptimizer(allow_test_matrices=True).optimize(one)
    assert [(a.task_id, a.assigned_hour) for a in result.assignments] == [("only", 8)]
    assert result.total_objective == 95

    two_of_three = create_synthetic_test_matrix(
        ["a", "b"], [6, 7, 8],
        [("a", 6, 90), ("a", 7, 70), ("a", 8, 20),
         ("b", 6, 80), ("b", 7, 10), ("b", 8, 60)],
    )
    result = ClassicalOptimizer(allow_test_matrices=True).optimize(two_of_three)
    assert len(result.assignments) == 2
    assert len({a.assigned_hour for a in result.assignments}) == 2
    assert result.total_objective == pytest.approx(150)


def test_output_is_deterministic_and_reference_is_independent() -> None:
    matrix = create_synthetic_test_matrix(
        ["b", "a"], [10, 9],
        [("a", 9, 50), ("a", 10, 50), ("b", 9, 50), ("b", 10, 50)],
    )
    optimizer = ClassicalOptimizer(allow_test_matrices=True)
    first = optimizer.optimize(matrix)
    second = optimizer.optimize(matrix)
    reference = optimizer.reference_optimize(matrix)
    assert first.assignments == second.assignments
    assert first.total_objective == second.total_objective == reference.total_objective == 100
    assert first.mode == "TEST/SYNTHETIC"


def test_synthetic_matrix_cannot_be_used_in_production_mode() -> None:
    matrix = create_synthetic_test_matrix(["a"], [9], [("a", 9, 50)])
    with pytest.raises(ValueError, match="explicit test-mode"):
        ClassicalOptimizer().optimize(matrix)


def test_optimizer_revalidates_incomplete_or_tampered_matrices() -> None:
    matrix = create_synthetic_test_matrix(
        ["a", "b"], [9, 10],
        [("a", 9, 80), ("a", 10, 60), ("b", 9, 40), ("b", 10, 70)],
    )
    incomplete = replace(matrix, cells=matrix.cells[:-1])
    with pytest.raises(ValueError, match="incomplete"):
        ClassicalOptimizer(allow_test_matrices=True).optimize(incomplete)

    mismarked = replace(matrix, nontriviality="PASS", assignment_contrast=999.0)
    with pytest.raises(ValueError, match="derived fields"):
        ClassicalOptimizer(allow_test_matrices=True).optimize(mismarked)


def test_synthetic_matrix_rejects_duplicate_ids_hours_missing_cells_and_bad_scores() -> None:
    with pytest.raises(ValueError, match="unique"):
        create_synthetic_test_matrix(["a", "a"], [9, 10], [])
    with pytest.raises(ValueError, match="unique"):
        create_synthetic_test_matrix(["a"], [9, 9], [])
    with pytest.raises(ValueError, match="incomplete"):
        create_synthetic_test_matrix(["a"], [9, 10], [("a", 9, 20)])
    for invalid_score in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite"):
            create_synthetic_test_matrix(["a"], [9], [("a", 9, invalid_score)])


def test_synthetic_matrix_rejects_unmarked_or_unsupported_provenance() -> None:
    cell = SyntheticTestPredictionCell("a", 9, 50, provenance_label="PRODUCTION")
    with pytest.raises(ValueError, match="TEST/SYNTHETIC"):
        validate_synthetic_test_matrix([cell], ["a"], [9])

    matrix = create_synthetic_test_matrix(["a"], [9], [("a", 9, 50)])
    invalid_cell = replace(matrix.cells[0], score_unit="unknown")
    with pytest.raises(ValueError, match="score unit"):
        validate_synthetic_test_matrix([invalid_cell], ["a"], [9])


def test_production_optimizer_rejects_synthetic_cells_even_if_mode_is_changed() -> None:
    matrix = create_synthetic_test_matrix(["a"], [9], [("a", 9, 50)])
    production_labeled = replace(matrix, mode="PRODUCTION")
    with pytest.raises(ValueError, match="PredictionResult provenance"):
        ClassicalOptimizer().optimize(production_labeled)


def test_existing_optimization_stage_reports_not_ready_without_production_matrix() -> None:
    result = OptimizationEngine().optimize_prediction_matrix(None)
    assert result == {
        "status": "NOT_READY",
        "candidate": None,
        "mode": "PRODUCTION",
        "reason": "validated prediction matrix is unavailable",
    }


def test_nontriviality_is_calculated_but_test_mode_never_claims_production() -> None:
    matrix = create_synthetic_test_matrix(
        ["a", "b"], [9, 10],
        [("a", 9, 90), ("a", 10, 10), ("b", 9, 10), ("b", 10, 90)],
    )
    result = ClassicalOptimizer(allow_test_matrices=True).optimize(matrix)
    assert matrix.nontriviality == "PASS"
    assert matrix.optimizer_eligible is False
    assert result.input_provenance["nontriviality_claim"] == "TEST_ONLY_NOT_PRODUCTION_EVIDENCE"


@pytest.mark.parametrize(
    ("lifecycle_state", "completed"),
    [("started", False), ("completed", True)],
)
def test_matrix_builder_rejects_unsupported_task_states(lifecycle_state, completed) -> None:
    task = OptimizationTaskInput(
        task_id="task-a",
        task_type="coding",
        priority=3,
        estimated_duration=normalize_duration(60, "minutes", "test_fixture"),
        lifecycle_state=lifecycle_state,
        completed=completed,
        outcome_valid=None,
        prediction_eligibility=PredictionEligibility.MODEL_FEATURE_UNIT_UNVERIFIED,
    )
    with pytest.raises(ValueError, match="created-task"):
        build_prediction_matrix(None, None, [task], [9])
