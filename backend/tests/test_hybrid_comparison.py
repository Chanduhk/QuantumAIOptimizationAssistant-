from backend.app.domain.assignment_qubo_ising import AssignmentQuboIsingBuilder
from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.hybrid_comparison import HybridComparator
from backend.app.domain.prediction_matrix import create_synthetic_test_matrix
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator
from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain


def problem():
    matrix = create_synthetic_test_matrix(
        ["a", "b"], [9, 10],
        [("a", 9, 90), ("a", 10, 10), ("b", 9, 20), ("b", 10, 80)],
    )
    classical = ClassicalOptimizer(allow_test_matrices=True).optimize(matrix)
    formulation = AssignmentQuboIsingBuilder(allow_test_matrices=True).build(matrix)
    return matrix, classical, formulation


def quantum_candidate(matrix, assignments):
    violations = []
    tasks = [item["task_id"] for item in assignments]
    hours = [item["candidate_hour"] for item in assignments]
    if len(assignments) != len(matrix.task_ids) or set(tasks) != set(matrix.task_ids):
        violations.append("each task must be assigned exactly once")
    if len(set(hours)) != len(hours):
        violations.append("each candidate hour may receive at most one task")
    if any(hour not in matrix.candidate_hours for hour in hours):
        violations.append("assigned hour is outside the candidate domain")
    objective = sum(matrix.score(item["task_id"], item["candidate_hour"]) for item in assignments)
    return {
        "status": "CANDIDATE", "mode": "TEST/SYNTHETIC",
        "runtime_backend": "local_statevector_simulator",
        "candidate": {
            "assignments": assignments, "objective_value": objective,
            "feasible": not violations, "constraint_violations": violations,
            "repaired": False, "solver_name": "qaoa_local_statevector",
        },
    }


def classical_candidate(matrix, assignments):
    objective = sum(matrix.score(item["task_id"], item["assigned_hour"]) for item in assignments)
    violations = []
    tasks = [item["task_id"] for item in assignments]
    hours = [item["assigned_hour"] for item in assignments]
    if len(assignments) != len(matrix.task_ids) or set(tasks) != set(matrix.task_ids):
        violations.append("each task must be assigned exactly once")
    if len(set(hours)) != len(hours):
        violations.append("each candidate hour may receive at most one task")
    if any(hour not in matrix.candidate_hours for hour in hours):
        violations.append("assigned hour is outside the candidate domain")
    return {
        "status": "CANDIDATE", "mode": matrix.mode, "assignments": assignments,
        "total_objective": objective, "feasibility": not violations,
        "constraint_violations": violations, "solver": "test-classical-reference",
        "runtime_seconds": 0.0, "input_provenance": {"label": "TEST/SYNTHETIC"},
    }


def compare(matrix, classical, quantum, formulation):
    return HybridComparator().compare(
        matrix, classical, quantum, formulation=formulation, allow_test_mode=True
    )


def test_same_objective_equal_objectives_and_energy_equivalence():
    matrix, classical, formulation = problem()
    quantum = quantum_candidate(matrix, [
        {"task_id": "a", "candidate_hour": 9},
        {"task_id": "b", "candidate_hour": 10},
    ])
    result = compare(matrix, classical, quantum, formulation)
    assert result.status == "COMPARED"
    assert result.objective_relation == "EQUAL"
    assert result.classical["objective_value"] == result.quantum["objective_value"] == 170
    assert result.quantum["qubo_energy"] == result.quantum["ising_energy"]
    assert result.quantum["runtime_seconds"] is None
    assert result.to_dict()["quantum_preferred_automatically"] is False
    assert result.to_dict() == compare(matrix, classical, quantum, formulation).to_dict()


def test_classical_candidate_higher_and_quantum_candidate_higher_are_neutral_relations():
    matrix, classical, formulation = problem()
    alternate = [{"task_id": "a", "candidate_hour": 10}, {"task_id": "b", "candidate_hour": 9}]
    result = compare(matrix, classical, quantum_candidate(matrix, alternate), formulation)
    assert result.objective_relation == "CLASSICAL_HIGHER"

    low_classical = classical_candidate(matrix, [
        {"task_id": "a", "assigned_hour": 10}, {"task_id": "b", "assigned_hour": 9}
    ])
    higher_quantum = quantum_candidate(matrix, [
        {"task_id": "a", "candidate_hour": 9}, {"task_id": "b", "candidate_hour": 10}
    ])
    result = compare(matrix, low_classical, higher_quantum, formulation)
    assert result.objective_relation == "QUANTUM_HIGHER"
    assert result.status == "COMPARED"


def test_quantum_infeasibility_is_reported_without_repair():
    matrix, classical, formulation = problem()
    raw = quantum_candidate(matrix, [
        {"task_id": "a", "candidate_hour": 9}, {"task_id": "a", "candidate_hour": 10}
    ])
    result = compare(matrix, classical, raw, formulation)
    assert result.status == "INFEASIBLE_CANDIDATE"
    assert result.quantum["feasibility"] == "INFEASIBLE"
    assert "each task must be assigned exactly once" in result.quantum["constraint_violations"]
    assert raw["candidate"]["repaired"] is False


def test_test_mode_is_explicit_and_bad_claims_or_missing_candidates_fail_closed():
    matrix, classical, formulation = problem()
    quantum = quantum_candidate(matrix, [
        {"task_id": "a", "candidate_hour": 9}, {"task_id": "b", "candidate_hour": 10}
    ])
    assert HybridComparator().compare(matrix, classical, quantum, formulation=formulation).status == "NOT_READY"
    bad = dict(quantum)
    bad["candidate"] = dict(quantum["candidate"], objective_value=0)
    assert compare(matrix, classical, bad, formulation).status == "INVALID_INPUT"
    assert compare(matrix, classical, None, formulation).status == "NOT_READY"


def test_executive_receives_comparison_as_context_without_replacing_decision_layer():
    evidence = {"mode": "PRODUCTION", "quantum_suitability": {"status": "NOT_READY"},
                "hybrid_comparison": {"status": "NOT_READY"}}
    brain = ExecutiveCognitiveBrain()
    result = brain.execute_planning_request(
        [{"id": "task-1", "title": "Task", "type": "writing", "priority": 2}],
        behavior_patterns={}, optimization_evidence=evidence,
    )
    assert result["optimization_evidence"] == evidence
    assert result["executive_context"]["optimization_evidence"] == evidence
    assert result["recommended_plan"]


def test_current_production_gate_returns_not_ready_and_does_not_run_qaoa():
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    evidence = orchestrator._build_hybrid_optimization_evidence([])
    assert evidence["quantum_suitability"]["status"] == "NOT_READY"
    assert evidence["quantum_candidate"]["status"] == "NOT_READY"
    assert evidence["hybrid_comparison"]["status"] == "NOT_READY"
    assert evidence["quantum_candidate"]["fallback"] is False
