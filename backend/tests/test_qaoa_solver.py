from __future__ import annotations

import math

import pytest

from backend.app.domain.assignment_qubo_ising import AssignmentQuboIsingBuilder
from backend.app.domain.prediction_matrix import create_synthetic_test_matrix
from backend.app.domain.qaoa_solver import AssignmentQAOASolver, _approximation_ratio
from backend.app.engines.optimization_engine import OptimizationEngine
from backend.app.quantum.optimization import QAOAConfig, QAOAParameterSet


def _test_problem():
    matrix = create_synthetic_test_matrix(
        ["task-a", "task-b"],
        [9, 10],
        [("task-a", 9, 90), ("task-a", 10, 10), ("task-b", 9, 20), ("task-b", 10, 80)],
    )
    formulation = AssignmentQuboIsingBuilder(allow_test_matrices=True).build(matrix)
    return matrix, formulation


def test_qaoa_consumes_f93_ising_and_reports_classical_qubo_and_original_objectives() -> None:
    matrix, formulation = _test_problem()
    config = QAOAConfig(
        depth=1,
        parameters=QAOAParameterSet((0.11,), (0.27,)),
        shots=512,
        seed=41,
    )
    result = AssignmentQAOASolver(allow_test_mode=True).solve(formulation, matrix, config)
    assert result.status == "CANDIDATE"
    assert result.mode == "TEST/SYNTHETIC"
    assert result.runtime_backend == "local_statevector_simulator"
    assert result.classical_objective == pytest.approx(170)
    assert result.exact_qubo_objective == pytest.approx(170)
    assert result.exact_qubo_energy == pytest.approx(-170)
    assert result.expectation_energy is not None
    assert result.statevector_norm == pytest.approx(1.0)
    assert result.candidate is not None
    assert result.candidate["qubo_energy"] == pytest.approx(result.candidate["ising_energy"])
    assert result.candidate["feasible"] is (not result.candidate["constraint_violations"])
    if result.candidate["feasible"]:
        score = sum(matrix.score(item["task_id"], item["candidate_hour"]) for item in result.candidate["assignments"])
        assert result.candidate["objective_value"] == pytest.approx(score)
        assert result.approximation_ratio == pytest.approx(score / 170)
        assert result.approximation_ratio_status == "DEFINED"
    assert sum(item["probability"] for item in result.measurement_distribution) == pytest.approx(1.0)
    assert result.parameters["seed"] == 41


def test_seeded_qaoa_candidate_is_reproducible() -> None:
    matrix, formulation = _test_problem()
    config = QAOAConfig(depth=1, optimize_parameters=True, max_iterations=7, shots=256, seed=59)
    solver = AssignmentQAOASolver(allow_test_mode=True)
    assert solver.solve(formulation, matrix, config) == solver.solve(formulation, matrix, config)


def test_infeasible_raw_measurement_is_reported_without_repair() -> None:
    matrix = create_synthetic_test_matrix(
        ["only-task"], [9, 10], [("only-task", 9, 80), ("only-task", 10, 20)]
    )
    formulation = AssignmentQuboIsingBuilder(allow_test_matrices=True).build(matrix)
    config = QAOAConfig(
        depth=1,
        parameters=QAOAParameterSet((0.0,), (0.0,)),
        shots=1,
        seed=0,
    )
    result = AssignmentQAOASolver(allow_test_mode=True).solve(formulation, matrix, config)
    assert result.status == "CANDIDATE"
    assert result.candidate["feasible"] is False
    assert result.candidate["repaired"] is False
    assert len(result.candidate["assignments"]) == 2
    assert result.approximation_ratio is None
    assert result.approximation_ratio_status == "INFEASIBLE_CANDIDATE"


def test_test_matrix_needs_opt_in_and_missing_production_data_is_not_ready() -> None:
    matrix, formulation = _test_problem()
    assert AssignmentQAOASolver().solve(formulation, matrix).status == "NOT_READY"
    assert OptimizationEngine().run_qaoa_candidate(None, None)["status"] == "NOT_READY"


def test_optimization_engine_exposes_qaoa_as_an_explicit_stage() -> None:
    matrix, formulation = _test_problem()
    result = OptimizationEngine().run_qaoa_candidate(
        formulation,
        matrix,
        allow_test_mode=True,
        config=QAOAConfig(
            depth=1,
            parameters=QAOAParameterSet((0.11,), (0.27,)),
            shots=64,
            seed=41,
        ),
    )
    assert result["status"] == "CANDIDATE"
    assert result["mode"] == "TEST/SYNTHETIC"


def test_oversized_problem_returns_too_large_without_simulation() -> None:
    hours = list(range(6, 15))
    matrix = create_synthetic_test_matrix(
        ["a"], hours, [("a", hour, float(hour)) for hour in hours]
    )
    formulation = AssignmentQuboIsingBuilder(allow_test_matrices=True).build(matrix)
    result = AssignmentQAOASolver(allow_test_mode=True).solve(
        formulation, matrix, QAOAConfig(max_qubits=9, seed=2)
    )
    assert result.status == "TOO_LARGE"
    assert "9 variables" in result.reason


@pytest.mark.parametrize(
    "config",
    [
        QAOAConfig(depth=4, max_depth=4, seed=2),
        QAOAConfig(max_iterations=26, seed=2),
        QAOAConfig(shots=10_001, max_shots=10_001, seed=2),
    ],
)
def test_unsafe_local_configuration_is_not_supported(config) -> None:
    matrix, formulation = _test_problem()
    result = AssignmentQAOASolver(allow_test_mode=True).solve(formulation, matrix, config)
    assert result.status == "NOT_SUPPORTED"


def test_mismatched_formulation_is_rejected() -> None:
    matrix, _ = _test_problem()
    other = create_synthetic_test_matrix(
        ["task-a", "task-b"], [9, 10],
        [("task-a", 9, 10), ("task-a", 10, 90), ("task-b", 9, 80), ("task-b", 10, 20)],
    )
    wrong_formulation = AssignmentQuboIsingBuilder(allow_test_matrices=True).build(other)
    result = AssignmentQAOASolver(allow_test_mode=True).solve(wrong_formulation, matrix)
    assert result.status == "INVALID_INPUT"
    assert "does not match" in result.reason


def test_malformed_formulation_input_returns_structured_error() -> None:
    matrix, _ = _test_problem()
    result = AssignmentQAOASolver(allow_test_mode=True).solve(object(), matrix)
    assert result.status == "INVALID_INPUT"
    assert "expected F9.3" in result.reason


@pytest.mark.parametrize(
    ("candidate", "optimum", "feasible", "ratio", "status"),
    [
        (5.0, 10.0, True, 0.5, "DEFINED"),
        (0.0, 0.0, True, None, "ZERO_CLASSICAL_OPTIMUM"),
        (3.0, 0.0, False, None, "INFEASIBLE_CANDIDATE"),
        (-1.0, 10.0, True, None, "NEGATIVE_OBJECTIVE"),
        (1.0, -1.0, True, None, "NEGATIVE_CLASSICAL_OPTIMUM"),
    ],
)
def test_approximation_ratio_edge_cases(candidate, optimum, feasible, ratio, status) -> None:
    actual, actual_status = _approximation_ratio(candidate, optimum, feasible)
    assert actual == ratio
    assert actual_status == status


def test_invalid_configuration_rejected_by_existing_contract() -> None:
    with pytest.raises(ValueError):
        QAOAConfig(depth=1, parameters=QAOAParameterSet((math.nan,), (0.1,)))
