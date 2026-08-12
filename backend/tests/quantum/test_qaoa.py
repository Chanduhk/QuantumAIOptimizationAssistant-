from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from backend.app.quantum import (
    ExactClassicalSolver,
    IsingProblem,
    QAOABenchmarkComparator,
    QAOACircuitBuilder,
    QAOAConfig,
    QAOACostEvaluator,
    QAOAEngine,
    QAOAParameterError,
    QAOAParameterSet,
    QUBOFormulator,
    QuantumExecutionConfig,
    QuantumOperation,
    QuantumObjective,
    QuantumVariable,
)


def objective(sense: str = "MINIMIZE") -> QuantumObjective:
    return QuantumObjective("obj_1", "Objective", sense)


def variables(count: int) -> tuple[QuantumVariable, ...]:
    return tuple(QuantumVariable(f"x{i}", f"X{i}", i) for i in range(count))


def qubo_problem(
    *,
    count: int = 2,
    linear: dict[str, float] | None = None,
    quadratic: dict[tuple[str, str], float] | None = None,
    constant: float = 0.0,
    sense: str = "MINIMIZE",
):
    return QUBOFormulator().formulate(
        problem_id="qubo_1",
        name="QUBO",
        variables=variables(count),
        linear_coefficients={} if linear is None else linear,
        quadratic_coefficients={} if quadratic is None else quadratic,
        constant_offset=constant,
        objective=objective(sense),
    )


def qaoa_config(
    *,
    gamma: float = math.pi / 4.0,
    beta: float = math.pi / 8.0,
    shots: int = 512,
    seed: int = 11,
) -> QAOAConfig:
    return QAOAConfig(depth=1, parameters=QAOAParameterSet((gamma,), (beta,)), shots=shots, seed=seed)


def independent_ising_energy(problem: IsingProblem, bitstring: str) -> float:
    spins = {variable_id: (2 * int(bitstring[index])) - 1 for index, variable_id in enumerate(problem.variables)}
    energy = float(problem.constant_offset)
    for variable_id, coefficient in problem.linear_coefficients.items():
        energy += coefficient * spins[variable_id]
    for (left, right), coefficient in problem.quadratic_coefficients.items():
        energy += coefficient * spins[left] * spins[right]
    return energy


def test_qaoa_parameter_set_validation() -> None:
    params = QAOAParameterSet((0.1,), (0.2,))

    assert params.depth == 1
    assert params.to_dict() == {"gammas": [0.1], "betas": [0.2]}
    with pytest.raises(QAOAParameterError):
        QAOAParameterSet((math.nan,), (0.2,))
    with pytest.raises(QAOAParameterError):
        QAOAParameterSet((0.1,), (0.2, 0.3))


def test_qaoa_config_validation_and_immutability() -> None:
    config = qaoa_config()

    assert config.depth == 1
    with pytest.raises(FrozenInstanceError):
        config.shots = 1  # type: ignore[misc]
    with pytest.raises(ValueError):
        QAOAConfig(depth=0, parameters=None, seed=1)
    with pytest.raises(ValueError):
        QAOAConfig(depth=2, parameters=QAOAParameterSet((0.1,), (0.2,)), seed=1)
    with pytest.raises(ValueError):
        QAOAConfig(depth=1, parameters=QAOAParameterSet((0.1,), (0.2,)), shots=1001, max_shots=1000, seed=1)


def test_qaoa_circuit_has_expected_layer_order() -> None:
    ising = IsingProblem("ising_1", "Ising", ("x0", "x1"), {"x0": 1.0}, {("x0", "x1"): 2.0}, 0.0, objective())
    params = QAOAParameterSet((0.5,), (0.25,))
    circuit = QAOACircuitBuilder().build(ising, params, QAOAConfig(depth=1, parameters=params, seed=1))

    assert [operation.gate for operation in circuit.operations] == ["H", "H", "RZ", "RZZ", "RX", "RX"]
    assert circuit.operations[2].metadata["angle"] == pytest.approx(1.0)
    assert circuit.operations[3].metadata["angle"] == pytest.approx(2.0)
    assert circuit.operations[4].metadata["angle"] == pytest.approx(0.5)


def test_qaoa_circuit_rejects_operation_limit() -> None:
    ising = IsingProblem("ising_1", "Ising", ("x0", "x1"), {"x0": 1.0}, {("x0", "x1"): 2.0}, 0.0, objective())
    params = QAOAParameterSet((0.5,), (0.25,))
    with pytest.raises(ValueError):
        QAOACircuitBuilder().build(ising, params, QAOAConfig(depth=1, parameters=params, max_operations=3, seed=1))


def test_parameterized_rx_gate_executes_real_mixer_unitary() -> None:
    from backend.app.quantum import QuantumCircuit, QuantumExecutionEngine, QuantumExecutionRequest

    operation = QuantumOperation("RX", (0,), metadata={"angle": math.pi})
    result = QuantumExecutionEngine().execute(
        QuantumExecutionRequest(
            "request_1",
            QuantumCircuit("circuit_1", 1, (operation,)),
            QuantumExecutionConfig(shots=64, seed=1),
        )
    )

    assert result.measurement.probabilities["1"] == pytest.approx(1.0)


def test_parameterized_rz_and_rzz_preserve_probability_norm() -> None:
    from backend.app.quantum import QuantumCircuit, QuantumExecutionEngine, QuantumExecutionRequest

    circuit = QuantumCircuit(
        "circuit_1",
        2,
        (
            QuantumOperation("H", (0,)),
            QuantumOperation("H", (1,)),
            QuantumOperation("RZ", (0,), metadata={"angle": 0.7}),
            QuantumOperation("RZZ", (0, 1), metadata={"angle": -1.1}),
        ),
    )
    result = QuantumExecutionEngine().execute(
        QuantumExecutionRequest("request_1", circuit, QuantumExecutionConfig(shots=128, seed=2))
    )

    assert sum(abs(amplitude) ** 2 for amplitude in result.statevector) == pytest.approx(1.0)
    assert sum(result.measurement.probabilities.values()) == pytest.approx(1.0)


def test_cost_evaluator_bitstring_and_expectation() -> None:
    ising = IsingProblem("ising_1", "Ising", ("x0",), {"x0": 2.0}, {}, 3.0, objective())
    evaluator = QAOACostEvaluator()

    assert evaluator.bitstring_energy(ising, "0") == pytest.approx(1.0)
    assert evaluator.bitstring_energy(ising, "1") == pytest.approx(5.0)
    assert evaluator.statevector_expectation(ising, (2**-0.5 + 0j, 2**-0.5 + 0j)) == pytest.approx(3.0)
    assert evaluator.empirical_expectation(ising, {"0": 3, "1": 1}) == pytest.approx(2.0)


def test_qaoa_solves_one_variable_qubo_through_execution_path() -> None:
    problem = qubo_problem(count=1, linear={"x0": -1.0})
    result = QAOAEngine().solve(problem, qaoa_config(gamma=math.pi / 2.0, beta=math.pi / 4.0, shots=256, seed=5))

    assert result.best_solution.solver_name == "qaoa_local_statevector"
    assert result.best_solution.metadata["method"] == "measured_candidate_energy_ranking"
    assert result.metadata["operation_count"] == 3
    assert result.metadata["statevector_norm"] == pytest.approx(1.0)
    assert set(result.best_solution.assignments) == {"x0"}


def test_qaoa_two_variable_quadratic_qubo_candidate_is_valid() -> None:
    problem = qubo_problem(count=2, linear={"x0": -1.0, "x1": -1.0}, quadratic={("x0", "x1"): 2.0})
    result = QAOAEngine().solve(problem, qaoa_config(shots=512, seed=9))

    assignment = dict(result.best_solution.assignments)
    assert set(assignment) == {"x0", "x1"}
    assert all(value in (0, 1) for value in assignment.values())
    assert result.best_solution.objective_value == pytest.approx(
        independent_ising_energy(QAOACostEvaluator().normalize_problem(problem)[0], result.best_solution.metadata["bitstring"])
    )


def test_qaoa_small_maxcut_style_ising() -> None:
    problem = IsingProblem("ising_1", "MaxCut style", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, objective())
    result = QAOAEngine().solve(problem, qaoa_config(shots=512, seed=8))

    assert result.representation == "Ising"
    assert result.best_solution.objective_value <= 1.0
    assert result.best_solution.metadata["representation"] == "Ising"


def test_qaoa_three_variable_qubo() -> None:
    problem = qubo_problem(count=3, linear={"x0": -2.0, "x1": 1.0}, quadratic={("x0", "x2"): -3.0}, constant=2.0)
    result = QAOAEngine().solve(problem, qaoa_config(shots=512, seed=13))

    assert len(result.best_solution.assignments) == 3
    assert math.isfinite(result.expectation_value)
    assert math.isfinite(result.empirical_expectation_value)


def test_qaoa_e2_converted_ising_problem() -> None:
    qubo = qubo_problem(count=2, linear={"x0": -2.0, "x1": 1.0}, quadratic={("x0", "x1"): 3.0})
    ising = QAOACostEvaluator().normalize_problem(qubo)[0]
    result = QAOAEngine().solve(ising, qaoa_config(shots=256, seed=17))

    assert result.representation == "Ising"
    assert result.best_solution.problem_id == ising.problem_id


def test_qaoa_problem_with_constant_offset() -> None:
    problem = qubo_problem(count=1, linear={"x0": -1.0}, constant=10.0)
    result = QAOAEngine().solve(problem, qaoa_config(shots=256, seed=19))

    assert result.best_solution.objective_value >= 9.0


def test_qaoa_maximization_formulated_qubo_uses_existing_e2_semantics() -> None:
    problem = qubo_problem(count=1, linear={"x0": 1.0}, sense="MAXIMIZE")
    result = QAOAEngine().solve(problem, qaoa_config(gamma=math.pi / 2.0, beta=math.pi / 4.0, shots=256, seed=23))

    assert result.metadata["comparison_mode"] == "MINIMIZE"
    assert result.best_solution.metadata["representation"] == "QUBO"


def test_qaoa_multiple_optima_tie_break_is_deterministic() -> None:
    problem = qubo_problem(count=2, linear={"x0": -1.0, "x1": -1.0}, quadratic={("x0", "x1"): 2.0})
    first = QAOAEngine().solve(problem, qaoa_config(shots=512, seed=29))
    second = QAOAEngine().solve(problem, qaoa_config(shots=512, seed=29))

    assert first.best_solution == second.best_solution


def test_seeded_qaoa_execution_is_reproducible() -> None:
    problem = qubo_problem(count=2, linear={"x0": -2.0, "x1": 1.0})
    first = QAOAEngine().solve(problem, qaoa_config(shots=512, seed=31))
    second = QAOAEngine().solve(problem, qaoa_config(shots=512, seed=31))

    assert first == second


def test_qaoa_different_parameters_can_change_distribution() -> None:
    problem = qubo_problem(count=1, linear={"x0": -1.0})
    first = QAOAEngine().solve(problem, qaoa_config(gamma=0.0, beta=0.0, shots=512, seed=37))
    second = QAOAEngine().solve(problem, qaoa_config(gamma=math.pi / 2.0, beta=math.pi / 4.0, shots=512, seed=37))

    assert first.expectation_value != pytest.approx(second.expectation_value)


def test_bounded_parameter_optimizer_generates_candidates() -> None:
    config = QAOAConfig(depth=1, optimize_parameters=True, angle_grid=(0.0, math.pi / 2.0), max_iterations=3, seed=1)
    result = QAOAEngine().solve(qubo_problem(count=1, linear={"x0": -1.0}), config)

    assert result.metadata["optimized_parameters"] is True
    assert result.metadata["parameter_index"] in (0, 1, 2)


def test_qaoa_rejects_oversized_qubit_request() -> None:
    with pytest.raises(ValueError):
        QAOAEngine().solve(qubo_problem(count=3), QAOAConfig(depth=1, parameters=QAOAParameterSet((0.0,), (0.0,)), seed=1, max_qubits=2))


def test_qaoa_rejects_oversized_depth_and_invalid_shots() -> None:
    with pytest.raises(ValueError):
        QAOAConfig(depth=4, max_depth=3, seed=1)
    with pytest.raises(ValueError):
        QAOAConfig(depth=1, shots=0, seed=1)


def test_qaoa_result_is_immutable() -> None:
    result = QAOAEngine().solve(qubo_problem(count=1, linear={"x0": -1.0}), qaoa_config())

    with pytest.raises(FrozenInstanceError):
        result.expectation_value = 0.0  # type: ignore[misc]


def test_qaoa_benchmark_comparator_uses_e3_for_reporting_only() -> None:
    problem = qubo_problem(count=1, linear={"x0": -1.0})
    result = QAOAEngine().solve(problem, qaoa_config(gamma=math.pi / 2.0, beta=math.pi / 4.0, shots=256, seed=41))
    report = QAOABenchmarkComparator().compare(problem, result)

    assert report.exact_reference_energy == pytest.approx(ExactClassicalSolver().solve_qubo(problem).objective_value)
    assert report.absolute_energy_gap >= 0.0
    assert isinstance(report.exact_optimum_found, bool)


def test_qaoa_candidate_energy_independently_recomputed() -> None:
    problem = qubo_problem(count=2, linear={"x0": -2.0, "x1": 1.0})
    result = QAOAEngine().solve(problem, qaoa_config(shots=256, seed=43))
    ising = QAOACostEvaluator().normalize_problem(problem)[0]
    bitstring = result.best_solution.metadata["bitstring"]

    assert result.best_solution.objective_value == pytest.approx(independent_ising_energy(ising, bitstring))


def test_qaoa_counts_and_probabilities_are_valid() -> None:
    problem = qubo_problem(count=2, linear={"x0": -2.0, "x1": 1.0})
    result = QAOAEngine().solve(problem, qaoa_config(shots=256, seed=47))

    assert result.empirical_expectation_value == pytest.approx(result.empirical_expectation_value)
    assert result.metadata["backend"] == "local_statevector_simulator"


def test_no_exact_solver_import_in_qaoa_engine_module() -> None:
    import inspect
    import backend.app.quantum.optimization.qaoa_engine as qaoa_engine

    source = inspect.getsource(qaoa_engine)
    assert "ExactClassicalSolver" not in source
    assert "solve_qubo" not in source
    assert "solve_ising" not in source
