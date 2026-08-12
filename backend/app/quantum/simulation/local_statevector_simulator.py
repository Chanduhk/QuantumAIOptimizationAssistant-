from __future__ import annotations

import cmath
import math
import random
from dataclasses import dataclass

from backend.app.quantum.execution.exceptions import QuantumBackendError, QuantumSimulationLimitError
from backend.app.quantum.execution.models import QuantumCircuit, QuantumExecutionConfig, QuantumMeasurementResult


@dataclass(frozen=True)
class SimulatorRunResult:
    """Immutable low-level simulator output before problem decoding."""

    measurement: QuantumMeasurementResult
    statevector: tuple[complex, ...]


class LocalStatevectorSimulator:
    """Small bounded statevector simulator for E.4 execution validation.

    Supports X, H, Z, CNOT, RX, RZ, and RZZ gates. This is a classical local simulator,
    not quantum hardware and not an optimization algorithm.
    """

    def run(self, circuit: QuantumCircuit, config: QuantumExecutionConfig) -> SimulatorRunResult:
        """Execute a circuit and return statevector plus measured counts."""

        if not isinstance(circuit, QuantumCircuit):
            raise QuantumBackendError("circuit must be a QuantumCircuit.")
        if not isinstance(config, QuantumExecutionConfig):
            raise QuantumBackendError("config must be a QuantumExecutionConfig.")
        if circuit.qubit_count > config.max_qubits:
            raise QuantumSimulationLimitError(
                f"circuit qubits {circuit.qubit_count} exceeds max_qubits {config.max_qubits}."
            )
        state = [0j] * (2 ** circuit.qubit_count)
        state[0] = 1 + 0j
        for operation in circuit.operations:
            if operation.gate == "X":
                state = self._apply_x(state, circuit.qubit_count, operation.targets[0])
            elif operation.gate == "H":
                state = self._apply_h(state, circuit.qubit_count, operation.targets[0])
            elif operation.gate == "Z":
                state = self._apply_z(state, circuit.qubit_count, operation.targets[0])
            elif operation.gate == "CNOT":
                state = self._apply_cnot(state, circuit.qubit_count, operation.controls[0], operation.targets[0])
            elif operation.gate == "RX":
                state = self._apply_rx(state, circuit.qubit_count, operation.targets[0], float(operation.metadata["angle"]))
            elif operation.gate == "RZ":
                state = self._apply_rz(state, circuit.qubit_count, operation.targets[0], float(operation.metadata["angle"]))
            elif operation.gate == "RZZ":
                state = self._apply_rzz(
                    state,
                    circuit.qubit_count,
                    operation.targets[0],
                    operation.targets[1],
                    float(operation.metadata["angle"]),
                )
            else:
                raise QuantumBackendError(f"unsupported operation '{operation.gate}'.")
        probabilities = self._probabilities(tuple(state), circuit.qubit_count)
        counts = self._sample_counts(probabilities, config.shots, config.seed)
        return SimulatorRunResult(
            measurement=QuantumMeasurementResult(counts=counts, probabilities=probabilities, shots=config.shots),
            statevector=tuple(state),
        )

    @staticmethod
    def _mask(qubit_count: int, qubit: int) -> int:
        return 1 << (qubit_count - 1 - qubit)

    def _apply_x(self, state: list[complex], qubit_count: int, target: int) -> list[complex]:
        mask = self._mask(qubit_count, target)
        result = state[:]
        for index in range(len(state)):
            if index & mask == 0:
                paired = index | mask
                result[index], result[paired] = state[paired], state[index]
        return result

    def _apply_z(self, state: list[complex], qubit_count: int, target: int) -> list[complex]:
        mask = self._mask(qubit_count, target)
        return [(-amplitude if index & mask else amplitude) for index, amplitude in enumerate(state)]

    def _apply_h(self, state: list[complex], qubit_count: int, target: int) -> list[complex]:
        mask = self._mask(qubit_count, target)
        result = state[:]
        scale = 1.0 / math.sqrt(2.0)
        for index in range(len(state)):
            if index & mask == 0:
                paired = index | mask
                zero = state[index]
                one = state[paired]
                result[index] = (zero + one) * scale
                result[paired] = (zero - one) * scale
        return result

    def _apply_cnot(self, state: list[complex], qubit_count: int, control: int, target: int) -> list[complex]:
        control_mask = self._mask(qubit_count, control)
        target_mask = self._mask(qubit_count, target)
        result = state[:]
        for index in range(len(state)):
            if index & control_mask and index & target_mask == 0:
                paired = index | target_mask
                result[index], result[paired] = state[paired], state[index]
        return result

    def _apply_rx(self, state: list[complex], qubit_count: int, target: int, angle: float) -> list[complex]:
        mask = self._mask(qubit_count, target)
        result = state[:]
        cosine = math.cos(angle / 2.0)
        sine = math.sin(angle / 2.0)
        for index in range(len(state)):
            if index & mask == 0:
                paired = index | mask
                zero = state[index]
                one = state[paired]
                result[index] = (cosine * zero) - (1j * sine * one)
                result[paired] = (-1j * sine * zero) + (cosine * one)
        return result

    def _apply_rz(self, state: list[complex], qubit_count: int, target: int, angle: float) -> list[complex]:
        mask = self._mask(qubit_count, target)
        phase_zero = cmath.exp(-0.5j * angle)
        phase_one = cmath.exp(0.5j * angle)
        return [(phase_one if index & mask else phase_zero) * amplitude for index, amplitude in enumerate(state)]

    def _apply_rzz(
        self,
        state: list[complex],
        qubit_count: int,
        left: int,
        right: int,
        angle: float,
    ) -> list[complex]:
        left_mask = self._mask(qubit_count, left)
        right_mask = self._mask(qubit_count, right)
        result: list[complex] = []
        for index, amplitude in enumerate(state):
            z_left = -1 if index & left_mask else 1
            z_right = -1 if index & right_mask else 1
            result.append(cmath.exp(-0.5j * angle * z_left * z_right) * amplitude)
        return result

    @staticmethod
    def _probabilities(state: tuple[complex, ...], qubit_count: int) -> dict[str, float]:
        probabilities: dict[str, float] = {}
        for index, amplitude in enumerate(state):
            probability = (amplitude.real * amplitude.real) + (amplitude.imag * amplitude.imag)
            if probability > 1e-15:
                probabilities[format(index, f"0{qubit_count}b")] = probability
        return dict(sorted(probabilities.items()))

    @staticmethod
    def _sample_counts(probabilities: dict[str, float], shots: int, seed: int | None) -> dict[str, int]:
        bitstrings = tuple(sorted(probabilities))
        rng = random.Random(seed)
        counts = {bitstring: 0 for bitstring in bitstrings}
        cumulative: list[tuple[str, float]] = []
        total = 0.0
        for bitstring in bitstrings:
            total += probabilities[bitstring]
            cumulative.append((bitstring, total))
        for _ in range(shots):
            sample = rng.random()
            selected = bitstrings[-1]
            for bitstring, threshold in cumulative:
                if sample <= threshold + 1e-15:
                    selected = bitstring
                    break
            counts[selected] += 1
        return {bitstring: counts[bitstring] for bitstring in bitstrings if counts[bitstring] > 0}
