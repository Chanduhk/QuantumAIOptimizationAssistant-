from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.quantum.domain import QuantumSolution
from backend.app.quantum.domain.quantum_objective import (
    _freeze_mapping,
    _thaw_value,
    _validate_identifier,
    _validate_non_negative_int,
)
from backend.app.quantum.optimization.exceptions import QAOAConfigurationError, QAOAParameterError, QAOAResultError

DEFAULT_ANGLE_GRID = (0.0, math.pi / 4.0, math.pi / 2.0, 3.0 * math.pi / 4.0, math.pi)


@dataclass(frozen=True)
class QAOAParameterSet:
    """Immutable gamma/beta parameter vector for p-layer QAOA."""

    gammas: tuple[float, ...]
    betas: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.gammas, tuple) or not isinstance(self.betas, tuple):
            raise QAOAParameterError("gammas and betas must be tuples.")
        if not self.gammas or len(self.gammas) != len(self.betas):
            raise QAOAParameterError("gammas and betas must be non-empty and equal length.")
        object.__setattr__(self, "gammas", tuple(_finite(value, "gamma") for value in self.gammas))
        object.__setattr__(self, "betas", tuple(_finite(value, "beta") for value in self.betas))

    @property
    def depth(self) -> int:
        """Return QAOA depth p."""

        return len(self.gammas)

    def to_dict(self) -> dict[str, list[float]]:
        """Return a JSON-friendly parameter representation."""

        return {"gammas": list(self.gammas), "betas": list(self.betas)}


@dataclass(frozen=True)
class QAOAConfig:
    """Immutable bounded QAOA execution and parameter configuration."""

    depth: int = 1
    parameters: QAOAParameterSet | None = None
    optimize_parameters: bool = False
    angle_grid: tuple[float, ...] = DEFAULT_ANGLE_GRID
    max_iterations: int = 25
    shots: int = 1024
    seed: int = 123
    max_qubits: int = 8
    max_depth: int = 3
    max_shots: int = 100_000
    max_operations: int = 512
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        depth = _positive_int(self.depth, "depth")
        max_depth = _positive_int(self.max_depth, "max_depth")
        if depth > max_depth:
            raise QAOAConfigurationError(f"depth {depth} exceeds max_depth {max_depth}.")
        object.__setattr__(self, "depth", depth)
        object.__setattr__(self, "max_depth", max_depth)
        if self.parameters is not None:
            if not isinstance(self.parameters, QAOAParameterSet):
                raise QAOAConfigurationError("parameters must be a QAOAParameterSet.")
            if self.parameters.depth != depth:
                raise QAOAParameterError("parameter depth must match config depth.")
        object.__setattr__(self, "angle_grid", self._validate_angle_grid(self.angle_grid))
        object.__setattr__(self, "max_iterations", _positive_int(self.max_iterations, "max_iterations"))
        object.__setattr__(self, "shots", _positive_int(self.shots, "shots"))
        object.__setattr__(self, "seed", _validate_seed(self.seed))
        object.__setattr__(self, "max_qubits", _positive_int(self.max_qubits, "max_qubits"))
        object.__setattr__(self, "max_shots", _positive_int(self.max_shots, "max_shots"))
        object.__setattr__(self, "max_operations", _positive_int(self.max_operations, "max_operations"))
        if self.shots > self.max_shots:
            raise QAOAConfigurationError(f"shots {self.shots} exceeds max_shots {self.max_shots}.")
        if not isinstance(self.optimize_parameters, bool):
            raise QAOAConfigurationError("optimize_parameters must be a boolean.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    @staticmethod
    def _validate_angle_grid(values: object) -> tuple[float, ...]:
        if not isinstance(values, tuple) or not values:
            raise QAOAConfigurationError("angle_grid must be a non-empty tuple.")
        return tuple(_finite(value, "angle_grid") for value in values)


@dataclass(frozen=True)
class QAOAResult:
    """Immutable QAOA run result produced from measured simulator candidates."""

    problem_id: str
    representation: str
    parameters: QAOAParameterSet
    expectation_value: float
    empirical_expectation_value: float
    best_solution: QuantumSolution
    ranked_candidates: tuple[QuantumSolution, ...]
    exact_reference_energy: float | None = None
    absolute_energy_gap: float | None = None
    relative_energy_gap: float | None = None
    exact_optimum_found: bool | None = None
    approximation_ratio: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        if self.representation not in {"QUBO", "Ising"}:
            raise QAOAResultError("representation must be QUBO or Ising.")
        if not isinstance(self.parameters, QAOAParameterSet):
            raise QAOAResultError("parameters must be a QAOAParameterSet.")
        object.__setattr__(self, "expectation_value", _finite(self.expectation_value, "expectation_value"))
        object.__setattr__(
            self,
            "empirical_expectation_value",
            _finite(self.empirical_expectation_value, "empirical_expectation_value"),
        )
        if not isinstance(self.best_solution, QuantumSolution):
            raise QAOAResultError("best_solution must be a QuantumSolution.")
        if not isinstance(self.ranked_candidates, tuple) or not self.ranked_candidates:
            raise QAOAResultError("ranked_candidates must be a non-empty tuple.")
        if any(not isinstance(candidate, QuantumSolution) for candidate in self.ranked_candidates):
            raise QAOAResultError("ranked_candidates must contain QuantumSolution instances.")
        for field_name in ("exact_reference_energy", "absolute_energy_gap", "relative_energy_gap", "approximation_ratio"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _finite(value, field_name))
        if self.exact_optimum_found is not None and not isinstance(self.exact_optimum_found, bool):
            raise QAOAResultError("exact_optimum_found must be a boolean or None.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly QAOA result representation."""

        return {
            "problem_id": self.problem_id,
            "representation": self.representation,
            "parameters": self.parameters.to_dict(),
            "expectation_value": self.expectation_value,
            "empirical_expectation_value": self.empirical_expectation_value,
            "best_solution": self.best_solution.to_dict(),
            "ranked_candidates": [candidate.to_dict() for candidate in self.ranked_candidates],
            "exact_reference_energy": self.exact_reference_energy,
            "absolute_energy_gap": self.absolute_energy_gap,
            "relative_energy_gap": self.relative_energy_gap,
            "exact_optimum_found": self.exact_optimum_found,
            "approximation_ratio": self.approximation_ratio,
            "metadata": _thaw_value(self.metadata),
        }


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise QAOAParameterError(f"{field_name} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise QAOAParameterError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise QAOAParameterError(f"{field_name} must be finite.")
    return number


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = _validate_non_negative_int(value, field_name)
    except ValueError as exc:
        raise QAOAConfigurationError(str(exc)) from None
    if parsed <= 0:
        raise QAOAConfigurationError(f"{field_name} must be positive.")
    return parsed


def _validate_seed(value: object) -> int:
    try:
        return _validate_non_negative_int(value, "seed")
    except ValueError as exc:
        raise QAOAConfigurationError(str(exc)) from None
