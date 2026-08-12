from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.quantum.integration import AIQuantumIntegrationResult

VALID_OBJECTIVE_SENSES = frozenset({"MINIMIZE", "MAXIMIZE"})
VALID_SUITABILITY = frozenset({"SUITABLE", "UNSUITABLE", "UNSUPPORTED", "REQUIRES_REFORMULATION", "RESOURCE_LIMIT"})
VALID_PATHS = frozenset({"quantum_hybrid", "classical_fallback", "requires_reformulation", "unsupported", "resource_limited"})


@dataclass(frozen=True)
class ExecutiveQuantumEvidence:
    """Immutable executive-facing evidence distilled from an E.7 result."""

    request_id: str
    problem_id: str
    objective_sense: str
    suitability_decision: str
    execution_path: str
    quantum_used: bool
    classical_used: bool
    exact_reference_available: bool
    exact_match: bool | None
    quantum_match: bool | None
    energy_gap: float | None
    relative_gap: float | None
    feasible: bool | None
    selected_solver: str | None
    selected_candidate_type: str | None
    reason_selected: str
    limitations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _identifier(self.request_id, "request_id"))
        object.__setattr__(self, "problem_id", _identifier(self.problem_id, "problem_id"))
        if self.objective_sense not in VALID_OBJECTIVE_SENSES:
            raise ValueError("objective_sense must be MINIMIZE or MAXIMIZE.")
        if self.suitability_decision not in VALID_SUITABILITY:
            raise ValueError("suitability_decision is invalid.")
        if self.execution_path not in VALID_PATHS:
            raise ValueError("execution_path is invalid.")
        for field_name in ("quantum_used", "classical_used", "exact_reference_available"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean.")
        for field_name in ("exact_match", "quantum_match", "feasible"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"{field_name} must be a boolean or None.")
        for field_name in ("energy_gap", "relative_gap"):
            value = getattr(self, field_name)
            if value is not None:
                number = _finite(value, field_name)
                if number < -1e-12:
                    raise ValueError(f"{field_name} cannot be negative.")
                object.__setattr__(self, field_name, max(0.0, number))
        if self.selected_solver is not None:
            object.__setattr__(self, "selected_solver", _text(self.selected_solver, "selected_solver"))
        if self.selected_candidate_type is not None:
            object.__setattr__(self, "selected_candidate_type", _text(self.selected_candidate_type, "selected_candidate_type"))
        object.__setattr__(self, "reason_selected", _text(self.reason_selected, "reason_selected"))
        object.__setattr__(self, "limitations", _text_tuple(self.limitations, "limitations"))
        object.__setattr__(self, "warnings", _text_tuple(self.warnings, "warnings"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic serialization-friendly evidence payload."""

        return {
            "request_id": self.request_id,
            "problem_id": self.problem_id,
            "objective_sense": self.objective_sense,
            "suitability_decision": self.suitability_decision,
            "execution_path": self.execution_path,
            "quantum_used": self.quantum_used,
            "classical_used": self.classical_used,
            "exact_reference_available": self.exact_reference_available,
            "exact_match": self.exact_match,
            "quantum_match": self.quantum_match,
            "energy_gap": self.energy_gap,
            "relative_gap": self.relative_gap,
            "feasible": self.feasible,
            "selected_solver": self.selected_solver,
            "selected_candidate_type": self.selected_candidate_type,
            "reason_selected": self.reason_selected,
            "limitations": list(self.limitations),
            "warnings": list(self.warnings),
            "metadata": _thaw(self.metadata),
        }


def evidence_from_e7(result: AIQuantumIntegrationResult) -> ExecutiveQuantumEvidence:
    """Convert a validated E.7 result into compact executive quantum evidence."""

    if not isinstance(result, AIQuantumIntegrationResult):
        raise ValueError("quantum_result must be an AIQuantumIntegrationResult.")
    selected_type = None if result.selected_candidate is None else result.selected_candidate.candidate_type
    reason = result.explanation
    if result.hybrid_result is not None:
        reason = result.hybrid_result.selection.reason_selected
    warnings = _warnings(result)
    return ExecutiveQuantumEvidence(
        request_id=result.request_id,
        problem_id=result.problem_id,
        objective_sense=result.objective_sense,
        suitability_decision=result.suitability_decision,
        execution_path=result.execution_path,
        quantum_used=result.quantum_used,
        classical_used=result.classical_used,
        exact_reference_available=result.exact_reference_available,
        exact_match=result.exact_match,
        quantum_match=result.exact_match if result.quantum_used else None,
        energy_gap=result.energy_gap,
        relative_gap=result.relative_gap,
        feasible=result.feasible,
        selected_solver=result.selected_solver,
        selected_candidate_type=selected_type,
        reason_selected=reason,
        limitations=result.suitability_reasons,
        warnings=warnings,
        metadata={
            "source": "AIQuantumIntegrationResult",
            "e6_used": result.execution_metadata.get("e6_used", False),
            "qaoa_executed": result.execution_metadata.get("qaoa_executed", False),
            "hardware_execution": result.execution_metadata.get("hardware_execution", False),
            "quantum_advantage_claimed": result.execution_metadata.get("quantum_advantage_claimed", False),
        },
    )


def _warnings(result: AIQuantumIntegrationResult) -> tuple[str, ...]:
    warnings = []
    if result.quantum_used and result.exact_match is False:
        warnings.append("QAOA candidate did not match the exact reference.")
    if result.suitability_decision == "RESOURCE_LIMIT":
        warnings.append("Quantum path exceeded the configured resource limit.")
    if result.suitability_decision == "REQUIRES_REFORMULATION":
        warnings.append("Problem requires reformulation before quantum execution.")
    if result.feasible is False:
        warnings.append("Selected candidate is infeasible.")
    if result.execution_metadata.get("hardware_execution") is True:
        warnings.append("Hardware execution metadata must be independently governed.")
    return tuple(sorted(dict.fromkeys(warnings)))


def _identifier(value: object, field_name: str) -> str:
    text = _text(value, field_name)
    if not text[0].isalpha() or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for char in text):
        raise ValueError(f"{field_name} contains unsafe characters.")
    return text


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    normalized = value.strip()
    if any(ord(char) < 32 for char in normalized):
        raise ValueError(f"{field_name} cannot contain control characters.")
    return normalized


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


def _text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be a tuple.")
    return tuple(_text(value, field_name) for value in values)


def _freeze_mapping(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    frozen: dict[str, Any] = {}
    for key in sorted(value):
        frozen[_text(key, f"{field_name} key")] = _freeze(value[key], field_name)
    return MappingProxyType(frozen)


def _freeze(value: Any, field_name: str) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value, field_name)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item, field_name) for item in value)
    if isinstance(value, float):
        return _finite(value, field_name)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
