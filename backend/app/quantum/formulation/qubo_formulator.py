from __future__ import annotations

from typing import Any, Mapping

from backend.app.quantum.domain import ObjectiveSense, QUBOProblem, QuantumConstraint, QuantumObjective, QuantumVariable
from backend.app.quantum.domain.quantum_objective import _validate_finite_float, _validate_identifier, _validate_name
from backend.app.quantum.formulation.constraint_encoder import ConstraintEncoder


class QUBOFormulator:
    """Create E.1 QUBOProblem objects from binary objective and constraints.

    The QUBO convention is E(x) = c + sum_i a_i x_i + sum_{i<j} b_ij x_i x_j,
    where all off-diagonal terms use canonical E.1 variable-id pairs.
    Maximization objectives are represented by negating the supplied objective
    coefficients while preserving the original objective sense in metadata.
    """

    def __init__(self, constraint_encoder: ConstraintEncoder | None = None) -> None:
        self.constraint_encoder = constraint_encoder or ConstraintEncoder()

    def formulate(
        self,
        *,
        problem_id: str,
        name: str,
        variables: tuple[QuantumVariable, ...],
        linear_coefficients: Mapping[str, float],
        quadratic_coefficients: Mapping[tuple[str, str], float] | None = None,
        constant_offset: float = 0.0,
        objective: QuantumObjective,
        constraints: tuple[QuantumConstraint, ...] = (),
        penalty: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> QUBOProblem:
        """Validate and formulate a QUBO without mutating caller-owned inputs."""

        _validate_identifier(problem_id, "problem_id")
        _validate_name(name, "name")
        if not isinstance(objective, QuantumObjective):
            raise ValueError("objective must be a QuantumObjective.")
        if not isinstance(variables, tuple) or not variables:
            raise ValueError("variables must be a non-empty tuple of QuantumVariable instances.")
        if not isinstance(constraints, tuple):
            raise ValueError("constraints must be a tuple.")
        quadratic_coefficients = {} if quadratic_coefficients is None else quadratic_coefficients
        metadata = {} if metadata is None else metadata

        ordered_variables = tuple(sorted(variables, key=lambda variable: variable.index))
        variable_ids = {variable.variable_id for variable in ordered_variables}
        linear = self._copy_linear(linear_coefficients)
        quadratic = self._copy_quadratic(quadratic_coefficients)
        constant = _validate_finite_float(constant_offset, "constant_offset")

        if objective.sense is ObjectiveSense.MAXIMIZE:
            linear = {key: -value for key, value in linear.items()}
            quadratic = {key: -value for key, value in quadratic.items()}
            constant = -constant

        all_variables = list(ordered_variables)
        penalty_metadata: list[dict[str, Any]] = []
        if constraints and penalty is None:
            raise ValueError("penalty must be supplied when constraints are encoded.")
        for constraint in sorted(constraints, key=lambda item: item.constraint_id):
            encoded = self.constraint_encoder.encode(
                constraint,
                tuple(all_variables),
                penalty=penalty,
                slack_start_index=len(all_variables),
            )
            all_variables.extend(encoded.variables)
            self._merge_linear(linear, encoded.linear_coefficients)
            self._merge_quadratic(quadratic, encoded.quadratic_coefficients)
            constant += encoded.constant_offset
            penalty_metadata.append(dict(encoded.metadata))

        formulation_metadata = {
            **dict(metadata),
            "formulation": "qubo",
            "qubo_convention": "constant + linear + canonical upper-triangular quadratic",
            "original_objective_sense": objective.sense.value,
            "objective_transformed_for_minimization": objective.sense is ObjectiveSense.MAXIMIZE,
            "encoded_constraints": tuple(penalty_metadata),
        }
        return QUBOProblem(
            problem_id=problem_id,
            name=name,
            variables=tuple(all_variables),
            linear_coefficients={key: value for key, value in sorted(linear.items()) if value != 0.0},
            quadratic_coefficients={key: value for key, value in sorted(quadratic.items()) if value != 0.0},
            constant_offset=constant,
            objective=objective,
            constraints=constraints,
            metadata=formulation_metadata,
        )

    @staticmethod
    def _copy_linear(coefficients: Mapping[str, float]) -> dict[str, float]:
        if not isinstance(coefficients, Mapping):
            raise ValueError("linear_coefficients must be a mapping.")
        return {
            str(variable_id).strip(): _validate_finite_float(value, "linear coefficient")
            for variable_id, value in sorted(coefficients.items())
        }

    @staticmethod
    def _copy_quadratic(coefficients: Mapping[tuple[str, str], float]) -> dict[tuple[str, str], float]:
        if not isinstance(coefficients, Mapping):
            raise ValueError("quadratic_coefficients must be a mapping.")
        copied: dict[tuple[str, str], float] = {}
        for pair, value in coefficients.items():
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError("quadratic coefficient keys must be two-item tuples.")
            canonical_pair = tuple(sorted((str(pair[0]).strip(), str(pair[1]).strip())))
            if canonical_pair in copied:
                raise ValueError("duplicate quadratic coefficient after canonicalization.")
            copied[canonical_pair] = _validate_finite_float(value, "quadratic coefficient")
        return copied

    @staticmethod
    def _merge_linear(target: dict[str, float], source: Mapping[str, float]) -> None:
        for variable_id in sorted(source):
            target[variable_id] = target.get(variable_id, 0.0) + source[variable_id]

    @staticmethod
    def _merge_quadratic(target: dict[tuple[str, str], float], source: Mapping[tuple[str, str], float]) -> None:
        for pair in sorted(source):
            target[pair] = target.get(pair, 0.0) + source[pair]
