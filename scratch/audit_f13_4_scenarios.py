import json
from backend.app.ai_rl.benchmark_environment import BenchmarkEvaluator, RLSchedulingBenchmarkEnvironment
from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager

mgr = PublicDatasetManager()
scenarios = mgr.get_scheduling_benchmark_scenarios()

for sc_id, sc in scenarios.items():
    print(f"\n==================== SCENARIO: {sc_id} ====================")
    print(f"Name: {sc['name']}")
    print(f"Description: {sc['description']}")
    avail = sc.get("available_hours", [])
    print(f"Scenario available_hours: {avail} (Count: {len(avail)})")
    if avail:
        print(f"Scenario horizon: [{min(avail)}, {max(avail) + 1}) = {len(avail)} hours")
    
    total_duration = sum(t["estimated_duration"] for t in sc["tasks"])
    print(f"Total task count: {len(sc['tasks'])}, Total duration: {total_duration} hours")
    for t in sc["tasks"]:
        print(f"  - {t['task_id']} ({t.get('title', '')}): dur={t['estimated_duration']}h, prio={t['priority']}, deadline={t.get('deadline_hour')}")

    # Inspect what the environment currently uses:
    env_default = RLSchedulingBenchmarkEnvironment(sc["tasks"], sc["behavior_patterns"])
    print(f"Env default start_hour={env_default.start_hour}, end_hour={env_default.end_hour}, actions={env_default.available_actions}")
