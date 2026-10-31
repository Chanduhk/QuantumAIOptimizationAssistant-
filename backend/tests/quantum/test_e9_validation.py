from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from backend.app.quantum.domain import (
    IsingProblem,
    QuantumConstraint,
    QuantumObjective,
    QuantumVariable,
    QUBOProblem,
)
from backend.app.quantum.integration import AIQuantumIntegrationConfig
from backend.app.quantum.optimization import QAOAConfig, QAOAParameterSet
from backend.app.quantum.validation import E9BenchmarkCase, E9BenchmarkResult, E9QuantumValidationHarness


def _qubo(problem_id: str = "e9_qubo") -> QUBOProblem:
    return QUBOProblem(
        problem_id=problem_id,
        name="E9 QUBO",
        variables=(
            QuantumVariable("x0", "Task 0", 0),
            QuantumVariable("x1", "Task 1", 1),
        ),
        linear_coefficients={"x0": -1.0, "x1": 0.5},
        quadratic_coefficients={("x0", "x1"): 1.0},
        constant_offset=0.25,
        objective=QuantumObjective("obj_" + problem_id, "Objective", "MINIMIZE"),
    )


def _constrained_qubo() -> QUBOProblem:
    return QUBOProblem(
        problem_id="e9_constrained",
        name="E9 Constrained QUBO",
        variables=(
            QuantumVariable("x0", "Task 0", 0),
            QuantumVariable("x1", "Task 1", 1),
        ),
        linear_coefficients={"x0": -1.0, "x1": -1.0},
        quadratic_coefficients={},
        constant_offset=0.0,
        objective=QuantumObjective("obj_e9_constrained", "Objective", "MINIMIZE"),
        constraints=(
            QuantumConstraint(
                "c_e9_exactly_one",
                "Exactly one",
                "EQ",
                1.0,
                {"x0": 1.0, "x1": 1.0},
            ),
        ),
    )


def _ising() -> IsingProblem:
    return IsingProblem(
        problem_id="e9_ising",
        name="E9 Ising",
        variables=("s0", "s1"),
        linear_coefficients={"s0": 0.5, "s1": -0.25},
        quadratic_coefficients={("s0", "s1"): 0.75},
        constant_offset=-0.1,
        objective=QuantumObjective("obj_e9_ising", "Objective", "MINIMIZE"),
    )


def _qaoa_config() -> QAOAConfig:
    return QAOAConfig(
        depth=1,
        parameters=QAOAParameterSet((0.0,), (0.0,)),
        shots=128,
        seed=42,
    )


def test_benchmark_case_validation_and_immutability():
    case = E9BenchmarkCase("case_valid", _qubo(), qaoa_config=_qaoa_config())
    assert case.case_id == "case_valid"
    with pytest.raises(FrozenInstanceError):
        case.case_id = "changed"
    with pytest.raises(ValueError):
        E9BenchmarkCase("", _qubo())


def test_benchmark_result_rejects_nan_and_invalid_gap():
    with pytest.raises(ValueError):
        E9BenchmarkResult(
            case_id="bad",
            problem_id="bad_problem",
            problem_type="QUBO",
            variable_count=1,
            constraint_count=0,
            objective_sense="MINIMIZE",
            classical_exact_energy=float("nan"),
            independent_exact_energy=0.0,
            quantum_candidate_energy=None,
            selected_energy=None,
            absolute_gap=None,
            relative_gap=None,
            exact_match=None,
            selected_solver=None,
            selected_candidate_type=None,
            feasible=None,
            quantum_used=False,
            classical_used=False,
            execution_path="unsupported",
            qaoa_depth=1,
            qaoa_shots=128,
            exact_runtime_ms=0.1,
            qaoa_runtime_ms=None,
            hybrid_runtime_ms=None,
            integration_runtime_ms=0.1,
            executive_runtime_ms=0.1,
            math_verified=True,
            executive_quantum_present=True,
        )
    with pytest.raises(ValueError):
        E9BenchmarkResult(
            case_id="bad",
            problem_id="bad_problem",
            problem_type="QUBO",
            variable_count=1,
            constraint_count=0,
            objective_sense="MINIMIZE",
            classical_exact_energy=0.0,
            independent_exact_energy=0.0,
            quantum_candidate_energy=None,
            selected_energy=None,
            absolute_gap=-1.0,
            relative_gap=None,
            exact_match=None,
            selected_solver=None,
            selected_candidate_type=None,
            feasible=None,
            quantum_used=False,
            classical_used=False,
            execution_path="unsupported",
            qaoa_depth=1,
            qaoa_shots=128,
            exact_runtime_ms=0.1,
            qaoa_runtime_ms=None,
            hybrid_runtime_ms=None,
            integration_runtime_ms=0.1,
            executive_runtime_ms=0.1,
            math_verified=True,
            executive_quantum_present=True,
        )


def test_independent_qubo_energy():
    harness = E9QuantumValidationHarness()
    problem = _qubo()
    assert harness.independent_qubo_energy(problem, {"x0": 1, "x1": 0}) == pytest.approx(-0.75)
    with pytest.raises(ValueError):
        harness.independent_qubo_energy(problem, {"x0": 1})


def test_independent_ising_energy():
    harness = E9QuantumValidationHarness()
    assert harness.independent_ising_energy(_ising(), {"s0": 0, "s1": 1}) == pytest.approx(-1.6)
    with pytest.raises(ValueError):
        harness.independent_ising_energy(_ising(), {"s0": 2, "s1": 1})


def test_exact_reference_matches_independent_enumeration():
    harness = E9QuantumValidationHarness()
    assert harness.verify_exact_reference(_qubo())
    assert harness.verify_exact_reference(_ising())


def test_qubo_to_ising_equivalence_exhaustive():
    harness = E9QuantumValidationHarness()
    assert harness.verify_qubo_ising_equivalence(_qubo())


def test_ising_to_qubo_equivalence_exhaustive():
    harness = E9QuantumValidationHarness()
    assert harness.verify_ising_qubo_equivalence(_ising())


def test_qaoa_circuit_audit_detects_required_primitives():
    audit = E9QuantumValidationHarness().audit_qaoa_circuit(_ising(), _qaoa_config())
    assert audit["qubit_count"] == 2
    assert audit["has_h_initialization"] is True
    assert audit["has_rx_mixer"] is True
    assert audit["has_rz_cost"] is True
    assert audit["has_rzz_cost"] is True


def test_run_case_quantum_hybrid_path_and_executive_outputs():
    result = E9QuantumValidationHarness().run_case(E9BenchmarkCase("hybrid", _qubo(), qaoa_config=_qaoa_config()))
    assert result.quantum_used is True
    assert result.classical_used is True
    assert result.execution_path == "quantum_hybrid"
    assert result.math_verified is True
    assert result.executive_quantum_present is True
    assert result.metadata["hardware_execution"] is False


def test_run_case_resource_limited_classical_fallback():
    case = E9BenchmarkCase(
        "resource_limited",
        _qubo("e9_resource_limited"),
        qaoa_config=_qaoa_config(),
        integration_config=AIQuantumIntegrationConfig(max_variables_for_quantum=1),
    )
    result = E9QuantumValidationHarness().run_case(case)
    assert result.quantum_used is False
    assert result.classical_used is True
    assert result.execution_path == "classical_fallback"
    assert result.executive_quantum_present is True


def test_run_case_constrained_problem():
    result = E9QuantumValidationHarness().run_case(
        E9BenchmarkCase("constrained", _constrained_qubo(), qaoa_config=_qaoa_config())
    )
    assert result.problem_type == "QUBO"
    assert result.constraint_count == 1
    assert result.math_verified is True


def test_run_case_ising_problem():
    result = E9QuantumValidationHarness().run_case(E9BenchmarkCase("ising", _ising(), qaoa_config=_qaoa_config()))
    assert result.problem_type == "Ising"
    assert result.math_verified is True
    assert result.executive_quantum_present is True


def test_run_case_reports_qaoa_non_match_honestly():
    problem = QUBOProblem(
        problem_id="e9_nonmatch",
        name="E9 Nonmatch",
        variables=(
            QuantumVariable("x0", "x0", 0),
            QuantumVariable("x1", "x1", 1),
            QuantumVariable("x2", "x2", 2),
        ),
        linear_coefficients={"x0": -4.0, "x1": 2.0, "x2": 3.0},
        quadratic_coefficients={("x1", "x2"): -1.0},
        constant_offset=0.0,
        objective=QuantumObjective("obj_e9_nonmatch", "Objective", "MINIMIZE"),
    )
    config = QAOAConfig(depth=1, parameters=QAOAParameterSet((0.0,), (0.0,)), shots=1, seed=7)
    result = E9QuantumValidationHarness().run_case(E9BenchmarkCase("nonmatch", problem, qaoa_config=config))
    assert result.classical_exact_energy == pytest.approx(-4.0)
    assert result.quantum_candidate_energy == pytest.approx(2.0)
    assert result.exact_match is False
    assert result.absolute_gap == pytest.approx(6.0)
    assert result.math_verified is True


def test_run_suite_returns_report_and_is_deterministic():
    harness = E9QuantumValidationHarness()
    report = harness.run_suite(
        (
            E9BenchmarkCase("suite_qubo", _qubo("e9_suite_qubo"), qaoa_config=_qaoa_config()),
            E9BenchmarkCase("suite_ising", _ising(), qaoa_config=_qaoa_config()),
        )
    )
    assert report.determinism_verified is True
    assert report.architecture_audit.passed is True
    assert report.summary == "E.9 validation passed"
    assert len(report.to_dict()["benchmark_results"]) == 2


def test_failure_checks_reject_invalid_inputs():
    checks = E9QuantumValidationHarness().failure_checks()
    assert checks == {
        "invalid_case_id": "rejected",
        "invalid_qaoa_nan": "rejected",
        "invalid_qaoa_shots": "rejected",
    }


def test_architecture_audit_passes_actual_repository():
    repo_root = Path(__file__).resolve().parents[3]
    audit = E9QuantumValidationHarness().architecture_audit(repo_root)
    assert audit.passed is True
    assert audit.forbidden_import_findings == ()
    assert audit.anti_cheating_findings == ()


def test_run_suite_rejects_empty_cases():
    with pytest.raises(ValueError):
        E9QuantumValidationHarness().run_suite(())
