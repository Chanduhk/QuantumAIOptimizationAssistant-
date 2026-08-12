from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.quantum.domain.quantum_objective import (
    _freeze_mapping,
    _thaw_value,
    _validate_enum,
    _validate_finite_float,
    _validate_identifier,
    _validate_name,
)


class ConstraintSense(str, Enum):
    """Supported constraint directions for quantum optimization contracts."""

    EQ = "EQ"
    LE = "LE"
    GE = "GE"


@dataclass(frozen=True)
class QuantumConstraint:
    """Immutable linear constraint contract without penalty encoding."""

    constraint_id: str
    name: str
    sense: ConstraintSense | str
    rhs: float
    coefficients: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", _validate_identifier(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "name", _validate_name(self.name, "name"))
        object.__setattr__(self, "sense", _validate_enum(self.sense, ConstraintSense, "sense"))
        object.__setattr__(self, "rhs", _validate_finite_float(self.rhs, "rhs"))
        object.__setattr__(self, "coefficients", self._freeze_coefficients(self.coefficients))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    @staticmethod
    def _freeze_coefficients(coefficients: Mapping[str, float]) -> Mapping[str, float]:
        if not isinstance(coefficients, Mapping):
            raise ValueError("coefficients must be a mapping.")
        frozen: dict[str, float] = {}
        for variable_id in sorted(coefficients):
            normalized_id = _validate_identifier(variable_id, "constraint coefficient variable_id")
            frozen[normalized_id] = _validate_finite_float(coefficients[variable_id], "constraint coefficient")
        return MappingProxyType(frozen)

    def variable_ids(self) -> tuple[str, ...]:
        """Return referenced variable IDs in deterministic order."""

        return tuple(sorted(self.coefficients))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without mutating the model."""

        return {
            "constraint_id": self.constraint_id,
            "name": self.name,
            "sense": self.sense.value,
            "rhs": self.rhs,
            "coefficients": {key: self.coefficients[key] for key in sorted(self.coefficients)},
            "metadata": _thaw_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QuantumConstraint":
        """Create a constraint from a mapping using normal constructor validation."""

        if not isinstance(data, Mapping):
            raise ValueError("QuantumConstraint data must be a mapping.")
        return cls(
            constraint_id=data.get("constraint_id"),
            name=data.get("name"),
            sense=data.get("sense"),
            rhs=data.get("rhs"),
            coefficients=data.get("coefficients", {}),
            metadata=data.get("metadata", {}),
        )
