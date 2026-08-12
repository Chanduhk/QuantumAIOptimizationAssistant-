from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.quantum.domain import IsingProblem, QUBOProblem
from backend.app.quantum.domain.quantum_objective import (
    _freeze_mapping,
    _thaw_value,
    _validate_identifier,
    _validate_name,
    _validate_non_negative_int,
)
from backend.app.quantum.hybrid import HybridCandidate, HybridOptimizationResult

VALID_OBJECTIVE_SENSES = frozenset({"MINIMIZE", "MAXIMIZE"})
VALID_INTEGRATION_DECISIONS = frozenset(
    {"SUITABLE", "UNSUITABLE", "UNSUPPORTED", "REQUIRES_REFORMULATION", "RESOURCE_LIMIT"}
)
VALID_EXECUTION_PATHS = frozenset(
    {"quantum_hybrid", "classical_fallback", "requires_reformulation", "unsupported", "resource_limited"}
)
VALID_VARIABLE_DOMAINS = frozenset({"binary"})


@dataclass(frozen=True)
class AIOptimizationVariable:
    """Immutable AI-facing optimization variable accepted by the E.7 adapter."""

    variable_id: str
    name: str
    index: int
    domain: str = "binary"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "variable_id", _validate_identifier(self.variable_id, "variable_id"))
        object.__setattr__(self, "name", _validate_name(self.name, "name"))
        object.__setattr__(self, "index", _validate_non_negative_int(self.index, "index"))
        if not isinstance(self.domain, str) or self.domain.strip().lower() not in VALID_VARIABLE_DOMAINS:
            raise ValueError("domain must be binary for E.7 quantum adaptation.")
        object.__setattr__(self, "domain", "binary")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly variable representation."""

        return {
            "variable_id": self.variable_id,
            "name": self.name,
            "index": self.index,
            "domain": self.domain,
            "metadata": _thaw_value(self.metadata),
        }


@dataclass(frozen=True)
class AIOptimizationProblem:
    """Immutable AI optimization problem contract that can be adapted to E.1/E.2."""

    problem_id: str
    name: str
    variables: tuple[AIOptimizationVariable, ...]
    linear_coefficients: Mapping[str, float]
    quadratic_coefficients: Mapping[tuple[str, str], float] = field(default_factory=dict)
    constant_offset: float = 0.0
    objective_sense: str = "MINIMIZE"
    constraints: tuple[Mapping[str, Any], ...] = ()
    penalty: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        object.__setattr__(self, "name", _validate_name(self.name, "name"))
        variables = self._validate_variables(self.variables)
        variable_ids = {variable.variable_id for variable in variables}
        object.__setattr__(self, "variables", variables)
        object.__setattr__(self, "linear_coefficients", _freeze_coefficients(self.linear_coefficients, variable_ids))
        object.__setattr__(
            self,
            "quadratic_coefficients",
            _freeze_quadratic_coefficients(self.quadratic_coefficients, variable_ids),
        )
        object.__setattr__(self, "constant_offset", _finite(self.constant_offset, "constant_offset"))
        if self.objective_sense not in VALID_OBJECTIVE_SENSES:
            raise ValueError("objective_sense must be MINIMIZE or MAXIMIZE.")
        object.__setattr__(self, "constraints", self._freeze_constraints(self.constraints, variable_ids))
        if self.constraints and self.penalty is None:
            raise ValueError("penalty is required for constrained AI optimization problems.")
        if self.penalty is not None:
            penalty = _finite(self.penalty, "penalty")
            if penalty <= 0:
                raise ValueError("penalty must be positive.")
            object.__setattr__(self, "penalty", penalty)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    @staticmethod
    def _validate_variables(variables: tuple[AIOptimizationVariable, ...]) -> tuple[AIOptimizationVariable, ...]:
        if not isinstance(variables, tuple) or not variables:
            raise ValueError("variables must be a non-empty tuple.")
        ordered = tuple(sorted(variables, key=lambda variable: variable.index))
        seen_ids: set[str] = set()
        seen_indexes: set[int] = set()
        for variable in ordered:
            if not isinstance(variable, AIOptimizationVariable):
                raise ValueError("variables must contain AIOptimizationVariable instances.")
            if variable.variable_id in seen_ids:
                raise ValueError("duplicate variable_id in variables.")
            if variable.index in seen_indexes:
                raise ValueError("duplicate variable index in variables.")
            seen_ids.add(variable.variable_id)
            seen_indexes.add(variable.index)
        return ordered

    @staticmethod
    def _freeze_constraints(
        constraints: tuple[Mapping[str, Any], ...],
        variable_ids: set[str],
    ) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(constraints, tuple):
            raise ValueError("constraints must be a tuple.")
        frozen: list[Mapping[str, Any]] = []
        seen_ids: set[str] = set()
        for constraint in sorted(constraints, key=lambda item: str(item.get("constraint_id", ""))):
            if not isinstance(constraint, Mapping):
                raise ValueError("constraints must contain mappings.")
            constraint_id = _validate_identifier(constraint.get("constraint_id"), "constraint_id")
            if constraint_id in seen_ids:
                raise ValueError("duplicate constraint_id in constraints.")
            coefficients = constraint.get("coefficients", {})
            if not isinstance(coefficients, Mapping):
                raise ValueError("constraint coefficients must be a mapping.")
            unknown = {str(variable_id).strip() for variable_id in coefficients} - variable_ids
            if unknown:
                raise ValueError(f"constraint references unknown variables: {sorted(unknown)}.")
            frozen.append(_freeze_mapping(constraint, "constraint"))
            seen_ids.add(constraint_id)
        return tuple(frozen)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly problem representation."""

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
            "objective_sense": self.objective_sense,
            "constraints": [_thaw_value(constraint) for constraint in self.constraints],
            "penalty": self.penalty,
            "metadata": _thaw_value(self.metadata),
        }


@dataclass(frozen=True)
class QuantumSuitabilityResult:
    """Immutable suitability decision for routing an AI problem into the quantum stack."""

    decision: str
    reasons: tuple[str, ...]
    variable_count: int
    estimated_states: int
    limiting_factor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision not in VALID_INTEGRATION_DECISIONS:
            raise ValueError("decision is invalid.")
        if not isinstance(self.reasons, tuple):
            raise ValueError("reasons must be a tuple.")
        if any(not isinstance(reason, str) or not reason.strip() for reason in self.reasons):
            raise ValueError("reasons must be non-empty strings.")
        object.__setattr__(self, "reasons", tuple(reason.strip() for reason in self.reasons))
        object.__setattr__(self, "variable_count", _validate_non_negative_int(self.variable_count, "variable_count"))
        states = _validate_non_negative_int(self.estimated_states, "estimated_states")
        object.__setattr__(self, "estimated_states", states)
        if self.limiting_factor is not None:
            object.__setattr__(self, "limiting_factor", _validate_name(self.limiting_factor, "limiting_factor"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly suitability result."""

        return {
            "decision": self.decision,
            "reasons": list(self.reasons),
            "variable_count": self.variable_count,
            "estimated_states": self.estimated_states,
            "limiting_factor": self.limiting_factor,
            "metadata": _thaw_value(self.metadata),
        }


@dataclass(frozen=True)
class AIQuantumIntegrationConfig:
    """Immutable routing configuration for E.7 AI + quantum integration."""

    allow_quantum: bool = True
    allow_classical_fallback: bool = True
    max_variables_for_quantum: int = 8
    max_states_for_suitability: int = 256
    qaoa_shots: int = 512
    qaoa_seed: int = 123
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.allow_quantum, bool):
            raise ValueError("allow_quantum must be a boolean.")
        if not isinstance(self.allow_classical_fallback, bool):
            raise ValueError("allow_classical_fallback must be a boolean.")
        for field_name in ("max_variables_for_quantum", "max_states_for_suitability", "qaoa_shots", "qaoa_seed"):
            value = _validate_non_negative_int(getattr(self, field_name), field_name)
            if field_name != "qaoa_seed" and value <= 0:
                raise ValueError(f"{field_name} must be positive.")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))


@dataclass(frozen=True)
class AIQuantumIntegrationResult:
    """Immutable unified E.7 result for E.8 consumption."""

    request_id: str
    problem_id: str
    objective_sense: str
    suitability_decision: str
    suitability_reasons: tuple[str, ...]
    execution_path: str
    quantum_used: bool
    classical_used: bool
    classical_candidate: HybridCandidate | None
    quantum_candidate: HybridCandidate | None
    hybrid_result: HybridOptimizationResult | None
    selected_candidate: HybridCandidate | None
    selected_solver: str | None
    objective_value: float | None
    energy: float | None
    feasible: bool | None
    exact_reference_available: bool
    exact_match: bool | None
    energy_gap: float | None
    relative_gap: float | None
    explanation: str
    execution_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _validate_identifier(self.request_id, "request_id"))
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        if self.objective_sense not in VALID_OBJECTIVE_SENSES:
            raise ValueError("objective_sense must be MINIMIZE or MAXIMIZE.")
        if self.suitability_decision not in VALID_INTEGRATION_DECISIONS:
            raise ValueError("suitability_decision is invalid.")
        if not isinstance(self.suitability_reasons, tuple):
            raise ValueError("suitability_reasons must be a tuple.")
        object.__setattr__(self, "suitability_reasons", tuple(_validate_name(item, "reason") for item in self.suitability_reasons))
        if self.execution_path not in VALID_EXECUTION_PATHS:
            raise ValueError("execution_path is invalid.")
        if not isinstance(self.quantum_used, bool) or not isinstance(self.classical_used, bool):
            raise ValueError("quantum_used and classical_used must be booleans.")
        for field_name in ("classical_candidate", "quantum_candidate", "selected_candidate"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, HybridCandidate):
                raise ValueError(f"{field_name} must be a HybridCandidate or None.")
        if self.hybrid_result is not None and not isinstance(self.hybrid_result, HybridOptimizationResult):
            raise ValueError("hybrid_result must be a HybridOptimizationResult or None.")
        if self.selected_solver is not None:
            object.__setattr__(self, "selected_solver", _validate_name(self.selected_solver, "selected_solver"))
        for field_name in ("objective_value", "energy", "energy_gap", "relative_gap"):
            value = getattr(self, field_name)
            if value is not None:
                parsed = _finite(value, field_name)
                if field_name in {"energy_gap", "relative_gap"} and parsed < -1e-12:
                    raise ValueError(f"{field_name} cannot be negative.")
                object.__setattr__(self, field_name, max(0.0, parsed) if field_name in {"energy_gap", "relative_gap"} else parsed)
        if self.feasible is not None and not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean or None.")
        if not isinstance(self.exact_reference_available, bool):
            raise ValueError("exact_reference_available must be a boolean.")
        if self.exact_match is not None and not isinstance(self.exact_match, bool):
            raise ValueError("exact_match must be a boolean or None.")
        object.__setattr__(self, "explanation", _validate_name(self.explanation, "explanation"))
        object.__setattr__(self, "execution_metadata", _freeze_mapping(self.execution_metadata, "execution_metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly unified E.7 result."""

        return {
            "request_id": self.request_id,
            "problem_id": self.problem_id,
            "objective_sense": self.objective_sense,
            "suitability_decision": self.suitability_decision,
            "suitability_reasons": list(self.suitability_reasons),
            "execution_path": self.execution_path,
            "quantum_used": self.quantum_used,
            "classical_used": self.classical_used,
            "classical_candidate": None if self.classical_candidate is None else self.classical_candidate.to_dict(),
            "quantum_candidate": None if self.quantum_candidate is None else self.quantum_candidate.to_dict(),
            "selected_candidate": None if self.selected_candidate is None else self.selected_candidate.to_dict(),
            "selected_solver": self.selected_solver,
            "objective_value": self.objective_value,
            "energy": self.energy,
            "feasible": self.feasible,
            "exact_reference_available": self.exact_reference_available,
            "exact_match": self.exact_match,
            "energy_gap": self.energy_gap,
            "relative_gap": self.relative_gap,
            "explanation": self.explanation,
            "execution_metadata": _thaw_value(self.execution_metadata),
        }


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _freeze_coefficients(coefficients: Mapping[str, float], variable_ids: set[str]) -> Mapping[str, float]:
    if not isinstance(coefficients, Mapping):
        raise ValueError("linear_coefficients must be a mapping.")
    frozen: dict[str, float] = {}
    for variable_id in sorted(coefficients):
        normalized_id = _validate_identifier(variable_id, "coefficient variable_id")
        if normalized_id not in variable_ids:
            raise ValueError(f"coefficient references unknown variable '{normalized_id}'.")
        frozen[normalized_id] = _finite(coefficients[variable_id], "coefficient")
    return MappingProxyType(frozen)


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
            raise ValueError("self quadratic terms are not supported; use linear_coefficients.")
        if left not in variable_ids or right not in variable_ids:
            raise ValueError("quadratic coefficient references unknown variable.")
        canonical = tuple(sorted((left, right)))
        if canonical in frozen:
            raise ValueError("duplicate quadratic coefficient after canonicalization.")
        frozen[canonical] = _finite(coefficient, "quadratic coefficient")
    return MappingProxyType(dict(sorted(frozen.items())))
