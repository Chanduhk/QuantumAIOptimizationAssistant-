"""Unit tests for urgency decay and soft-freeze compression behavior."""

from datetime import datetime, timedelta
import unittest

from models import Task
from strategic_compression import (
    apply_strategic_compression,
    update_penalty_recovery,
    compute_adaptive_recovery,
)
from forecast import compute_effective_terminal_risk_weight


class TestUrgencyDecayAntiStarvation(unittest.TestCase):
    """Validate urgency-decay growth and soft-freeze penalty mechanics."""

    def test_effective_priority_increases_after_each_defer(self):
        """Urgency boost should increase linearly with each deferred day."""
        now = datetime.now()
        task = Task("Deferred Growth", 2.0, 5.0, now + timedelta(days=2), urgency_decay_k=0.1)

        # Baseline effective priority before deferral growth.
        self.assertEqual(task.effective_priority(), 5.0)

        # Simulate three deferred days.
        task.increment_deferred_day()
        self.assertEqual(task.effective_priority(), 5.1)
        task.increment_deferred_day()
        self.assertEqual(task.effective_priority(), 5.2)
        task.increment_deferred_day()
        self.assertEqual(task.effective_priority(), 5.3)

    def test_soft_freeze_uses_penalty_without_frozen_flag(self):
        """Compression should apply penalty factors and avoid boolean frozen state."""
        now = datetime.now()
        tasks = [
            Task("High A", 2.0, 9.0, now + timedelta(days=1)),
            Task("High B", 2.0, 8.0, now + timedelta(days=1)),
            Task("High C", 2.0, 7.0, now + timedelta(days=1)),
            Task("High D", 2.0, 6.0, now + timedelta(days=1)),
            Task("High E", 2.0, 5.0, now + timedelta(days=1)),
        ]

        # Force overload so compression mode activates.
        activated = apply_strategic_compression(
            tasks=tasks,
            capacity_per_day=8.0,
            planning_horizon=1,
            compression_threshold=1.2,
        )

        self.assertTrue(activated)
        self.assertTrue(all(not hasattr(task, "frozen") for task in tasks))
        penalized = [t for t in tasks if t.freeze_penalty_factor < 1.0]
        self.assertGreaterEqual(len(penalized), 1)
        self.assertTrue(all(abs(t.freeze_penalty_factor - 0.4) < 1e-9 for t in penalized))

    def test_diversity_enforced_adds_short_when_missing(self):
        """Diversity should add a short task when provisional protected set is all long."""
        now = datetime.now()
        tasks = [
            Task("Long A", 4.0, 10, now + timedelta(days=1)),
            Task("Long B", 3.0, 9, now + timedelta(days=1)),
            Task("Short C", 1.0, 4, now + timedelta(days=1)),
            Task("Filler D", 2.0, 2, now + timedelta(days=1)),
        ]

        activated = apply_strategic_compression(
            tasks=tasks,
            capacity_per_day=8.0,
            planning_horizon=1,
            compression_threshold=1.2,
        )
        self.assertTrue(activated)

        protected = [t for t in tasks if t.freeze_penalty_factor == 1.0]
        protected_total = sum(t.duration for t in protected)
        self.assertTrue(any(t.duration <= 2.0 for t in protected))
        self.assertTrue(any(t.duration >= 2.0 for t in protected))
        self.assertLessEqual(protected_total, 7.2)

    def test_diversity_enforced_adds_long_when_missing(self):
        """Diversity should add a long task when provisional protected set is all short."""
        now = datetime.now()
        tasks = [
            Task("Short A", 1.5, 9, now + timedelta(days=1)),
            Task("Short B", 1.5, 8, now + timedelta(days=1)),
            Task("Short C", 1.5, 7, now + timedelta(days=1)),
            Task("Short D", 1.5, 6, now + timedelta(days=1)),
            Task("Short E", 1.5, 5, now + timedelta(days=1)),
            Task("Long F", 2.5, 3, now + timedelta(days=1)),
        ]

        activated = apply_strategic_compression(
            tasks=tasks,
            capacity_per_day=8.0,
            planning_horizon=1,
            compression_threshold=1.2,
        )
        self.assertTrue(activated)

        protected = [t for t in tasks if t.freeze_penalty_factor == 1.0]
        protected_total = sum(t.duration for t in protected)
        self.assertTrue(any(t.duration <= 2.0 for t in protected))
        self.assertTrue(any(t.duration >= 2.0 for t in protected))
        self.assertLessEqual(protected_total, 7.2)

    def test_diversity_replacement_reverts_on_capacity_violation(self):
        """If diversity replacement exceeds hard limit, original protected set should remain."""
        now = datetime.now()
        tasks = [
            Task("Short A", 1.5, 9, now + timedelta(days=1)),
            Task("Short B", 1.5, 8, now + timedelta(days=1)),
            Task("Short C", 1.5, 7, now + timedelta(days=1)),
            Task("Short D", 1.5, 6, now + timedelta(days=1)),
            Task("Tiny E", 1.0, 1, now + timedelta(days=1)),
            Task("Long F", 3.5, 3, now + timedelta(days=1)),
        ]

        activated = apply_strategic_compression(
            tasks=tasks,
            capacity_per_day=8.0,
            planning_horizon=1,
            compression_threshold=1.2,
        )
        self.assertTrue(activated)

        protected = [t for t in tasks if t.freeze_penalty_factor == 1.0]
        self.assertTrue(all(t.duration < 2.0 for t in protected))
        self.assertFalse(any(t.duration >= 2.0 for t in protected))

    def test_diversity_no_candidate_keeps_original(self):
        """If no missing-category candidate exists, provisional protected set remains."""
        now = datetime.now()
        tasks = [
            Task("Long A", 4.0, 10, now + timedelta(days=1)),
            Task("Long B", 3.0, 9, now + timedelta(days=1)),
            Task("Long C", 2.5, 8, now + timedelta(days=1)),
            Task("Long D", 2.1, 7, now + timedelta(days=1)),
        ]

        activated = apply_strategic_compression(
            tasks=tasks,
            capacity_per_day=8.0,
            planning_horizon=1,
            compression_threshold=1.2,
        )
        self.assertTrue(activated)

        protected = [t for t in tasks if t.freeze_penalty_factor == 1.0]
        self.assertTrue(all(t.duration > 2.0 for t in protected))

    def test_duration_two_satisfies_both_categories(self):
        """A 2.0h protected task should satisfy both diversity categories."""
        now = datetime.now()
        tasks = [
            Task("Bridge Two Hours", 2.0, 10, now + timedelta(days=1)),
            Task("Long A", 4.0, 9, now + timedelta(days=1)),
            Task("Long B", 3.0, 8, now + timedelta(days=1)),
            Task("Small C", 1.0, 1, now + timedelta(days=1)),
        ]

        activated = apply_strategic_compression(
            tasks=tasks,
            capacity_per_day=8.0,
            planning_horizon=1,
            compression_threshold=1.2,
        )
        self.assertTrue(activated)

        protected = [t for t in tasks if t.freeze_penalty_factor == 1.0]
        self.assertTrue(any(abs(t.duration - 2.0) < 1e-9 for t in protected))
        self.assertTrue(any(t.duration <= 2.0 for t in protected))
        self.assertTrue(any(t.duration >= 2.0 for t in protected))

    def test_replace_any_protected_policy_applied(self):
        """Replace-any policy should allow replacing anti-starvation-selected protected task."""
        now = datetime.now()
        starved_long = Task("Starved Long", 3.0, 4, now + timedelta(days=1))
        starved_long.days_deferred = 10
        dominant_long = Task("Dominant Long", 4.0, 10, now + timedelta(days=1))
        short_candidate = Task("Short Candidate", 1.0, 2, now + timedelta(days=1))
        filler = Task("Filler", 2.0, 1, now + timedelta(days=1))
        tasks = [starved_long, dominant_long, short_candidate, filler]

        activated = apply_strategic_compression(
            tasks=tasks,
            capacity_per_day=8.0,
            planning_horizon=1,
            compression_threshold=1.2,
            anti_starvation_days=5,
        )
        self.assertTrue(activated)

        self.assertLess(starved_long.freeze_penalty_factor, 1.0)
        self.assertEqual(short_candidate.freeze_penalty_factor, 1.0)

    def test_penalty_recovery_reaches_one(self):
        """Adaptive recovery should smoothly converge and remain capped at 1.0."""
        now = datetime.now()
        task = Task("Recovering Task", 2.0, 5.0, now + timedelta(days=1))
        task.freeze_penalty_factor = 0.4

        for _ in range(30):
            update_penalty_recovery([task], overload_index=0.8)

        self.assertLessEqual(task.freeze_penalty_factor, 0.01)
        self.assertGreaterEqual(task.freeze_penalty_factor, 0.0)

    def test_critical_recovery_case_a_overload_one_point_two_five_is_slower(self):
        """Case A: overload 1.25 should be slower."""
        now = datetime.now()
        task = Task("Overload A", 2.0, 5.0, now + timedelta(days=1))
        task.freeze_penalty_factor = 0.4

        before = task.freeze_penalty_factor
        update_penalty_recovery([task], overload_index=1.25)
        step = task.freeze_penalty_factor - before

        recovery_base = min(0.30, max(0.10, 0.20 + 0.10 * (1.0 - 1.25)))
        expected = -recovery_base * (1.0 / 1.25) * (1.0 - 0.4)
        self.assertAlmostEqual(step, expected, places=6)

    def test_critical_recovery_case_b_overload_one_is_moderate(self):
        """Case B: overload 1.0 should be moderate."""
        now = datetime.now()
        task = Task("Overload B", 2.0, 5.0, now + timedelta(days=1))
        task.freeze_penalty_factor = 0.4

        before = task.freeze_penalty_factor
        update_penalty_recovery([task], overload_index=1.0)
        step = task.freeze_penalty_factor - before

        recovery_base = min(0.30, max(0.10, 0.20 + 0.10 * (1.0 - 1.0)))
        expected = -recovery_base * (1.0 / 1.0) * (1.0 - 0.4)
        self.assertAlmostEqual(step, expected, places=6)
        self.assertLessEqual(step, 0.0)

    def test_critical_recovery_case_c_overload_zero_point_eight_is_faster(self):
        """Case C: overload 0.8 should be faster."""
        now = datetime.now()
        task = Task("Overload C", 2.0, 5.0, now + timedelta(days=1))
        task.freeze_penalty_factor = 0.4

        before = task.freeze_penalty_factor
        update_penalty_recovery([task], overload_index=0.8)
        step = task.freeze_penalty_factor - before

        recovery_base = min(0.30, max(0.10, 0.20 + 0.10 * (1.0 - 0.8)))
        expected = -recovery_base * (1.0 / 0.8) * (1.0 - 0.4)
        self.assertAlmostEqual(step, expected, places=6)
        self.assertLess(step, -0.12)

    def test_overload_ordering_one_point_two_five_one_zero_zero_point_eight(self):
        """Recovery should be slower -> moderate -> faster across overload cases."""
        now = datetime.now()
        task_slow = Task("Slow", 2.0, 5.0, now + timedelta(days=1))
        task_mid = Task("Mid", 2.0, 5.0, now + timedelta(days=1))
        task_fast = Task("Fast", 2.0, 5.0, now + timedelta(days=1))
        task_slow.freeze_penalty_factor = 0.4
        task_mid.freeze_penalty_factor = 0.4
        task_fast.freeze_penalty_factor = 0.4

        slow_before = task_slow.freeze_penalty_factor
        mid_before = task_mid.freeze_penalty_factor
        fast_before = task_fast.freeze_penalty_factor

        update_penalty_recovery([task_slow], overload_index=1.25)
        update_penalty_recovery([task_mid], overload_index=1.0)
        update_penalty_recovery([task_fast], overload_index=0.8)

        slow_step = task_slow.freeze_penalty_factor - slow_before
        mid_step = task_mid.freeze_penalty_factor - mid_before
        fast_step = task_fast.freeze_penalty_factor - fast_before

        self.assertGreater(slow_step, mid_step)
        self.assertGreater(mid_step, fast_step)

    def test_backlog_diversification_limits_duration_below_point_eight(self):
        """When overload < 0.8, recovery selection should obey duration cap."""
        now = datetime.now()
        tasks = [
            Task("A", 2.0, 9, now + timedelta(days=1)),
            Task("B", 1.0, 9, now + timedelta(days=1)),
            Task("C", 1.0, 8, now + timedelta(days=1)),
            Task("D", 1.0, 7, now + timedelta(days=1)),
            Task("E", 1.0, 6, now + timedelta(days=1)),
        ]

        for task in tasks:
            task.freeze_penalty_factor = 0.4

        update_penalty_recovery(tasks, overload_index=0.7, daily_capacity=8.0)

        recovered = [t.name for t in tasks if t.freeze_penalty_factor < 0.4]
        not_recovered = [t.name for t in tasks if t.freeze_penalty_factor == 0.4]

        # Duration cap = 0.5 * 8h = 4h; adaptive relief caps recovery to top 2.
        self.assertEqual(set(recovered), {"A", "B"})
        self.assertEqual(set(not_recovered), {"C", "D", "E"})

    def test_backlog_throttling_not_applied_at_point_eight_or_higher(self):
        """When overload >= 0.8, recovery should apply to all penalized tasks."""
        now = datetime.now()
        tasks = [
            Task("T1", 2.0, 9, now + timedelta(days=1)),
            Task("T2", 1.0, 8, now + timedelta(days=1)),
            Task("T3", 1.0, 7, now + timedelta(days=1)),
            Task("T4", 1.0, 6, now + timedelta(days=1)),
            Task("T5", 1.0, 5, now + timedelta(days=1)),
        ]

        for task in tasks:
            task.freeze_penalty_factor = 0.4

        update_penalty_recovery(tasks, overload_index=0.8, daily_capacity=8.0)
        self.assertTrue(all(t.freeze_penalty_factor < 0.4 for t in tasks))

    def test_damped_recovery_shrinks_as_penalty_grows(self):
        """Recovery increments should smoothly shrink as penalty approaches 1.0."""
        now = datetime.now()
        task = Task("Smooth Convergence", 2.0, 5.0, now + timedelta(days=1))
        task.freeze_penalty_factor = 0.4

        increments = []
        for _ in range(8):
            before = task.freeze_penalty_factor
            update_penalty_recovery([task], overload_index=0.8)
            increments.append(task.freeze_penalty_factor - before)

        magnitudes = [abs(x) for x in increments]
        self.assertTrue(all(magnitudes[i] >= magnitudes[i + 1] for i in range(len(magnitudes) - 1)))

    def test_penalty_never_decreases_or_exceeds_one(self):
        """Adaptive recovery must be monotonic non-decreasing and capped."""
        now = datetime.now()
        task = Task("Monotonic Penalty", 2.0, 5.0, now + timedelta(days=1))
        task.freeze_penalty_factor = 0.4

        history = [task.freeze_penalty_factor]
        for overload in [1.25, 1.1, 1.0, 0.9, 0.8, 0.7, 0.5]:
            update_penalty_recovery([task], overload_index=overload)
            history.append(task.freeze_penalty_factor)

        self.assertTrue(all(history[i] >= history[i + 1] for i in range(len(history) - 1)))
        self.assertGreaterEqual(task.freeze_penalty_factor, 0.0)

    def test_recovery_is_capped_at_point_thirty(self):
        """Recovery increment must be capped at 0.30."""
        now = datetime.now()
        task = Task("Capped Recovery", 2.0, 5.0, now + timedelta(days=1))
        task.freeze_penalty_factor = 0.4

        before = task.freeze_penalty_factor
        update_penalty_recovery([task], overload_index=0.2, daily_capacity=8.0)
        step = task.freeze_penalty_factor - before
        self.assertAlmostEqual(step, -0.30, places=6)

    def test_recovery_function_never_negative(self):
        """Adaptive recovery helper should never return negative values."""
        self.assertGreaterEqual(compute_adaptive_recovery(1.25, 0.4), 0.0)
        self.assertGreaterEqual(compute_adaptive_recovery(1.0, 0.8), 0.0)
        self.assertGreaterEqual(compute_adaptive_recovery(0.8, 0.95), 0.0)

    def test_terminal_recovery_is_capped_on_final_day(self):
        """Final day should still recover, but with a 0.12 cap."""
        now = datetime.now()
        tasks = [
            Task("Final A", 2.0, 8.0, now + timedelta(days=1)),
            Task("Final B", 1.5, 7.0, now + timedelta(days=1)),
        ]
        for task in tasks:
            task.freeze_penalty_factor = 0.4

        updated = update_penalty_recovery(
            tasks,
            overload_index=0.7,
            daily_capacity=8.0,
            remaining_days=0
        )
        self.assertEqual(updated, 2)
        self.assertTrue(all(abs(t.freeze_penalty_factor - 0.28) < 1e-9 for t in tasks))

    def test_final_day_recovery_selects_at_most_three_tasks(self):
        """Final-day override should recover no more than three tasks."""
        now = datetime.now()
        tasks = [
            Task("F1", 1.0, 6.0, now + timedelta(days=1)),
            Task("F2", 1.0, 6.0, now + timedelta(days=1)),
            Task("F3", 1.0, 6.0, now + timedelta(days=1)),
            Task("F4", 1.0, 6.0, now + timedelta(days=1)),
            Task("F5", 1.0, 6.0, now + timedelta(days=1)),
        ]
        for task in tasks:
            task.freeze_penalty_factor = 0.4

        updated = update_penalty_recovery(
            tasks,
            overload_index=0.7,
            daily_capacity=8.0,
            remaining_days=0
        )
        recovered = [t for t in tasks if t.freeze_penalty_factor < 0.4]
        self.assertEqual(updated, 3)
        self.assertEqual(len(recovered), 3)

    def test_final_day_recovery_filters_long_and_high_penalty_tasks(self):
        """Final-day override should skip long tasks and near-fully recovered tasks."""
        now = datetime.now()
        tasks = [
            Task("Eligible A", 2.0, 6.0, now + timedelta(days=1)),
            Task("Eligible B", 2.5, 6.0, now + timedelta(days=1)),
            Task("Eligible C", 1.5, 6.0, now + timedelta(days=1)),
            Task("Too Long", 3.0, 6.0, now + timedelta(days=1)),
            Task("Too Recovered", 1.0, 6.0, now + timedelta(days=1)),
        ]
        penalties = {
            "Eligible A": 0.4,
            "Eligible B": 0.4,
            "Eligible C": 0.4,
            "Too Long": 0.4,
            "Too Recovered": 0.9,
        }
        for task in tasks:
            task.freeze_penalty_factor = penalties[task.name]

        updated = update_penalty_recovery(
            tasks,
            overload_index=0.7,
            daily_capacity=8.0,
            remaining_days=0
        )
        by_name = {t.name: t for t in tasks}
        self.assertEqual(updated, 3)
        self.assertAlmostEqual(by_name["Eligible A"].freeze_penalty_factor, 0.28, places=6)
        self.assertAlmostEqual(by_name["Eligible B"].freeze_penalty_factor, 0.28, places=6)
        self.assertAlmostEqual(by_name["Eligible C"].freeze_penalty_factor, 0.28, places=6)
        self.assertAlmostEqual(by_name["Too Long"].freeze_penalty_factor, 0.4, places=6)
        self.assertAlmostEqual(by_name["Too Recovered"].freeze_penalty_factor, 0.9, places=6)

    def test_terminal_risk_weight_cap(self):
        """Terminal damping should cap near-horizon risk weight per policy."""
        self.assertAlmostEqual(compute_effective_terminal_risk_weight(0.15, 2), 0.20, places=6)
        self.assertAlmostEqual(compute_effective_terminal_risk_weight(0.2, 1), 0.25, places=6)
        self.assertAlmostEqual(compute_effective_terminal_risk_weight(0.16, 1), 0.24, places=6)
        self.assertAlmostEqual(compute_effective_terminal_risk_weight(0.3, 0), 0.25, places=6)
        self.assertAlmostEqual(compute_effective_terminal_risk_weight(0.12, 0), 0.24, places=6)
        self.assertAlmostEqual(compute_effective_terminal_risk_weight(0.17, 3), 0.17, places=6)


if __name__ == "__main__":
    unittest.main()
