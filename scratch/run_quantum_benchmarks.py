import json
from backend.app.quantum.benchmarking.quantum_benchmark_runner import QuantumBenchmarkRunner

def run():
    print("Executing Quantum and Classical Optimization Benchmarking Suite (Stages 9A to 9F)...")
    runner = QuantumBenchmarkRunner()
    summary = runner.run_all_benchmarks()
    out = summary.to_dict()

    print("\n=== Stage 9A: Formulation Correctness ===")
    print(json.dumps(out["stage_9a_formulation"], indent=2))

    print("\n=== Stage 9B: Classical Reference Solutions ===")
    for ref in out["stage_9b_classical_references"]:
        print(f"Problem: {ref['problem_id']}, Vars: {ref['num_variables']}, Energy: {ref['optimal_energy']}, Bits: {ref['optimal_bitstrings']}, Runtime: {ref['runtime_ms']}ms")

    print("\n=== Stage 9C: QAOA Simulations ===")
    for q in out["stage_9c_qaoa_simulations"]:
        print(f"Problem: {q['problem_id']}, Qubits: {q['num_qubits']}, Opt: {q['exact_optimal_energy']}, QAOA: {q['best_sampled_energy']}, ApproxRatio: {q['approximation_ratio']}, NormValid: {q['statevector_norm_valid']}, Runtime: {q['runtime_ms']}ms")

    print("\n=== Stage 9D: Hybrid Optimization Comparisons ===")
    for h in out["stage_9d_hybrid_comparisons"]:
        print(f"Problem: {h['problem_id']}, Classical: {h['classical_energy']}, QAOA: {h['qaoa_energy']}, Selected: {h['selected_energy']}, Source: {h['selected_source']}, Fallback: {h['fallback_active']}")

    print("\n=== Stage 9E: Multi-Objective Optimization ===")
    print(json.dumps(out["stage_9e_multi_objective"], indent=2))

    print("\n=== Stage 9F: Provenance & Safety ===")
    print("Provenance Banner:", out["provenance"])
    print("Hardware Access:", out["quantum_hardware_access"])
    print("Quantum Advantage Claimed:", out["quantum_advantage_observed"])

    with open("scratch/quantum_optimization_benchmark_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nSaved complete benchmark summary to scratch/quantum_optimization_benchmark_results.json")

if __name__ == "__main__":
    run()
