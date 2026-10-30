import json
from backend.app.ai_rl.benchmark_environment import BenchmarkEvaluator
from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager

def run_rl_benchmarks():
    mgr = PublicDatasetManager()
    scenarios = mgr.get_scheduling_benchmark_scenarios()

    results = {}
    for sc_id, sc_data in scenarios.items():
        tasks = sc_data["tasks"]
        patterns = sc_data["behavior_patterns"]
        avail_hours = sc_data.get("available_hours")
        feasible_flag = sc_data.get("is_mathematically_feasible")
        print(f"\n================ Running RL Benchmark: {sc_id} ({len(tasks)} tasks, Feasible={feasible_flag}) ================")

        # 1. Baseline Priority First
        base_priority = BenchmarkEvaluator.evaluate_heuristic_priority(
            tasks, patterns, scenario_id=sc_id, episodes=10,
            available_hours=avail_hours, is_mathematically_feasible=feasible_flag
        )
        print("Heuristic Priority:", base_priority.to_dict())

        # 2. Baseline EDF
        base_edf = BenchmarkEvaluator.evaluate_earliest_deadline_first(
            tasks, patterns, scenario_id=sc_id, episodes=10,
            available_hours=avail_hours, is_mathematically_feasible=feasible_flag
        )
        print("Heuristic EDF:", base_edf.to_dict())

        # 3. Trained Q-Policy
        q_metrics, scheduler = BenchmarkEvaluator.train_and_evaluate_q_learning(
            tasks, patterns, scenario_id=sc_id, training_episodes=50, eval_episodes=5,
            available_hours=avail_hours, is_mathematically_feasible=feasible_flag
        )
        print("Trained Q-Policy:", q_metrics.to_dict())

        results[sc_id] = {
            "baseline_priority": base_priority.to_dict(),
            "baseline_edf": base_edf.to_dict(),
            "trained_q_policy": q_metrics.to_dict(),
        }

    out_file = "scratch/rl_benchmark_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved complete benchmark results to {out_file}")

if __name__ == "__main__":
    run_rl_benchmarks()
