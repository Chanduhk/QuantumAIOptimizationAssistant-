import json
import math
from backend.app.ai_rl.benchmark_environment import BenchmarkEvaluator, RLSchedulingBenchmarkEnvironment
from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager

mgr = PublicDatasetManager()
sc = mgr.get_scheduling_benchmark_scenarios()["scenario_heavy_conflict"]
tasks = sc["tasks"]
patterns = sc["behavior_patterns"]
avail = sc["available_hours"]

print("================ TESTING HORIZON ENFORCEMENT ON HEAVY CONFLICT ================")
print(f"Tasks: {len(tasks)}, Duration: {sum(t['estimated_duration'] for t in tasks)}h")
print(f"Strict horizon: [{min(avail)}, {max(avail)+1}) = {len(avail)} hours")

# Test with strict horizon [9, 16] (end_hour=16 means finish by 17)
env_strict = RLSchedulingBenchmarkEnvironment(
    tasks, patterns, start_hour=min(avail), end_hour=max(avail), seed=0
)
print(f"Env actions: {env_strict.available_actions}")
print(f"Env start: {env_strict.start_hour}, end: {env_strict.end_hour}")

# What happens if we step into env_strict?
# If a task starts at 16 with duration 1.5h, completion is 17.5 > end_hour + 1 (17.0) -> out of bounds!
# If a task action is < 9 or > 16 -> invalid assignment!
