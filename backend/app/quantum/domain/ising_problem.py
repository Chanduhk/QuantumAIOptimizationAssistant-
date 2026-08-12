from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.quantum.domain.quantum_objective import (
    QuantumObjective,
    _freeze_mapping,
    _thaw_value,
    _validate_finite_float,
    _validate_identifier,
    _validate_name,
)


@dataclass(frozen=True)
class IsingProblem:
    """Immutable framework-independent Ising Hamiltonian contract."""

    problem_id: str
    name: str
    variables: tuple[str, ...]
    linear_coefficients: Mapping[str, float]
    quadratic_coefficients: Mapping[tuple[str, str], float]
    constant_offset: float
    objective: QuantumObjective
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        object.__setattr__(self, "name", _validate_name(self.name, "name"))
        variables = self._validate_variables(self.variables)
        variable_ids = set(variables)
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
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    @staticmethod
    def _validate_variables(variables: tuple[str, ...]) -> tuple[str, ...]:
        if not isinstance(variables, tuple) or not variables:
            raise ValueError("variables must be a non-empty tuple of spin IDs.")
        normalized = tuple(_validate_identifier(variable_id, "spin variable_id") for variable_id in variables)
        if len(set(normalized)) != len(normalized):
            raise ValueError("duplicate spin variable_id in Ising variables.")
        return tuple(sorted(normalized))

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
                raise ValueError(f"linear coefficient references unknown spin '{normalized_id}'.")
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
                raise ValueError("self quadratic terms are not allowed in Ising couplings.")
            if left not in variable_ids or right not in variable_ids:
                raise ValueError("quadratic coefficient references unknown spin.")
            canonical_pair = tuple(sorted((left, right)))
            if canonical_pair in frozen:
                raise ValueError("duplicate quadratic coefficient after canonicalization.")
            frozen[canonical_pair] = _validate_finite_float(coefficient, "quadratic coefficient")
        return MappingProxyType(dict(sorted(frozen.items())))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without mutating the model."""

        return {
            "problem_id": self.problem_id,
            "name": self.name,
            "variables": list(self.variables),
            "linear_coefficients": {key: self.linear_coefficients[key] for key in sorted(self.linear_coefficients)},
            "quadratic_coefficients": [
                {"variables": list(pair), "coefficient": self.quadratic_coefficients[pair]}
                for pair in sorted(self.quadratic_coefficients)
            ],
            "constant_offset": self.constant_offset,
            "objective": self.objective.to_dict(),
            "metadata": _thaw_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IsingProblem":
        """Create an Ising problem from a mapping using normal constructor validation."""

        if not isinstance(data, Mapping):
            raise ValueError("IsingProblem data must be a mapping.")
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
            variables=tuple(data.get("variables", [])),
            linear_coefficients=data.get("linear_coefficients", {}),
            quadratic_coefficients=quadratic_coefficients,
            constant_offset=data.get("constant_offset"),
            objective=QuantumObjective.from_dict(data.get("objective", {})),
            metadata=data.get("metadata", {}),
        )
