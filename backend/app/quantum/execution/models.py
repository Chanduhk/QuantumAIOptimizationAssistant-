from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.quantum.domain import IsingProblem, QUBOProblem, QuantumSolution
from backend.app.quantum.domain.quantum_objective import (
    _freeze_mapping,
    _thaw_value,
    _validate_identifier,
    _validate_name,
    _validate_non_negative_int,
)
from backend.app.quantum.execution.exceptions import QuantumCircuitError, QuantumExecutionError

SUPPORTED_GATES = frozenset({"X", "H", "Z", "CNOT", "RX", "RZ", "RZZ"})
SUPPORTED_BACKENDS = frozenset({"local_statevector_simulator"})
MAX_DEFAULT_QUBITS = 12
MAX_DEFAULT_SHOTS = 100_000


@dataclass(frozen=True)
class QuantumOperation:
    """Immutable quantum operation contract for the local execution boundary."""

    gate: str
    targets: tuple[int, ...]
    controls: tuple[int, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.gate, str) or not self.gate.strip():
            raise QuantumCircuitError("gate must be a non-empty string.")
        gate = self.gate.strip().upper()
        if gate not in SUPPORTED_GATES:
            raise QuantumCircuitError(f"unsupported gate '{gate}'.")
        object.__setattr__(self, "gate", gate)
        object.__setattr__(self, "targets", self._validate_qubits(self.targets, "targets"))
        object.__setattr__(self, "controls", self._validate_qubits(self.controls, "controls"))
        if gate == "CNOT":
            if len(self.controls) != 1 or len(self.targets) != 1:
                raise QuantumCircuitError("CNOT requires exactly one control and one target.")
            if self.controls[0] == self.targets[0]:
                raise QuantumCircuitError("CNOT control and target must differ.")
        elif gate == "RZZ":
            if self.controls:
                raise QuantumCircuitError("RZZ does not support controls.")
            if len(self.targets) != 2:
                raise QuantumCircuitError("RZZ requires exactly two targets.")
        elif self.controls:
            raise QuantumCircuitError(f"{gate} does not support controls.")
        elif len(self.targets) != 1:
            raise QuantumCircuitError(f"{gate} requires exactly one target.")
        if gate in {"RX", "RZ", "RZZ"}:
            angle = self.metadata.get("angle")
            if isinstance(angle, bool):
                raise QuantumCircuitError(f"{gate} angle must be numeric.")
            try:
                numeric_angle = float(angle)
            except (TypeError, ValueError):
                raise QuantumCircuitError(f"{gate} requires finite numeric metadata angle.") from None
            if not math.isfinite(numeric_angle):
                raise QuantumCircuitError(f"{gate} angle must be finite.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    @staticmethod
    def _validate_qubits(values: object, field_name: str) -> tuple[int, ...]:
        if not isinstance(values, tuple):
            raise QuantumCircuitError(f"{field_name} must be a tuple of qubit indexes.")
        normalized: list[int] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise QuantumCircuitError(f"{field_name} must contain non-negative integer qubits.")
            normalized.append(value)
        if len(set(normalized)) != len(normalized):
            raise QuantumCircuitError(f"{field_name} cannot contain duplicate qubits.")
        return tuple(normalized)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly operation representation."""

        return {
            "gate": self.gate,
            "targets": list(self.targets),
            "controls": list(self.controls),
            "metadata": _thaw_value(self.metadata),
        }


@dataclass(frozen=True)
class QuantumCircuit:
    """Immutable framework-independent quantum circuit representation."""

    circuit_id: str
    qubit_count: int
    operations: tuple[QuantumOperation, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "circuit_id", _validate_identifier(self.circuit_id, "circuit_id"))
        qubit_count = _validate_non_negative_int(self.qubit_count, "qubit_count")
        if qubit_count <= 0:
            raise QuantumCircuitError("qubit_count must be positive.")
        object.__setattr__(self, "qubit_count", qubit_count)
        if not isinstance(self.operations, tuple):
            raise QuantumCircuitError("operations must be a tuple.")
        for operation in self.operations:
            if not isinstance(operation, QuantumOperation):
                raise QuantumCircuitError("operations must contain QuantumOperation instances.")
            for qubit in operation.targets + operation.controls:
                if qubit >= qubit_count:
                    raise QuantumCircuitError(f"operation references qubit {qubit}, but circuit has {qubit_count}.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly circuit representation."""

        return {
            "circuit_id": self.circuit_id,
            "qubit_count": self.qubit_count,
            "operations": [operation.to_dict() for operation in self.operations],
            "metadata": _thaw_value(self.metadata),
        }


@dataclass(frozen=True)
class QuantumExecutionConfig:
    """Immutable bounded simulator execution configuration."""

    backend_name: str = "local_statevector_simulator"
    shots: int = 1024
    seed: int | None = None
    deterministic: bool = True
    max_qubits: int = MAX_DEFAULT_QUBITS
    max_shots: int = MAX_DEFAULT_SHOTS
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_name", _validate_name(self.backend_name, "backend_name"))
        if self.backend_name not in SUPPORTED_BACKENDS:
            raise QuantumExecutionError(f"unsupported backend '{self.backend_name}'.")
        shots = _positive_int(self.shots, "shots")
        max_qubits = _positive_int(self.max_qubits, "max_qubits")
        max_shots = _positive_int(self.max_shots, "max_shots")
        if shots > max_shots:
            raise QuantumExecutionError(f"shots {shots} exceeds configured max_shots {max_shots}.")
        object.__setattr__(self, "shots", shots)
        object.__setattr__(self, "max_qubits", max_qubits)
        object.__setattr__(self, "max_shots", max_shots)
        if self.seed is not None:
            object.__setattr__(self, "seed", _validate_non_negative_int(self.seed, "seed"))
        if not isinstance(self.deterministic, bool):
            raise QuantumExecutionError("deterministic must be a boolean.")
        if self.deterministic and self.seed is None:
            raise QuantumExecutionError("deterministic execution requires an explicit seed.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))


@dataclass(frozen=True)
class QuantumExecutionRequest:
    """Immutable request separating circuit execution from problem semantics."""

    request_id: str
    circuit: QuantumCircuit
    config: QuantumExecutionConfig
    variable_mapping: Mapping[str, int] = field(default_factory=dict)
    problem: QUBOProblem | IsingProblem | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _validate_identifier(self.request_id, "request_id"))
        if not isinstance(self.circuit, QuantumCircuit):
            raise QuantumExecutionError("circuit must be a QuantumCircuit.")
        if not isinstance(self.config, QuantumExecutionConfig):
            raise QuantumExecutionError("config must be a QuantumExecutionConfig.")
        if self.circuit.qubit_count > self.config.max_qubits:
            raise QuantumExecutionError(
                f"qubit_count {self.circuit.qubit_count} exceeds configured max_qubits {self.config.max_qubits}."
            )
        object.__setattr__(self, "variable_mapping", self._freeze_variable_mapping(self.variable_mapping))
        if self.problem is not None and not isinstance(self.problem, (QUBOProblem, IsingProblem)):
            raise QuantumExecutionError("problem must be a QUBOProblem, IsingProblem, or None.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def _freeze_variable_mapping(self, mapping: Mapping[str, int]) -> Mapping[str, int]:
        if not isinstance(mapping, Mapping):
            raise QuantumExecutionError("variable_mapping must be a mapping.")
        frozen: dict[str, int] = {}
        seen_qubits: set[int] = set()
        for variable_id in sorted(mapping):
            normalized_id = _validate_identifier(variable_id, "variable_id")
            qubit = mapping[variable_id]
            if isinstance(qubit, bool) or not isinstance(qubit, int) or qubit < 0:
                raise QuantumExecutionError("variable_mapping qubits must be non-negative integers.")
            if qubit >= self.circuit.qubit_count:
                raise QuantumExecutionError(f"variable '{normalized_id}' maps to unknown qubit {qubit}.")
            if qubit in seen_qubits:
                raise QuantumExecutionError("variable_mapping cannot map multiple variables to the same qubit.")
            frozen[normalized_id] = qubit
            seen_qubits.add(qubit)
        return MappingProxyType(frozen)


@dataclass(frozen=True)
class QuantumMeasurementResult:
    """Immutable measured counts and probabilities from an execution backend."""

    counts: Mapping[str, int]
    probabilities: Mapping[str, float]
    shots: int

    def __post_init__(self) -> None:
        shots = _positive_int(self.shots, "shots")
        object.__setattr__(self, "shots", shots)
        counts = self._freeze_counts(self.counts, shots)
        probabilities = self._freeze_probabilities(self.probabilities)
        count_width = len(next(iter(counts)))
        if any(len(bitstring) != count_width for bitstring in probabilities):
            raise QuantumExecutionError("probability bitstrings must match count bitstring width.")
        object.__setattr__(self, "counts", counts)
        object.__setattr__(self, "probabilities", probabilities)

    @staticmethod
    def _freeze_counts(counts: Mapping[str, int], shots: int) -> Mapping[str, int]:
        if not isinstance(counts, Mapping) or not counts:
            raise QuantumExecutionError("counts must be a non-empty mapping.")
        frozen: dict[str, int] = {}
        total = 0
        bit_length: int | None = None
        for bitstring in sorted(counts):
            _validate_bitstring(bitstring)
            count = counts[bitstring]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise QuantumExecutionError("counts must be non-negative integers.")
            bit_length = len(bitstring) if bit_length is None else bit_length
            if len(bitstring) != bit_length:
                raise QuantumExecutionError("all bitstrings must have the same width.")
            frozen[bitstring] = count
            total += count
        if total != shots:
            raise QuantumExecutionError("counts total must equal shots.")
        return MappingProxyType(frozen)

    @staticmethod
    def _freeze_probabilities(probabilities: Mapping[str, float]) -> Mapping[str, float]:
        if not isinstance(probabilities, Mapping) or not probabilities:
            raise QuantumExecutionError("probabilities must be a non-empty mapping.")
        frozen: dict[str, float] = {}
        for bitstring in sorted(probabilities):
            _validate_bitstring(bitstring)
            probability = probabilities[bitstring]
            if isinstance(probability, bool):
                raise QuantumExecutionError("probabilities must be numeric.")
            try:
                numeric = float(probability)
            except (TypeError, ValueError):
                raise QuantumExecutionError("probabilities must be numeric.") from None
            if not math.isfinite(numeric) or numeric < -1e-12 or numeric > 1.0 + 1e-12:
                raise QuantumExecutionError("probabilities must be finite values between 0 and 1.")
            frozen[bitstring] = max(0.0, min(1.0, numeric))
        probability_total = sum(frozen.values())
        if abs(probability_total - 1.0) > 1e-9:
            raise QuantumExecutionError("probabilities must sum to 1.")
        return MappingProxyType(frozen)


@dataclass(frozen=True)
class QuantumExecutionResult:
    """Immutable execution result with optional decoded QuantumSolution."""

    request_id: str
    backend_name: str
    measurement: QuantumMeasurementResult
    statevector: tuple[complex, ...]
    candidate_solution: QuantumSolution | None
    success: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _validate_identifier(self.request_id, "request_id"))
        object.__setattr__(self, "backend_name", _validate_name(self.backend_name, "backend_name"))
        if not isinstance(self.measurement, QuantumMeasurementResult):
            raise QuantumExecutionError("measurement must be a QuantumMeasurementResult.")
        if not isinstance(self.statevector, tuple) or not self.statevector:
            raise QuantumExecutionError("statevector must be a non-empty tuple.")
        for amplitude in self.statevector:
            if not isinstance(amplitude, complex):
                raise QuantumExecutionError("statevector amplitudes must be complex numbers.")
            if not math.isfinite(amplitude.real) or not math.isfinite(amplitude.imag):
                raise QuantumExecutionError("statevector amplitudes must be finite.")
        if self.candidate_solution is not None and not isinstance(self.candidate_solution, QuantumSolution):
            raise QuantumExecutionError("candidate_solution must be a QuantumSolution or None.")
        if not isinstance(self.success, bool):
            raise QuantumExecutionError("success must be a boolean.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))


def _positive_int(value: object, field_name: str) -> int:
    parsed = _validate_non_negative_int(value, field_name)
    if parsed <= 0:
        raise QuantumExecutionError(f"{field_name} must be positive.")
    return parsed


def _validate_bitstring(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise QuantumExecutionError("bitstring must be a non-empty string.")
    if any(bit not in {"0", "1"} for bit in value):
        raise QuantumExecutionError("bitstring must contain only 0 and 1.")
    return value
