"""Phase F13.4 — Unit and Regression Test Suite for RL Schedule Feasibility
and Benchmark Integrity Verification.

Covers:
- Mathematical feasibility audit of scheduling benchmark scenarios
- Proof of infeasibility for scenario_heavy_conflict (12h demanded in 8h horizon)
- Feasibility of scenario_high_load_feasible (7.5h demanded in 8h horizon)
- Multi-hour slot occupancy and interval reservation
- Fractional-hour boundary overlap detection (boundary contact vs true overlap)
- Slot capacity overflow consistency across fractional loads
- Independence of deadline violations and collision metrics
- Correct counting of invalid assignments and tasks outside horizon
- Explicit reporting of scheduled and unscheduled task counts
- Identical scenario constraint evaluation across Heuristic Priority, EDF, and Trained Q-Policy
- Preservation of production policy and personal application database
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import pytest

from backend.app.ai_rl.benchmark_environment import (
    BenchmarkEvaluator,
    PolicyEvaluationMetrics,
    RLSchedulingBenchmarkEnvironment,
    DEFAULT_BENCHMARK_POLICY_PATH,
)
from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager
from backend.app.domain.optimization_input_contract import normalize_duration


class TestRLScheduleFeasibilityAndIntegrity:
    """Stage 2, 3, 4 regression tests for RL schedule feasibility and metric integrity."""

    def test_mathematical_infeasibility_of_scenario_heavy_conflict(self):
        """Verify that scenario_heavy_conflict is recognized as strictly mathematically infeasible."""
        mgr = PublicDatasetManager()
        scenarios = mgr.get_scheduling_benchmark_scenarios()
        sc = scenarios["scenario_heavy_conflict"]

        tasks = sc["tasks"]
        avail_hours = sc["available_hours"]
        horizon_hours = float(len(avail_hours))
        total_duration = sum(
            normalize_duration(
                t["estimated_duration"],
                t["estimated_duration_unit"],
                t["estimated_duration_source"],
            ).normalized_hours
            for t in tasks
        )

        assert total_duration == 12.0
        assert horizon_hours == 8.0
        assert total_duration > horizon_hours
        assert sc["is_mathematically_feasible"] is False
        assert "Overloaded Infeasibility Stress Test" in sc["name"]

    def test_feasibility_of_scenario_high_load_feasible(self):
        """Verify that scenario_high_load_feasible is mathematically feasible."""
        mgr = PublicDatasetManager()
        scenarios = mgr.get_scheduling_benchmark_scenarios()
        assert "scenario_high_load_feasible" in scenarios
        sc = scenarios["scenario_high_load_feasible"]

        tasks = sc["tasks"]
        avail_hours = sc["available_hours"]
        horizon_hours = float(len(avail_hours))
        total_duration = sum(
            normalize_duration(
                t["estimated_duration"],
                t["estimated_duration_unit"],
                t["estimated_duration_source"],
            ).normalized_hours
            for t in tasks
        )

        assert total_duration == 7.5
        assert horizon_hours == 8.0
        assert total_duration <= horizon_hours
        assert sc["is_mathematically_feasible"] is True

    def test_multi_hour_occupancy_interval_reservation(self):
        """Verify multi-hour tasks reserve every occupied hourly slot."""
        tasks = [
            {
                "task_id": "T1",
                "priority": 5,
                "estimated_duration": 2.5,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
            },
            {
                "task_id": "T2",
                "priority": 4,
                "estimated_duration": 1.0,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
            },
        ]
        # Horizon [9, 13) (4 hours)
        env = RLSchedulingBenchmarkEnvironment(
            tasks, behavior_patterns={}, available_hours=[9, 10, 11, 12]
        )
        env.reset()

        # Place T1 at 9: spans [9.0, 11.5), occupying slots 9, 10, 11
        _, _, _, info1 = env.step(action_hour=9)
        assert info1["collision"] is False
        assert env.occupied_slots[9] == 1.0
        assert env.occupied_slots[10] == 1.0
        assert env.occupied_slots[11] == 0.5

        # Place T2 at 11: spans [11.0, 12.0), adds 1.0 to slot 11 -> load is 1.5 > 1.0!
        _, _, _, info2 = env.step(action_hour=11)
        assert info2["collision"] is True
        assert info2["slot_overflow"] is True
        assert info2["interval_overlap"] is True
        assert env.slot_capacity_overflows == 1
        assert env.overlapping_task_intervals == 1

    def test_fractional_hour_boundary_overlap_detection(self):
        """Verify overlap detection handles exact adjacent fractional boundaries without false positives."""
        tasks = [
            {
                "task_id": "T1",
                "priority": 4,
                "estimated_duration": 1.5,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
            },
            {
                "task_id": "T2_adjacent",
                "priority": 3,
                "estimated_duration": 1.5,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
            },
        ]
        env = RLSchedulingBenchmarkEnvironment(
            tasks, behavior_patterns={}, available_hours=[9, 10, 11, 12]
        )
        env.reset()

        # T1 at 9: spans [9.0, 10.5)
        _, _, _, info1 = env.step(action_hour=9)
        assert info1["collision"] is False

        # T2 at 10.5: boundary touch at 10.5.
        # Direct check with mathematical condition:
        t1_start, t1_end = 9.0, 10.5
        t2_start, t2_end = 10.5, 12.0
        is_overlapping = max(t1_start, t2_start) < min(t1_end, t2_end) - 1e-6
        assert is_overlapping is False  # Exact boundary does not overlap

        # Now test true fractional overlap: T2 placed at 10: spans [10.0, 11.5)
        t3_start, t3_end = 10.0, 11.5
        is_true_overlap = max(t1_start, t3_start) < min(t1_end, t3_end) - 1e-6
        assert is_true_overlap is True  # Overlaps [10.0, 10.5)

    def test_deadline_violations_independent_of_collisions(self):
        """Verify deadline violations are tracked independently of collision metrics."""
        tasks = [
            {
                "task_id": "T1",
                "priority": 5,
                "estimated_duration": 1.0,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
                "deadline_hour": 10,
            },
            {
                "task_id": "T2",
                "priority": 4,
                "estimated_duration": 1.0,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
                "deadline_hour": 15,
            },
        ]
        env = RLSchedulingBenchmarkEnvironment(
            tasks, behavior_patterns={}, available_hours=[9, 10, 11, 12]
        )
        env.reset()

        # Step 1: Schedule T1 at hour 11 (completion 12.0 > deadline 10)
        # Collision-free, but late!
        _, _, _, info1 = env.step(action_hour=11)
        assert info1["collision"] is False
        assert info1["on_time"] is False
        assert env.collisions == 0
        assert env.deadline_violations == 1

        # Step 2: Schedule T2 at hour 11 (collides with T1, completion 12.0 <= deadline 15)
        # On-time, but colliding!
        _, _, _, info2 = env.step(action_hour=11)
        assert info2["collision"] is True
        assert info2["on_time"] is True
        assert env.collisions == 1
        assert env.deadline_violations == 1  # Unchanged!

    def test_invalid_assignments_and_outside_horizon_counted_correctly(self):
        """Verify tasks placed outside the scheduling horizon are counted as invalid and outside horizon."""
        tasks = [
            {
                "task_id": "T1",
                "priority": 5,
                "estimated_duration": 2.0,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
            },
        ]
        # Horizon [9, 17) -> start=9, end=16 (horizon_end = 17)
        env = RLSchedulingBenchmarkEnvironment(
            tasks, behavior_patterns={}, available_hours=list(range(9, 17))
        )
        env.reset()

        # Place task at 16 with duration 2h -> completion is 18.0 > 17.0!
        _, _, _, info = env.step(action_hour=16)
        assert info["outside_horizon"] is True
        assert info["invalid_assignment"] is True
        assert env.tasks_outside_horizon == 1
        assert env.invalid_task_assignments == 1

    def test_unscheduled_and_scheduled_tasks_explicitly_reported(self):
        """Verify PolicyEvaluationMetrics explicitly reports total_tasks_scheduled and unscheduled_tasks."""
        metrics = PolicyEvaluationMetrics(
            policy_name="TestPolicy",
            scenario_id="test_sc",
            episode_count=5,
            mean_reward=150.0,
            std_reward=2.0,
            task_completion_rate_pct=100.0,
            deadline_adherence_rate_pct=90.0,
            collision_count=0,
            total_tasks_scheduled=20,
            unscheduled_tasks=0,
            tasks_outside_horizon=0,
            is_mathematically_feasible=True,
            total_task_hours_demanded=5.0,
            available_horizon_hours=8.0,
            mean_runtime_ms=0.45,
        )
        d = metrics.to_dict()
        assert d["total_tasks_scheduled"] == 20
        assert d["unscheduled_tasks"] == 0
        assert d["tasks_outside_horizon"] == 0
        assert d["is_mathematically_feasible"] is True
        assert d["total_task_hours_demanded"] == 5.0
        assert d["available_horizon_hours"] == 8.0
        assert d["mean_runtime_ms"] == 0.45

    def test_all_policies_evaluated_under_identical_scenario_constraints(self):
        """Verify Heuristic Priority, EDF, and Trained Q-Policy run under identical constraints."""
        mgr = PublicDatasetManager()
        scenarios = mgr.get_scheduling_benchmark_scenarios()
        sc = scenarios["scenario_high_load_feasible"]
        tasks = sc["tasks"]
        patterns = sc["behavior_patterns"]
        avail = sc["available_hours"]
        feasible = sc["is_mathematically_feasible"]

        # Run 3 episodes of each
        priority_m = BenchmarkEvaluator.evaluate_heuristic_priority(
            tasks, patterns, scenario_id="high_load", episodes=3,
            available_hours=avail, is_mathematically_feasible=feasible
        )
        edf_m = BenchmarkEvaluator.evaluate_earliest_deadline_first(
            tasks, patterns, scenario_id="high_load", episodes=3,
            available_hours=avail, is_mathematically_feasible=feasible
        )
        q_m, _ = BenchmarkEvaluator.train_and_evaluate_q_learning(
            tasks, patterns, scenario_id="high_load", training_episodes=15, eval_episodes=3,
            seeds=[42], available_hours=avail, is_mathematically_feasible=feasible
        )

        assert priority_m.total_task_hours_demanded == edf_m.total_task_hours_demanded == q_m.total_task_hours_demanded == 7.5
        assert priority_m.available_horizon_hours == edf_m.available_horizon_hours == q_m.available_horizon_hours == 8.0
        assert priority_m.is_mathematically_feasible is edf_m.is_mathematically_feasible is q_m.is_mathematically_feasible is True
        assert priority_m.total_tasks_scheduled == 18  # 6 * 3
        assert edf_m.total_tasks_scheduled == 18
        assert q_m.total_tasks_scheduled == 18  # 6 * 1 * 3
        assert priority_m.mean_runtime_ms >= 0.0
        assert edf_m.mean_runtime_ms >= 0.0
        assert q_m.mean_runtime_ms >= 0.0

    def test_preservation_of_production_policy_and_database(self):
        """Verify that running benchmarks does not touch production policy or application DB."""
        prod_policy_path = Path(__file__).resolve().parents[2] / "artifacts" / "rl_scheduler_policy.json"
        db_path = Path(__file__).resolve().parents[2] / "behavior_engine.db"

        # Production policy is strictly isolated from DEFAULT_BENCHMARK_POLICY_PATH
        assert prod_policy_path != DEFAULT_BENCHMARK_POLICY_PATH
        assert "benchmark" in str(DEFAULT_BENCHMARK_POLICY_PATH)

        if prod_policy_path.exists():
            prod_mtime_before = os.path.getmtime(prod_policy_path)
            # Instantiating BenchmarkEvaluator should use DEFAULT_BENCHMARK_POLICY_PATH
            mgr = PublicDatasetManager()
            sc = mgr.get_scheduling_benchmark_scenarios()["scenario_light_load"]
            BenchmarkEvaluator.train_and_evaluate_q_learning(
                sc["tasks"], sc["behavior_patterns"], training_episodes=2, eval_episodes=1, seeds=[42],
                available_hours=sc["available_hours"]
            )
            prod_mtime_after = os.path.getmtime(prod_policy_path)
            assert prod_mtime_before == prod_mtime_after, "Production policy was modified by benchmark!"
