import json
import math
from backend.app.ai_rl.benchmark_environment import BenchmarkEvaluator, RLSchedulingBenchmarkEnvironment
from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager
from backend.app.domain.optimization_input_contract import normalize_duration

mgr = PublicDatasetManager()
sc = mgr.get_scheduling_benchmark_scenarios()["scenario_heavy_conflict"]
tasks = sc["tasks"]
patterns = sc["behavior_patterns"]
available_hours = sc["available_hours"]

print("==================== AUDITING SCENARIO HEAVY CONFLICT ====================")
print(f"Scenario available hours: {available_hours} (Horizon: {min(available_hours)} to {max(available_hours)+1})")
print(f"Total task count: {len(tasks)}, Total required duration: {sum(t['estimated_duration'] for t in tasks)} hours")

# 1. Inspect Heuristic Priority First schedule
print("\n--- 1. Heuristic Priority First (1 Episode) ---")
env_p = RLSchedulingBenchmarkEnvironment(tasks, patterns, seed=0)
sorted_tasks_p = sorted(tasks, key=lambda t: -int(t.get("priority", 3)))
focus_hours = sorted(patterns.get("best_focus_hours", [9, 10, 11]))
used_hours_p = set()

for t in sorted_tasks_p:
    dur = t["estimated_duration"]
    span = max(1, math.ceil(dur - 1e-6))
    def _fits(h):
        if h + dur > env_p.end_hour + 1:
            return False
        return all((h + off) not in used_hours_p for off in range(span))
    
    chosen = None
    for fh in focus_hours:
        if fh in env_p.available_actions and _fits(fh):
            chosen = fh
            break
    if chosen is None:
        for h in env_p.available_actions:
            if _fits(h):
                chosen = h
                break
    chosen = chosen if chosen is not None else env_p.available_actions[0]
    for off in range(span):
        used_hours_p.add(chosen + off)
    
    _, r, _, info = env_p.step(chosen)

for st in env_p.scheduled_tasks:
    in_horizon = (st["scheduled_start"] >= min(available_hours) and st["scheduled_end"] <= max(available_hours) + 1)
    on_time = st["scheduled_end"] <= st.get("deadline_hour", 24)
    print(f"Task {st['task_id']} (prio={st['priority']}, dur={st['estimated_duration']}h, ddl={st.get('deadline_hour')}): "
          f"[{st['scheduled_start']}, {st['scheduled_end']}) | in_scenario_horizon={in_horizon} | on_time={on_time}")
print(f"Total reward: {env_p.total_reward:.2f}, collisions: {env_p.collisions}, overflows: {env_p.slot_capacity_overflows}, "
      f"overlaps: {env_p.overlapping_task_intervals}, deadline_violations: {env_p.deadline_violations}, invalid: {env_p.invalid_task_assignments}")

# 2. Inspect EDF schedule
print("\n--- 2. Earliest Deadline First (1 Episode) ---")
env_edf = RLSchedulingBenchmarkEnvironment(tasks, patterns, seed=0)
sorted_tasks_edf = sorted(tasks, key=lambda t: int(t.get("deadline_hour", 22)))
current_hour = env_edf.start_hour
used_hours_edf = set()

for t in sorted_tasks_edf:
    dur = t["estimated_duration"]
    span = max(1, math.ceil(dur - 1e-6))
    def _fits(h):
        if h + dur > env_edf.end_hour + 1:
            return False
        return all((h + off) not in used_hours_edf for off in range(span))
    
    chosen = None
    for h in env_edf.available_actions:
        if h >= current_hour and _fits(h):
            chosen = h
            break
    if chosen is None:
        for h in env_edf.available_actions:
            if _fits(h):
                chosen = h
                break
    chosen = chosen if chosen is not None else env_edf.available_actions[0]
    for off in range(span):
        used_hours_edf.add(chosen + off)
    current_hour = chosen + span
    
    _, r, _, info = env_edf.step(chosen)

for st in env_edf.scheduled_tasks:
    in_horizon = (st["scheduled_start"] >= min(available_hours) and st["scheduled_end"] <= max(available_hours) + 1)
    on_time = st["scheduled_end"] <= st.get("deadline_hour", 24)
    print(f"Task {st['task_id']} (prio={st['priority']}, dur={st['estimated_duration']}h, ddl={st.get('deadline_hour')}): "
          f"[{st['scheduled_start']}, {st['scheduled_end']}) | in_scenario_horizon={in_horizon} | on_time={on_time}")
print(f"Total reward: {env_edf.total_reward:.2f}, collisions: {env_edf.collisions}, overflows: {env_edf.slot_capacity_overflows}, "
      f"overlaps: {env_edf.overlapping_task_intervals}, deadline_violations: {env_edf.deadline_violations}, invalid: {env_edf.invalid_task_assignments}")

# 3. Inspect Trained Q-Policy
print("\n--- 3. Trained Q-Policy Evaluation (Episode with seed 42) ---")
q_metrics, scheduler = BenchmarkEvaluator.train_and_evaluate_q_learning(
    tasks, patterns, scenario_id="scenario_heavy_conflict", training_episodes=30, eval_episodes=1, seeds=[42]
)
env_q = RLSchedulingBenchmarkEnvironment(tasks, patterns, seed=42)
used_hours_q = set()
while not env_q.is_done():
    task = env_q.raw_tasks[env_q.current_task_index]
    dur = task["estimated_duration"]
    span = max(1, math.ceil(dur - 1e-6))
    state = env_q._get_current_state()
    pref = scheduler.choose_action(state)
    action = scheduler._pick_available_hour(pref, used_hours_q, duration_hours=dur)
    for off in range(span):
        used_hours_q.add(action + off)
    env_q.step(action)

for st in env_q.scheduled_tasks:
    in_horizon = (st["scheduled_start"] >= min(available_hours) and st["scheduled_end"] <= max(available_hours) + 1)
    on_time = st["scheduled_end"] <= st.get("deadline_hour", 24)
    print(f"Task {st['task_id']} (prio={st['priority']}, dur={st['estimated_duration']}h, ddl={st.get('deadline_hour')}): "
          f"[{st['scheduled_start']}, {st['scheduled_end']}) | in_scenario_horizon={in_horizon} | on_time={on_time}")
print(f"Total reward: {env_q.total_reward:.2f}, collisions: {env_q.collisions}, overflows: {env_q.slot_capacity_overflows}, "
      f"overlaps: {env_q.overlapping_task_intervals}, deadline_violations: {env_q.deadline_violations}, invalid: {env_q.invalid_task_assignments}")
