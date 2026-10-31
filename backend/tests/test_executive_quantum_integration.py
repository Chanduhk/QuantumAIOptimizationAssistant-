from __future__ import annotations

import math
from pathlib import Path
from dataclasses import FrozenInstanceError

import pytest

from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
from backend.app.orchestrator.executive_quantum_evidence import ExecutiveQuantumEvidence, evidence_from_e7
from backend.app.orchestrator.executive_quantum_integration import ExecutiveQuantumIntegration
from backend.app.quantum import (
    AIOptimizationProblem,
    AIOptimizationVariable,
    AIQuantumIntegrationConfig,
    AIQuantumIntegrationEngine,
    IsingProblem,
    QAOAConfig,
    QAOAParameterSet,
    QuantumObjective,
)


def variables(count: int) -> tuple[AIOptimizationVariable, ...]:
    return tuple(AIOptimizationVariable(f"x{index}", f"X{index}", index) for index in range(count))


def ai_problem(
    problem_id: str = "ai_problem",
    *,
    count: int = 1,
    linear: dict[str, float] | None = None,
    quadratic: dict[tuple[str, str], float] | None = None,
    constraints: tuple[dict[str, object], ...] = (),
    penalty: float | None = None,
) -> AIOptimizationProblem:
    return AIOptimizationProblem(
        problem_id=problem_id,
        name="AI Problem",
        variables=variables(count),
        linear_coefficients={} if linear is None else linear,
        quadratic_coefficients={} if quadratic is None else quadratic,
        constraints=constraints,
        penalty=penalty,
    )


def qaoa_config(seed: int = 11) -> QAOAConfig:
    return QAOAConfig(
        depth=1,
        parameters=QAOAParameterSet((math.pi / 4.0,), (math.pi / 8.0,)),
        shots=512,
        seed=seed,
    )


def quantum_result(problem=None, *, seed: int = 11, config: AIQuantumIntegrationConfig | None = None):
    return AIQuantumIntegrationEngine().optimize(
        "request_quantum",
        problem or ai_problem(linear={"x0": -1.0}),
        config=config,
        qaoa_config=qaoa_config(seed),
    )


def test_evidence_from_quantum_used_result() -> None:
    evidence = evidence_from_e7(quantum_result())

    assert evidence.quantum_used is True
    assert evidence.classical_used is True
    assert evidence.exact_match is True
    assert evidence.quantum_match is True
    assert evidence.energy_gap == pytest.approx(0.0)


def test_evidence_from_classical_fallback_result() -> None:
    result = quantum_result(config=AIQuantumIntegrationConfig(allow_quantum=False))
    evidence = evidence_from_e7(result)

    assert evidence.execution_path == "classical_fallback"
    assert evidence.quantum_used is False
    assert evidence.classical_used is True
    assert evidence.quantum_match is None


def test_evidence_from_non_match_result() -> None:
    ising = IsingProblem(
        "ising_case",
        "Ising",
        ("x0", "x1"),
        {},
        {("x0", "x1"): 1.0},
        0.0,
        QuantumObjective("obj_case", "Objective", "MINIMIZE"),
    )
    evidence = evidence_from_e7(quantum_result(ising, seed=13))

    assert evidence.exact_match is False
    assert evidence.energy_gap is not None and evidence.energy_gap > 0.0
    assert "QAOA candidate did not match" in evidence.warnings[0]


def test_evidence_from_resource_limited_result() -> None:
    result = quantum_result(
        ai_problem("large_problem", count=9, linear={"x0": -1.0}),
        config=AIQuantumIntegrationConfig(max_variables_for_quantum=8),
    )
    evidence = evidence_from_e7(result)

    assert evidence.suitability_decision == "RESOURCE_LIMIT"
    assert evidence.execution_path == "classical_fallback"
    assert "quantum limit" in " ".join(evidence.limitations).lower()


def test_evidence_from_requires_reformulation_result() -> None:
    result = AIQuantumIntegrationEngine().optimize(
        "request_quantum",
        {
            "problem_id": "needs_reformulation",
            "name": "Needs Reformulation",
            "variables": [{"variable_id": "x0", "name": "X0", "index": 0, "domain": "continuous"}],
            "linear_coefficients": {"x0": 1.0},
        },
    )
    evidence = evidence_from_e7(result)

    assert evidence.suitability_decision == "REQUIRES_REFORMULATION"
    assert evidence.quantum_used is False
    assert evidence.selected_solver is None


def test_evidence_validation_rejects_malformed_values() -> None:
    with pytest.raises(ValueError):
        ExecutiveQuantumEvidence("", "p", "MINIMIZE", "SUITABLE", "quantum_hybrid", True, True, True, True, True, 0.0, 0.0, True, "solver", "quantum_qaoa", "reason")
    with pytest.raises(ValueError):
        ExecutiveQuantumEvidence("r", "p", "BAD", "SUITABLE", "quantum_hybrid", True, True, True, True, True, 0.0, 0.0, True, "solver", "quantum_qaoa", "reason")
    with pytest.raises(ValueError):
        ExecutiveQuantumEvidence("r", "p", "MINIMIZE", "BAD", "quantum_hybrid", True, True, True, True, True, 0.0, 0.0, True, "solver", "quantum_qaoa", "reason")
    with pytest.raises(ValueError):
        ExecutiveQuantumEvidence("r", "p", "MINIMIZE", "SUITABLE", "bad", True, True, True, True, True, 0.0, 0.0, True, "solver", "quantum_qaoa", "reason")


def test_evidence_rejects_nan_and_infinity() -> None:
    with pytest.raises(ValueError):
        ExecutiveQuantumEvidence("r", "p", "MINIMIZE", "SUITABLE", "quantum_hybrid", True, True, True, True, True, math.nan, 0.0, True, "solver", "quantum_qaoa", "reason")
    with pytest.raises(ValueError):
        ExecutiveQuantumEvidence("r", "p", "MINIMIZE", "SUITABLE", "quantum_hybrid", True, True, True, True, True, 0.0, math.inf, True, "solver", "quantum_qaoa", "reason")


def test_evidence_is_immutable_and_nested_metadata_frozen() -> None:
    evidence = evidence_from_e7(quantum_result())

    with pytest.raises(FrozenInstanceError):
        evidence.problem_id = "new"  # type: ignore[misc]
    with pytest.raises(TypeError):
        evidence.metadata["source"] = "new"  # type: ignore[index]


def test_evidence_to_dict_is_serializable() -> None:
    data = evidence_from_e7(quantum_result()).to_dict()

    assert data["request_id"] == "request_quantum"
    assert isinstance(data["limitations"], list)
    assert isinstance(data["metadata"], dict)


def test_adapter_rejects_non_e7_result() -> None:
    with pytest.raises(ValueError):
        ExecutiveQuantumIntegration().adapt({"bad": "payload"})  # type: ignore[arg-type]


def test_reasoning_evidence_for_exact_match_is_low_risk() -> None:
    evidence = ExecutiveQuantumIntegration().adapt(quantum_result())
    reasoning_evidence = ExecutiveQuantumIntegration().to_reasoning_evidence(evidence)

    assert reasoning_evidence.source == "AIQuantumIntegration"
    assert reasoning_evidence.risk_level == "low"
    assert reasoning_evidence.confidence >= 80.0


def test_reasoning_evidence_for_non_match_is_medium_risk() -> None:
    ising = IsingProblem("ising_case", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, QuantumObjective("obj_case", "Objective", "MINIMIZE"))
    evidence = ExecutiveQuantumIntegration().adapt(quantum_result(ising, seed=17))
    reasoning_evidence = ExecutiveQuantumIntegration().to_reasoning_evidence(evidence)

    assert reasoning_evidence.risk_level == "medium"
    assert reasoning_evidence.metadata["exact_match"] is False


def test_quantum_outputs_have_expected_shape() -> None:
    outputs = ExecutiveQuantumIntegration().outputs(evidence_from_e7(quantum_result()))

    assert set(outputs) == {
        "executive_quantum_summary",
        "executive_quantum_evidence",
        "executive_quantum_risk",
        "executive_quantum_tradeoffs",
        "executive_quantum_reasoning",
        "executive_quantum_recommendation",
        "executive_quantum_confidence",
        "executive_quantum_gap",
    }
    assert outputs["executive_quantum_summary"]["quantum_used"] is True


def test_quantum_tradeoffs_for_fallback_and_non_match() -> None:
    integration = ExecutiveQuantumIntegration()
    fallback = integration.tradeoffs(evidence_from_e7(quantum_result(config=AIQuantumIntegrationConfig(allow_quantum=False))))
    ising = IsingProblem("ising_case", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, QuantumObjective("obj_case", "Objective", "MINIMIZE"))
    non_match = integration.tradeoffs(evidence_from_e7(quantum_result(ising, seed=19)))

    assert any("Classical fallback" in item for item in fallback)
    assert any("did not match" in item for item in non_match)


def test_executive_brain_without_quantum_is_backward_compatible() -> None:
    result = ExecutiveCognitiveBrain().execute_planning_request([{"id": "t1", "title": "Task", "estimated_duration": 1.0}])

    assert "executive_quantum_summary" not in result
    assert "executive_reasoning" in result


def test_executive_brain_with_quantum_outputs_present() -> None:
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=quantum_result(),
    )

    assert result["executive_quantum_summary"]["quantum_used"] is True
    assert result["executive_quantum_evidence"]["exact_match"] is True
    assert "AIQuantumIntegration" in {
        item["source"] for item in result["executive_reasoning"]["reasoning_trace"]["evidence_used"]
    }


def test_executive_brain_reasoning_not_blindly_biased_to_quantum_on_non_match() -> None:
    ising = IsingProblem("ising_case", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, QuantumObjective("obj_case", "Objective", "MINIMIZE"))
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=quantum_result(ising, seed=23),
    )

    assert result["executive_quantum_summary"]["exact_match"] is False
    assert result["executive_quantum_risk"]["risk_level"] == "medium"
    assert "blindly" not in result["executive_summary"].lower()


def test_executive_brain_quantum_fallback_summary() -> None:
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=quantum_result(config=AIQuantumIntegrationConfig(allow_quantum=False)),
    )

    assert result["executive_quantum_summary"]["execution_path"] == "classical_fallback"
    assert result["executive_quantum_summary"]["quantum_used"] is False


def test_executive_brain_quantum_resource_limit_summary() -> None:
    q_result = quantum_result(
        ai_problem("large_problem", count=9, linear={"x0": -1.0}),
        config=AIQuantumIntegrationConfig(max_variables_for_quantum=8),
    )
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=q_result,
    )

    assert result["executive_quantum_summary"]["suitability_decision"] == "RESOURCE_LIMIT"
    assert result["executive_quantum_risk"]["resource_limited"] is True


def test_executive_brain_requires_reformulation_summary() -> None:
    q_result = AIQuantumIntegrationEngine().optimize(
        "request_quantum",
        {
            "problem_id": "needs_reformulation",
            "name": "Needs Reformulation",
            "variables": [{"variable_id": "x0", "name": "X0", "index": 0, "domain": "continuous"}],
            "linear_coefficients": {"x0": 1.0},
        },
    )
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=q_result,
    )

    assert result["executive_quantum_risk"]["requires_reformulation"] is True
    assert result["executive_quantum_summary"]["selected_solver"] is None


def test_executive_brain_rejects_invalid_quantum_evidence() -> None:
    with pytest.raises(ValueError):
        ExecutiveCognitiveBrain().execute_planning_request(
            [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
            quantum_result={"bad": "payload"},
        )


def test_executive_quantum_result_is_deterministic() -> None:
    q_result = quantum_result(seed=29)
    first = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=q_result,
    )
    second = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=q_result,
    )

    assert first["executive_quantum_summary"] == second["executive_quantum_summary"]
    assert first["executive_quantum_reasoning"] == second["executive_quantum_reasoning"]


def test_quantum_gap_preserved_in_executive_outputs() -> None:
    ising = IsingProblem("ising_case", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, QuantumObjective("obj_case", "Objective", "MINIMIZE"))
    q_result = quantum_result(ising, seed=31)
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=q_result,
    )

    assert result["executive_quantum_gap"]["energy_gap"] == pytest.approx(q_result.energy_gap)
    assert result["executive_quantum_gap"]["relative_gap"] == pytest.approx(q_result.relative_gap)


def test_quantum_risk_is_merged_into_risk_summary() -> None:
    ising = IsingProblem("ising_case", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, QuantumObjective("obj_case", "Objective", "MINIMIZE"))
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=quantum_result(ising, seed=37),
    )

    assert result["risk_summary"]["quantum_risk_level"] == "medium"
    assert result["risk_summary"]["risk_score"] >= 35.0


def test_quantum_tradeoffs_are_merged() -> None:
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=quantum_result(),
    )

    assert result["tradeoff_analysis"]["quantum_tradeoff_count"] >= 1
    assert any("Quantum candidate evidence" in item for item in result["tradeoff_analysis"]["tradeoffs"])


def test_executive_context_contains_quantum_evidence_when_present() -> None:
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=quantum_result(),
    )

    assert result["executive_context"]["quantum_evidence"]["problem_id"] == "ai_problem"


def test_resource_and_governance_outputs_still_exist_with_quantum() -> None:
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=quantum_result(),
    )

    assert "resource_summary" in result
    assert "governance_summary" in result
    assert isinstance(result["resource_summary"], dict)
    assert isinstance(result["governance_summary"], dict)


def test_quantum_outputs_do_not_leak_quantum_internals() -> None:
    result = ExecutiveCognitiveBrain().execute_planning_request(
        [{"id": "t1", "title": "Task", "estimated_duration": 1.0}],
        quantum_result=quantum_result(),
    )
    evidence = result["executive_quantum_evidence"]

    assert "statevector" not in evidence
    assert "circuit" not in evidence
    assert "hybrid_result" not in evidence


def test_source_file_has_no_forbidden_quantum_solver_calls() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend" / "app" / "orchestrator" / "executive_quantum_integration.py").read_text(encoding="utf-8")
    evidence_source = (root / "backend" / "app" / "orchestrator" / "executive_quantum_evidence.py").read_text(encoding="utf-8")

    assert "QAOAEngine" not in source
    assert "ExactClassicalSolver" not in source
    assert "solve(" not in source
    assert "QAOAEngine" not in evidence_source
    assert "ExactClassicalSolver" not in evidence_source


def test_source_file_has_no_executive_import_in_e7() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend" / "app" / "quantum" / "integration" / "integration_engine.py").read_text(encoding="utf-8")

    assert "executive_cognitive_brain" not in source
    assert "ExecutiveCognitiveBrain" not in source


def test_repeated_evidence_adaptation_is_identical() -> None:
    result = quantum_result(seed=41)

    assert ExecutiveQuantumIntegration().adapt(result) == ExecutiveQuantumIntegration().adapt(result)


def test_quantum_summary_confidence_for_reformulation_is_lower_than_match() -> None:
    integration = ExecutiveQuantumIntegration()
    match = integration.outputs(evidence_from_e7(quantum_result()))
    reformulation = integration.outputs(
        evidence_from_e7(
            AIQuantumIntegrationEngine().optimize(
                "request_quantum",
                {
                    "problem_id": "needs_reformulation",
                    "name": "Needs Reformulation",
                    "variables": [{"variable_id": "x0", "name": "X0", "index": 0, "domain": "continuous"}],
                    "linear_coefficients": {"x0": 1.0},
                },
            )
        )
    )

    assert reformulation["executive_quantum_confidence"]["confidence"] < match["executive_quantum_confidence"]["confidence"]


def test_quantum_recommendation_is_truthful_for_non_match() -> None:
    ising = IsingProblem("ising_case", "Ising", ("x0", "x1"), {}, {("x0", "x1"): 1.0}, 0.0, QuantumObjective("obj_case", "Objective", "MINIMIZE"))
    outputs = ExecutiveQuantumIntegration().outputs(evidence_from_e7(quantum_result(ising, seed=43)))

    assert outputs["executive_quantum_recommendation"]["recommendation"] == "Prefer verified hybrid selection over raw quantum candidate"
