from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.quantum.domain.quantum_constraints import QuantumConstraint
from backend.app.quantum.domain.quantum_objective import (
    BINARY_DOMAIN,
    QuantumObjective,
    QuantumVariable,
    _freeze_mapping,
    _thaw_value,
    _validate_finite_float,
    _validate_identifier,
    _validate_name,
)


@dataclass(frozen=True)
class QUBOProblem:
    """Immutable framework-independent QUBO problem contract."""

    problem_id: str
    name: str
    variables: tuple[QuantumVariable, ...]
    linear_coefficients: Mapping[str, float]
    quadratic_coefficients: Mapping[tuple[str, str], float]
    constant_offset: float
    objective: QuantumObjective
    constraints: tuple[QuantumConstraint, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        object.__setattr__(self, "name", _validate_name(self.name, "name"))
        variables = self._validate_variables(self.variables)
        variable_ids = {variable.variable_id for variable in variables}
        object.__setattr__(self, "variables", variables)
        object.__setattr__(
            self,
            "linear_coefficients",
            self._freeze_linear_coefficients(self.linear_coefficients, variable_ids),
        )
        object.__setattr__(
            self,
            "quadratic_coefficients",
            self._freeze_quadratic_coefficients(self.quadratic_coefficients, variable_ids),
        )
        object.__setattr__(self, "constant_offset", _validate_finite_float(self.constant_offset, "constant_offset"))
        if not isinstance(self.objective, QuantumObjective):
            raise ValueError("objective must be a QuantumObjective.")
        constraints = self._validate_constraints(self.constraints, variable_ids)
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    @staticmethod
    def _validate_variables(variables: tuple[QuantumVariable, ...]) -> tuple[QuantumVariable, ...]:
        if not isinstance(variables, tuple) or not variables:
            raise ValueError("variables must be a non-empty tuple.")
        seen_ids: set[str] = set()
        seen_indexes: set[int] = set()
        sorted_variables = tuple(sorted(variables, key=lambda variable: variable.index))
        for variable in sorted_variables:
            if not isinstance(variable, QuantumVariable):
                raise ValueError("variables must contain QuantumVariable instances.")
            if variable.domain != BINARY_DOMAIN:
                raise ValueError("QUBO variables must be binary.")
            if variable.variable_id in seen_ids:
                raise ValueError("duplicate variable_id in QUBO variables.")
            if variable.index in seen_indexes:
                raise ValueError("duplicate variable index in QUBO variables.")
            seen_ids.add(variable.variable_id)
            seen_indexes.add(variable.index)
        return sorted_variables

    @staticmethod
    def _freeze_linear_coefficients(
        coefficients: Mapping[str, float],
        variable_ids: set[str],
    ) -> Mapping[str, float]:
        if not isinstance(coefficients, Mapping):
            raise ValueError("linear_coefficients must be a mapping.")
        frozen: dict[str, float] = {}
        for variable_id in sorted(coefficients):
            normalized_id = _validate_identifier(variable_id, "linear coefficient variable_id")
            if normalized_id not in variable_ids:
                raise ValueError(f"linear coefficient references unknown variable '{normalized_id}'.")
            frozen[normalized_id] = _validate_finite_float(coefficients[variable_id], "linear coefficient")
        return MappingProxyType(frozen)

    @staticmethod
    def _freeze_quadratic_coefficients(
        coefficients: Mapping[tuple[str, str], float],
        variable_ids: set[str],
    ) -> Mapping[tuple[str, str], float]:
        if not isinstance(coefficients, Mapping):
            raise ValueError("quadratic_coefficients must be a mapping.")
        frozen: dict[tuple[str, str], float] = {}
        for pair, coefficient in coefficients.items():
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError("quadratic coefficient keys must be two-item tuples.")
            left = _validate_identifier(pair[0], "quadratic coefficient variable_id")
            right = _validate_identifier(pair[1], "quadratic coefficient variable_id")
            if left == right:
                raise ValueError("self quadratic terms are not allowed; use linear_coefficients.")
            if left not in variable_ids or right not in variable_ids:
                raise ValueError("quadratic coefficient references unknown variable.")
            canonical_pair = tuple(sorted((left, right)))
            if canonical_pair in frozen:
                raise ValueError("duplicate quadratic coefficient after canonicalization.")
            frozen[canonical_pair] = _validate_finite_float(coefficient, "quadratic coefficient")
        return MappingProxyType(dict(sorted(frozen.items())))

    @staticmethod
    def _validate_constraints(
        constraints: tuple[QuantumConstraint, ...],
        variable_ids: set[str],
    ) -> tuple[QuantumConstraint, ...]:
        if not isinstance(constraints, tuple):
            raise ValueError("constraints must be a tuple.")
        seen_ids: set[str] = set()
        sorted_constraints = tuple(sorted(constraints, key=lambda constraint: constraint.constraint_id))
        for constraint in sorted_constraints:
            if not isinstance(constraint, QuantumConstraint):
                raise ValueError("constraints must contain QuantumConstraint instances.")
            if constraint.constraint_id in seen_ids:
                raise ValueError("duplicate constraint_id in QUBO constraints.")
            unknown = set(constraint.variable_ids()) - variable_ids
            if unknown:
                raise ValueError(f"constraint references unknown variables: {sorted(unknown)}.")
            seen_ids.add(constraint.constraint_id)
        return sorted_constraints

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without mutating the model."""

        return {
            "problem_id": self.problem_id,
            "name": self.name,
            "variables": [variable.to_dict() for variable in self.variables],
            "linear_coefficients": {key: self.linear_coefficients[key] for key in sorted(self.linear_coefficients)},
            "quadratic_coefficients": [
                {"variables": list(pair), "coefficient": self.quadratic_coefficients[pair]}
                for pair in sorted(self.quadratic_coefficients)
            ],
            "constant_offset": self.constant_offset,
            "objective": self.objective.to_dict(),
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "metadata": _thaw_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QUBOProblem":
        """Create a QUBO problem from a mapping using normal constructor validation."""

        if not isinstance(data, Mapping):
            raise ValueError("QUBOProblem data must be a mapping.")
        quadratic_entries = data.get("quadratic_coefficients", [])
        quadratic_coefficients: dict[tuple[str, str], float] = {}
        for entry in quadratic_entries:
            if not isinstance(entry, Mapping):
                raise ValueError("quadratic_coefficients entries must be mappings.")
            variables = entry.get("variables")
            if not isinstance(variables, list) or len(variables) != 2:
                raise ValueError("quadratic entry variables must contain two IDs.")
            quadratic_coefficients[(variables[0], variables[1])] = entry.get("coefficient")
        return cls(
            problem_id=data.get("problem_id"),
            name=data.get("name"),
            variables=tuple(QuantumVariable.from_dict(item) for item in data.get("variables", [])),
            linear_coefficients=data.get("linear_coefficients", {}),
            quadratic_coefficients=quadratic_coefficients,
            constant_offset=data.get("constant_offset"),
            objective=QuantumObjective.from_dict(data.get("objective", {})),
            constraints=tuple(QuantumConstraint.from_dict(item) for item in data.get("constraints", [])),
            metadata=data.get("metadata", {}),
        )
