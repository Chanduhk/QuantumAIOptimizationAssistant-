from backend.app.ai_rl.benchmark_environment import (
    RLSchedulingBenchmarkEnvironment,
    BenchmarkEvaluator,
)
from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager

def run_test():
    mgr = PublicDatasetManager()
    scenarios = mgr.get_scheduling_benchmark_scenarios()
    sc = scenarios["scenario_heavy_conflict"]
    tasks = sc["tasks"]
    patterns = sc["behavior_patterns"]
    avail = sc["available_hours"]

    print("Running evaluate_heuristic_priority with avail...")
    # Currently evaluate_heuristic_priority doesn't take available_hours yet.
    # We will test our updated logic once we update BenchmarkEvaluator.

if __name__ == "__main__":
    run_test()
