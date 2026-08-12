from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from backend.app.quantum.domain import (
    ConstraintSense,
    IsingProblem,
    ObjectiveSense,
    QUBOProblem,
    QuantumConstraint,
    QuantumObjective,
    QuantumSolution,
    QuantumSolveMetadata,
    QuantumSolveRequest,
    QuantumVariable,
)


def objective() -> QuantumObjective:
    return QuantumObjective("obj_main", "Minimize cost", ObjectiveSense.MINIMIZE)


def variables() -> tuple[QuantumVariable, QuantumVariable]:
    return (
        QuantumVariable("x0", "First variable", 0),
        QuantumVariable("x1", "Second variable", 1),
    )


def qubo_problem(**overrides: object) -> QUBOProblem:
    data = {
        "problem_id": "qubo_1",
        "name": "Valid QUBO",
        "variables": variables(),
        "linear_coefficients": {"x0": 1.5, "x1": -0.25},
        "quadratic_coefficients": {("x1", "x0"): 2.0},
        "constant_offset": 0.5,
        "objective": objective(),
        "constraints": (
            QuantumConstraint(
                "constraint_1",
                "One selected",
                ConstraintSense.LE,
                1.0,
                {"x0": 1.0, "x1": 1.0},
            ),
        ),
        "metadata": {"source": "test", "nested": {"safe": [1, 2]}},
    }
    data.update(overrides)
    return QUBOProblem(**data)


def test_valid_quantum_variable() -> None:
    variable = QuantumVariable("x0", "Binary variable", 0, metadata={"kind": "binary"})

    assert variable.variable_id == "x0"
    assert variable.domain == (0, 1)
    assert variable.metadata["kind"] == "binary"


@pytest.mark.parametrize("identifier", ["", " ", "../x", "x.1", "x/1", "x\n1", "_x"])
def test_invalid_variable_id(identifier: str) -> None:
    with pytest.raises(ValueError):
        QuantumVariable(identifier, "Variable", 0)


def test_empty_variable_name_rejected() -> None:
    with pytest.raises(ValueError):
        QuantumVariable("x0", " ", 0)


def test_invalid_variable_index_rejected() -> None:
    with pytest.raises(ValueError):
        QuantumVariable("x0", "Variable", -1)


def test_invalid_variable_domain_rejected() -> None:
    with pytest.raises(ValueError):
        QuantumVariable("x0", "Variable", 0, domain=(0, 2))


def test_valid_objective() -> None:
    obj = QuantumObjective("obj_1", "Maximize value", "MAXIMIZE")

    assert obj.sense is ObjectiveSense.MAXIMIZE
    assert obj.to_dict()["sense"] == "MAXIMIZE"


def test_invalid_objective_sense_rejected() -> None:
    with pytest.raises(ValueError):
        QuantumObjective("obj_1", "Objective", "MIN")


def test_valid_constraint() -> None:
    constraint = QuantumConstraint("constraint_1", "Capacity", "LE", 2.0, {"x0": 1.0})

    assert constraint.sense is ConstraintSense.LE
    assert constraint.variable_ids() == ("x0",)


def test_invalid_constraint_sense_rejected() -> None:
    with pytest.raises(ValueError):
        QuantumConstraint("constraint_1", "Capacity", "LT", 2.0, {"x0": 1.0})


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_constraint_rejects_nan_and_infinity(bad_value: float) -> None:
    with pytest.raises(ValueError):
        QuantumConstraint("constraint_1", "Capacity", "LE", bad_value, {"x0": 1.0})
    with pytest.raises(ValueError):
        QuantumConstraint("constraint_1", "Capacity", "LE", 1.0, {"x0": bad_value})


def test_valid_qubo_problem_canonicalizes_quadratic_terms() -> None:
    problem = qubo_problem()

    assert problem.quadratic_coefficients[("x0", "x1")] == 2.0
    assert list(problem.quadratic_coefficients) == [("x0", "x1")]
    assert problem.variables[0].variable_id == "x0"


def test_empty_qubo_rejected() -> None:
    with pytest.raises(ValueError):
        qubo_problem(variables=())


def test_duplicate_qubo_variable_rejected() -> None:
    duplicate = (
        QuantumVariable("x0", "First variable", 0),
        QuantumVariable("x0", "Duplicate variable", 1),
    )

    with pytest.raises(ValueError):
        qubo_problem(variables=duplicate)


def test_duplicate_qubo_variable_index_rejected() -> None:
    duplicate_index = (
        QuantumVariable("x0", "First variable", 0),
        QuantumVariable("x1", "Second variable", 0),
    )

    with pytest.raises(ValueError):
        qubo_problem(variables=duplicate_index)


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_invalid_qubo_coefficient_rejected(bad_value: float) -> None:
    with pytest.raises(ValueError):
        qubo_problem(linear_coefficients={"x0": bad_value})
    with pytest.raises(ValueError):
        qubo_problem(quadratic_coefficients={("x0", "x1"): bad_value})
    with pytest.raises(ValueError):
        qubo_problem(constant_offset=bad_value)


def test_unknown_qubo_variable_reference_rejected() -> None:
    with pytest.raises(ValueError):
        qubo_problem(linear_coefficients={"missing": 1.0})
    with pytest.raises(ValueError):
        qubo_problem(quadratic_coefficients={("x0", "missing"): 1.0})


def test_duplicate_quadratic_pair_rejected_after_canonicalization() -> None:
    with pytest.raises(ValueError):
        qubo_problem(quadratic_coefficients={("x0", "x1"): 1.0, ("x1", "x0"): 2.0})


def test_self_quadratic_term_rejected() -> None:
    with pytest.raises(ValueError):
        qubo_problem(quadratic_coefficients={("x0", "x0"): 1.0})


def test_duplicate_constraint_ids_rejected() -> None:
    constraints = (
        QuantumConstraint("constraint_1", "A", "LE", 1.0, {"x0": 1.0}),
        QuantumConstraint("constraint_1", "B", "GE", 0.0, {"x1": 1.0}),
    )

    with pytest.raises(ValueError):
        qubo_problem(constraints=constraints)


def test_constraint_unknown_variable_rejected_by_qubo_problem() -> None:
    constraints = (QuantumConstraint("constraint_1", "Bad", "LE", 1.0, {"missing": 1.0}),)

    with pytest.raises(ValueError):
        qubo_problem(constraints=constraints)


def test_valid_ising_problem() -> None:
    problem = IsingProblem(
        problem_id="ising_1",
        name="Valid Ising",
        variables=("s1", "s0"),
        linear_coefficients={"s0": -1.0, "s1": 0.5},
        quadratic_coefficients={("s1", "s0"): 1.25},
        constant_offset=0.0,
        objective=objective(),
        metadata={"kind": "ising"},
    )

    assert problem.variables == ("s0", "s1")
    assert problem.quadratic_coefficients[("s0", "s1")] == 1.25


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_invalid_ising_coefficient_rejected(bad_value: float) -> None:
    with pytest.raises(ValueError):
        IsingProblem(
            "ising_1",
            "Invalid Ising",
            ("s0",),
            {"s0": bad_value},
            {},
            0.0,
            objective(),
        )


def test_ising_unknown_reference_and_duplicate_pair_rejected() -> None:
    with pytest.raises(ValueError):
        IsingProblem("ising_1", "Bad", ("s0",), {"missing": 1.0}, {}, 0.0, objective())
    with pytest.raises(ValueError):
        IsingProblem(
            "ising_1",
            "Bad",
            ("s0", "s1"),
            {},
            {("s0", "s1"): 1.0, ("s1", "s0"): 2.0},
            0.0,
            objective(),
        )


def test_valid_quantum_solution() -> None:
    solution = QuantumSolution(
        solution_id="solution_1",
        problem_id="qubo_1",
        assignments={"x0": 1, "x1": 0},
        objective_value=-2.5,
        feasible=True,
        energy=-2.5,
        solver_name="exact enumerator",
        execution_mode="exact_classical",
        runtime_seconds=0.01,
    )

    assert solution.assignments["x0"] == 1
    assert solution.execution_mode.value == "exact_classical"


@pytest.mark.parametrize("bad_assignment", [2, -1, True, 0.5, "1"])
def test_invalid_solution_assignment_value_rejected(bad_assignment: object) -> None:
    with pytest.raises(ValueError):
        QuantumSolution(
            "solution_1",
            "qubo_1",
            {"x0": bad_assignment},
            1.0,
            True,
            None,
            "solver",
            "exact_classical",
        )


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_invalid_solution_objective_or_energy_rejected(bad_value: float) -> None:
    with pytest.raises(ValueError):
        QuantumSolution("solution_1", "qubo_1", {"x0": 1}, bad_value, True, None, "solver", "exact_classical")
    with pytest.raises(ValueError):
        QuantumSolution("solution_1", "qubo_1", {"x0": 1}, 1.0, True, bad_value, "solver", "exact_classical")


def test_negative_runtime_and_invalid_execution_mode_rejected() -> None:
    with pytest.raises(ValueError):
        QuantumSolution("solution_1", "qubo_1", {"x0": 1}, 1.0, True, None, "solver", "exact_classical", -0.1)
    with pytest.raises(ValueError):
        QuantumSolution("solution_1", "qubo_1", {"x0": 1}, 1.0, True, None, "solver", "unsupported")
    with pytest.raises(ValueError):
        QuantumSolveMetadata("solver", "exact_classical", runtime_seconds=-1.0)


def test_solve_request_and_metadata_validation() -> None:
    metadata = QuantumSolveMetadata(
        "local solver",
        "local_simulator",
        backend_name="local_backend",
        seed=7,
        runtime_seconds=0.0,
        iterations=0,
        shots=10,
    )
    request = QuantumSolveRequest(
        "request_1",
        "qubo_1",
        "local solver",
        "local_simulator",
        configuration={"temperature": [1.0, 0.5]},
        deterministic_seed=7,
        resource_limits={"max_seconds": 5.0},
    )

    assert metadata.to_dict()["execution_mode"] == "local_simulator"
    assert request.resource_limits["max_seconds"] == 5.0
    with pytest.raises(ValueError):
        QuantumSolveRequest("request_1", "qubo_1", "solver", "local_simulator", resource_limits={"bad": -1.0})


def test_immutability_and_nested_immutability() -> None:
    variable = QuantumVariable("x0", "Variable", 0, metadata={"nested": {"values": [1, 2]}})
    problem = qubo_problem()

    with pytest.raises(FrozenInstanceError):
        variable.name = "New name"  # type: ignore[misc]
    with pytest.raises(TypeError):
        problem.linear_coefficients["x0"] = 4.0  # type: ignore[index]
    with pytest.raises(TypeError):
        variable.metadata["nested"]["values"] = (3,)  # type: ignore[index]


def test_deterministic_equality() -> None:
    assert qubo_problem() == qubo_problem()
    assert QuantumVariable("x0", "Variable", 0) == QuantumVariable("x0", "Variable", 0)


def test_qubo_serialization_round_trip() -> None:
    problem = qubo_problem()
    restored = QUBOProblem.from_dict(problem.to_dict())

    assert restored == problem
    assert restored.to_dict() == problem.to_dict()


def test_solution_serialization_round_trip() -> None:
    solution = QuantumSolution(
        "solution_1",
        "qubo_1",
        {"x0": 1},
        1.0,
        False,
        None,
        "solver",
        "quantum_simulator",
        metadata={"samples": [1, 0]},
    )

    assert QuantumSolution.from_dict(solution.to_dict()) == solution


def test_malformed_solution_and_problem_input_rejected() -> None:
    with pytest.raises(ValueError):
        QuantumSolution.from_dict("bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        QUBOProblem.from_dict("bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        IsingProblem.from_dict({"problem_id": "ising_1"})


def test_metadata_rejects_non_finite_float() -> None:
    with pytest.raises(ValueError):
        QuantumVariable("x0", "Variable", 0, metadata={"bad": math.nan})
