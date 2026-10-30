from __future__ import annotations

import copy
import json
import logging
import math
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.domain.optimization_input_contract import normalize_duration

logger = logging.getLogger(__name__)

DEFAULT_BENCHMARK_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "artifacts" / "rl_scheduler_benchmark_candidate.json"
)


@dataclass
class PolicyEvaluationMetrics:
    """Evaluation metrics for a scheduling policy across benchmark episodes."""

    policy_name: str
    scenario_id: str
    episode_count: int
    mean_reward: float
    std_reward: float
    task_completion_rate_pct: float
    deadline_adherence_rate_pct: float
    collision_count: int
    states_learned: int = 0
    seeds_evaluated: List[int] = field(default_factory=list)
    duplicate_start_times: int = 0
    slot_capacity_overflows: int = 0
    overlapping_task_intervals: int = 0
    deadline_violations: int = 0
    invalid_task_assignments: int = 0
    tasks_outside_horizon: int = 0
    unscheduled_tasks: int = 0
    total_tasks_scheduled: int = 0
    is_mathematically_feasible: bool = True
    total_task_hours_demanded: float = 0.0
    available_horizon_hours: float = 0.0
    mean_runtime_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "scenario_id": self.scenario_id,
            "episode_count": self.episode_count,
            "mean_reward": round(self.mean_reward, 2),
            "std_reward": round(self.std_reward, 2),
            "task_completion_rate_pct": round(self.task_completion_rate_pct, 1),
            "deadline_adherence_rate_pct": round(self.deadline_adherence_rate_pct, 1),
            "collision_count": self.collision_count,
            "duplicate_start_times": self.duplicate_start_times,
            "slot_capacity_overflows": self.slot_capacity_overflows,
            "overlapping_task_intervals": self.overlapping_task_intervals,
            "deadline_violations": self.deadline_violations,
            "invalid_task_assignments": self.invalid_task_assignments,
            "tasks_outside_horizon": self.tasks_outside_horizon,
            "unscheduled_tasks": self.unscheduled_tasks,
            "total_tasks_scheduled": self.total_tasks_scheduled,
            "is_mathematically_feasible": self.is_mathematically_feasible,
            "total_task_hours_demanded": round(self.total_task_hours_demanded, 2),
            "available_horizon_hours": round(self.available_horizon_hours, 2),
            "mean_runtime_ms": round(self.mean_runtime_ms, 2),
            "states_learned": self.states_learned,
            "seeds_evaluated": self.seeds_evaluated,
        }


class RLSchedulingBenchmarkEnvironment:
    """Isolated, reproducible scheduling environment modeling tasks, energy, and deadlines.
    
    Strictly isolated from personal user production database.
    """

    def __init__(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
        available_hours: Optional[List[int]] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.raw_tasks = copy.deepcopy(tasks)
        self.behavior_patterns = copy.deepcopy(behavior_patterns)
        if available_hours is not None and len(available_hours) > 0:
            self.available_actions = sorted(list(available_hours))
            self.start_hour = min(self.available_actions)
            self.end_hour = max(self.available_actions)
        else:
            self.start_hour = start_hour if start_hour is not None else 6
            self.end_hour = end_hour if end_hour is not None else 22
            self.available_actions = list(range(self.start_hour, self.end_hour + 1))
        self.rng = random.Random(seed)
        self.reset()

    def reset(self) -> Dict[str, Any]:
        """Reset the environment to the beginning of the scheduling horizon."""
        self.occupied_slots: Dict[int, float] = {}  # hour -> duration used
        self.scheduled_tasks: List[Dict[str, Any]] = []
        self.current_task_index = 0
        self.total_reward = 0.0
        self.deadline_violations = 0
        self.collisions = 0
        self.duplicate_start_times = 0
        self.slot_capacity_overflows = 0
        self.overlapping_task_intervals = 0
        self.invalid_task_assignments = 0
        self.tasks_outside_horizon = 0
        self.unscheduled_tasks = 0
        return self._get_current_state()

    def _get_current_state(self) -> Dict[str, Any]:
        if self.is_done():
            return {
                "hour_bucket": 7,
                "productivity_bucket": 0,
                "priority": 1,
                "task_type": "done",
                "energy_bucket": 0,
            }
        task = self.raw_tasks[self.current_task_index]
        hour = int(task.get("prediction_hour") or task.get("scheduled_hour") or 10)
        productivity = float(
            task.get("predicted_productivity")
            or self.behavior_patterns.get("average_productivity", 50.0)
        )
        priority = int(task.get("priority") or 3)
        task_type = str(task.get("task_type", "general")).strip().lower() or "general"
        energy = self._estimate_energy_level(hour)

        return {
            "hour_bucket": min(hour // 3, 7),
            "productivity_bucket": min(int(productivity // 20), 5),
            "priority": max(1, min(priority, 5)),
            "task_type": task_type,
            "energy_bucket": min(int(energy // 20), 5),
        }

    def _estimate_energy_level(self, hour: int) -> float:
        best_focus_hours = [int(h) for h in self.behavior_patterns.get("best_focus_hours", [])]
        if best_focus_hours:
            dist = min(abs(hour - fh) for fh in best_focus_hours)
            return max(20.0, 100.0 - (dist * 12.0))
        return float(self.behavior_patterns.get("average_energy_level", 60.0))

    def is_done(self) -> bool:
        return self.current_task_index >= len(self.raw_tasks)

    def step(self, action_hour: int) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """Schedule the current task into action_hour and return (next_state, reward, done, info)."""
        if self.is_done():
            return self._get_current_state(), 0.0, True, {"message": "Already done"}

        task = self.raw_tasks[self.current_task_index]
        dur_unit = task.get("estimated_duration_unit", "hours")
        dur_src = task.get("estimated_duration_source", "benchmark")
        norm = normalize_duration(task.get("estimated_duration", 1.0), dur_unit, dur_src)
        dur_hours = norm.normalized_hours

        priority = float(task.get("priority", 3.0))
        deadline = task.get("deadline_hour", self.end_hour)
        completion_hour = action_hour + dur_hours

        # 1. Base completion and priority reward
        reward = 10.0 + (priority * 4.0)

        # 2. Focus and energy alignment bonus
        best_focus = {int(h) for h in self.behavior_patterns.get("best_focus_hours", [])}
        if action_hour in best_focus:
            reward += 12.0
        energy = self._estimate_energy_level(action_hour)
        reward += (energy / 100.0) * 8.0

        # 3. Deadline check
        if deadline is not None and completion_hour > deadline:
            tardiness = completion_hour - deadline
            reward -= 15.0 + (tardiness * 5.0)
            self.deadline_violations += 1
        else:
            reward += 10.0  # On-time completion incentive

        # 4. Multi-hour occupancy and constraint checks
        # 4a. Duplicate start times
        has_duplicate_start = any(
            t.get("scheduled_start") == action_hour for t in self.scheduled_tasks
        )
        if has_duplicate_start:
            self.duplicate_start_times += 1

        # 4b. Overlapping task intervals with already scheduled tasks
        has_interval_overlap = False
        for t in self.scheduled_tasks:
            t_start = float(t["scheduled_start"])
            t_end = float(t["scheduled_end"])
            if max(float(action_hour), t_start) < min(completion_hour, t_end) - 1e-6:
                has_interval_overlap = True
                break
        if has_interval_overlap:
            self.overlapping_task_intervals += 1

        # 4c. Slot capacity overflow across all hourly slots spanned by task
        has_slot_overflow = False
        start_slot = int(action_hour)
        end_slot = int(math.ceil(completion_hour - 1e-6))
        for slot in range(start_slot, end_slot):
            slot_duration = min(completion_hour, float(slot + 1)) - max(float(action_hour), float(slot))
            existing_load = self.occupied_slots.get(slot, 0.0)
            if existing_load + slot_duration > 1.0 + 1e-6:
                has_slot_overflow = True
            self.occupied_slots[slot] = existing_load + slot_duration

        if has_slot_overflow:
            self.slot_capacity_overflows += 1

        is_collision = has_slot_overflow or has_interval_overlap or has_duplicate_start
        if is_collision:
            reward -= 20.0  # Heavy collision penalty
            self.collisions += 1

        # 5. Out of bounds / invalid assignment check
        horizon_start = float(self.start_hour)
        horizon_end = float(self.end_hour + 1)

        is_outside_horizon = False
        if float(action_hour) < horizon_start or completion_hour > horizon_end + 1e-6:
            is_outside_horizon = True
            self.tasks_outside_horizon += 1

        is_invalid_assignment = False
        if action_hour < self.start_hour or action_hour not in self.available_actions:
            is_invalid_assignment = True
        if completion_hour > horizon_end + 1e-6:
            is_invalid_assignment = True

        if is_invalid_assignment:
            reward -= 15.0
            self.invalid_task_assignments += 1

        scheduled_task = {
            **task,
            "scheduled_start": action_hour,
            "scheduled_end": round(completion_hour, 2),
            "step_reward": round(reward, 2),
        }
        self.scheduled_tasks.append(scheduled_task)
        self.total_reward += reward
        self.current_task_index += 1

        done = self.is_done()
        next_state = self._get_current_state()
        info = {
            "task_id": task.get("task_id", f"T{self.current_task_index}"),
            "completion_hour": completion_hour,
            "deadline": deadline,
            "on_time": deadline is None or completion_hour <= deadline,
            "collision": is_collision,
            "duplicate_start": has_duplicate_start,
            "interval_overlap": has_interval_overlap,
            "slot_overflow": has_slot_overflow,
            "invalid_assignment": is_invalid_assignment,
            "outside_horizon": is_outside_horizon,
        }
        return next_state, reward, done, info


class BenchmarkEvaluator:
    """Trains and compares RL scheduling policy against classical heuristics."""

    @staticmethod
    def evaluate_heuristic_priority(
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        scenario_id: str = "light",
        episodes: int = 10,
        available_hours: Optional[List[int]] = None,
        is_mathematically_feasible: Optional[bool] = None,
    ) -> PolicyEvaluationMetrics:
        """Baseline 1: Priority-First Heuristic."""
        start_time = time.perf_counter()
        durations = [
            normalize_duration(
                t.get("estimated_duration", 1.0),
                t.get("estimated_duration_unit", "hours"),
                t.get("estimated_duration_source", "benchmark"),
            ).normalized_hours
            for t in tasks
        ]
        total_demanded_hours = round(sum(durations), 2)
        horizon_hours = float(len(available_hours)) if available_hours else float(23 - 6)
        feasible_flag = (
            is_mathematically_feasible
            if is_mathematically_feasible is not None
            else (total_demanded_hours <= horizon_hours)
        )

        rewards = []
        violations = 0
        completed = 0
        total_tasks = len(tasks) * episodes
        total_collisions = 0
        total_duplicate_starts = 0
        total_slot_overflows = 0
        total_interval_overlaps = 0
        total_deadline_violations = 0
        total_invalid_assignments = 0
        total_tasks_outside_horizon = 0

        for ep in range(episodes):
            env = RLSchedulingBenchmarkEnvironment(
                tasks, behavior_patterns, available_hours=available_hours, seed=ep
            )
            sorted_tasks = sorted(tasks, key=lambda t: -int(t.get("priority", 3)))
            # Sort best focus hours
            focus_hours = sorted(behavior_patterns.get("best_focus_hours", [9, 10, 11]))
            used_hours: set[int] = set()

            ep_reward = 0.0
            for task in sorted_tasks:
                dur_unit = task.get("estimated_duration_unit", "hours")
                dur_src = task.get("estimated_duration_source", "benchmark")
                dur_hours = normalize_duration(task.get("estimated_duration", 1.0), dur_unit, dur_src).normalized_hours
                span = max(1, math.ceil(dur_hours - 1e-6))

                def _fits(h: int) -> bool:
                    if h not in env.available_actions:
                        return False
                    if h + dur_hours > env.end_hour + 1 + 1e-6:
                        return False
                    return all((h + off) not in used_hours for off in range(span))

                chosen = None
                for fh in focus_hours:
                    if fh in env.available_actions and _fits(fh):
                        chosen = fh
                        break
                if chosen is None:
                    for h in env.available_actions:
                        if _fits(h):
                            chosen = h
                            break
                chosen = chosen if chosen is not None else env.available_actions[0]
                for off in range(span):
                    used_hours.add(chosen + off)

                _, r, _, info = env.step(chosen)
                ep_reward += r
                if not info["on_time"] or info["collision"]:
                    violations += 1
                completed += 1
            rewards.append(ep_reward)
            total_collisions += env.collisions
            total_duplicate_starts += env.duplicate_start_times
            total_slot_overflows += env.slot_capacity_overflows
            total_interval_overlaps += env.overlapping_task_intervals
            total_deadline_violations += env.deadline_violations
            total_invalid_assignments += env.invalid_task_assignments
            total_tasks_outside_horizon += env.tasks_outside_horizon

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        mean_runtime_ms = round(elapsed_ms / max(1, episodes), 2)
        completion_rate = 100.0 * (completed / total_tasks)
        adherence_rate = max(0.0, 100.0 * (1.0 - (violations / total_tasks)))
        return PolicyEvaluationMetrics(
            policy_name="Heuristic_Priority_First",
            scenario_id=scenario_id,
            episode_count=episodes,
            mean_reward=float(np.mean(rewards)),
            std_reward=float(np.std(rewards)),
            task_completion_rate_pct=completion_rate,
            deadline_adherence_rate_pct=adherence_rate,
            collision_count=total_collisions,
            states_learned=0,
            seeds_evaluated=list(range(episodes)),
            duplicate_start_times=total_duplicate_starts,
            slot_capacity_overflows=total_slot_overflows,
            overlapping_task_intervals=total_interval_overlaps,
            deadline_violations=total_deadline_violations,
            invalid_task_assignments=total_invalid_assignments,
            tasks_outside_horizon=total_tasks_outside_horizon,
            unscheduled_tasks=0,
            total_tasks_scheduled=completed,
            is_mathematically_feasible=feasible_flag,
            total_task_hours_demanded=total_demanded_hours,
            available_horizon_hours=horizon_hours,
            mean_runtime_ms=mean_runtime_ms,
        )

    @staticmethod
    def evaluate_earliest_deadline_first(
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        scenario_id: str = "light",
        episodes: int = 10,
        available_hours: Optional[List[int]] = None,
        is_mathematically_feasible: Optional[bool] = None,
    ) -> PolicyEvaluationMetrics:
        """Baseline 2: Earliest Deadline First (EDF) scheduler."""
        start_time = time.perf_counter()
        durations = [
            normalize_duration(
                t.get("estimated_duration", 1.0),
                t.get("estimated_duration_unit", "hours"),
                t.get("estimated_duration_source", "benchmark"),
            ).normalized_hours
            for t in tasks
        ]
        total_demanded_hours = round(sum(durations), 2)
        horizon_hours = float(len(available_hours)) if available_hours else float(23 - 6)
        feasible_flag = (
            is_mathematically_feasible
            if is_mathematically_feasible is not None
            else (total_demanded_hours <= horizon_hours)
        )

        rewards = []
        violations = 0
        completed = 0
        total_tasks = len(tasks) * episodes
        total_collisions = 0
        total_duplicate_starts = 0
        total_slot_overflows = 0
        total_interval_overlaps = 0
        total_deadline_violations = 0
        total_invalid_assignments = 0
        total_tasks_outside_horizon = 0

        for ep in range(episodes):
            env = RLSchedulingBenchmarkEnvironment(
                tasks, behavior_patterns, available_hours=available_hours, seed=ep
            )
            # Sort by deadline ascending
            sorted_tasks = sorted(tasks, key=lambda t: int(t.get("deadline_hour", 22)))
            current_hour = env.start_hour
            used_hours: set[int] = set()

            ep_reward = 0.0
            for task in sorted_tasks:
                dur_unit = task.get("estimated_duration_unit", "hours")
                dur_src = task.get("estimated_duration_source", "benchmark")
                dur_hours = normalize_duration(task.get("estimated_duration", 1.0), dur_unit, dur_src).normalized_hours
                span = max(1, math.ceil(dur_hours - 1e-6))

                def _fits(h: int) -> bool:
                    if h not in env.available_actions:
                        return False
                    if h + dur_hours > env.end_hour + 1 + 1e-6:
                        return False
                    return all((h + off) not in used_hours for off in range(span))

                chosen = None
                for h in env.available_actions:
                    if h >= current_hour and _fits(h):
                        chosen = h
                        break
                if chosen is None:
                    for h in env.available_actions:
                        if _fits(h):
                            chosen = h
                            break
                chosen = chosen if chosen is not None else env.available_actions[0]
                for off in range(span):
                    used_hours.add(chosen + off)
                current_hour = chosen + span

                _, r, _, info = env.step(chosen)
                ep_reward += r
                if not info["on_time"] or info["collision"]:
                    violations += 1
                completed += 1
            rewards.append(ep_reward)
            total_collisions += env.collisions
            total_duplicate_starts += env.duplicate_start_times
            total_slot_overflows += env.slot_capacity_overflows
            total_interval_overlaps += env.overlapping_task_intervals
            total_deadline_violations += env.deadline_violations
            total_invalid_assignments += env.invalid_task_assignments
            total_tasks_outside_horizon += env.tasks_outside_horizon

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        mean_runtime_ms = round(elapsed_ms / max(1, episodes), 2)
        completion_rate = 100.0 * (completed / total_tasks)
        adherence_rate = max(0.0, 100.0 * (1.0 - (violations / total_tasks)))
        return PolicyEvaluationMetrics(
            policy_name="Earliest_Deadline_First_EDF",
            scenario_id=scenario_id,
            episode_count=episodes,
            mean_reward=float(np.mean(rewards)),
            std_reward=float(np.std(rewards)),
            task_completion_rate_pct=completion_rate,
            deadline_adherence_rate_pct=adherence_rate,
            collision_count=total_collisions,
            states_learned=0,
            seeds_evaluated=list(range(episodes)),
            duplicate_start_times=total_duplicate_starts,
            slot_capacity_overflows=total_slot_overflows,
            overlapping_task_intervals=total_interval_overlaps,
            deadline_violations=total_deadline_violations,
            invalid_task_assignments=total_invalid_assignments,
            tasks_outside_horizon=total_tasks_outside_horizon,
            unscheduled_tasks=0,
            total_tasks_scheduled=completed,
            is_mathematically_feasible=feasible_flag,
            total_task_hours_demanded=total_demanded_hours,
            available_horizon_hours=horizon_hours,
            mean_runtime_ms=mean_runtime_ms,
        )

    @staticmethod
    def train_and_evaluate_q_learning(
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        scenario_id: str = "light",
        training_episodes: int = 60,
        eval_episodes: int = 10,
        policy_save_path: Optional[Path] = None,
        seeds: Optional[List[int]] = None,
        available_hours: Optional[List[int]] = None,
        is_mathematically_feasible: Optional[bool] = None,
    ) -> Tuple[PolicyEvaluationMetrics, RLScheduler]:
        """Train Q-learning agent on isolated benchmark environment and evaluate across seeds."""
        durations = [
            normalize_duration(
                t.get("estimated_duration", 1.0),
                t.get("estimated_duration_unit", "hours"),
                t.get("estimated_duration_source", "benchmark"),
            ).normalized_hours
            for t in tasks
        ]
        total_demanded_hours = round(sum(durations), 2)
        horizon_hours = float(len(available_hours)) if available_hours else float(23 - 6)
        feasible_flag = (
            is_mathematically_feasible
            if is_mathematically_feasible is not None
            else (total_demanded_hours <= horizon_hours)
        )

        save_path = policy_save_path or DEFAULT_BENCHMARK_POLICY_PATH
        eval_seeds = seeds or [42, 123, 999]

        scheduler = RLScheduler(
            policy_path=str(save_path),
            learning_rate=0.25,
            discount_factor=0.90,
            exploration_rate=0.20,
            available_actions=available_hours,
        )

        # 1. Training Phase
        for ep in range(training_episodes):
            env = RLSchedulingBenchmarkEnvironment(
                tasks, behavior_patterns, available_hours=available_hours, seed=ep
            )
            state = env.reset()
            # Linear decay of exploration rate
            scheduler.exploration_rate = max(0.05, 0.30 * (1.0 - ep / training_episodes))

            while not env.is_done():
                action = scheduler.choose_action(state)
                next_state, reward, done, _ = env.step(action)
                scheduler.update_policy(state, action, reward, next_state)
                state = next_state

        # Save benchmark candidate policy
        scheduler._save_policy()

        # 2. Evaluation Phase (Exploitation mode: exploration_rate = 0.0)
        start_eval_time = time.perf_counter()
        scheduler.exploration_rate = 0.0
        all_eval_rewards: List[float] = []
        violations = 0
        completed = 0
        total_eval_tasks = len(tasks) * len(eval_seeds) * eval_episodes
        total_collisions = 0
        total_duplicate_starts = 0
        total_slot_overflows = 0
        total_interval_overlaps = 0
        total_deadline_violations = 0
        total_invalid_assignments = 0
        total_tasks_outside_horizon = 0

        for seed in eval_seeds:
            for ep_idx in range(eval_episodes):
                env = RLSchedulingBenchmarkEnvironment(
                    tasks, behavior_patterns, available_hours=available_hours, seed=seed * 100 + ep_idx
                )
                state = env.reset()
                ep_reward = 0.0
                used_hours: set[int] = set()

                while not env.is_done():
                    task = env.raw_tasks[env.current_task_index]
                    dur_unit = task.get("estimated_duration_unit", "hours")
                    dur_src = task.get("estimated_duration_source", "benchmark")
                    dur_hours = normalize_duration(task.get("estimated_duration", 1.0), dur_unit, dur_src).normalized_hours
                    span = max(1, math.ceil(dur_hours - 1e-6))

                    preferred_hour = scheduler.choose_action(state)
                    # Use production collision avoidance rule from RLScheduler.optimize_schedule
                    action = scheduler._pick_available_hour(preferred_hour, used_hours, duration_hours=dur_hours)
                    for off in range(span):
                        used_hours.add(action + off)

                    next_state, r, _, info = env.step(action)
                    ep_reward += r
                    if not info["on_time"] or info["collision"]:
                        violations += 1
                    completed += 1
                    state = next_state
                all_eval_rewards.append(ep_reward)
                total_collisions += env.collisions
                total_duplicate_starts += env.duplicate_start_times
                total_slot_overflows += env.slot_capacity_overflows
                total_interval_overlaps += env.overlapping_task_intervals
                total_deadline_violations += env.deadline_violations
                total_invalid_assignments += env.invalid_task_assignments
                total_tasks_outside_horizon += env.tasks_outside_horizon

        elapsed_eval_ms = (time.perf_counter() - start_eval_time) * 1000.0
        mean_runtime_ms = round(elapsed_eval_ms / max(1, len(all_eval_rewards)), 2)
        completion_rate = 100.0 * (completed / total_eval_tasks)
        adherence_rate = max(0.0, 100.0 * (1.0 - (violations / total_eval_tasks)))
        learned_states = len(scheduler.q_table)

        metrics = PolicyEvaluationMetrics(
            policy_name="Trained_Q_Learning_Policy (with Collision Avoidance)",
            scenario_id=scenario_id,
            episode_count=len(all_eval_rewards),
            mean_reward=float(np.mean(all_eval_rewards)),
            std_reward=float(np.std(all_eval_rewards)),
            task_completion_rate_pct=completion_rate,
            deadline_adherence_rate_pct=adherence_rate,
            collision_count=total_collisions,
            states_learned=learned_states,
            seeds_evaluated=eval_seeds,
            duplicate_start_times=total_duplicate_starts,
            slot_capacity_overflows=total_slot_overflows,
            overlapping_task_intervals=total_interval_overlaps,
            deadline_violations=total_deadline_violations,
            invalid_task_assignments=total_invalid_assignments,
            tasks_outside_horizon=total_tasks_outside_horizon,
            unscheduled_tasks=0,
            total_tasks_scheduled=completed,
            is_mathematically_feasible=feasible_flag,
            total_task_hours_demanded=total_demanded_hours,
            available_horizon_hours=horizon_hours,
            mean_runtime_ms=mean_runtime_ms,
        )

        return metrics, scheduler

