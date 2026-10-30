"""
Phase F13 Benchmark Suite Tests.
Verifies PublicDatasetManager, RLSchedulingBenchmarkEnvironment,
VectorMemoryBenchmarkEvaluator, QuantumBenchmarkRunner, and
FastAPI benchmark endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager
from backend.app.ai_rl.benchmark_environment import (
    RLSchedulingBenchmarkEnvironment,
    BenchmarkEvaluator,
)
from backend.app.memory.benchmark_evaluator import VectorMemoryBenchmarkEvaluator
from backend.app.quantum.benchmarking.quantum_benchmark_runner import QuantumBenchmarkRunner


@pytest.fixture
def client():
    return TestClient(app)


def test_public_dataset_manager_matrix_and_catalog():
    manager = PublicDatasetManager()
    matrix = manager.get_compatibility_matrix()
    assert len(matrix) >= 5
    # Verify documented columns
    required_cols = [
        "dataset_name", "source", "official_download_location", "license",
        "dataset_version", "target_variable", "target_units", "feature_compatibility",
        "sample_count", "missing_value_concerns", "temporal_structure",
        "known_leakage_risks", "model_candidates_supported", "preprocessing_required",
        "train_validation_test_strategy", "baseline", "evaluation_metrics",
        "estimated_download_size", "status", "reason_accepted_or_rejected"
    ]
    for row in matrix:
        for col in required_cols:
            assert col in row, f"Missing column {col} in row {row.get('dataset_name')}"

    catalog = manager.get_dataset_catalog()
    assert len(catalog) >= 3
    for entry in catalog:
        assert "total_records" in entry
        assert "promotion_verdict" in entry

    scenarios = manager.get_scheduling_benchmark_scenarios()
    assert len(scenarios) >= 3
    for s_id, s in scenarios.items():
        assert "tasks" in s
        assert len(s["tasks"]) > 0


def test_rl_benchmark_environment_execution():
    manager = PublicDatasetManager()
    scenarios = manager.get_scheduling_benchmark_scenarios()
    first_scenario = next(iter(scenarios.values()))
    env = RLSchedulingBenchmarkEnvironment(
        tasks=first_scenario["tasks"],
        behavior_patterns=first_scenario["behavior_patterns"],
    )
    obs = env.reset()
    assert "hour_bucket" in obs
    assert "priority" in obs

    next_obs, reward, done, step_info = env.step(action_hour=9)
    assert isinstance(reward, float)
    assert isinstance(done, bool)

    p_metrics = BenchmarkEvaluator.evaluate_heuristic_priority(
        first_scenario["tasks"], first_scenario["behavior_patterns"], scenario_id="light", episodes=5
    )
    assert p_metrics.mean_reward > 0
    assert p_metrics.task_completion_rate_pct == 100.0

    edf_metrics = BenchmarkEvaluator.evaluate_earliest_deadline_first(
        first_scenario["tasks"], first_scenario["behavior_patterns"], scenario_id="light", episodes=5
    )
    assert edf_metrics.mean_reward > 0
    assert edf_metrics.task_completion_rate_pct == 100.0


def test_vector_memory_benchmark():
    metrics = VectorMemoryBenchmarkEvaluator.evaluate_retrieval(force_fallback=True)
    assert hasattr(metrics, "recall_at_1")
    assert hasattr(metrics, "recall_at_3")
    assert hasattr(metrics, "recall_at_5")
    assert hasattr(metrics, "mrr")
    assert metrics.mean_latency_ms >= 0
    d = metrics.to_dict()
    assert "recall_at_1" in d
    assert "mean_latency_ms" in d


def test_quantum_benchmark_runner_all_stages():
    runner = QuantumBenchmarkRunner()
    report = runner.run_all_benchmarks()
    report_dict = report.to_dict()
    assert "stage_9a_formulation" in report_dict
    assert "stage_9b_classical_references" in report_dict
    assert "stage_9c_qaoa_simulations" in report_dict
    assert "stage_9d_hybrid_comparisons" in report_dict
    assert "stage_9e_multi_objective" in report_dict
    assert "provenance" in report_dict

    # Verify Stage 9A formulation correctness
    assert report.stage_9a_formulation.all_exact_matches is True
    assert report.stage_9a_formulation.qubo_direct_vs_evaluated_max_diff == 0.0

    # Verify Stage 9B exact classical solver
    assert len(report.stage_9b_classical_references) > 0

    # Verify Stage 9F provenance
    assert "LOCAL_CLASSICAL_SIMULATION" in report.provenance
    assert report.quantum_hardware_access == "NONE_LOCAL_SIMULATION_ONLY"
    assert report.quantum_advantage_observed is False


def test_benchmark_api_endpoints(client):
    res_datasets = client.get("/api/v1/benchmarks/datasets")
    assert res_datasets.status_code == 200
    data_d = res_datasets.json()["result"]
    assert "catalog" in data_d
    assert "compatibility_matrix" in data_d
    assert "scheduling_scenarios" in data_d

    res_quantum = client.get("/api/v1/benchmarks/quantum")
    assert res_quantum.status_code == 200
    data_q = res_quantum.json()["result"]
    assert "provenance" in data_q
    assert data_q["quantum_advantage_observed"] is False

    res_rl = client.get("/api/v1/benchmarks/rl")
    assert res_rl.status_code == 200
    data_rl = res_rl.json()["result"]
    assert "scenario_light_load" in data_rl or "status" in data_rl

    res_vm = client.get("/api/v1/benchmarks/vector-memory")
    assert res_vm.status_code == 200
    data_vm = res_vm.json()["result"]
    assert "recall_at_1" in data_vm or "status" in data_vm


if __name__ == "__main__":
    print("Running test_public_dataset_manager_matrix_and_catalog...")
    test_public_dataset_manager_matrix_and_catalog()
    print("Running test_rl_benchmark_environment_execution...")
    test_rl_benchmark_environment_execution()
    print("Running test_vector_memory_benchmark...")
    test_vector_memory_benchmark()
    print("Running test_quantum_benchmark_runner_all_stages...")
    test_quantum_benchmark_runner_all_stages()
    print("Running test_benchmark_api_endpoints...")
    c = TestClient(app)
    test_benchmark_api_endpoints(c)
    print("ALL 5 BENCHMARK SUITE TESTS PASSED SUCCESSFULLY!")

