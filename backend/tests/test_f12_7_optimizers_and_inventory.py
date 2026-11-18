from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.resilient_http import CircuitBreaker, CircuitState, ResilientHttpClient, redact_secrets
from backend.app.domain.classical_optimizer import ClassicalAssignment, ClassicalCandidate, ClassicalOptimizer
from backend.app.domain.multi_objective_model import OptimizationObjective
from backend.app.domain.prediction_matrix import PredictionMatrix, SyntheticTestPredictionCell
from backend.app.domain.simulation_model import SimulationResult
from backend.app.engines.multi_objective_optimization_engine import MultiObjectiveOptimizationEngine
from backend.app.ml.system_inventory import (
    ComponentType,
    OperationalState,
    SystemComponentRegistry,
    get_system_inventory,
)
from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.quantum.domain import (
    ObjectiveSense,
    QUBOProblem,
    QuantumObjective,
    QuantumVariable,
)
from backend.app.quantum.formulation import QUBOFormulator
from backend.app.quantum.hybrid import HybridOptimizationEngine
from backend.app.quantum.optimization import QAOAConfig, QAOAEngine
from backend.main import app


def test_system_component_inventory_discovers_all_components():
    """Verify that every supported model, optimizer, heuristic, and provider is cataloged."""
    registry = SystemComponentRegistry.get_instance()
    inventory = registry.initialize_all(force=True)

    expected_canonical_ids = {
        "duration_ratio_model",
        "productivity_model",
        "rl_scheduler",
        "vector_memory_embedding",
        "classical_optimizer",
        "multi_objective_optimizer",
        "exact_classical_solver",
        "qubo_formulator",
        "qaoa_simulator",
        "hybrid_optimizer",
        "prediction_engine",
        "autonomous_planning_engine",
        "decision_pipeline",
        "conversational_intelligence",
        "public_dataset_manager",
        "training_controller",
    }

    assert expected_canonical_ids.issubset(set(inventory.keys()))

    # Verify honest distinction: optimizers are AVAILABLE without requiring an ML model
    assert inventory["classical_optimizer"].can_execute_now is True
    assert inventory["classical_optimizer"].operational_state == OperationalState.AVAILABLE
    assert inventory["multi_objective_optimizer"].can_execute_now is True
    assert inventory["exact_classical_solver"].can_execute_now is True
    assert inventory["qubo_formulator"].can_execute_now is True
    assert inventory["qaoa_simulator"].can_execute_now is True

    # Duration model: available for prediction, accurately reporting operational/fallback state
    dur = inventory["duration_ratio_model"]
    assert dur.can_execute_now is True
    assert isinstance(dur.fallback_active, bool)
    assert dur.training_state in {OperationalState.NOT_READY_INSUFFICIENT_DATA, OperationalState.TRAINED}

    # Productivity model: available for prediction, accurately reporting operational/fallback state
    prod = inventory["productivity_model"]
    assert prod.can_execute_now is True
    assert isinstance(prod.fallback_active, bool)

    # Quantum simulation: explicit provenance, never claims quantum hardware
    qaoa = inventory["qaoa_simulator"]
    assert qaoa.requires_external_api is False
    assert "software execution" in qaoa.provenance.lower() or "simulation" in qaoa.notes.lower()


def test_inventory_is_idempotent_and_creates_no_duplicates():
    """Verify that repeated registry initialization does not create duplicate entries."""
    registry = SystemComponentRegistry.get_instance()
    inv1 = registry.initialize_all(force=True)
    count1 = len(inv1)

    inv2 = registry.initialize_all(force=False)
    assert len(inv2) == count1
    assert set(inv1.keys()) == set(inv2.keys())


def test_classical_optimizer_executes_without_ml_model():
    """Verify that classical schedule optimization executes independently of any ML model."""
    from backend.app.domain.prediction_matrix import validate_synthetic_test_matrix

    cells = [
        SyntheticTestPredictionCell(task_id=101, candidate_start_hour=9, value=85.0),
        SyntheticTestPredictionCell(task_id=101, candidate_start_hour=10, value=60.0),
        SyntheticTestPredictionCell(task_id=102, candidate_start_hour=9, value=70.0),
        SyntheticTestPredictionCell(task_id=102, candidate_start_hour=10, value=90.0),
    ]
    matrix = validate_synthetic_test_matrix(cells, [101, 102], [9, 10])

    optimizer = ClassicalOptimizer(allow_test_matrices=True)
    candidate = optimizer.optimize(matrix)

    assert candidate.feasibility is True
    assert len(candidate.assignments) == 2
    assert candidate.total_objective > 0
    assert candidate.solver == "deterministic_hungarian_assignment"
    assert candidate.runtime_seconds >= 0.0


def test_multi_objective_optimization_engine_executes_successfully():
    """Verify that multi-objective evaluation ranks scenarios and produces trade-offs."""
    engine = MultiObjectiveOptimizationEngine()

    sim1 = SimulationResult(
        scenario_id="scenario_balanced",
        success_probability=0.92,
        goal_completion_probability=0.88,
        milestone_completion_probability=0.85,
        workload_score=45.0,
        risk_score=15.0,
        confidence_score=90.0,
        projected_state={"cadence": "sustainable"},
        recommendations=["Steady cadence"],
    )

    sim2 = SimulationResult(
        scenario_id="scenario_aggressive",
        success_probability=0.75,
        goal_completion_probability=0.70,
        milestone_completion_probability=0.65,
        workload_score=85.0,
        risk_score=60.0,
        confidence_score=75.0,
        projected_state={"cadence": "overload"},
        recommendations=["High sprint"],
    )

    res = engine.optimize([sim1, sim2])
    assert res.selected_scenario_id in {"scenario_balanced", "scenario_aggressive"}
    assert res.overall_score > 0
    assert len(res.tradeoffs) > 0


def test_exact_classical_qubo_solver():
    """Verify that ExactClassicalSolver finds optimal binary state for a QUBO."""
    v0 = QuantumVariable("x0", "X0", 0)
    v1 = QuantumVariable("x1", "X1", 1)
    obj = QuantumObjective("obj_1", "Objective", ObjectiveSense.MINIMIZE)

    problem = QUBOProblem(
        problem_id="qubo_1",
        name="QUBO Test",
        variables=(v0, v1),
        linear_coefficients={"x0": -2.0, "x1": -3.0},
        quadratic_coefficients={("x0", "x1"): 4.0},
        constant_offset=0.0,
        objective=obj,
    )

    solution = ExactClassicalSolver().solve_qubo(problem)
    assert solution.feasible is True
    assert solution.objective_value <= 0


def test_resilient_http_client_retries_and_circuit_breaker():
    """Verify circuit breaker transitions and secret redaction."""
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.2)
    client = ResilientHttpClient(default_timeout=0.5, max_retries=2, circuit_breaker=breaker)

    # Secret redaction check
    dirty_text = "https://api.example.com/v1?token=secret12345&auth=bearer98765"
    clean_text = redact_secrets(dirty_text)
    assert "secret12345" not in clean_text
    assert "***REDACTED***" in clean_text

    # Verify circuit breaker records failure on unreachable local port
    with pytest.raises(RuntimeError):
        client.execute_request("http://127.0.0.1:59999/unreachable")

    assert breaker.failure_count >= 1

    # Force second failure to open circuit
    with pytest.raises(RuntimeError):
        client.execute_request("http://127.0.0.1:59999/unreachable")

    assert breaker.state == CircuitState.OPEN

    # Circuit is OPEN: subsequent requests fail immediately without network call
    with pytest.raises(RuntimeError, match="circuit breaker OPEN"):
        client.execute_request("http://127.0.0.1:59999/unreachable")


def test_component_inventory_endpoint():
    """Verify that GET /api/v1/system/component-inventory exposes all components to frontend."""
    client = TestClient(app)
    resp = client.get("/api/v1/system/component-inventory")
    assert resp.status_code == 200

    data = resp.json()["result"]
    assert data["total_components"] >= 16
    assert data["available_for_execution"] >= 10
    assert data["optimizers_available"] >= 4

    components = data["components"]
    assert "classical_optimizer" in components
    assert "duration_ratio_model" in components
    assert "qaoa_simulator" in components
    assert components["classical_optimizer"]["operational_state"] == "AVAILABLE"
    assert components["classical_optimizer"]["can_execute_now"] is True


def test_model_status_endpoint_includes_inventory():
    """Verify that GET /api/v1/ml/model-status returns total components and inventory details."""
    client = TestClient(app)
    resp = client.get("/api/v1/ml/model-status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total_components_available"] >= 10
    assert "component_inventory" in data
    assert "classical_optimizer" in data["component_inventory"]
