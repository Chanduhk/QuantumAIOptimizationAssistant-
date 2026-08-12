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
    _validate_non_negative_float,
    _validate_non_negative_int,
    _validate_optional_non_negative_int,
)


class ExecutionMode(str, Enum):
    """Solver execution categories supported by the domain contract."""

    EXACT_CLASSICAL = "exact_classical"
    LOCAL_SIMULATOR = "local_simulator"
    QUANTUM_SIMULATOR = "quantum_simulator"
    QUANTUM_HARDWARE = "quantum_hardware"


@dataclass(frozen=True)
class QuantumSolveMetadata:
    """Immutable solver execution metadata without provider coupling."""

    solver_name: str
    execution_mode: ExecutionMode | str
    backend_name: str | None = None
    deterministic: bool = True
    seed: int | None = None
    runtime_seconds: float | None = None
    iterations: int | None = None
    shots: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "solver_name", _validate_name(self.solver_name, "solver_name"))
        object.__setattr__(self, "execution_mode", _validate_enum(self.execution_mode, ExecutionMode, "execution_mode"))
        if self.backend_name is not None:
            object.__setattr__(self, "backend_name", _validate_name(self.backend_name, "backend_name"))
        if not isinstance(self.deterministic, bool):
            raise ValueError("deterministic must be a boolean.")
        object.__setattr__(self, "seed", _validate_optional_non_negative_int(self.seed, "seed"))
        if self.runtime_seconds is not None:
            object.__setattr__(
                self,
                "runtime_seconds",
                _validate_non_negative_float(self.runtime_seconds, "runtime_seconds"),
            )
        object.__setattr__(self, "iterations", _validate_optional_non_negative_int(self.iterations, "iterations"))
        object.__setattr__(self, "shots", _validate_optional_non_negative_int(self.shots, "shots"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without mutating the model."""

        return {
            "solver_name": self.solver_name,
            "execution_mode": self.execution_mode.value,
            "backend_name": self.backend_name,
            "deterministic": self.deterministic,
            "seed": self.seed,
            "runtime_seconds": self.runtime_seconds,
            "iterations": self.iterations,
            "shots": self.shots,
            "metadata": _thaw_value(self.metadata),
        }


@dataclass(frozen=True)
class QuantumSolution:
    """Immutable solver-independent optimization result contract."""

    solution_id: str
    problem_id: str
    assignments: Mapping[str, int]
    objective_value: float
    feasible: bool
    energy: float | None
    solver_name: str
    execution_mode: ExecutionMode | str
    runtime_seconds: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "solution_id", _validate_identifier(self.solution_id, "solution_id"))
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        object.__setattr__(self, "assignments", self._freeze_assignments(self.assignments))
        object.__setattr__(self, "objective_value", _validate_finite_float(self.objective_value, "objective_value"))
        if not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean.")
        if self.energy is not None:
            object.__setattr__(self, "energy", _validate_finite_float(self.energy, "energy"))
        object.__setattr__(self, "solver_name", _validate_name(self.solver_name, "solver_name"))
        object.__setattr__(self, "execution_mode", _validate_enum(self.execution_mode, ExecutionMode, "execution_mode"))
        if self.runtime_seconds is not None:
            object.__setattr__(
                self,
                "runtime_seconds",
                _validate_non_negative_float(self.runtime_seconds, "runtime_seconds"),
            )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    @staticmethod
    def _freeze_assignments(assignments: Mapping[str, int]) -> Mapping[str, int]:
        if not isinstance(assignments, Mapping) or not assignments:
            raise ValueError("assignments must be a non-empty mapping.")
        frozen: dict[str, int] = {}
        for variable_id in sorted(assignments):
            normalized_id = _validate_identifier(variable_id, "assignment variable_id")
            value = assignments[variable_id]
            if isinstance(value, bool) or value not in (0, 1):
                raise ValueError("assignment values must be exactly 0 or 1.")
            frozen[normalized_id] = int(value)
        return MappingProxyType(frozen)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without mutating the model."""

        return {
            "solution_id": self.solution_id,
            "problem_id": self.problem_id,
            "assignments": {key: self.assignments[key] for key in sorted(self.assignments)},
            "objective_value": self.objective_value,
            "feasible": self.feasible,
            "energy": self.energy,
            "solver_name": self.solver_name,
            "execution_mode": self.execution_mode.value,
            "runtime_seconds": self.runtime_seconds,
            "metadata": _thaw_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QuantumSolution":
        """Create a solution from a mapping using normal constructor validation."""

        if not isinstance(data, Mapping):
            raise ValueError("QuantumSolution data must be a mapping.")
        return cls(
            solution_id=data.get("solution_id"),
            problem_id=data.get("problem_id"),
            assignments=data.get("assignments", {}),
            objective_value=data.get("objective_value"),
            feasible=data.get("feasible"),
            energy=data.get("energy"),
            solver_name=data.get("solver_name"),
            execution_mode=data.get("execution_mode"),
            runtime_seconds=data.get("runtime_seconds"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class QuantumSolveRequest:
    """Immutable request contract for future solver layers."""

    request_id: str
    problem_id: str
    solver_name: str
    execution_mode: ExecutionMode | str
    configuration: Mapping[str, Any] = field(default_factory=dict)
    deterministic_seed: int | None = None
    resource_limits: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _validate_identifier(self.request_id, "request_id"))
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        object.__setattr__(self, "solver_name", _validate_name(self.solver_name, "solver_name"))
        object.__setattr__(self, "execution_mode", _validate_enum(self.execution_mode, ExecutionMode, "execution_mode"))
        object.__setattr__(self, "configuration", _freeze_mapping(self.configuration, "configuration"))
        object.__setattr__(
            self,
            "deterministic_seed",
            _validate_optional_non_negative_int(self.deterministic_seed, "deterministic_seed"),
        )
        object.__setattr__(self, "resource_limits", self._freeze_resource_limits(self.resource_limits))

    @staticmethod
    def _freeze_resource_limits(resource_limits: Mapping[str, float]) -> Mapping[str, float]:
        if not isinstance(resource_limits, Mapping):
            raise ValueError("resource_limits must be a mapping.")
        frozen: dict[str, float] = {}
        for key in sorted(resource_limits):
            name = _validate_identifier(key, "resource limit key")
            frozen[name] = _validate_non_negative_float(resource_limits[key], "resource limit")
        return MappingProxyType(frozen)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without mutating the model."""

        return {
            "request_id": self.request_id,
            "problem_id": self.problem_id,
            "solver_name": self.solver_name,
            "execution_mode": self.execution_mode.value,
            "configuration": _thaw_value(self.configuration),
            "deterministic_seed": self.deterministic_seed,
            "resource_limits": {key: self.resource_limits[key] for key in sorted(self.resource_limits)},
        }
