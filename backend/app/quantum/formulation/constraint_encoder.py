from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.app.quantum.domain import ConstraintSense, QuantumConstraint, QuantumVariable
from backend.app.quantum.domain.quantum_objective import _validate_finite_float

MAX_SLACK_CAPACITY = 1024
INTEGER_TOLERANCE = 1e-9


@dataclass(frozen=True)
class EncodedConstraint:
    """QUBO penalty terms produced from one supported linear constraint."""

    variables: tuple[QuantumVariable, ...]
    linear_coefficients: Mapping[str, float]
    quadratic_coefficients: Mapping[tuple[str, str], float]
    constant_offset: float
    metadata: Mapping[str, object]


class ConstraintEncoder:
    """Encode supported E.1 linear constraints as squared QUBO penalties.

    Equality constraints use P(g(x) - b)^2. Inequalities are supported only for
    non-negative integer coefficients and integer bounds, using deterministic
    binary slack variables before applying the same squared penalty.
    """

    def encode(
        self,
        constraint: QuantumConstraint,
        variables: tuple[QuantumVariable, ...],
        *,
        penalty: float,
        slack_start_index: int | None = None,
    ) -> EncodedConstraint:
        """Return immutable QUBO penalty terms for one supported constraint."""

        if not isinstance(constraint, QuantumConstraint):
            raise ValueError("constraint must be a QuantumConstraint.")
        if not isinstance(variables, tuple) or any(not isinstance(variable, QuantumVariable) for variable in variables):
            raise ValueError("variables must be a tuple of QuantumVariable instances.")
        penalty_value = self._positive_penalty(penalty)
        variable_ids = {variable.variable_id for variable in variables}
        unknown = set(constraint.variable_ids()) - variable_ids
        if unknown:
            raise ValueError(f"constraint '{constraint.constraint_id}' references unknown variables: {sorted(unknown)}.")

        slack_index = len(variables) if slack_start_index is None else self._valid_slack_start(slack_start_index)
        expression = {key: float(constraint.coefficients[key]) for key in sorted(constraint.coefficients)}
        slack_variables: list[QuantumVariable] = []
        sense = constraint.sense
        rhs = float(constraint.rhs)

        if sense is ConstraintSense.LE:
            slack_variables = self._build_inequality_slack(
                constraint=constraint,
                variables=variables,
                capacity=rhs,
                sign=1.0,
                expression=expression,
                start_index=slack_index,
            )
        elif sense is ConstraintSense.GE:
            maximum_lhs = sum(float(value) for value in constraint.coefficients.values())
            capacity = maximum_lhs - rhs
            slack_variables = self._build_inequality_slack(
                constraint=constraint,
                variables=variables,
                capacity=capacity,
                sign=-1.0,
                expression=expression,
                start_index=slack_index,
            )
        elif sense is not ConstraintSense.EQ:
            raise ValueError(f"unsupported constraint sense for '{constraint.constraint_id}'.")

        linear, quadratic, constant = self._square_expression(expression, rhs, penalty_value)
        return EncodedConstraint(
            variables=tuple(slack_variables),
            linear_coefficients=MappingProxyType(dict(sorted(linear.items()))),
            quadratic_coefficients=MappingProxyType(dict(sorted(quadratic.items()))),
            constant_offset=constant,
            metadata=MappingProxyType({
                "constraint_id": constraint.constraint_id,
                "constraint_sense": constraint.sense.value,
                "penalty": penalty_value,
                "slack_variable_ids": tuple(variable.variable_id for variable in slack_variables),
            }),
        )

    def _build_inequality_slack(
        self,
        *,
        constraint: QuantumConstraint,
        variables: tuple[QuantumVariable, ...],
        capacity: float,
        sign: float,
        expression: dict[str, float],
        start_index: int,
    ) -> list[QuantumVariable]:
        self._validate_integer_compatible_inequality(constraint, capacity)
        integer_capacity = int(round(capacity))
        existing_ids = {variable.variable_id for variable in variables}
        slack_variables: list[QuantumVariable] = []
        for offset, weight in enumerate(self._slack_weights(integer_capacity)):
            variable_id = f"slack_{constraint.constraint_id}_{offset}"
            if variable_id in existing_ids:
                raise ValueError(f"slack variable '{variable_id}' conflicts with an existing variable.")
            slack_variable = QuantumVariable(
                variable_id=variable_id,
                name=f"Slack {constraint.constraint_id} {offset}",
                index=start_index + offset,
                metadata={"source_constraint_id": constraint.constraint_id, "slack_weight": weight},
            )
            expression[variable_id] = sign * float(weight)
            slack_variables.append(slack_variable)
        return slack_variables

    @staticmethod
    def _validate_integer_compatible_inequality(constraint: QuantumConstraint, capacity: float) -> None:
        if capacity < -INTEGER_TOLERANCE:
            raise ValueError(f"constraint '{constraint.constraint_id}' has no feasible non-negative slack capacity.")
        if capacity > MAX_SLACK_CAPACITY:
            raise ValueError(f"constraint '{constraint.constraint_id}' slack capacity exceeds supported bound.")
        if abs(capacity - round(capacity)) > INTEGER_TOLERANCE:
            raise ValueError(f"constraint '{constraint.constraint_id}' requires an integer-compatible slack capacity.")
        if abs(float(constraint.rhs) - round(float(constraint.rhs))) > INTEGER_TOLERANCE:
            raise ValueError(f"constraint '{constraint.constraint_id}' requires an integer rhs for slack encoding.")
        if float(constraint.rhs) < -INTEGER_TOLERANCE:
            raise ValueError(f"constraint '{constraint.constraint_id}' requires a non-negative rhs.")
        for variable_id, coefficient in constraint.coefficients.items():
            coefficient_value = float(coefficient)
            if coefficient_value < -INTEGER_TOLERANCE:
                raise ValueError(
                    f"constraint '{constraint.constraint_id}' has negative coefficient for '{variable_id}'."
                )
            if abs(coefficient_value - round(coefficient_value)) > INTEGER_TOLERANCE:
                raise ValueError(
                    f"constraint '{constraint.constraint_id}' has non-integer coefficient for '{variable_id}'."
                )

    @staticmethod
    def _slack_weights(capacity: int) -> tuple[int, ...]:
        if capacity <= 0:
            return ()
        weights: list[int] = []
        remaining = capacity
        next_weight = 1
        while remaining > 0:
            weight = min(next_weight, remaining)
            weights.append(weight)
            remaining -= weight
            next_weight *= 2
        return tuple(weights)

    @staticmethod
    def _square_expression(
        coefficients: Mapping[str, float],
        rhs: float,
        penalty: float,
    ) -> tuple[dict[str, float], dict[tuple[str, str], float], float]:
        linear: dict[str, float] = {}
        quadratic: dict[tuple[str, str], float] = {}
        ids = tuple(sorted(coefficients))
        for variable_id in ids:
            coefficient = coefficients[variable_id]
            linear[variable_id] = linear.get(variable_id, 0.0) + penalty * (
                coefficient * coefficient - (2.0 * rhs * coefficient)
            )
        for index, left in enumerate(ids):
            for right in ids[index + 1 :]:
                pair = tuple(sorted((left, right)))
                quadratic[pair] = quadratic.get(pair, 0.0) + penalty * 2.0 * coefficients[left] * coefficients[right]
        constant = penalty * rhs * rhs
        return linear, quadratic, constant

    @staticmethod
    def _positive_penalty(value: object) -> float:
        penalty = _validate_finite_float(value, "penalty")
        if penalty <= 0:
            raise ValueError("penalty must be positive.")
        return penalty

    @staticmethod
    def _valid_slack_start(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("slack_start_index must be a non-negative integer.")
        return value
