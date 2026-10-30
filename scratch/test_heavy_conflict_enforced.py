import time
import math
import numpy as np
from backend.app.ai_rl.benchmark_environment import (
    RLSchedulingBenchmarkEnvironment,
    BenchmarkEvaluator,
    PolicyEvaluationMetrics,
)
from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager
from backend.app.domain.optimization_input_contract import normalize_duration

def test_trace():
    mgr = PublicDatasetManager()
    scenarios = mgr.get_scheduling_benchmark_scenarios()
    sc = scenarios["scenario_heavy_conflict"]
    tasks = sc["tasks"]
    patterns = sc["behavior_patterns"]
    avail = sc["available_hours"]

    print("=== Testing Heavy Conflict with Enforced Available Hours ===")
    print(f"Available hours: {avail} (Horizon: {min(avail)} to {max(avail)+1})")
    total_dur = sum(normalize_duration(t["estimated_duration"], t["estimated_duration_unit"], t["estimated_duration_source"]).normalized_hours for t in tasks)
    print(f"Demanded hours: {total_dur} across {len(tasks)} tasks.")

    # 1. Test Environment with available_hours
    env = RLSchedulingBenchmarkEnvironment(tasks, patterns, start_hour=min(avail), end_hour=max(avail))
    print(f"Env start: {env.start_hour}, end: {env.end_hour}, actions: {env.available_actions}")

    # 2. Test Scheduler with available_actions
    sched = RLScheduler(available_actions=avail)
    print(f"Scheduler available_actions: {sched.available_actions}")

if __name__ == "__main__":
    test_trace()
