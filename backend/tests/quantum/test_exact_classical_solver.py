from __future__ import annotations

import itertools
import math
from dataclasses import FrozenInstanceError

import pytest

from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.quantum.domain import (
    IsingProblem,
    ObjectiveSense,
    QUBOProblem,
    QuantumConstraint,
    QuantumObjective,
    QuantumVariable,
)
from backend.app.quantum.formulation import IsingToQUBOConverter, QUBOFormulator, QUBOToIsingConverter

TOLERANCE = 1e-9


def objective(sense: ObjectiveSense | str = ObjectiveSense.MINIMIZE) -> QuantumObjective:
    return QuantumObjective("objective_1", "Objective", sense)


def variables(count: int) -> tuple[QuantumVariable, ...]:
    return tuple(QuantumVariable(f"x{index}", f"X{index}", index) for index in range(count))


def qubo_problem(
    *,
    count: int = 3,
    linear: dict[str, float] | None = None,
    quadratic: dict[tuple[str, str], float] | None = None,
    constant: float = 0.0,
    sense: ObjectiveSense | str = ObjectiveSense.MINIMIZE,
) -> QUBOProblem:
    return QUBOProblem(
        problem_id="qubo_1",
        name="QUBO",
        variables=variables(count),
        linear_coefficients={} if linear is None else linear,
        quadratic_coefficients={} if quadratic is None else quadratic,
        constant_offset=constant,
        objective=objective(sense),
    )


def ising_problem(
    *,
    count: int = 3,
    linear: dict[str, float] | None = None,
    quadratic: dict[tuple[str, str], float] | None = None,
    constant: float = 0.0,
    sense: ObjectiveSense | str = ObjectiveSense.MINIMIZE,
) -> IsingProblem:
    return IsingProblem(
        problem_id="ising_1",
        name="Ising",
        variables=tuple(f"x{index}" for index in range(count)),
        linear_coefficients={} if linear is None else linear,
        quadratic_coefficients={} if quadratic is None else quadratic,
        constant_offset=constant,
        objective=objective(sense),
    )


def binary_assignments(variable_ids: tuple[str, ...]) -> list[dict[str, int]]:
    return [dict(zip(variable_ids, values)) for values in itertools.product((0, 1), repeat=len(variable_ids))]


def spins_from_binary(assignment: dict[str, int]) -> dict[str, int]:
    return {key: (2 * value) - 1 for key, value in assignment.items()}


def reference_qubo_energy(problem: QUBOProblem, assignment: dict[str, int]) -> float:
    energy = float(problem.constant_offset)
    for variable_id, coefficient in problem.linear_coefficients.items():
        energy += coefficient * assignment[variable_id]
    for (left, right), coefficient in problem.quadratic_coefficients.items():
        energy += coefficient * assignment[left] * assignment[right]
    return energy


def reference_ising_energy(problem: IsingProblem, spins: dict[str, int]) -> float:
    energy = float(problem.constant_offset)
    for variable_id, coefficient in problem.linear_coefficients.items():
        energy += coefficient * spins[variable_id]
    for (left, right), coefficient in problem.quadratic_coefficients.items():
        energy += coefficient * spins[left] * spins[right]
    return energy


def reference_best_qubo(problem: QUBOProblem, comparison: str = "MINIMIZE") -> tuple[dict[str, int], float]:
    variable_ids = tuple(variable.variable_id for variable in problem.variables)
    best_assignment: dict[str, int] | None = None
    best_energy: float | None = None
    for assignment in binary_assignments(variable_ids):
        energy = reference_qubo_energy(problem, assignment)
        if best_energy is None:
            best_assignment = assignment
            best_energy = energy
            continue
        if comparison == "MINIMIZE" and energy < best_energy - TOLERANCE:
            best_assignment = assignment
            best_energy = energy
        elif comparison == "MAXIMIZE" and energy > best_energy + TOLERANCE:
            best_assignment = assignment
            best_energy = energy
    assert best_assignment is not None and best_energy is not None
    return best_assignment, best_energy


def reference_best_ising(problem: IsingProblem, comparison: str = "MINIMIZE") -> tuple[dict[str, int], float]:
    variable_ids = problem.variables
    best_binary: dict[str, int] | None = None
    best_energy: float | None = None
    for assignment in binary_assignments(variable_ids):
        energy = reference_ising_energy(problem, spins_from_binary(assignment))
        if best_energy is None:
            best_binary = assignment
            best_energy = energy
            continue
        if comparison == "MINIMIZE" and energy < best_energy - TOLERANCE:
            best_binary = assignment
            best_energy = energy
        elif comparison == "MAXIMIZE" and energy > best_energy + TOLERANCE:
            best_binary = assignment
            best_energy = energy
    assert best_binary is not None and best_energy is not None
    return best_binary, best_energy


def test_solver_construction_defaults() -> None:
    solver = ExactClassicalSolver()

    assert solver.max_variables == 20
    assert solver.max_states == 1_048_576


@pytest.mark.parametrize("kwargs", [{"max_variables": 0}, {"max_variables": -1}, {"max_states": 0}, {"max_states": -5}])
def test_solver_rejects_invalid_limits(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        ExactClassicalSolver(**kwargs)


def test_solve_dispatch_rejects_invalid_problem() -> None:
    with pytest.raises(ValueError):
        ExactClassicalSolver().solve("bad")  # type: ignore[arg-type]


def test_one_variable_minimization_known_optimum() -> None:
    problem = qubo_problem(count=1, linear={"x0": -2.0}, constant=3.0)
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 1}
    assert solution.objective_value == pytest.approx(1.0)


def test_two_variable_linear_minimization_known_optimum() -> None:
    problem = qubo_problem(count=2, linear={"x0": 2.0, "x1": -3.0})
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 0, "x1": 1}
    assert solution.objective_value == pytest.approx(-3.0)


def test_quadratic_interaction_known_optimum() -> None:
    problem = qubo_problem(count=2, linear={"x0": -1.0, "x1": -1.0}, quadratic={("x0", "x1"): 3.0})
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 0, "x1": 1}
    assert solution.objective_value == pytest.approx(-1.0)


def test_conflicting_linear_and_quadratic_terms() -> None:
    problem = qubo_problem(count=3, linear={"x0": -5.0, "x1": -5.0, "x2": 1.0}, quadratic={("x0", "x1"): 12.0})
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 0, "x1": 1, "x2": 0}
    assert solution.objective_value == pytest.approx(-5.0)


def test_positive_coefficients_choose_zero_assignment() -> None:
    problem = qubo_problem(count=3, linear={"x0": 1.0, "x1": 2.0}, quadratic={("x0", "x2"): 3.0})
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 0, "x1": 0, "x2": 0}
    assert solution.objective_value == pytest.approx(0.0)


def test_mixed_negative_coefficients_known_optimum() -> None:
    problem = qubo_problem(count=3, linear={"x0": -2.0, "x1": 4.0, "x2": -1.0}, quadratic={("x0", "x2"): -3.0})
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 1, "x1": 0, "x2": 1}
    assert solution.objective_value == pytest.approx(-6.0)


def test_constant_offset_included_in_solution_value() -> None:
    problem = qubo_problem(count=2, linear={"x0": -1.0}, constant=10.0)
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert solution.objective_value == pytest.approx(9.0)


def test_direct_maximization_qubo_uses_max_comparison() -> None:
    problem = qubo_problem(count=2, linear={"x0": 2.0, "x1": 3.0}, sense=ObjectiveSense.MAXIMIZE)
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 1, "x1": 1}
    assert solution.objective_value == pytest.approx(5.0)
    assert solution.metadata["comparison_mode"] == "MAXIMIZE"


def test_e2_maximization_formulated_qubo_uses_minimized_transformed_energy() -> None:
    problem = QUBOFormulator().formulate(
        problem_id="qubo_max",
        name="Max QUBO",
        variables=variables(2),
        linear_coefficients={"x0": 2.0, "x1": 3.0},
        objective=objective("MAXIMIZE"),
    )
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 1, "x1": 1}
    assert solution.objective_value == pytest.approx(-5.0)
    assert solution.metadata["comparison_mode"] == "MINIMIZE"


def test_multiple_optima_tie_breaks_by_problem_variable_order() -> None:
    problem = qubo_problem(count=2, linear={"x0": -1.0, "x1": -1.0}, quadratic={("x0", "x1"): 2.0})
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 0, "x1": 1}
    assert solution.metadata["tie_break_policy"] == "lexicographically_smallest_assignment_by_problem_variable_order"


def test_shuffled_variable_input_uses_e1_index_order() -> None:
    shuffled = (QuantumVariable("x2", "X2", 2), QuantumVariable("x0", "X0", 0), QuantumVariable("x1", "X1", 1))
    problem = QUBOProblem("qubo_1", "QUBO", shuffled, {"x2": -1.0}, {}, 0.0, objective())
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert tuple(problem.variables[index].variable_id for index in range(3)) == ("x0", "x1", "x2")
    assert dict(solution.assignments) == {"x0": 0, "x1": 0, "x2": 1}


def test_qubo_solution_metadata_is_exact_classical() -> None:
    solution = ExactClassicalSolver().solve_qubo(qubo_problem(count=2, linear={"x0": -1.0}))

    assert solution.solver_name == "exact_classical"
    assert solution.execution_mode.value == "exact_classical"
    assert solution.metadata["method"] == "exhaustive_enumeration"
    assert solution.metadata["exact"] is True
    assert solution.metadata["evaluated_states"] == 4


def test_solver_rejects_max_variable_limit_exceeded_before_enumeration() -> None:
    problem = qubo_problem(count=3)

    with pytest.raises(ValueError, match="variable count 3 exceeds limit 2"):
        ExactClassicalSolver(max_variables=2).solve_qubo(problem)


def test_solver_rejects_max_state_limit_exceeded_before_enumeration() -> None:
    problem = qubo_problem(count=4)

    with pytest.raises(ValueError, match="state count 16 exceeds limit 8"):
        ExactClassicalSolver(max_states=8).solve_qubo(problem)


def test_qubo_energy_evaluator_rejects_invalid_assignment() -> None:
    solver = ExactClassicalSolver()
    problem = qubo_problem(count=1)

    with pytest.raises(ValueError):
        solver.evaluate_qubo_energy(problem, {"x0": 2})
    with pytest.raises(ValueError):
        solver.evaluate_qubo_energy(problem, {})


def test_ising_energy_evaluator_rejects_invalid_spins() -> None:
    solver = ExactClassicalSolver()
    problem = ising_problem(count=1)

    with pytest.raises(ValueError):
        solver.evaluate_ising_energy(problem, {"x0": 0})
    with pytest.raises(ValueError):
        solver.evaluate_ising_energy(problem, {})


def test_solve_methods_reject_wrong_problem_type() -> None:
    solver = ExactClassicalSolver()

    with pytest.raises(ValueError):
        solver.solve_qubo(ising_problem(count=1))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        solver.solve_ising(qubo_problem(count=1))  # type: ignore[arg-type]


def test_valid_ising_minimization_known_optimum() -> None:
    problem = ising_problem(count=2, linear={"x0": 1.0, "x1": -2.0}, quadratic={("x0", "x1"): 1.0})
    solution = ExactClassicalSolver().solve_ising(problem)

    assert dict(solution.metadata["spin_assignments"]) == {"x0": -1, "x1": 1}
    assert dict(solution.assignments) == {"x0": 0, "x1": 1}
    assert solution.objective_value == pytest.approx(-4.0)


def test_valid_ising_maximization_known_optimum() -> None:
    problem = ising_problem(count=2, linear={"x0": 1.0, "x1": 2.0}, sense="MAXIMIZE")
    solution = ExactClassicalSolver().solve_ising(problem)

    assert dict(solution.assignments) == {"x0": 1, "x1": 1}
    assert solution.objective_value == pytest.approx(3.0)
    assert solution.metadata["comparison_mode"] == "MAXIMIZE"


def test_ising_constant_offset_included() -> None:
    problem = ising_problem(count=1, linear={"x0": 1.0}, constant=5.0)
    solution = ExactClassicalSolver().solve_ising(problem)

    assert solution.objective_value == pytest.approx(4.0)


def test_qubo_to_ising_solver_consistency() -> None:
    problem = qubo_problem(count=3, linear={"x0": -2.0, "x1": 1.0}, quadratic={("x0", "x2"): -3.0}, constant=2.0)
    qubo_solution = ExactClassicalSolver().solve_qubo(problem)
    ising_problem_equivalent = QUBOToIsingConverter().convert(problem)
    ising_solution = ExactClassicalSolver().solve_ising(ising_problem_equivalent)

    assert dict(ising_solution.assignments) == dict(qubo_solution.assignments)
    assert ising_solution.objective_value == pytest.approx(qubo_solution.objective_value)


def test_ising_to_qubo_solver_consistency() -> None:
    problem = ising_problem(count=3, linear={"x0": 0.5, "x2": -1.0}, quadratic={("x0", "x1"): 2.0}, constant=-0.5)
    ising_solution = ExactClassicalSolver().solve_ising(problem)
    qubo_equivalent = IsingToQUBOConverter().convert(problem)
    qubo_solution = ExactClassicalSolver().solve_qubo(qubo_equivalent)

    assert dict(qubo_solution.assignments) == dict(ising_solution.assignments)
    assert qubo_solution.objective_value == pytest.approx(ising_solution.objective_value)


def test_e2_constrained_qubo_exact_solution() -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", "EQ", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = QUBOFormulator().formulate(
        problem_id="qubo_constrained",
        name="Constrained",
        variables=variables(2),
        linear_coefficients={"x0": -3.0, "x1": -1.0},
        objective=objective(),
        constraints=(constraint,),
        penalty=10.0,
    )
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert dict(solution.assignments) == {"x0": 1, "x1": 0}
    assert solution.objective_value == pytest.approx(-3.0)


def test_e2_inequality_slack_qubo_exact_solution() -> None:
    constraint = QuantumConstraint("c_le", "At most one", "LE", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = QUBOFormulator().formulate(
        problem_id="qubo_le",
        name="LE",
        variables=variables(2),
        linear_coefficients={"x0": -3.0, "x1": -2.0},
        objective=objective(),
        constraints=(constraint,),
        penalty=10.0,
    )
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert solution.assignments["x0"] == 1
    assert solution.assignments["x1"] == 0
    assert solution.assignments["slack_c_le_0"] == 0


def test_independent_qubo_objective_verification() -> None:
    problem = qubo_problem(count=3, linear={"x0": -2.0, "x1": 1.0}, quadratic={("x0", "x2"): -4.0}, constant=3.0)
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert solution.objective_value == pytest.approx(reference_qubo_energy(problem, dict(solution.assignments)))
    _, reference_energy = reference_best_qubo(problem)
    assert solution.objective_value == pytest.approx(reference_energy)


def test_independent_ising_objective_verification() -> None:
    problem = ising_problem(count=3, linear={"x0": -1.0, "x2": 2.0}, quadratic={("x0", "x1"): -0.5}, constant=1.0)
    solution = ExactClassicalSolver().solve_ising(problem)

    spins = dict(solution.metadata["spin_assignments"])
    assert solution.objective_value == pytest.approx(reference_ising_energy(problem, spins))
    _, reference_energy = reference_best_ising(problem)
    assert solution.objective_value == pytest.approx(reference_energy)


def test_input_qubo_remains_unchanged_after_solving() -> None:
    problem = qubo_problem(count=2, linear={"x0": -1.0}, constant=1.0)
    before = problem.to_dict()
    solution = ExactClassicalSolver().solve_qubo(problem)

    assert problem.to_dict() == before
    with pytest.raises(FrozenInstanceError):
        solution.objective_value = 0.0  # type: ignore[misc]


def test_input_ising_remains_unchanged_after_solving() -> None:
    problem = ising_problem(count=2, linear={"x0": -1.0}, constant=1.0)
    before = problem.to_dict()
    ExactClassicalSolver().solve_ising(problem)

    assert problem.to_dict() == before


def test_repeated_qubo_runs_are_deterministic() -> None:
    problem = qubo_problem(count=3, linear={"x0": -1.0, "x2": -2.0}, quadratic={("x0", "x1"): 1.5})
    solver = ExactClassicalSolver()

    assert solver.solve_qubo(problem) == solver.solve_qubo(problem)


def test_repeated_ising_runs_are_deterministic() -> None:
    problem = ising_problem(count=3, linear={"x0": -1.0, "x1": 0.5}, quadratic={("x0", "x2"): -1.5})
    solver = ExactClassicalSolver()

    assert solver.solve_ising(problem) == solver.solve_ising(problem)


@pytest.mark.parametrize(
    ("linear", "quadratic", "constant"),
    [
        ({"x0": 1.0}, {}, 0.0),
        ({"x0": -1.0, "x1": 2.0}, {("x0", "x1"): -3.0}, 4.0),
        ({"x0": 0.5, "x2": -2.0}, {("x1", "x2"): 1.25}, -1.0),
        ({"x0": 2.0, "x1": -1.0, "x2": 3.0}, {("x0", "x2"): -4.0}, 0.25),
    ],
)
def test_property_style_qubo_reference_optima(
    linear: dict[str, float],
    quadratic: dict[tuple[str, str], float],
    constant: float,
) -> None:
    problem = qubo_problem(count=3, linear=linear, quadratic=quadratic, constant=constant)
    solution = ExactClassicalSolver().solve_qubo(problem)
    reference_assignment, reference_energy = reference_best_qubo(problem)

    assert dict(solution.assignments) == reference_assignment
    assert solution.objective_value == pytest.approx(reference_energy)


@pytest.mark.parametrize(
    ("linear", "quadratic", "constant"),
    [
        ({"x0": 1.0}, {}, 0.0),
        ({"x0": -1.0, "x1": 2.0}, {("x0", "x1"): -3.0}, 4.0),
        ({"x0": 0.5, "x2": -2.0}, {("x1", "x2"): 1.25}, -1.0),
    ],
)
def test_property_style_ising_reference_optima(
    linear: dict[str, float],
    quadratic: dict[tuple[str, str], float],
    constant: float,
) -> None:
    problem = ising_problem(count=3, linear=linear, quadratic=quadratic, constant=constant)
    solution = ExactClassicalSolver().solve_ising(problem)
    reference_assignment, reference_energy = reference_best_ising(problem)

    assert dict(solution.assignments) == reference_assignment
    assert solution.objective_value == pytest.approx(reference_energy)


def test_eight_variable_exhaustive_qubo_problem() -> None:
    count = 8
    problem = qubo_problem(
        count=count,
        linear={f"x{i}": float((i % 4) - 2) for i in range(count)},
        quadratic={(f"x{i}", f"x{i + 1}"): float(i + 1) / 5.0 for i in range(count - 1)},
        constant=1.5,
    )
    solution = ExactClassicalSolver(max_variables=8, max_states=256).solve_qubo(problem)
    reference_assignment, reference_energy = reference_best_qubo(problem)

    assert solution.metadata["evaluated_states"] == 256
    assert dict(solution.assignments) == reference_assignment
    assert solution.objective_value == pytest.approx(reference_energy)


def test_eight_variable_equivalent_ising_problem() -> None:
    problem = qubo_problem(
        count=8,
        linear={f"x{i}": float((i % 3) - 1) for i in range(8)},
        quadratic={(f"x{i}", f"x{i + 1}"): -0.25 for i in range(7)},
    )
    qubo_solution = ExactClassicalSolver(max_variables=8, max_states=256).solve_qubo(problem)
    ising_solution = ExactClassicalSolver(max_variables=8, max_states=256).solve_ising(QUBOToIsingConverter().convert(problem))

    assert dict(ising_solution.assignments) == dict(qubo_solution.assignments)
    assert ising_solution.objective_value == pytest.approx(qubo_solution.objective_value)


def test_malformed_qubo_construction_rejects_nan_before_solving() -> None:
    with pytest.raises(ValueError):
        qubo_problem(count=1, linear={"x0": math.nan})


def test_malformed_ising_construction_rejects_infinity_before_solving() -> None:
    with pytest.raises(ValueError):
        ising_problem(count=1, linear={"x0": math.inf})


def test_solution_serialization_contains_reference_metadata() -> None:
    solution = ExactClassicalSolver().solve_qubo(qubo_problem(count=1, linear={"x0": -1.0}))
    data = solution.to_dict()

    assert data["metadata"]["solver_name"] == "exact_classical"
    assert data["metadata"]["representation"] == "QUBO"
    assert data["metadata"]["variable_count"] == 1


def test_solver_output_assignment_is_quantum_solution_binary_for_ising() -> None:
    solution = ExactClassicalSolver().solve_ising(ising_problem(count=1, linear={"x0": -1.0}))

    assert solution.assignments["x0"] in (0, 1)
    assert solution.metadata["spin_assignments"]["x0"] in (-1, 1)
