from dataclasses import replace

from backend.app.domain.assignment_qubo_ising import AssignmentQuboIsingBuilder
from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.prediction_matrix import create_synthetic_test_matrix
from backend.app.domain.quantum_suitability import QuantumSuitabilityAnalyzer
from backend.app.quantum.optimization import QAOAConfig


def problem(scores=None):
    scores = scores or [("a", 9, 90), ("a", 10, 10), ("b", 9, 20), ("b", 10, 80)]
    matrix = create_synthetic_test_matrix(["a", "b"], [9, 10], scores)
    classical = ClassicalOptimizer(allow_test_matrices=True).optimize(matrix)
    formulation = AssignmentQuboIsingBuilder(allow_test_matrices=True).build(matrix)
    return matrix, classical, formulation


def test_explicit_synthetic_problem_is_suitable_and_production_default_is_closed():
    matrix, classical, formulation = problem()
    analyzer = QuantumSuitabilityAnalyzer()
    assert analyzer.assess(matrix, classical, formulation).status == "NOT_READY"
    result = analyzer.assess(matrix, classical, formulation, allow_test_mode=True)
    assert result.status == "SUITABLE"
    assert result.mode == "TEST/SYNTHETIC"
    assert "algorithm evidence only" in result.reasons[-1]


def test_missing_or_incomplete_production_evidence_is_not_ready():
    analyzer = QuantumSuitabilityAnalyzer()
    assert analyzer.assess(None, None, None).status == "NOT_READY"
    matrix, classical, formulation = problem()
    incomplete = replace(matrix, cells=matrix.cells[:-1])
    result = analyzer.assess(incomplete, classical, formulation, allow_test_mode=True)
    assert result.status == "NOT_READY"
    assert "incomplete" in result.reasons[0]


def test_invalid_provenance_and_nontriviality_are_rejected():
    matrix, classical, formulation = problem()
    bad_cell = replace(matrix.cells[0], provenance_label="UNVERIFIED")
    bad_matrix = replace(matrix, cells=(bad_cell, *matrix.cells[1:]))
    assert QuantumSuitabilityAnalyzer().assess(
        bad_matrix, classical, formulation, allow_test_mode=True
    ).status == "NOT_READY"

    flat, flat_classical, flat_formulation = problem(
        [("a", 9, 50), ("a", 10, 40), ("b", 9, 40), ("b", 10, 30)]
    )
    result = QuantumSuitabilityAnalyzer().assess(
        flat, flat_classical, flat_formulation, allow_test_mode=True
    )
    assert result.status == "NOT_SUITABLE"
    assert "nontriviality" in result.reasons[0]


def test_mismatched_classical_candidate_is_rejected():
    matrix, classical, formulation = problem()
    wrong = classical.to_dict()
    wrong["total_objective"] = 0.0
    result = QuantumSuitabilityAnalyzer().assess(
        matrix, wrong, formulation, allow_test_mode=True
    )
    assert result.status == "NOT_READY"


def test_unsupported_local_qubit_count_is_explicit():
    tasks, hours = ["a", "b", "c"], [9, 10, 11]
    values = ((90, 10, 20), (10, 90, 30), (20, 30, 90))
    cells = [(task, hour, values[ti][hi]) for ti, task in enumerate(tasks) for hi, hour in enumerate(hours)]
    matrix = create_synthetic_test_matrix(tasks, hours, cells)
    classical = ClassicalOptimizer(allow_test_matrices=True).optimize(matrix)
    formulation = AssignmentQuboIsingBuilder(allow_test_matrices=True).build(matrix)
    result = QuantumSuitabilityAnalyzer().assess(
        matrix, classical, formulation, allow_test_mode=True, config=QAOAConfig(max_qubits=9)
    )
    assert result.status == "NOT_SUPPORTED"
    assert "variable count" in result.reasons[0]
