from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.quantum.domain.quantum_objective import (
    _freeze_mapping,
    _thaw_value,
    _validate_identifier,
    _validate_name,
    _validate_non_negative_int,
)

VALID_CANDIDATE_TYPES = frozenset({"classical_exact", "quantum_qaoa", "classical_heuristic"})
VALID_SENSES = frozenset({"MINIMIZE", "MAXIMIZE"})


@dataclass(frozen=True)
class HybridCandidate:
    """Immutable comparable candidate from exact, QAOA, or optional heuristic sources."""

    candidate_id: str
    candidate_type: str
    problem_id: str
    objective_value: float
    feasible: bool
    assignment: Mapping[str, int]
    energy: float
    sense: str
    solver_name: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _validate_identifier(self.candidate_id, "candidate_id"))
        if self.candidate_type not in VALID_CANDIDATE_TYPES:
            raise ValueError("candidate_type must be classical_exact, quantum_qaoa, or classical_heuristic.")
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        object.__setattr__(self, "objective_value", _finite(self.objective_value, "objective_value"))
        if not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean.")
        object.__setattr__(self, "assignment", _freeze_assignment(self.assignment))
        object.__setattr__(self, "energy", _finite(self.energy, "energy"))
        if self.sense not in VALID_SENSES:
            raise ValueError("sense must be MINIMIZE or MAXIMIZE.")
        object.__setattr__(self, "solver_name", _validate_name(self.solver_name, "solver_name"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-friendly candidate representation."""

        return {
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "problem_id": self.problem_id,
            "objective_value": self.objective_value,
            "feasible": self.feasible,
            "assignment": {key: self.assignment[key] for key in sorted(self.assignment)},
            "energy": self.energy,
            "sense": self.sense,
            "solver_name": self.solver_name,
            "metadata": _thaw_value(self.metadata),
        }


@dataclass(frozen=True)
class HybridComparison:
    """Immutable per-candidate comparison against the exact reference."""

    candidate_id: str
    candidate_type: str
    objective_value: float
    feasible: bool
    energy_gap_to_exact: float
    relative_gap: float | None
    exact_match: bool
    rank: int
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _validate_identifier(self.candidate_id, "candidate_id"))
        if self.candidate_type not in VALID_CANDIDATE_TYPES:
            raise ValueError("candidate_type is invalid.")
        object.__setattr__(self, "objective_value", _finite(self.objective_value, "objective_value"))
        if not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean.")
        gap = _finite(self.energy_gap_to_exact, "energy_gap_to_exact")
        if gap < -1e-12:
            raise ValueError("energy_gap_to_exact cannot be negative.")
        object.__setattr__(self, "energy_gap_to_exact", max(0.0, gap))
        if self.relative_gap is not None:
            relative = _finite(self.relative_gap, "relative_gap")
            if relative < -1e-12:
                raise ValueError("relative_gap cannot be negative.")
            object.__setattr__(self, "relative_gap", max(0.0, relative))
        if not isinstance(self.exact_match, bool):
            raise ValueError("exact_match must be a boolean.")
        rank = _validate_non_negative_int(self.rank, "rank")
        if rank <= 0:
            raise ValueError("rank must be positive.")
        object.__setattr__(self, "rank", rank)
        object.__setattr__(self, "rationale", _validate_name(self.rationale, "rationale"))


@dataclass(frozen=True)
class HybridSelection:
    """Immutable selected candidate and selection rationale."""

    selected_candidate_id: str
    selected_candidate_type: str
    selected_objective_value: float
    reason_selected: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_candidate_id", _validate_identifier(self.selected_candidate_id, "selected_candidate_id"))
        if self.selected_candidate_type not in VALID_CANDIDATE_TYPES:
            raise ValueError("selected_candidate_type is invalid.")
        object.__setattr__(self, "selected_objective_value", _finite(self.selected_objective_value, "selected_objective_value"))
        object.__setattr__(self, "reason_selected", _validate_name(self.reason_selected, "reason_selected"))


@dataclass(frozen=True)
class HybridOptimizationConfig:
    """Immutable bounded hybrid comparison configuration."""

    include_exact_reference: bool = True
    include_qaoa_candidate: bool = True
    max_candidates: int = 8
    exact_match_tolerance: float = 1e-9
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.include_exact_reference, bool):
            raise ValueError("include_exact_reference must be a boolean.")
        if not isinstance(self.include_qaoa_candidate, bool):
            raise ValueError("include_qaoa_candidate must be a boolean.")
        max_candidates = _validate_non_negative_int(self.max_candidates, "max_candidates")
        if max_candidates <= 0:
            raise ValueError("max_candidates must be positive.")
        object.__setattr__(self, "max_candidates", max_candidates)
        tolerance = _finite(self.exact_match_tolerance, "exact_match_tolerance")
        if tolerance < 0:
            raise ValueError("exact_match_tolerance cannot be negative.")
        object.__setattr__(self, "exact_match_tolerance", tolerance)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))


@dataclass(frozen=True)
class HybridBenchmarkReport:
    """Immutable local benchmark report for exact vs quantum comparison."""

    exact_reference_energy: float
    quantum_candidate_energy: float | None
    energy_gap: float | None
    relative_gap: float | None
    exact_match: bool | None
    candidate_count: int
    selected_candidate_type: str
    problem_size: int
    qaoa_depth: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "exact_reference_energy", _finite(self.exact_reference_energy, "exact_reference_energy"))
        for field_name in ("quantum_candidate_energy", "energy_gap", "relative_gap"):
            value = getattr(self, field_name)
            if value is not None:
                parsed = _finite(value, field_name)
                if field_name != "quantum_candidate_energy" and parsed < -1e-12:
                    raise ValueError(f"{field_name} cannot be negative.")
                object.__setattr__(self, field_name, max(0.0, parsed) if field_name != "quantum_candidate_energy" else parsed)
        if self.exact_match is not None and not isinstance(self.exact_match, bool):
            raise ValueError("exact_match must be a boolean or None.")
        candidate_count = _validate_non_negative_int(self.candidate_count, "candidate_count")
        if candidate_count <= 0:
            raise ValueError("candidate_count must be positive.")
        object.__setattr__(self, "candidate_count", candidate_count)
        if self.selected_candidate_type not in VALID_CANDIDATE_TYPES:
            raise ValueError("selected_candidate_type is invalid.")
        object.__setattr__(self, "problem_size", _validate_non_negative_int(self.problem_size, "problem_size"))
        if self.qaoa_depth is not None:
            object.__setattr__(self, "qaoa_depth", _validate_non_negative_int(self.qaoa_depth, "qaoa_depth"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))


@dataclass(frozen=True)
class HybridOptimizationResult:
    """Immutable final hybrid optimization comparison result."""

    problem_id: str
    objective_sense: str
    selected_candidate: HybridCandidate
    candidates: tuple[HybridCandidate, ...]
    comparisons: tuple[HybridComparison, ...]
    selection: HybridSelection
    benchmark_report: HybridBenchmarkReport
    feasibility_summary: Mapping[str, bool]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "problem_id", _validate_identifier(self.problem_id, "problem_id"))
        if self.objective_sense not in VALID_SENSES:
            raise ValueError("objective_sense must be MINIMIZE or MAXIMIZE.")
        if not isinstance(self.selected_candidate, HybridCandidate):
            raise ValueError("selected_candidate must be a HybridCandidate.")
        if not isinstance(self.candidates, tuple) or not self.candidates:
            raise ValueError("candidates must be a non-empty tuple.")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate IDs must be unique.")
        if any(not isinstance(candidate, HybridCandidate) for candidate in self.candidates):
            raise ValueError("candidates must contain HybridCandidate instances.")
        if not isinstance(self.comparisons, tuple) or not self.comparisons:
            raise ValueError("comparisons must be a non-empty tuple.")
        if any(not isinstance(comparison, HybridComparison) for comparison in self.comparisons):
            raise ValueError("comparisons must contain HybridComparison instances.")
        if not isinstance(self.selection, HybridSelection):
            raise ValueError("selection must be a HybridSelection.")
        if not isinstance(self.benchmark_report, HybridBenchmarkReport):
            raise ValueError("benchmark_report must be a HybridBenchmarkReport.")
        object.__setattr__(self, "feasibility_summary", _freeze_bool_mapping(self.feasibility_summary))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))


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


def _freeze_assignment(value: Mapping[str, int]) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("assignment must be a non-empty mapping.")
    frozen: dict[str, int] = {}
    for variable_id in sorted(value):
        normalized_id = _validate_identifier(variable_id, "assignment variable_id")
        bit = value[variable_id]
        if isinstance(bit, bool) or bit not in (0, 1):
            raise ValueError("assignment values must be 0 or 1.")
        frozen[normalized_id] = int(bit)
    return MappingProxyType(frozen)


def _freeze_bool_mapping(value: Mapping[str, bool]) -> Mapping[str, bool]:
    if not isinstance(value, Mapping):
        raise ValueError("feasibility_summary must be a mapping.")
    frozen: dict[str, bool] = {}
    for key in sorted(value):
        normalized_id = _validate_identifier(key, "feasibility key")
        flag = value[key]
        if not isinstance(flag, bool):
            raise ValueError("feasibility_summary values must be booleans.")
        frozen[normalized_id] = flag
    return MappingProxyType(frozen)
