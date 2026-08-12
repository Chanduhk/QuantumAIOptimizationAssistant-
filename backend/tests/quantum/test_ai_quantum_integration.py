from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from backend.app.quantum import (
    AIOptimizationProblem,
    AIOptimizationVariable,
    AIQuantumIntegrationConfig,
    AIQuantumIntegrationEngine,
    AIQuantumIntegrationResult,
    AIQuantumProblemAdapter,
    AIQuantumRouter,
    ExactClassicalSolver,
    IsingProblem,
    QAOAConfig,
    QAOAParameterSet,
    QUBOFormulator,
    QuantumConstraint,
    QuantumObjective,
    QuantumSuitabilityAnalyzer,
    QuantumSuitabilityResult,
    QuantumVariable,
)


def ai_variable(index: int, *, domain: str = "binary") -> AIOptimizationVariable:
    return AIOptimizationVariable(f"x{index}", f"X{index}", index, domain=domain)


def ai_problem(
    *,
    problem_id: str = "ai_problem",
    count: int = 2,
    linear: dict[str, float] | None = None,
    quadratic: dict[tuple[str, str], float] | None = None,
    sense: str = "MINIMIZE",
    constraints: tuple[dict[str, object], ...] = (),
    penalty: float | None = None,
) -> AIOptimizationProblem:
    return AIOptimizationProblem(
        problem_id=problem_id,
        name="AI Problem",
        variables=tuple(ai_variable(index) for index in range(count)),
        linear_coefficients={} if linear is None else linear,
        quadratic_coefficients={} if quadratic is None else quadratic,
        objective_sense=sense,
        constraints=constraints,
        penalty=penalty,
    )


def objective(sense: str = "MINIMIZE") -> QuantumObjective:
    return QuantumObjective("obj_test", "Objective", sense)


def qubo_problem(count: int = 2):
    variables = tuple(QuantumVariable(f"x{index}", f"X{index}", index) for index in range(count))
    return QUBOFormulator().formulate(
        problem_id="qubo_problem",
        name="QUBO Problem",
        variables=variables,
        linear_coefficients={"x0": -1.0},
        quadratic_coefficients={},
        objective=objective(),
    )


def qaoa_config(seed: int = 123, *, max_qubits: int = 8) -> QAOAConfig:
    return QAOAConfig(
        depth=1,
        parameters=QAOAParameterSet((math.pi / 4.0,), (math.pi / 8.0,)),
        shots=512,
        seed=seed,
        max_qubits=max_qubits,
    )


def qubo_energy(problem, assignment: dict[str, int]) -> float:
    energy = float(problem.constant_offset)
    for variable_id, coefficient in problem.linear_coefficients.items():
        energy += coefficient * assignment[variable_id]
    for (left, right), coefficient in problem.quadratic_coefficients.items():
        energy += coefficient * assignment[left] * assignment[right]
    return energy


def ising_energy(problem: IsingProblem, assignment: dict[str, int]) -> float:
    spins = {variable_id: (2 * assignment[variable_id]) - 1 for variable_id in problem.variables}
    energy = float(problem.constant_offset)
    for variable_id, coefficient in problem.linear_coefficients.items():
        energy += coefficient * spins[variable_id]
    for (left, right), coefficient in problem.quadratic_coefficients.items():
        energy += coefficient * spins[left] * spins[right]
    return energy


def test_ai_variable_validation_and_immutability() -> None:
    variable = ai_variable(0)

    assert variable.domain == "binary"
    with pytest.raises(FrozenInstanceError):
        variable.name = "new"  # type: ignore[misc]
    with pytest.raises(ValueError):
        AIOptimizationVariable("", "X", 0)
    with pytest.raises(ValueError):
        AIOptimizationVariable("x", "", 0)
    with pytest.raises(ValueError):
        AIOptimizationVariable("x", "X", -1)
    with pytest.raises(ValueError):
        AIOptimizationVariable("x", "X", 0, domain="continuous")


def test_ai_problem_validation_and_nested_immutability() -> None:
    problem = ai_problem(linear={"x0": -1.0})

    assert problem.linear_coefficients["x0"] == -1.0
    with pytest.raises(FrozenInstanceError):
        problem.name = "new"  # type: ignore[misc]
    with pytest.raises(TypeError):
        problem.linear_coefficients["x0"] = 0.0  # type: ignore[index]
    with pytest.raises(ValueError):
        ai_problem(count=0)
    with pytest.raises(ValueError):
        AIOptimizationProblem("p", "P", (ai_variable(0), ai_variable(0)), {})


def test_ai_problem_rejects_unknown_nan_and_infinity() -> None:
    with pytest.raises(ValueError):
        ai_problem(linear={"unknown": 1.0})
    with pytest.raises(ValueError):
        ai_problem(linear={"x0": math.nan})
    with pytest.raises(ValueError):
        ai_problem(linear={"x0": math.inf})
    with pytest.raises(ValueError):
        ai_problem(sense="BAD")


def test_ai_problem_requires_penalty_for_constraints() -> None:
    constraint = ({"constraint_id": "c1", "name": "One", "sense": "EQ", "rhs": 1.0, "coefficients": {"x0": 1.0}},)

    with pytest.raises(ValueError):
        ai_problem(count=1, constraints=constraint)
    assert ai_problem(count=1, constraints=constraint, penalty=5.0).penalty == 5.0


def test_adapter_preserves_objective_variables_coefficients_and_constraints() -> None:
    constraint = ({"constraint_id": "c1", "name": "One", "sense": "EQ", "rhs": 1.0, "coefficients": {"x0": 1.0}},)
    source = ai_problem(
        count=2,
        linear={"x0": -2.0, "x1": 1.0},
        quadratic={("x0", "x1"): 0.5},
        sense="MINIMIZE",
        constraints=constraint,
        penalty=10.0,
    )
    adapted = AIQuantumProblemAdapter().adapt(source)

    assert adapted.problem_id == source.problem_id
    assert adapted.objective.sense.value == "MINIMIZE"
    assert tuple(variable.variable_id for variable in adapted.variables[:2]) == ("x0", "x1")
    assert adapted.constraints[0].constraint_id == "c1"
    assert adapted.metadata["source"] == "ai_quantum_integration"


def test_adapter_accepts_mapping_and_existing_quantum_problem() -> None:
    data = ai_problem(count=1, linear={"x0": -1.0}).to_dict()
    adapted = AIQuantumProblemAdapter().adapt(data)
    existing = qubo_problem(count=1)

    assert adapted.problem_id == "ai_problem"
    assert AIQuantumProblemAdapter().adapt(existing) is existing


def test_adapter_rejects_malformed_mapping() -> None:
    with pytest.raises(ValueError):
        AIQuantumProblemAdapter().adapt({"problem_id": "bad"})


def test_suitability_suitable_small_qubo() -> None:
    result = QuantumSuitabilityAnalyzer().analyze(qubo_problem(count=2), qaoa_config=qaoa_config())

    assert result.decision == "SUITABLE"
    assert result.variable_count == 2
    assert result.estimated_states == 4


def test_suitability_unsuitable_when_quantum_disabled() -> None:
    result = QuantumSuitabilityAnalyzer().analyze(
        qubo_problem(count=1),
        config=AIQuantumIntegrationConfig(allow_quantum=False),
    )

    assert result.decision == "UNSUITABLE"
    assert result.limiting_factor == "allow_quantum"


def test_suitability_resource_limits_e7_and_qaoa() -> None:
    problem = qubo_problem(count=3)

    e7_limited = QuantumSuitabilityAnalyzer().analyze(
        problem,
        config=AIQuantumIntegrationConfig(max_variables_for_quantum=2),
        qaoa_config=qaoa_config(max_qubits=8),
    )
    qaoa_limited = QuantumSuitabilityAnalyzer().analyze(
        problem,
        config=AIQuantumIntegrationConfig(max_variables_for_quantum=8),
        qaoa_config=qaoa_config(max_qubits=2),
    )

    assert e7_limited.decision == "RESOURCE_LIMIT"
    assert qaoa_limited.decision == "RESOURCE_LIMIT"


def test_suitability_state_limit() -> None:
    result = QuantumSuitabilityAnalyzer().analyze(
        qubo_problem(count=4),
        config=AIQuantumIntegrationConfig(max_states_for_suitability=8),
        qaoa_config=qaoa_config(max_qubits=8),
    )

    assert result.decision == "RESOURCE_LIMIT"
    assert result.limiting_factor == "max_states_for_suitability"


def test_suitability_rejects_unsupported_problem_object() -> None:
    result = QuantumSuitabilityAnalyzer().analyze("bad")  # type: ignore[arg-type]

    assert result.decision == "UNSUPPORTED"


def test_router_paths() -> None:
    router = AIQuantumRouter()
    config = AIQuantumIntegrationConfig()

    assert router.route(QuantumSuitabilityResult("SUITABLE", ("ok",), 1, 2), config) == "quantum_hybrid"
    assert router.route(QuantumSuitabilityResult("UNSUITABLE", ("no",), 1, 2), config) == "classical_fallback"
    assert router.route(
        QuantumSuitabilityResult("RESOURCE_LIMIT", ("large",), 9, 512),
        AIQuantumIntegrationConfig(allow_classical_fallback=False),
    ) == "resource_limited"


def test_integration_quantum_path_uses_e6() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_1",
        ai_problem(count=1, linear={"x0": -1.0}),
        qaoa_config=qaoa_config(11),
    )

    assert result.execution_path == "quantum_hybrid"
    assert result.quantum_used is True
    assert result.classical_used is True
    assert result.hybrid_result is not None
    assert result.execution_metadata["e6_used"] is True
    assert result.execution_metadata["qaoa_executed"] is True


def test_integration_classical_fallback_when_quantum_disabled() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_2",
        ai_problem(count=1, linear={"x0": -1.0}),
        config=AIQuantumIntegrationConfig(allow_quantum=False),
    )

    assert result.execution_path == "classical_fallback"
    assert result.quantum_used is False
    assert result.classical_used is True
    assert result.selected_candidate is not None
    assert result.selected_candidate.candidate_type == "classical_exact"


def test_integration_resource_limit_falls_back_classically() -> None:
    problem = ai_problem(count=9, linear={"x0": -1.0})
    result = AIQuantumIntegrationEngine().optimize(
        "request_3",
        problem,
        config=AIQuantumIntegrationConfig(max_variables_for_quantum=8),
    )

    assert result.suitability_decision == "RESOURCE_LIMIT"
    assert result.execution_path == "classical_fallback"
    assert result.quantum_used is False
    assert result.classical_used is True


def test_integration_resource_limit_without_fallback_returns_controlled_result() -> None:
    problem = ai_problem(count=9, linear={"x0": -1.0})
    result = AIQuantumIntegrationEngine().optimize(
        "request_4",
        problem,
        config=AIQuantumIntegrationConfig(max_variables_for_quantum=8, allow_classical_fallback=False),
    )

    assert result.execution_path == "resource_limited"
    assert result.selected_candidate is None
    assert result.exact_reference_available is False


def test_integration_requires_reformulation_for_unsupported_mapping_domain() -> None:
    data = {
        "problem_id": "continuous_problem",
        "name": "Continuous",
        "variables": [{"variable_id": "x0", "name": "X0", "index": 0, "domain": "continuous"}],
        "linear_coefficients": {"x0": 1.0},
    }
    result = AIQuantumIntegrationEngine().optimize("request_5", data)

    assert result.suitability_decision == "REQUIRES_REFORMULATION"
    assert result.execution_path == "requires_reformulation"
    assert result.quantum_used is False


def test_integration_invalid_request_raises() -> None:
    with pytest.raises(ValueError):
        AIQuantumIntegrationEngine().optimize("", ai_problem(count=1))
    with pytest.raises(ValueError):
        AIQuantumIntegrationEngine().optimize("request_6", "bad")  # type: ignore[arg-type]


def test_integration_constrained_qubo() -> None:
    constraint = ({"constraint_id": "c1", "name": "One", "sense": "EQ", "rhs": 1.0, "coefficients": {"x0": 1.0, "x1": 1.0}},)
    result = AIQuantumIntegrationEngine().optimize(
        "request_7",
        ai_problem(count=2, linear={"x0": -3.0, "x1": -1.0}, constraints=constraint, penalty=10.0),
        qaoa_config=qaoa_config(17),
    )

    assert result.execution_path == "quantum_hybrid"
    assert result.feasible is True
    assert result.hybrid_result is not None


def test_integration_exact_match_case() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_8",
        ai_problem(count=1, linear={"x0": -1.0}),
        qaoa_config=qaoa_config(19),
    )

    assert result.exact_match is True
    assert result.energy_gap == pytest.approx(0.0)


def test_integration_non_match_case_with_ising() -> None:
    problem = IsingProblem("ising_nonmatch", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, objective())
    result = AIQuantumIntegrationEngine().optimize("request_9", problem, qaoa_config=qaoa_config(23))

    assert result.exact_match is False
    assert result.energy_gap is not None and result.energy_gap > 0
    assert result.quantum_candidate is not None
    assert result.classical_candidate is not None


def test_integration_result_validation_and_immutability() -> None:
    result = AIQuantumIntegrationEngine().optimize("request_10", ai_problem(count=1, linear={"x0": -1.0}))

    with pytest.raises(FrozenInstanceError):
        result.problem_id = "new"  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.execution_metadata["e7_engine"] = "new"  # type: ignore[index]
    with pytest.raises(ValueError):
        AIQuantumIntegrationResult(
            request_id="request_10",
            problem_id="p",
            objective_sense="MINIMIZE",
            suitability_decision="BAD",
            suitability_reasons=("reason",),
            execution_path="unsupported",
            quantum_used=False,
            classical_used=False,
            classical_candidate=None,
            quantum_candidate=None,
            hybrid_result=None,
            selected_candidate=None,
            selected_solver=None,
            objective_value=None,
            energy=None,
            feasible=None,
            exact_reference_available=False,
            exact_match=None,
            energy_gap=None,
            relative_gap=None,
            explanation="explanation",
        )


def test_integration_to_dict_is_serialization_friendly() -> None:
    result = AIQuantumIntegrationEngine().optimize("request_11", ai_problem(count=1, linear={"x0": -1.0}))
    data = result.to_dict()

    assert data["request_id"] == "request_11"
    assert isinstance(data["suitability_reasons"], list)
    assert isinstance(data["execution_metadata"], dict)


def test_integration_is_deterministic_for_repeated_runs() -> None:
    problem = ai_problem(count=2, linear={"x0": -2.0, "x1": 1.0})
    engine = AIQuantumIntegrationEngine()

    assert engine.optimize("request_12", problem, qaoa_config=qaoa_config(29)) == engine.optimize(
        "request_12",
        problem,
        qaoa_config=qaoa_config(29),
    )


def test_objective_sense_preserved_for_maximize_ai_problem() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_13",
        ai_problem(count=1, linear={"x0": 1.0}, sense="MAXIMIZE"),
        qaoa_config=qaoa_config(31),
    )

    assert result.objective_sense == "MAXIMIZE"
    assert result.hybrid_result is not None
    assert result.hybrid_result.objective_sense == "MINIMIZE"


def test_variable_identity_preserved_through_selected_candidate() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_14",
        ai_problem(count=2, linear={"x1": -1.0}),
        qaoa_config=qaoa_config(37),
    )

    assert result.selected_candidate is not None
    assert set(result.selected_candidate.assignment) == {"x0", "x1"}


def test_no_quantum_claim_when_fallback_used() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_15",
        ai_problem(count=1, linear={"x0": -1.0}),
        config=AIQuantumIntegrationConfig(allow_quantum=False),
    )

    assert result.execution_metadata["qaoa_executed"] is False
    assert result.execution_metadata["hardware_execution"] is False
    assert result.execution_metadata["quantum_advantage_claimed"] is False
    assert "Classical fallback used" in result.explanation


def test_independent_energy_verification_for_qubo_result() -> None:
    source = ai_problem(count=2, linear={"x0": -2.0, "x1": 1.0}, quadratic={("x0", "x1"): -0.5})
    problem = AIQuantumProblemAdapter().adapt(source)
    result = AIQuantumIntegrationEngine().optimize("request_16", source, qaoa_config=qaoa_config(41))

    assert result.selected_candidate is not None
    assert result.objective_value == pytest.approx(qubo_energy(problem, dict(result.selected_candidate.assignment)))


def test_independent_energy_verification_for_ising_result() -> None:
    problem = IsingProblem("ising_verify", "Ising", ("x0", "x1"), {"x0": 0.5}, {("x0", "x1"): 1.0}, 0.0, objective())
    result = AIQuantumIntegrationEngine().optimize("request_17", problem, qaoa_config=qaoa_config(43))

    assert result.selected_candidate is not None
    assert result.objective_value == pytest.approx(ising_energy(problem, dict(result.selected_candidate.assignment)))


def test_exact_reference_matches_e3_when_quantum_path_runs() -> None:
    source = ai_problem(count=2, linear={"x0": -1.0, "x1": 0.25})
    adapted = AIQuantumProblemAdapter().adapt(source)
    result = AIQuantumIntegrationEngine().optimize("request_18", source, qaoa_config=qaoa_config(47))

    assert result.hybrid_result is not None
    assert result.hybrid_result.benchmark_report.exact_reference_energy == pytest.approx(
        ExactClassicalSolver().solve(adapted).objective_value
    )


def test_qaoa_candidate_is_genuine_and_not_exact_substitution() -> None:
    problem = IsingProblem("ising_not_substituted", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, objective())
    result = AIQuantumIntegrationEngine().optimize("request_19", problem, qaoa_config=qaoa_config(53))

    assert result.quantum_candidate is not None
    assert result.classical_candidate is not None
    assert result.quantum_candidate.objective_value != result.classical_candidate.objective_value
    assert result.execution_metadata["qaoa_executed"] is True


def test_malformed_qaoa_configuration_fails_safely() -> None:
    with pytest.raises(ValueError):
        qaoa_config(max_qubits=0)


def test_config_validation_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        AIQuantumIntegrationConfig(max_variables_for_quantum=0)
    with pytest.raises(ValueError):
        AIQuantumIntegrationConfig(qaoa_shots=0)
    with pytest.raises(ValueError):
        AIQuantumIntegrationConfig(qaoa_seed=-1)


def test_suitability_result_validation() -> None:
    result = QuantumSuitabilityResult("SUITABLE", ("ok",), 1, 2)

    assert result.to_dict()["decision"] == "SUITABLE"
    with pytest.raises(ValueError):
        QuantumSuitabilityResult("BAD", ("ok",), 1, 2)
    with pytest.raises(ValueError):
        QuantumSuitabilityResult("SUITABLE", ("",), 1, 2)


def test_mapping_quadratic_sequence_is_supported() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_20",
        {
            "problem_id": "mapping_problem",
            "name": "Mapping Problem",
            "variables": [
                {"variable_id": "x0", "name": "X0", "index": 0},
                {"variable_id": "x1", "name": "X1", "index": 1},
            ],
            "linear_coefficients": {"x0": -1.0},
            "quadratic_coefficients": [{"variables": ["x0", "x1"], "coefficient": 0.25}],
        },
        qaoa_config=qaoa_config(59),
    )

    assert result.problem_id == "mapping_problem"
    assert result.execution_path == "quantum_hybrid"


def test_large_resource_limited_problem_without_exact_capacity_is_controlled() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_21",
        ai_problem(problem_id="too_large", count=21, linear={"x0": -1.0}),
        config=AIQuantumIntegrationConfig(max_variables_for_quantum=8),
    )

    assert result.execution_path == "resource_limited"
    assert result.selected_candidate is None
    assert result.classical_used is False


def test_classical_fallback_feasibility_is_reported() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_22",
        ai_problem(count=1, linear={"x0": -1.0}),
        config=AIQuantumIntegrationConfig(allow_quantum=False),
    )

    assert result.feasible is True
    assert result.classical_candidate is not None
    assert result.classical_candidate.feasible is True
