from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from backend.app.quantum import (
    ExactClassicalSolver,
    HybridCandidate,
    HybridCandidateComparator,
    HybridFeasibilityChecker,
    HybridOptimizationConfig,
    HybridOptimizationEngine,
    IsingProblem,
    QAOAConfig,
    QAOAEngine,
    QAOAParameterSet,
    QUBOFormulator,
    QuantumConstraint,
    QuantumObjective,
    QuantumSolution,
    QuantumVariable,
)


def objective(sense: str = "MINIMIZE") -> QuantumObjective:
    return QuantumObjective("obj_1", "Objective", sense)


def variables(count: int) -> tuple[QuantumVariable, ...]:
    return tuple(QuantumVariable(f"x{i}", f"X{i}", i) for i in range(count))


def qubo_problem(
    *,
    count: int = 2,
    linear: dict[str, float] | None = None,
    quadratic: dict[tuple[str, str], float] | None = None,
    constant: float = 0.0,
    sense: str = "MINIMIZE",
    constraints: tuple[QuantumConstraint, ...] = (),
    penalty: float | None = None,
):
    return QUBOFormulator().formulate(
        problem_id="qubo_1",
        name="QUBO",
        variables=variables(count),
        linear_coefficients={} if linear is None else linear,
        quadratic_coefficients={} if quadratic is None else quadratic,
        constant_offset=constant,
        objective=objective(sense),
        constraints=constraints,
        penalty=penalty,
    )


def qaoa_config(seed: int = 11) -> QAOAConfig:
    return QAOAConfig(
        depth=1,
        parameters=QAOAParameterSet((math.pi / 4.0,), (math.pi / 8.0,)),
        shots=512,
        seed=seed,
    )


def independent_qubo_energy(problem, assignment: dict[str, int]) -> float:
    energy = float(problem.constant_offset)
    for variable_id, coefficient in problem.linear_coefficients.items():
        energy += coefficient * assignment[variable_id]
    for (left, right), coefficient in problem.quadratic_coefficients.items():
        energy += coefficient * assignment[left] * assignment[right]
    return energy


def independent_ising_energy(problem: IsingProblem, assignment: dict[str, int]) -> float:
    spins = {variable_id: (2 * assignment[variable_id]) - 1 for variable_id in problem.variables}
    energy = float(problem.constant_offset)
    for variable_id, coefficient in problem.linear_coefficients.items():
        energy += coefficient * spins[variable_id]
    for (left, right), coefficient in problem.quadratic_coefficients.items():
        energy += coefficient * spins[left] * spins[right]
    return energy


def candidate(
    candidate_id: str = "candidate_1",
    candidate_type: str = "classical_heuristic",
    value: float = 1.0,
    feasible: bool = True,
    assignment: dict[str, int] | None = None,
    sense: str = "MINIMIZE",
) -> HybridCandidate:
    return HybridCandidate(
        candidate_id=candidate_id,
        candidate_type=candidate_type,
        problem_id="qubo_1",
        objective_value=value,
        feasible=feasible,
        assignment={"x0": 0} if assignment is None else assignment,
        energy=value,
        sense=sense,
        solver_name="test_solver",
    )


def test_hybrid_candidate_validation_and_immutability() -> None:
    item = candidate()

    assert item.candidate_type == "classical_heuristic"
    with pytest.raises(FrozenInstanceError):
        item.objective_value = 0.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        item.assignment["x0"] = 1  # type: ignore[index]
    with pytest.raises(ValueError):
        candidate(candidate_type="bad")
    with pytest.raises(ValueError):
        candidate(value=math.nan)
    with pytest.raises(ValueError):
        candidate(value=math.inf)


def test_hybrid_config_validation() -> None:
    config = HybridOptimizationConfig(max_candidates=3)

    assert config.max_candidates == 3
    with pytest.raises(ValueError):
        HybridOptimizationConfig(max_candidates=0)
    with pytest.raises(ValueError):
        HybridOptimizationConfig(exact_match_tolerance=-1.0)


def test_feasibility_checker_validates_assignment_domain() -> None:
    problem = qubo_problem(count=2, linear={"x0": -1.0})
    checker = HybridFeasibilityChecker()

    assert checker.validate_assignment(problem, {"x0": 1, "x1": 0}) is True
    assert checker.validate_assignment(problem, {"x0": 1}) is False
    assert checker.validate_assignment(problem, {"x0": 1, "x1": 2}) is False
    assert checker.validate_assignment(problem, {"x0": 1, "x1": 0, "extra": 0}) is False


def test_feasibility_checker_validates_qubo_constraints() -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", "EQ", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo_problem(count=2, constraints=(constraint,), penalty=10.0)
    checker = HybridFeasibilityChecker()

    assert checker.validate_assignment(problem, {"x0": 1, "x1": 0}) is True
    assert checker.validate_assignment(problem, {"x0": 1, "x1": 1}) is False


def test_comparator_minimization_ranking() -> None:
    candidates = (
        candidate("c1", value=2.0, assignment={"x0": 1}),
        candidate("c2", value=1.0, assignment={"x0": 0}),
    )
    ranked = HybridCandidateComparator().rank(candidates, exact_reference_energy=1.0, sense="MINIMIZE", tolerance=1e-9)

    assert ranked[0].candidate_id == "c2"


def test_comparator_maximization_ranking() -> None:
    candidates = (
        candidate("c1", value=2.0, assignment={"x0": 1}, sense="MAXIMIZE"),
        candidate("c2", value=1.0, assignment={"x0": 0}, sense="MAXIMIZE"),
    )
    ranked = HybridCandidateComparator().rank(candidates, exact_reference_energy=2.0, sense="MAXIMIZE", tolerance=1e-9)

    assert ranked[0].candidate_id == "c1"


def test_comparator_feasible_beats_infeasible() -> None:
    candidates = (
        candidate("infeasible", value=-10.0, feasible=False, assignment={"x0": 1}),
        candidate("feasible", value=0.0, feasible=True, assignment={"x0": 0}),
    )
    ranked = HybridCandidateComparator().rank(candidates, exact_reference_energy=0.0, sense="MINIMIZE", tolerance=1e-9)

    assert ranked[0].candidate_id == "feasible"


def test_comparator_tie_break_prefers_quantum_when_exact_match() -> None:
    candidates = (
        candidate("classical", "classical_exact", value=-1.0, assignment={"x0": 1}),
        candidate("quantum", "quantum_qaoa", value=-1.0, assignment={"x0": 1}),
    )
    ranked = HybridCandidateComparator().rank(candidates, exact_reference_energy=-1.0, sense="MINIMIZE", tolerance=1e-9)

    assert ranked[0].candidate_id == "quantum"


def test_comparator_rejects_empty_and_duplicate_candidates() -> None:
    comparator = HybridCandidateComparator()

    with pytest.raises(ValueError):
        comparator.rank((), exact_reference_energy=0.0, sense="MINIMIZE", tolerance=1e-9)
    with pytest.raises(ValueError):
        comparator.rank((candidate("same"), candidate("same")), exact_reference_energy=0.0, sense="MINIMIZE", tolerance=1e-9)


def test_hybrid_engine_minimization_exact_vs_qaoa() -> None:
    problem = qubo_problem(count=2, linear={"x0": -1.0, "x1": -1.0}, quadratic={("x0", "x1"): 2.0})
    result = HybridOptimizationEngine().optimize(problem, qaoa_config=qaoa_config(13))

    assert result.benchmark_report.exact_reference_energy == pytest.approx(ExactClassicalSolver().solve_qubo(problem).objective_value)
    assert result.selection.selected_candidate_type in {"classical_exact", "quantum_qaoa"}
    assert result.feasibility_summary["classical_exact_qubo_1"] is True
    assert result.feasibility_summary["quantum_qaoa_qubo_1"] is True


def test_hybrid_engine_maximization() -> None:
    problem = qubo_problem(count=1, linear={"x0": 1.0}, sense="MAXIMIZE")
    result = HybridOptimizationEngine().optimize(problem, qaoa_config=qaoa_config(17))

    assert result.objective_sense == "MINIMIZE"
    assert result.benchmark_report.candidate_count == 2


def test_hybrid_engine_constrained_qubo() -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", "EQ", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo_problem(count=2, linear={"x0": -3.0, "x1": -1.0}, constraints=(constraint,), penalty=10.0)
    result = HybridOptimizationEngine().optimize(problem, qaoa_config=qaoa_config(19))

    assert result.selected_candidate.feasible is True
    assert result.benchmark_report.problem_size == 2


def test_hybrid_engine_ising_problem() -> None:
    problem = IsingProblem("ising_1", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, objective())
    result = HybridOptimizationEngine().optimize(problem, qaoa_config=qaoa_config(23))

    assert result.problem_id == "ising_1"
    assert result.benchmark_report.quantum_candidate_energy is not None


def test_hybrid_exact_match_and_non_match_cases() -> None:
    match_problem = qubo_problem(count=1, linear={"x0": -1.0})
    match = HybridOptimizationEngine().optimize(match_problem, qaoa_config=qaoa_config(29))
    non_match_problem = IsingProblem("ising_1", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, objective())
    non_match = HybridOptimizationEngine().optimize(non_match_problem, qaoa_config=qaoa_config(31))

    assert match.benchmark_report.exact_match is True
    assert non_match.benchmark_report.exact_match is False


def test_hybrid_revalidates_infeasible_additional_candidate() -> None:
    problem = qubo_problem(count=1, linear={"x0": -1.0})
    bad = candidate("heuristic_bad", assignment={"unknown": 1}, value=-99.0)
    result = HybridOptimizationEngine().optimize(
        problem,
        qaoa_config=qaoa_config(37),
        additional_candidates=(bad,),
    )

    assert result.feasibility_summary["heuristic_bad"] is False
    assert result.selected_candidate.candidate_id != "heuristic_bad"


def test_hybrid_rejects_too_many_candidates() -> None:
    problem = qubo_problem(count=1, linear={"x0": -1.0})
    extras = tuple(candidate(f"h{i}", assignment={"x0": 0}, value=float(i)) for i in range(3))

    with pytest.raises(ValueError):
        HybridOptimizationEngine().optimize(
            problem,
            qaoa_config=qaoa_config(41),
            config=HybridOptimizationConfig(max_candidates=2),
            additional_candidates=extras,
        )


def test_hybrid_rejects_invalid_problem() -> None:
    with pytest.raises(ValueError):
        HybridOptimizationEngine().optimize("bad")  # type: ignore[arg-type]


def test_hybrid_result_is_immutable() -> None:
    result = HybridOptimizationEngine().optimize(qubo_problem(count=1, linear={"x0": -1.0}), qaoa_config=qaoa_config(43))

    with pytest.raises(FrozenInstanceError):
        result.problem_id = "new"  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.feasibility_summary["classical_exact_qubo_1"] = False  # type: ignore[index]


def test_hybrid_comparison_rows_are_ranked() -> None:
    result = HybridOptimizationEngine().optimize(qubo_problem(count=1, linear={"x0": -1.0}), qaoa_config=qaoa_config(47))

    assert tuple(comparison.rank for comparison in result.comparisons) == (1, 2)
    assert all(comparison.rationale for comparison in result.comparisons)


def test_hybrid_benchmark_report_contains_quantum_gap() -> None:
    result = HybridOptimizationEngine().optimize(qubo_problem(count=1, linear={"x0": -1.0}), qaoa_config=qaoa_config(53))

    assert result.benchmark_report.quantum_candidate_energy is not None
    assert result.benchmark_report.energy_gap is not None
    assert result.benchmark_report.relative_gap is not None


def test_hybrid_without_qaoa_candidate() -> None:
    result = HybridOptimizationEngine().optimize(
        qubo_problem(count=1, linear={"x0": -1.0}),
        config=HybridOptimizationConfig(include_qaoa_candidate=False),
    )

    assert len(result.candidates) == 1
    assert result.selected_candidate.candidate_type == "classical_exact"
    assert result.benchmark_report.quantum_candidate_energy is None


def test_hybrid_requires_at_least_one_candidate() -> None:
    with pytest.raises(ValueError):
        HybridOptimizationEngine().optimize(
            qubo_problem(count=1, linear={"x0": -1.0}),
            config=HybridOptimizationConfig(include_exact_reference=False, include_qaoa_candidate=False),
        )


def test_hybrid_deterministic_repeated_runs() -> None:
    problem = qubo_problem(count=2, linear={"x0": -2.0, "x1": 1.0})
    engine = HybridOptimizationEngine()

    assert engine.optimize(problem, qaoa_config=qaoa_config(59)) == engine.optimize(problem, qaoa_config=qaoa_config(59))


def test_independent_energy_verification_for_selected_qubo_candidate() -> None:
    problem = qubo_problem(count=2, linear={"x0": -2.0, "x1": 1.0})
    result = HybridOptimizationEngine().optimize(problem, qaoa_config=qaoa_config(61))

    assert result.selected_candidate.objective_value == pytest.approx(
        independent_qubo_energy(problem, dict(result.selected_candidate.assignment))
    )


def test_independent_energy_verification_for_selected_ising_candidate() -> None:
    problem = IsingProblem("ising_1", "Ising", ("x0", "x1"), {"x0": 0.5}, {("x0", "x1"): 1.0}, 0.0, objective())
    result = HybridOptimizationEngine().optimize(problem, qaoa_config=qaoa_config(67))

    assert result.selected_candidate.objective_value == pytest.approx(
        independent_ising_energy(problem, dict(result.selected_candidate.assignment))
    )


def test_hybrid_metadata_documents_non_cheating_policy() -> None:
    result = HybridOptimizationEngine().optimize(qubo_problem(count=1, linear={"x0": -1.0}), qaoa_config=qaoa_config(71))

    assert "not used to overwrite quantum candidate" in result.metadata["non_cheating_policy"]


def test_hybrid_candidate_from_malformed_solution_metadata_still_validates_assignment() -> None:
    solution = QuantumSolution(
        "manual_solution",
        "qubo_1",
        {"x0": 1},
        -1.0,
        True,
        -1.0,
        "manual",
        "exact_classical",
        metadata={"source": "manual"},
    )
    problem = qubo_problem(count=1, linear={"x0": -1.0})
    engine = HybridOptimizationEngine()
    manual = engine._candidate_from_solution(  # deliberate public-behavior test of conversion helper
        solution=solution,
        problem=problem,
        candidate_id="manual_candidate",
        candidate_type="classical_heuristic",
        sense="MINIMIZE",
    )

    assert manual.feasible is True


def test_hybrid_rejects_invalid_additional_candidate_type() -> None:
    with pytest.raises(ValueError):
        HybridOptimizationEngine().optimize(
            qubo_problem(count=1, linear={"x0": -1.0}),
            qaoa_config=qaoa_config(73),
            additional_candidates=("bad",),  # type: ignore[arg-type]
        )


def test_hybrid_candidate_rejects_invalid_sense_and_feasibility() -> None:
    with pytest.raises(ValueError):
        candidate(sense="BAD")
    with pytest.raises(ValueError):
        HybridCandidate(
            "candidate_1",
            "classical_heuristic",
            "qubo_1",
            1.0,
            "yes",  # type: ignore[arg-type]
            {"x0": 1},
            1.0,
            "MINIMIZE",
            "solver",
        )


def test_hybrid_candidate_rejects_invalid_assignment_value() -> None:
    with pytest.raises(ValueError):
        candidate(assignment={"x0": 2})


def test_hybrid_selection_reason_is_explicit() -> None:
    result = HybridOptimizationEngine().optimize(qubo_problem(count=1, linear={"x0": -1.0}), qaoa_config=qaoa_config(79))

    assert result.selection.reason_selected
    assert result.selection.selected_candidate_id == result.selected_candidate.candidate_id


def test_hybrid_no_hidden_classical_replacement_of_quantum_candidate() -> None:
    problem = IsingProblem("ising_1", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, objective())
    result = HybridOptimizationEngine().optimize(problem, qaoa_config=qaoa_config(83))
    quantum = next(candidate for candidate in result.candidates if candidate.candidate_type == "quantum_qaoa")
    exact = next(candidate for candidate in result.candidates if candidate.candidate_type == "classical_exact")

    assert quantum.objective_value != exact.objective_value
    assert result.benchmark_report.exact_match is False


def test_hybrid_exact_reference_energy_matches_e3() -> None:
    problem = qubo_problem(count=3, linear={"x0": -2.0, "x1": 1.0}, quadratic={("x0", "x2"): -3.0})
    result = HybridOptimizationEngine().optimize(problem, qaoa_config=qaoa_config(89))

    assert result.benchmark_report.exact_reference_energy == pytest.approx(
        ExactClassicalSolver().solve_qubo(problem).objective_value
    )
