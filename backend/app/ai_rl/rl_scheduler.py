from __future__ import annotations

from backend.app.domain.optimization_input_contract import normalize_duration

import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional


class RLScheduler:
    """Q-learning scheduler that learns which hour slot best fits a task."""

    def __init__(
        self,
        policy_path: Optional[str] = None,
        learning_rate: float = 0.2,
        discount_factor: float = 0.85,
        exploration_rate: float = 0.1,
        available_actions: Optional[List[int]] = None,
    ) -> None:
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.policy_path = Path(
            policy_path
            or Path(__file__).resolve().parents[2] / "artifacts" / "rl_scheduler_policy.json"
        )
        self.available_actions = (
            sorted(list(available_actions))
            if available_actions is not None
            else [hour for hour in range(6, 23)]
        )
        self.q_table: Dict[str, Dict[str, float]] = {}
        self.readiness_status = "NOT_READY_INSUFFICIENT_EPISODES"
        self._load_policy()

    def train_agent(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        episodes: int = 25,
    ) -> Dict[str, Any]:
        """Train the Q-table over repeated scheduling episodes."""
        if not tasks:
            raise ValueError("At least one task is required to train the RL scheduler.")

        rewards: List[float] = []
        for _ in range(episodes):
            episode_reward = 0.0
            for task in tasks:
                state = self._build_state(task, behavior_patterns)
                action = self.choose_action(state)
                reward = self._calculate_reward(task, action, behavior_patterns)
                next_state = self._build_state(
                    {
                        **task,
                        "scheduled_hour": action,
                    },
                    behavior_patterns,
                )
                self.update_policy(state, action, reward, next_state)
                episode_reward += reward
            rewards.append(round(episode_reward, 2))

        self._save_policy()
        return {
            "episodes": episodes,
            "average_reward": round(sum(rewards) / len(rewards), 2),
            "final_reward": rewards[-1],
            "states_learned": len(self.q_table),
        }

    def choose_action(self, state: Dict[str, Any]) -> int:
        """Choose an hour slot using epsilon-greedy action selection."""
        state_key = self._serialize_state(state)
        self.q_table.setdefault(state_key, {str(action): 0.0 for action in self.available_actions})

        if random.random() < self.exploration_rate:
            return random.choice(self.available_actions)

        state_actions = self.q_table[state_key]
        return int(max(state_actions, key=state_actions.get))

    def update_policy(
        self,
        state: Dict[str, Any],
        action: int,
        reward: float,
        next_state: Dict[str, Any],
    ) -> None:
        """Update the Q-table using the Q-learning rule."""
        state_key = self._serialize_state(state)
        next_state_key = self._serialize_state(next_state)

        self.q_table.setdefault(state_key, {str(candidate): 0.0 for candidate in self.available_actions})
        self.q_table.setdefault(
            next_state_key,
            {str(candidate): 0.0 for candidate in self.available_actions},
        )

        current_q = self.q_table[state_key][str(action)]
        max_future_q = max(self.q_table[next_state_key].values())
        updated_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_future_q - current_q
        )
        self.q_table[state_key][str(action)] = round(updated_q, 4)

    def optimize_schedule(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        train_before_optimize: bool = False,
    ) -> Dict[str, Any]:
        """Assign tasks to learned time slots and return a productivity-weighted schedule."""
        if train_before_optimize:
            self.train_agent(tasks, behavior_patterns)

        optimized_schedule: List[Dict[str, Any]] = []
        used_hours: set[int] = set()

        for task in tasks:
            if task.get("estimated_duration") is None:
                raise ValueError("estimated_duration is required for forward scheduling.")
            duration_unit = task.get("estimated_duration_unit")
            duration_source = task.get("estimated_duration_source")
            if duration_unit is None or duration_source is None:
                raise ValueError("explicit estimated duration unit and source are required.")
            duration = normalize_duration(task["estimated_duration"], duration_unit, duration_source).normalized_hours

            state = self._build_state(task, behavior_patterns)
            preferred_hour = self.choose_action(state)
            selected_hour = self._pick_available_hour(preferred_hour, used_hours, duration_hours=duration)

            span_slots = max(1, math.ceil(duration - 1e-6))
            for offset in range(span_slots):
                used_hours.add(selected_hour + offset)

            task_copy = dict(task)
            task_copy["rl_scheduled_hour"] = selected_hour
            task_copy["rl_scheduled_end_hour"] = round(selected_hour + duration, 2)
            task_copy["rl_reward_estimate"] = round(
                self._calculate_reward(task_copy, selected_hour, behavior_patterns),
                2,
            )
            optimized_schedule.append(task_copy)

        optimized_schedule.sort(key=lambda item: float(item["rl_scheduled_hour"]))
        self._save_policy()
        return {
            "optimized_schedule": optimized_schedule,
            "policy_states": len(self.q_table),
        }

    def _build_state(self, task: Dict[str, Any], behavior_patterns: Dict[str, Any]) -> Dict[str, Any]:
        hour = int(task.get("prediction_hour") or task.get("scheduled_hour") or task.get("hour_of_day") or 10)
        productivity = float(task.get("predicted_productivity") or behavior_patterns.get("average_productivity", 50.0))
        priority = int(task.get("priority") or 3)
        task_type = str(task.get("task_type", "general")).strip().lower() or "general"
        energy = self._estimate_energy_level(hour, behavior_patterns)

        return {
            "hour_bucket": min(hour // 3, 7),
            "productivity_bucket": min(int(productivity // 20), 5),
            "priority": max(1, min(priority, 5)),
            "task_type": task_type,
            "energy_bucket": min(int(energy // 20), 5),
        }

    def _calculate_reward(
        self,
        task: Dict[str, Any],
        action_hour: int,
        behavior_patterns: Dict[str, Any],
    ) -> float:
        predicted_productivity = float(task.get("predicted_productivity") or behavior_patterns.get("average_productivity", 50.0))
        priority = float(task.get("priority") or 3.0)
        best_focus_hours = {int(hour) for hour in behavior_patterns.get("best_focus_hours", [])}
        preferred_task_types = {
            str(task_type).lower() for task_type in behavior_patterns.get("preferred_task_types", [])
        }
        hourly_productivity = {
            int(hour): float(score) for hour, score in behavior_patterns.get("hourly_productivity", {}).items()
        }

        reward = predicted_productivity * 0.6
        reward += priority * 8.0
        reward += hourly_productivity.get(action_hour, 0.0) * 0.3
        reward += 10.0 if action_hour in best_focus_hours else 0.0
        reward += (
            6.0
            if str(task.get("task_type", "")).lower() in preferred_task_types
            else 0.0
        )
        reward += self._estimate_energy_level(action_hour, behavior_patterns) * 0.1
        return reward

    def _estimate_energy_level(self, hour: int, behavior_patterns: Dict[str, Any]) -> float:
        best_focus_hours = [int(item) for item in behavior_patterns.get("best_focus_hours", [])]
        if best_focus_hours:
            distance = min(abs(hour - focus_hour) for focus_hour in best_focus_hours)
            return max(20.0, 100.0 - (distance * 12.0))
        return float(behavior_patterns.get("average_energy_level", 60.0))

    def _pick_available_hour(
        self,
        preferred_hour: int,
        used_hours: set[int],
        duration_hours: float = 1.0,
    ) -> int:
        span_slots = max(1, math.ceil(duration_hours - 1e-6))
        max_horizon = max(self.available_actions) + 1 if self.available_actions else 23

        def _is_span_available(start: int) -> bool:
            if start not in self.available_actions:
                return False
            if start + duration_hours > max_horizon:
                return False
            return all((start + offset) not in used_hours for offset in range(span_slots))

        if _is_span_available(preferred_hour):
            return preferred_hour

        for candidate in self.available_actions:
            if _is_span_available(candidate):
                return candidate
        return preferred_hour

    def _serialize_state(self, state: Dict[str, Any]) -> str:
        return "|".join(
            [
                str(state["hour_bucket"]),
                str(state["productivity_bucket"]),
                str(state["priority"]),
                str(state["task_type"]),
                str(state["energy_bucket"]),
            ]
        )

    def _load_policy(self) -> None:
        loaded = False
        if self.policy_path.exists():
            try:
                data = json.loads(self.policy_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.q_table = data
                    if any(any(v != 0.0 for v in actions.values()) for actions in self.q_table.values() if isinstance(actions, dict)):
                        loaded = True
                        self.readiness_status = "TRAINED"
            except Exception:
                pass

        if not loaded:
            benchmark_candidate = self.policy_path.parent / "rl_scheduler_benchmark_candidate.json"
            if benchmark_candidate.exists():
                try:
                    data = json.loads(benchmark_candidate.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and any(any(v != 0.0 for v in actions.values()) for actions in data.values() if isinstance(actions, dict)):
                        self.q_table = data
                        self.readiness_status = "TRAINED"
                        loaded = True
                except Exception:
                    pass

    def _save_policy(self) -> None:
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)
        self.policy_path.write_text(json.dumps(self.q_table, indent=2), encoding="utf-8")
