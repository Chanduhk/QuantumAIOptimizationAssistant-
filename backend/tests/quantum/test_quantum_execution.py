from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.app.quantum import (
    ExactClassicalSolver,
    IsingProblem,
    LocalStatevectorSimulator,
    QUBOFormulator,
    QUBOToIsingConverter,
    QuantumCircuit,
    QuantumCircuitError,
    QuantumDecodingError,
    QuantumExecutionConfig,
    QuantumExecutionEngine,
    QuantumExecutionError,
    QuantumExecutionRequest,
    QuantumMeasurementResult,
    QuantumObjective,
    QuantumOperation,
    QuantumSimulationLimitError,
    QuantumVariable,
)


def config(*, shots: int = 256, seed: int = 7, max_qubits: int = 4) -> QuantumExecutionConfig:
    return QuantumExecutionConfig(shots=shots, seed=seed, max_qubits=max_qubits)


def circuit(*operations: QuantumOperation, qubits: int = 1, circuit_id: str = "circuit_1") -> QuantumCircuit:
    return QuantumCircuit(circuit_id=circuit_id, qubit_count=qubits, operations=tuple(operations))


def request(
    circ: QuantumCircuit,
    *,
    variable_mapping: dict[str, int] | None = None,
    problem: object | None = None,
    shots: int = 256,
    seed: int = 7,
) -> QuantumExecutionRequest:
    return QuantumExecutionRequest(
        request_id="request_1",
        circuit=circ,
        config=config(shots=shots, seed=seed, max_qubits=8),
        variable_mapping={} if variable_mapping is None else variable_mapping,
        problem=problem,
    )


def objective() -> QuantumObjective:
    return QuantumObjective("obj_1", "Objective", "MINIMIZE")


def qubo_problem():
    return QUBOFormulator().formulate(
        problem_id="qubo_1",
        name="QUBO",
        variables=(QuantumVariable("x0", "X0", 0), QuantumVariable("x1", "X1", 1)),
        linear_coefficients={"x0": -2.0, "x1": 1.0},
        quadratic_coefficients={("x0", "x1"): 3.0},
        objective=objective(),
    )


def test_backend_construction() -> None:
    assert isinstance(LocalStatevectorSimulator(), LocalStatevectorSimulator)
    assert isinstance(QuantumExecutionEngine(), QuantumExecutionEngine)


def test_valid_empty_circuit_execution_produces_zero_state() -> None:
    result = QuantumExecutionEngine().execute(request(circuit(qubits=1)))

    assert result.measurement.probabilities["0"] == pytest.approx(1.0)
    assert result.measurement.counts == {"0": 256}
    assert result.metadata["backend_type"] == "local_simulator"


def test_x_gate_prepares_one_state() -> None:
    result = QuantumExecutionEngine().execute(request(circuit(QuantumOperation("X", (0,)), qubits=1)))

    assert result.measurement.probabilities["1"] == pytest.approx(1.0)
    assert result.measurement.counts == {"1": 256}


def test_h_gate_prepares_plus_state_probabilities() -> None:
    result = QuantumExecutionEngine().execute(request(circuit(QuantumOperation("H", (0,)), qubits=1), shots=1000))

    assert result.measurement.probabilities["0"] == pytest.approx(0.5)
    assert result.measurement.probabilities["1"] == pytest.approx(0.5)
    assert sum(result.measurement.counts.values()) == 1000


def test_h_z_prepares_minus_state_probabilities() -> None:
    result = QuantumExecutionEngine().execute(
        request(circuit(QuantumOperation("H", (0,)), QuantumOperation("Z", (0,)), qubits=1))
    )

    assert result.measurement.probabilities["0"] == pytest.approx(0.5)
    assert result.measurement.probabilities["1"] == pytest.approx(0.5)
    assert result.statevector[0].real == pytest.approx(2**-0.5)
    assert result.statevector[1].real == pytest.approx(-(2**-0.5))


def test_cnot_preserves_qubit_ordering() -> None:
    result = QuantumExecutionEngine().execute(
        request(circuit(QuantumOperation("X", (0,)), QuantumOperation("CNOT", (1,), controls=(0,)), qubits=2))
    )

    assert result.measurement.probabilities["11"] == pytest.approx(1.0)


def test_bell_state_probabilities() -> None:
    result = QuantumExecutionEngine().execute(
        request(circuit(QuantumOperation("H", (0,)), QuantumOperation("CNOT", (1,), controls=(0,)), qubits=2))
    )

    assert result.measurement.probabilities["00"] == pytest.approx(0.5)
    assert result.measurement.probabilities["11"] == pytest.approx(0.5)


def test_seed_reproducibility_for_sampling() -> None:
    circ = circuit(QuantumOperation("H", (0,)), qubits=1)
    first = QuantumExecutionEngine().execute(request(circ, shots=1000, seed=42))
    second = QuantumExecutionEngine().execute(request(circ, shots=1000, seed=42))

    assert first.measurement.counts == second.measurement.counts
    assert first == second


def test_different_seed_changes_probabilistic_counts_but_not_probabilities() -> None:
    circ = circuit(QuantumOperation("H", (0,)), qubits=1)
    first = QuantumExecutionEngine().execute(request(circ, shots=1000, seed=1))
    second = QuantumExecutionEngine().execute(request(circ, shots=1000, seed=2))

    assert first.measurement.probabilities == second.measurement.probabilities
    assert first.measurement.counts != second.measurement.counts


def test_invalid_gate_rejected() -> None:
    with pytest.raises(QuantumCircuitError):
        QuantumOperation("Y", (0,))


def test_invalid_qubit_rejected() -> None:
    with pytest.raises(QuantumCircuitError):
        QuantumOperation("X", (-1,))


def test_cnot_validation() -> None:
    with pytest.raises(QuantumCircuitError):
        QuantumOperation("CNOT", (0,), controls=(0,))
    with pytest.raises(QuantumCircuitError):
        QuantumOperation("CNOT", (1,))


def test_circuit_rejects_out_of_range_operation() -> None:
    with pytest.raises(QuantumCircuitError):
        circuit(QuantumOperation("X", (1,)), qubits=1)


def test_circuit_rejects_zero_qubits() -> None:
    with pytest.raises(QuantumCircuitError):
        QuantumCircuit("circuit_1", 0)


def test_config_rejects_missing_seed_for_deterministic_execution() -> None:
    with pytest.raises(QuantumExecutionError):
        QuantumExecutionConfig(shots=10, deterministic=True)


def test_config_rejects_invalid_shots_and_backend() -> None:
    with pytest.raises(QuantumExecutionError):
        QuantumExecutionConfig(shots=0, seed=1)
    with pytest.raises(QuantumExecutionError):
        QuantumExecutionConfig(backend_name="unsupported", shots=1, seed=1)


def test_config_rejects_oversized_shots() -> None:
    with pytest.raises(QuantumExecutionError):
        QuantumExecutionConfig(shots=11, max_shots=10, seed=1)


def test_request_rejects_oversized_qubits() -> None:
    with pytest.raises(QuantumExecutionError):
        QuantumExecutionRequest("request_1", circuit(qubits=3), config(shots=1, seed=1, max_qubits=2))


def test_request_rejects_bad_variable_mapping() -> None:
    with pytest.raises(QuantumExecutionError):
        request(circuit(qubits=1), variable_mapping={"x0": 2})
    with pytest.raises(QuantumExecutionError):
        request(circuit(qubits=2), variable_mapping={"x0": 0, "x1": 0})


def test_measurement_rejects_invalid_bitstring_and_count_total() -> None:
    with pytest.raises(QuantumExecutionError):
        QuantumMeasurementResult({"2": 1}, {"2": 1.0}, 1)
    with pytest.raises(QuantumExecutionError):
        QuantumMeasurementResult({"0": 1}, {"0": 1.0}, 2)


def test_measurement_rejects_nan_and_infinity_probabilities() -> None:
    with pytest.raises(QuantumExecutionError):
        QuantumMeasurementResult({"0": 1}, {"0": float("nan")}, 1)
    with pytest.raises(QuantumExecutionError):
        QuantumMeasurementResult({"0": 1}, {"0": float("inf")}, 1)


def test_result_objects_are_immutable() -> None:
    result = QuantumExecutionEngine().execute(request(circuit(qubits=1)))

    with pytest.raises(FrozenInstanceError):
        result.success = False  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.measurement.counts["0"] = 0  # type: ignore[index]


def test_backend_limit_error_direct_run() -> None:
    with pytest.raises(QuantumSimulationLimitError):
        LocalStatevectorSimulator().run(circuit(qubits=3), config(shots=1, seed=1, max_qubits=2))


def test_engine_rejects_invalid_request() -> None:
    with pytest.raises(ValueError):
        QuantumExecutionEngine().execute("bad")  # type: ignore[arg-type]


def test_result_decoding_for_qubo_candidate_solution() -> None:
    problem = qubo_problem()
    circ = circuit(QuantumOperation("X", (0,)), qubits=2)
    result = QuantumExecutionEngine().execute(
        request(circ, variable_mapping={"x0": 0, "x1": 1}, problem=problem, shots=10, seed=5)
    )

    assert result.candidate_solution is not None
    assert dict(result.candidate_solution.assignments) == {"x0": 1, "x1": 0}
    assert result.candidate_solution.objective_value == pytest.approx(-2.0)


def test_result_decoding_for_ising_candidate_solution() -> None:
    qubo = qubo_problem()
    ising = QUBOToIsingConverter().convert(qubo)
    circ = circuit(QuantumOperation("X", (0,)), qubits=2)
    result = QuantumExecutionEngine().execute(
        request(circ, variable_mapping={"x0": 0, "x1": 1}, problem=ising, shots=10, seed=5)
    )

    assert result.candidate_solution is not None
    assert dict(result.candidate_solution.assignments) == {"x0": 1, "x1": 0}
    assert result.candidate_solution.objective_value == pytest.approx(-2.0)


def test_no_problem_yields_no_candidate_solution() -> None:
    result = QuantumExecutionEngine().execute(request(circuit(QuantumOperation("X", (0,)), qubits=1)))

    assert result.candidate_solution is None


def test_decoder_requires_variable_mapping_for_problem() -> None:
    with pytest.raises(QuantumDecodingError):
        QuantumExecutionEngine().execute(request(circuit(qubits=1), problem=qubo_problem()))


def test_e3_reference_compatibility_for_prepared_optimum() -> None:
    problem = qubo_problem()
    exact = ExactClassicalSolver().solve_qubo(problem)
    circ = circuit(QuantumOperation("X", (0,)), qubits=2)
    result = QuantumExecutionEngine().execute(
        request(circ, variable_mapping={"x0": 0, "x1": 1}, problem=problem, shots=20, seed=9)
    )

    assert result.candidate_solution is not None
    assert dict(result.candidate_solution.assignments) == dict(exact.assignments)
    assert result.candidate_solution.objective_value == pytest.approx(exact.objective_value)


def test_e4_does_not_claim_optimization_for_non_optimal_prepared_state() -> None:
    problem = qubo_problem()
    exact = ExactClassicalSolver().solve_qubo(problem)
    result = QuantumExecutionEngine().execute(
        request(circuit(qubits=2), variable_mapping={"x0": 0, "x1": 1}, problem=problem, shots=20, seed=9)
    )

    assert result.candidate_solution is not None
    assert dict(result.candidate_solution.assignments) != dict(exact.assignments)
    assert result.candidate_solution.metadata["method"] == "measurement_decoding"


def test_metadata_correctness() -> None:
    circ = circuit(QuantumOperation("H", (0,)), qubits=1)
    result = QuantumExecutionEngine().execute(request(circ, shots=64, seed=11))

    assert result.metadata["provider"] == "internal_statevector"
    assert result.metadata["qubit_count"] == 1
    assert result.metadata["shots"] == 64
    assert result.metadata["seed"] == 11


def test_repeated_execution_is_deterministic() -> None:
    circ = circuit(QuantumOperation("H", (0,)), qubits=1)
    engine = QuantumExecutionEngine()

    assert engine.execute(request(circ, shots=128, seed=12)) == engine.execute(request(circ, shots=128, seed=12))


def test_variable_mapping_preserves_qubit_order_in_decoding() -> None:
    problem = qubo_problem()
    circ = circuit(QuantumOperation("X", (1,)), qubits=2)
    result = QuantumExecutionEngine().execute(
        request(circ, variable_mapping={"x0": 1, "x1": 0}, problem=problem, shots=5, seed=1)
    )

    assert result.candidate_solution is not None
    assert dict(result.candidate_solution.assignments) == {"x0": 1, "x1": 0}


def test_known_statevector_for_x_then_h() -> None:
    circ = circuit(QuantumOperation("X", (0,)), QuantumOperation("H", (0,)), qubits=1)
    result = QuantumExecutionEngine().execute(request(circ, shots=10, seed=3))

    assert result.statevector[0].real == pytest.approx(2**-0.5)
    assert result.statevector[1].real == pytest.approx(-(2**-0.5))


def test_malformed_metadata_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError):
        QuantumOperation("X", (0,), metadata={"bad": float("nan")})
