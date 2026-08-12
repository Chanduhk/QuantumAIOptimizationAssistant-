from __future__ import annotations

import itertools
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
    QuantumVariable,
)
from backend.app.quantum.formulation import (
    ConstraintEncoder,
    IsingToQUBOConverter,
    QUBOFormulator,
    QUBOToIsingConverter,
)

TOLERANCE = 1e-9


def obj(sense: ObjectiveSense | str = ObjectiveSense.MINIMIZE) -> QuantumObjective:
    return QuantumObjective("objective_1", "Objective", sense)


def vars3() -> tuple[QuantumVariable, QuantumVariable, QuantumVariable]:
    return (
        QuantumVariable("x0", "X0", 0),
        QuantumVariable("x1", "X1", 1),
        QuantumVariable("x2", "X2", 2),
    )


def formulator() -> QUBOFormulator:
    return QUBOFormulator()


def qubo(
    *,
    linear: dict[str, float] | None = None,
    quadratic: dict[tuple[str, str], float] | None = None,
    constant: float = 0.0,
    sense: ObjectiveSense | str = ObjectiveSense.MINIMIZE,
    constraints: tuple[QuantumConstraint, ...] = (),
    penalty: float | None = None,
) -> QUBOProblem:
    return formulator().formulate(
        problem_id="qubo_1",
        name="QUBO",
        variables=vars3(),
        linear_coefficients={} if linear is None else linear,
        quadratic_coefficients={} if quadratic is None else quadratic,
        constant_offset=constant,
        objective=obj(sense),
        constraints=constraints,
        penalty=penalty,
    )


def assignments(variable_ids: tuple[str, ...]) -> list[dict[str, int]]:
    return [
        dict(zip(variable_ids, values))
        for values in itertools.product((0, 1), repeat=len(variable_ids))
    ]


def spins_from_binary(binary_assignment: dict[str, int]) -> dict[str, int]:
    return {key: (2 * value) - 1 for key, value in binary_assignment.items()}


def qubo_energy(problem: QUBOProblem, assignment: dict[str, int]) -> float:
    return QUBOToIsingConverter.evaluate_qubo_energy(problem, assignment)


def ising_energy(problem: IsingProblem, spin_assignment: dict[str, int]) -> float:
    return QUBOToIsingConverter.evaluate_ising_energy(problem, spin_assignment)


def assert_qubo_ising_equivalent(problem: QUBOProblem) -> IsingProblem:
    converted = QUBOToIsingConverter().convert(problem)
    for assignment in assignments(tuple(variable.variable_id for variable in problem.variables)):
        assert ising_energy(converted, spins_from_binary(assignment)) == pytest.approx(
            qubo_energy(problem, assignment),
            abs=TOLERANCE,
        )
    return converted


def assert_ising_qubo_equivalent(problem: IsingProblem) -> QUBOProblem:
    converted = IsingToQUBOConverter().convert(problem)
    for assignment in assignments(problem.variables):
        assert qubo_energy(converted, assignment) == pytest.approx(
            ising_energy(problem, spins_from_binary(assignment)),
            abs=TOLERANCE,
        )
    return converted


def test_valid_linear_qubo_formulation() -> None:
    problem = qubo(linear={"x0": 1.0, "x1": -2.0}, constant=3.0)

    assert problem.linear_coefficients["x0"] == 1.0
    assert problem.constant_offset == 3.0
    assert problem.objective.sense is ObjectiveSense.MINIMIZE


def test_valid_quadratic_qubo_formulation() -> None:
    problem = qubo(quadratic={("x1", "x0"): 4.0})

    assert problem.quadratic_coefficients[("x0", "x1")] == 4.0


def test_reversed_quadratic_input_merges_cleanly_with_constraint_penalty() -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", "EQ", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo(quadratic={("x1", "x0"): 4.0}, constraints=(constraint,), penalty=2.0)

    assert problem.quadratic_coefficients[("x0", "x1")] == pytest.approx(8.0)


def test_mixed_qubo_formulation_preserves_constant_offset() -> None:
    problem = qubo(linear={"x0": 1.0}, quadratic={("x0", "x2"): -3.0}, constant=-2.5)

    assert problem.constant_offset == -2.5
    assert qubo_energy(problem, {"x0": 1, "x1": 0, "x2": 1}) == pytest.approx(-4.5)


def test_maximization_objective_is_negated_for_minimization_qubo() -> None:
    problem = qubo(linear={"x0": 3.0}, quadratic={("x0", "x1"): -2.0}, constant=1.0, sense="MAXIMIZE")

    assert problem.objective.sense is ObjectiveSense.MAXIMIZE
    assert problem.linear_coefficients["x0"] == -3.0
    assert problem.quadratic_coefficients[("x0", "x1")] == 2.0
    assert problem.constant_offset == -1.0
    assert problem.metadata["objective_transformed_for_minimization"] is True


def test_minimization_objective_is_not_negated() -> None:
    problem = qubo(linear={"x0": 3.0}, sense="MINIMIZE")

    assert problem.linear_coefficients["x0"] == 3.0
    assert problem.metadata["objective_transformed_for_minimization"] is False


def test_equality_constraint_penalty_encoding() -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", ConstraintSense.EQ, 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo(constraints=(constraint,), penalty=10.0)

    assert problem.linear_coefficients["x0"] == pytest.approx(-10.0)
    assert problem.linear_coefficients["x1"] == pytest.approx(-10.0)
    assert problem.quadratic_coefficients[("x0", "x1")] == pytest.approx(20.0)
    assert problem.constant_offset == pytest.approx(10.0)


def test_equality_constraint_energy_zero_for_satisfied_assignments() -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", "EQ", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo(constraints=(constraint,), penalty=5.0)

    assert qubo_energy(problem, {"x0": 1, "x1": 0, "x2": 0}) == pytest.approx(0.0)
    assert qubo_energy(problem, {"x0": 1, "x1": 1, "x2": 0}) == pytest.approx(5.0)


def test_less_equal_constraint_adds_slack_variables() -> None:
    constraint = QuantumConstraint("c_le", "At most one", "LE", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo(constraints=(constraint,), penalty=7.0)

    slack_ids = [variable.variable_id for variable in problem.variables if variable.variable_id.startswith("slack_")]
    assert slack_ids == ["slack_c_le_0"]
    assert problem.metadata["encoded_constraints"][0]["slack_variable_ids"] == ("slack_c_le_0",)


def test_less_equal_constraint_penalty_with_slack_is_correct() -> None:
    constraint = QuantumConstraint("c_le", "At most one", "LE", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo(constraints=(constraint,), penalty=3.0)

    assert qubo_energy(problem, {"x0": 1, "x1": 0, "x2": 0, "slack_c_le_0": 0}) == pytest.approx(0.0)
    assert qubo_energy(problem, {"x0": 0, "x1": 0, "x2": 0, "slack_c_le_0": 1}) == pytest.approx(0.0)
    assert qubo_energy(problem, {"x0": 1, "x1": 1, "x2": 0, "slack_c_le_0": 0}) == pytest.approx(3.0)


def test_greater_equal_constraint_adds_slack_variables() -> None:
    constraint = QuantumConstraint("c_ge", "At least one", "GE", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo(constraints=(constraint,), penalty=7.0)

    slack_ids = [variable.variable_id for variable in problem.variables if variable.variable_id.startswith("slack_")]
    assert slack_ids == ["slack_c_ge_0"]


def test_greater_equal_constraint_penalty_with_slack_is_correct() -> None:
    constraint = QuantumConstraint("c_ge", "At least one", "GE", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo(constraints=(constraint,), penalty=3.0)

    assert qubo_energy(problem, {"x0": 1, "x1": 0, "x2": 0, "slack_c_ge_0": 0}) == pytest.approx(0.0)
    assert qubo_energy(problem, {"x0": 1, "x1": 1, "x2": 0, "slack_c_ge_0": 1}) == pytest.approx(0.0)
    assert qubo_energy(problem, {"x0": 0, "x1": 0, "x2": 0, "slack_c_ge_0": 0}) == pytest.approx(3.0)


def test_multi_bit_slack_capacity_is_representable() -> None:
    constraint = QuantumConstraint("c_le", "At most five", "LE", 5.0, {"x0": 1.0})
    problem = qubo(constraints=(constraint,), penalty=1.0)

    slack_weights = [
        variable.metadata["slack_weight"]
        for variable in problem.variables
        if variable.variable_id.startswith("slack_")
    ]
    assert slack_weights == [1, 2, 2]


@pytest.mark.parametrize("penalty", [None, 0.0, -1.0, math.nan, math.inf])
def test_penalty_validation(penalty: float | None) -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", "EQ", 1.0, {"x0": 1.0})
    with pytest.raises(ValueError):
        qubo(constraints=(constraint,), penalty=penalty)


def test_unknown_objective_variable_rejected() -> None:
    with pytest.raises(ValueError):
        qubo(linear={"missing": 1.0})


def test_unknown_constraint_variable_rejected() -> None:
    constraint = QuantumConstraint("c_eq", "Bad", "EQ", 1.0, {"missing": 1.0})
    with pytest.raises(ValueError):
        qubo(constraints=(constraint,), penalty=1.0)


def test_duplicate_variables_rejected_by_formulator_output() -> None:
    duplicate = (QuantumVariable("x0", "X0", 0), QuantumVariable("x0", "X duplicate", 1))
    with pytest.raises(ValueError):
        formulator().formulate(
            problem_id="qubo_bad",
            name="Bad",
            variables=duplicate,
            linear_coefficients={"x0": 1.0},
            objective=obj(),
        )


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_formulator_rejects_nan_and_infinity(bad_value: float) -> None:
    with pytest.raises(ValueError):
        qubo(linear={"x0": bad_value})
    with pytest.raises(ValueError):
        qubo(quadratic={("x0", "x1"): bad_value})
    with pytest.raises(ValueError):
        qubo(constant=bad_value)


def test_non_integer_inequality_rejected() -> None:
    constraint = QuantumConstraint("c_le", "Fractional", "LE", 1.5, {"x0": 1.0})
    with pytest.raises(ValueError):
        qubo(constraints=(constraint,), penalty=1.0)


def test_negative_inequality_coefficient_rejected() -> None:
    constraint = QuantumConstraint("c_le", "Negative", "LE", 1.0, {"x0": -1.0})
    with pytest.raises(ValueError):
        qubo(constraints=(constraint,), penalty=1.0)


def test_infeasible_greater_equal_constraint_rejected() -> None:
    constraint = QuantumConstraint("c_ge", "Too high", "GE", 5.0, {"x0": 1.0})
    with pytest.raises(ValueError):
        qubo(constraints=(constraint,), penalty=1.0)


def test_slack_capacity_bound_rejected() -> None:
    constraint = QuantumConstraint("c_le", "Too large", "LE", 1025.0, {"x0": 1.0})
    with pytest.raises(ValueError):
        qubo(constraints=(constraint,), penalty=1.0)


def test_constraint_encoder_output_is_immutable() -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", "EQ", 1.0, {"x0": 1.0})
    encoded = ConstraintEncoder().encode(constraint, (QuantumVariable("x0", "X0", 0),), penalty=2.0)

    with pytest.raises(FrozenInstanceError):
        encoded.constant_offset = 5.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        encoded.linear_coefficients["x0"] = 0.0  # type: ignore[index]


def test_formulation_does_not_mutate_inputs() -> None:
    linear = {"x0": 1.0}
    quadratic = {("x1", "x0"): 2.0}
    variables = vars3()

    problem = formulator().formulate(
        problem_id="qubo_immutable",
        name="Immutable",
        variables=variables,
        linear_coefficients=linear,
        quadratic_coefficients=quadratic,
        constant_offset=0.0,
        objective=obj(),
    )
    linear["x0"] = 99.0
    quadratic[("x1", "x0")] = 99.0

    assert problem.linear_coefficients["x0"] == 1.0
    assert problem.quadratic_coefficients[("x0", "x1")] == 2.0


def test_deterministic_ordering() -> None:
    shuffled = (QuantumVariable("x2", "X2", 2), QuantumVariable("x0", "X0", 0), QuantumVariable("x1", "X1", 1))
    problem = formulator().formulate(
        problem_id="qubo_order",
        name="Ordered",
        variables=shuffled,
        linear_coefficients={"x2": 1.0, "x0": 2.0},
        quadratic_coefficients={("x2", "x0"): 3.0},
        objective=obj(),
    )

    assert tuple(variable.variable_id for variable in problem.variables) == ("x0", "x1", "x2")
    assert list(problem.linear_coefficients) == ["x0", "x2"]
    assert list(problem.quadratic_coefficients) == [("x0", "x2")]


@pytest.mark.parametrize(
    ("linear", "quadratic", "constant"),
    [
        ({"x0": 1.0}, {}, 0.0),
        ({}, {("x0", "x1"): 2.0}, 0.0),
        ({"x0": -1.5, "x2": 3.0}, {("x1", "x2"): -2.0}, 4.25),
        ({"x0": 1.0, "x1": 2.0}, {("x0", "x2"): 3.0, ("x1", "x2"): -4.0}, -1.0),
    ],
)
def test_qubo_to_ising_exhaustive_energy_equivalence(
    linear: dict[str, float],
    quadratic: dict[tuple[str, str], float],
    constant: float,
) -> None:
    assert_qubo_ising_equivalent(qubo(linear=linear, quadratic=quadratic, constant=constant))


def test_qubo_to_ising_coefficients_are_exact_for_small_case() -> None:
    problem = qubo(linear={"x0": 2.0}, quadratic={("x0", "x1"): 4.0}, constant=1.0)
    converted = QUBOToIsingConverter().convert(problem)

    assert converted.linear_coefficients["x0"] == pytest.approx(2.0)
    assert converted.linear_coefficients["x1"] == pytest.approx(1.0)
    assert converted.quadratic_coefficients[("x0", "x1")] == pytest.approx(1.0)
    assert converted.constant_offset == pytest.approx(3.0)


def test_qubo_to_ising_preserves_objective_sense_and_metadata() -> None:
    problem = qubo(linear={"x0": 1.0}, sense="MAXIMIZE")
    converted = QUBOToIsingConverter().convert(problem, problem_id="ising_custom", name="Custom Ising")

    assert converted.problem_id == "ising_custom"
    assert converted.name == "Custom Ising"
    assert converted.objective.sense is ObjectiveSense.MAXIMIZE
    assert converted.metadata["original_objective_sense"] == "MAXIMIZE"


def test_ising_to_qubo_coefficients_are_exact_for_small_case() -> None:
    problem = IsingProblem(
        "ising_1",
        "Ising",
        ("x0", "x1"),
        {"x0": 2.0, "x1": 1.0},
        {("x0", "x1"): 1.0},
        3.0,
        obj(),
    )
    converted = IsingToQUBOConverter().convert(problem)

    assert converted.linear_coefficients["x0"] == pytest.approx(2.0)
    assert converted.linear_coefficients.get("x1", 0.0) == pytest.approx(0.0)
    assert converted.quadratic_coefficients[("x0", "x1")] == pytest.approx(4.0)
    assert converted.constant_offset == pytest.approx(1.0)


@pytest.mark.parametrize(
    "problem",
    [
        IsingProblem("ising_1", "Linear", ("x0", "x1"), {"x0": -1.0}, {}, 2.0, obj()),
        IsingProblem("ising_2", "Quadratic", ("x0", "x1"), {}, {("x0", "x1"): 1.5}, -3.0, obj()),
        IsingProblem(
            "ising_3",
            "Mixed",
            ("x0", "x1", "x2"),
            {"x0": 1.0, "x1": -2.0},
            {("x0", "x2"): 0.5, ("x1", "x2"): -1.25},
            4.0,
            obj(),
        ),
    ],
)
def test_ising_to_qubo_exhaustive_energy_equivalence(problem: IsingProblem) -> None:
    assert_ising_qubo_equivalent(problem)


def test_qubo_to_ising_to_qubo_round_trip_energy_equivalence() -> None:
    original = qubo(linear={"x0": -2.0, "x1": 3.0}, quadratic={("x0", "x2"): 5.0}, constant=-1.5)
    round_trip = IsingToQUBOConverter().convert(QUBOToIsingConverter().convert(original))

    for assignment in assignments(("x0", "x1", "x2")):
        assert qubo_energy(round_trip, assignment) == pytest.approx(qubo_energy(original, assignment), abs=TOLERANCE)


def test_ising_to_qubo_to_ising_round_trip_energy_equivalence() -> None:
    original = IsingProblem(
        "ising_1",
        "Round Trip",
        ("x0", "x1", "x2"),
        {"x0": 0.5, "x2": -2.0},
        {("x0", "x1"): 1.0, ("x1", "x2"): -3.0},
        2.5,
        obj("MAXIMIZE"),
    )
    round_trip = QUBOToIsingConverter().convert(IsingToQUBOConverter().convert(original))

    for assignment in assignments(("x0", "x1", "x2")):
        spin_assignment = spins_from_binary(assignment)
        assert ising_energy(round_trip, spin_assignment) == pytest.approx(
            ising_energy(original, spin_assignment),
            abs=TOLERANCE,
        )


def test_constrained_qubo_to_ising_energy_equivalence_for_all_augmented_assignments() -> None:
    constraint = QuantumConstraint("c_le", "At most one", "LE", 1.0, {"x0": 1.0, "x1": 1.0})
    problem = qubo(linear={"x2": 2.0}, constraints=(constraint,), penalty=4.0)

    assert_qubo_ising_equivalent(problem)


def test_constant_offsets_preserved_through_conversions() -> None:
    problem = qubo(linear={"x0": 1.0}, quadratic={("x0", "x1"): 2.0}, constant=7.0)
    ising = QUBOToIsingConverter().convert(problem)
    restored = IsingToQUBOConverter().convert(ising)

    assert restored.constant_offset == pytest.approx(problem.constant_offset)
    for assignment in assignments(("x0", "x1", "x2")):
        assert qubo_energy(restored, assignment) == pytest.approx(qubo_energy(problem, assignment), abs=TOLERANCE)


def test_variable_mapping_preserved_across_conversions() -> None:
    problem = qubo(linear={"x0": 1.0, "x2": 2.0})
    ising = QUBOToIsingConverter().convert(problem)
    restored = IsingToQUBOConverter().convert(ising)

    assert tuple(variable.variable_id for variable in restored.variables) == ("x0", "x1", "x2")
    assert ising.metadata["variable_mapping"] == (("x0", "x0"), ("x1", "x1"), ("x2", "x2"))


def test_converter_rejects_invalid_problem_types() -> None:
    with pytest.raises(ValueError):
        QUBOToIsingConverter().convert("bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        IsingToQUBOConverter().convert("bad")  # type: ignore[arg-type]


def test_energy_evaluators_reject_invalid_assignments() -> None:
    problem = qubo(linear={"x0": 1.0})
    ising = QUBOToIsingConverter().convert(problem)

    with pytest.raises(ValueError):
        qubo_energy(problem, {"x0": 2, "x1": 0, "x2": 0})
    with pytest.raises(ValueError):
        ising_energy(ising, {"x0": 0, "x1": 1, "x2": 1})


def test_empty_problem_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        formulator().formulate(
            problem_id="qubo_bad",
            name="Bad",
            variables=(),
            linear_coefficients={},
            objective=obj(),
        )


def test_serialization_compatibility_after_formulation_and_conversion() -> None:
    problem = qubo(linear={"x0": 1.0}, quadratic={("x1", "x2"): -2.0}, constant=3.0)
    ising = QUBOToIsingConverter().convert(problem)
    restored_qubo = IsingToQUBOConverter().convert(ising)

    assert QUBOProblem.from_dict(problem.to_dict()) == problem
    assert IsingProblem.from_dict(ising.to_dict()) == ising
    assert QUBOProblem.from_dict(restored_qubo.to_dict()) == restored_qubo


def test_deterministic_repeated_formulation_and_conversion() -> None:
    first = qubo(linear={"x1": 2.0, "x0": 1.0}, quadratic={("x2", "x0"): 3.0})
    second = qubo(linear={"x1": 2.0, "x0": 1.0}, quadratic={("x2", "x0"): 3.0})

    assert first == second
    assert QUBOToIsingConverter().convert(first) == QUBOToIsingConverter().convert(second)


def test_large_small_problem_n8_exhaustive_equivalence() -> None:
    variables = tuple(QuantumVariable(f"x{i}", f"X{i}", i) for i in range(8))
    linear = {f"x{i}": float((i % 3) - 1) for i in range(8)}
    quadratic = {(f"x{i}", f"x{i + 1}"): float(i + 1) / 3.0 for i in range(7)}
    problem = formulator().formulate(
        problem_id="qubo_n8",
        name="N8",
        variables=variables,
        linear_coefficients=linear,
        quadratic_coefficients=quadratic,
        constant_offset=1.25,
        objective=obj(),
    )

    assert_qubo_ising_equivalent(problem)


def test_formulation_metadata_explains_penalties() -> None:
    constraint = QuantumConstraint("c_eq", "Exactly one", "EQ", 1.0, {"x0": 1.0})
    problem = qubo(constraints=(constraint,), penalty=9.0)

    encoded = problem.metadata["encoded_constraints"][0]
    assert encoded["constraint_id"] == "c_eq"
    assert encoded["constraint_sense"] == "EQ"
    assert encoded["penalty"] == 9.0


def test_objective_sense_preserved_through_round_trip() -> None:
    original = qubo(linear={"x0": 1.0}, sense="MAXIMIZE")
    restored = IsingToQUBOConverter().convert(QUBOToIsingConverter().convert(original))

    assert restored.objective.sense is ObjectiveSense.MAXIMIZE


def test_invalid_custom_conversion_identifiers_rejected() -> None:
    problem = qubo(linear={"x0": 1.0})
    ising = QUBOToIsingConverter().convert(problem)

    with pytest.raises(ValueError):
        QUBOToIsingConverter().convert(problem, problem_id="../bad")
    with pytest.raises(ValueError):
        IsingToQUBOConverter().convert(ising, problem_id="../bad")
