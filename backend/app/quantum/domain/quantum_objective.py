from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

_SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,127}$")
BINARY_DOMAIN: tuple[int, int] = (0, 1)


class ObjectiveSense(str, Enum):
    """Supported objective directions for quantum optimization contracts."""

    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"


@dataclass(frozen=True)
class QuantumVariable:
    """Immutable binary optimization variable contract."""

    variable_id: str
    name: str
    index: int
    domain: tuple[int, int] = BINARY_DOMAIN
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "variable_id", _validate_identifier(self.variable_id, "variable_id"))
        object.__setattr__(self, "name", _validate_name(self.name, "name"))
        object.__setattr__(self, "index", _validate_non_negative_int(self.index, "index"))
        if tuple(self.domain) != BINARY_DOMAIN:
            raise ValueError("domain must be exactly (0, 1) for E.1 binary variables.")
        object.__setattr__(self, "domain", BINARY_DOMAIN)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without mutating the model."""

        return {
            "variable_id": self.variable_id,
            "name": self.name,
            "index": self.index,
            "domain": list(self.domain),
            "metadata": _thaw_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QuantumVariable":
        """Create a variable from a mapping using normal constructor validation."""

        if not isinstance(data, Mapping):
            raise ValueError("QuantumVariable data must be a mapping.")
        return cls(
            variable_id=data.get("variable_id"),
            name=data.get("name"),
            index=data.get("index"),
            domain=tuple(data.get("domain", BINARY_DOMAIN)),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class QuantumObjective:
    """Immutable objective metadata contract."""

    objective_id: str
    name: str
    sense: ObjectiveSense | str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective_id", _validate_identifier(self.objective_id, "objective_id"))
        object.__setattr__(self, "name", _validate_name(self.name, "name"))
        object.__setattr__(self, "sense", _validate_enum(self.sense, ObjectiveSense, "sense"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without mutating the model."""

        return {
            "objective_id": self.objective_id,
            "name": self.name,
            "sense": self.sense.value,
            "metadata": _thaw_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QuantumObjective":
        """Create an objective from a mapping using normal constructor validation."""

        if not isinstance(data, Mapping):
            raise ValueError("QuantumObjective data must be a mapping.")
        return cls(
            objective_id=data.get("objective_id"),
            name=data.get("name"),
            sense=data.get("sense"),
            metadata=data.get("metadata", {}),
        )


def _validate_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty.")
    if not _SAFE_IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} contains unsafe characters.")
    return normalized


def _validate_name(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty.")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError(f"{field_name} cannot contain control characters.")
    return normalized


def _validate_finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _validate_non_negative_float(value: object, field_name: str) -> float:
    number = _validate_finite_float(value, field_name)
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return number


def _validate_non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return value


def _validate_optional_non_negative_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _validate_non_negative_int(value, field_name)


def _validate_enum(value: object, enum_type: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        for member in enum_type:
            if normalized == member.value:
                return member
    raise ValueError(f"{field_name} must be one of {[member.value for member in enum_type]}.")


def _freeze_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    frozen: dict[str, Any] = {}
    for key in sorted(value):
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-empty strings.")
        frozen[key.strip()] = _freeze_value(value[key], f"{field_name}.{key}")
    return MappingProxyType(frozen)


def _freeze_value(value: Any, field_name: str) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value, field_name)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item, field_name) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_value(item, field_name) for item in value))
    if isinstance(value, float):
        return _validate_finite_float(value, field_name)
    return value


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_value(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value
