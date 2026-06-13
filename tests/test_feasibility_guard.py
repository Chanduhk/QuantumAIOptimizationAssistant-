"""Unit tests for Minimum Active Task Guarantee (MATG) in soft-freeze mode."""

from datetime import datetime, timedelta
import unittest

from day_model import Day
from forecast import MultiDayForecaster
from models import EnergyProfile, Task
from scheduler import Scheduler
from strategic_compression import ensure_feasible_task_set, MIN_ACTIVE_TASKS, MIN_ACTIVE_DURATION


class TestFeasibilityGuard(unittest.TestCase):
    """Validate MATG behavior under deadlock-prone deferral states."""

    def test_guard_reactivates_deferred_tasks_when_active_set_is_empty(self):
        """If all tasks are deferred, guard must reactivate enough tasks for feasibility."""
        now = datetime.now()
        tasks = [
            Task("Low", 1.0, 2, now + timedelta(days=1)),
            Task("Mid", 1.0, 5, now + timedelta(days=1)),
            Task("High", 1.0, 9, now + timedelta(days=1)),
        ]

        for task in tasks:
            task.deferred = True

        active_tasks, reactivated_count = ensure_feasible_task_set(tasks, capacity_per_day=8.0)
        active_duration = sum(t.duration for t in active_tasks)

        self.assertGreaterEqual(len(active_tasks), MIN_ACTIVE_TASKS)
        self.assertGreaterEqual(active_duration, MIN_ACTIVE_DURATION)
        self.assertGreater(active_duration, 0.0)
        self.assertGreaterEqual(reactivated_count, 1)

    def test_no_empty_candidate_set_possible(self):
        """Guard should always return a non-empty feasible set when capacity allows."""
        now = datetime.now()
        tasks = [
            Task("Task A", 2.0, 4, now + timedelta(days=1)),
            Task("Task B", 2.0, 6, now + timedelta(days=1)),
            Task("Task C", 2.0, 8, now + timedelta(days=1)),
            Task("Task D", 2.0, 9, now + timedelta(days=1)),
        ]

        for task in tasks:
            task.deferred = True

        active_tasks, reactivated_count = ensure_feasible_task_set(tasks, capacity_per_day=8.0)
        active_duration = sum(t.duration for t in active_tasks)

        self.assertGreater(reactivated_count, 0)
        self.assertGreaterEqual(len(active_tasks), MIN_ACTIVE_TASKS)
        self.assertGreaterEqual(active_duration, MIN_ACTIVE_DURATION)

    def test_system_stabilizes_over_five_day_simulation(self):
        """Five-day simulation should remain feasible and produce a positive score."""
        now = datetime.now()
        day = Day(available_hours=8, sleep_hours=7)
        tasks = [
            Task("Deadlocked 1", 2.0, 4, now + timedelta(days=1)),
            Task("Deadlocked 2", 2.0, 6, now + timedelta(days=1)),
            Task("Deadlocked 3", 2.0, 8, now + timedelta(days=2)),
            Task("Deadlocked 4", 2.0, 7, now + timedelta(days=2)),
            Task("Deadlocked 5", 2.0, 5, now + timedelta(days=3)),
        ]

        # Simulate a deadlock-prone start: all tasks begin deferred.
        for task in tasks:
            task.deferred = True
            task.freeze_penalty_factor = 0.4
            day.add_task(task)

        scheduler = Scheduler(day, EnergyProfile())
        forecaster = MultiDayForecaster(day, scheduler, days=5)
        score = forecaster.simulate()

        self.assertGreater(score, 0.0)
        self.assertTrue(all(not hasattr(task, "frozen") for task in day.tasks))


if __name__ == "__main__":
    unittest.main()
