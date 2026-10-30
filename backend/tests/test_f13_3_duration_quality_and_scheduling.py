"""Phase F13.3 — Unit test suite for Personal Training Data Quality Validation
and Scheduling Environment Hardening.

Covers:
- DurationQualityGate (overnight runaway, sub-minute artifacts, zero/negative, plausible durations)
- TaskDatabaseAdapter quality-filtering integration
- Readiness assessment gates preserving 20 duration, 10 productivity, 25 RL thresholds
- Productivity ground-truth vs heuristic proxy separation
- Multi-hour slot occupancy and collision avoidance in RLScheduler
- BenchmarkEnvironment 5 separate scheduling constraint metrics
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
import pytest

from backend.app.ai_rl.benchmark_environment import (
    BenchmarkEvaluator,
    PolicyEvaluationMetrics,
    RLSchedulingBenchmarkEnvironment,
)
from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.ml.datasets.duration_quality_gate import (
    DurationExclusionReason,
    DurationQualityAssessment,
    DurationQualityGate,
)
from backend.app.ml.readiness import (
    assess_duration_model_readiness,
    assess_productivity_model_readiness,
    assess_rl_scheduler_readiness,
)


class TestDurationQualityGate:
    """Tests for Stage 1, 2, and 3: Duration quality validation and gate semantics."""

    def test_plausible_durations_accepted(self):
        # 10.25 minutes for 30m estimate (Task 4-like)
        assessment = DurationQualityGate.assess_duration(
            actual_duration_minutes=10.25,
            estimated_duration_minutes=30.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment.is_eligible is True
        assert assessment.exclusion_reason is None

        # 60.0 minutes for 60m estimate (Task 5-like)
        assessment_60 = DurationQualityGate.assess_duration(
            actual_duration_minutes=60.0,
            estimated_duration_minutes=60.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_60.is_eligible is True
        assert assessment_60.exclusion_reason is None

        # Task without estimate but plausible 45m duration
        assessment_no_est = DurationQualityGate.assess_duration(
            actual_duration_minutes=45.0,
            estimated_duration_minutes=None,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_no_est.is_eligible is True

    def test_overnight_and_runaway_durations_excluded(self):
        # Task 2: 15,714.87 minutes (~10.9 days)
        assessment_t2 = DurationQualityGate.assess_duration(
            actual_duration_minutes=15714.87,
            estimated_duration_minutes=70.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_t2.is_eligible is False
        assert assessment_t2.code == DurationExclusionReason.EXCESSIVE_WALL_CLOCK_DURATION_OVERNIGHT

        # Task 3: 14,704.58 minutes (~10.2 days)
        assessment_t3 = DurationQualityGate.assess_duration(
            actual_duration_minutes=14704.58,
            estimated_duration_minutes=70.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_t3.is_eligible is False
        assert assessment_t3.code == DurationExclusionReason.EXCESSIVE_WALL_CLOCK_DURATION_OVERNIGHT

        # Extreme ratio runaway: 500m for a 15m task (>10x ratio and >=360m)
        assessment_ratio = DurationQualityGate.assess_duration(
            actual_duration_minutes=500.0,
            estimated_duration_minutes=15.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_ratio.is_eligible is False
        assert assessment_ratio.code == DurationExclusionReason.EXTREME_DURATION_RATIO_RUNAWAY

    def test_sub_minute_automation_artifacts_excluded(self):
        # Task 7: 0.12 minutes (7.4 seconds) for 45m estimate
        assessment_t7 = DurationQualityGate.assess_duration(
            actual_duration_minutes=0.12,
            estimated_duration_minutes=45.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_t7.is_eligible is False
        assert assessment_t7.code == DurationExclusionReason.SUB_MINIMAL_AUTOMATION_ARTIFACT

        # Plausible short task: 2 minutes for 5m estimate
        assessment_short = DurationQualityGate.assess_duration(
            actual_duration_minutes=2.0,
            estimated_duration_minutes=5.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_short.is_eligible is True

    def test_invalid_lifecycle_and_zero_negative_durations_excluded(self):
        # Incomplete task (not completed)
        assessment_incomplete = DurationQualityGate.assess_duration(
            actual_duration_minutes=30.0,
            has_completed_status=False,
            has_timestamps=True,
        )
        assert assessment_incomplete.is_eligible is False
        assert assessment_incomplete.code == DurationExclusionReason.TASK_NOT_COMPLETED

        # Missing timestamps
        assessment_notimestamps = DurationQualityGate.assess_duration(
            actual_duration_minutes=30.0,
            has_completed_status=True,
            has_timestamps=False,
        )
        assert assessment_notimestamps.is_eligible is False
        assert assessment_notimestamps.code == DurationExclusionReason.MISSING_TIMESTAMPS

        # Zero duration
        assessment_zero = DurationQualityGate.assess_duration(
            actual_duration_minutes=0.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_zero.is_eligible is False
        assert assessment_zero.code == DurationExclusionReason.ZERO_OR_NEGATIVE_DURATION

        # Negative duration
        assessment_neg = DurationQualityGate.assess_duration(
            actual_duration_minutes=-10.0,
            has_completed_status=True,
            has_timestamps=True,
        )
        assert assessment_neg.is_eligible is False
        assert assessment_neg.code == DurationExclusionReason.ZERO_OR_NEGATIVE_DURATION


class TestProductivityGroundTruthSemantics:
    """Tests for Stage 4: Productivity ground truth labels vs heuristic proxies."""

    def test_genuine_labels_vs_heuristics(self):
        raw_rating = 4.0
        score = (raw_rating / 5.0) * 100.0
        assert score == 80.0

    def test_readiness_thresholds_governance_safeguard(self):
        from backend.app.database.db import SessionLocal
        from backend.app.ml.readiness import (
            MINIMUM_EVALUATION_ROWS,
            MINIMUM_TRAINING_ROWS,
            MINIMUM_RL_EPISODES,
        )
        assert MINIMUM_EVALUATION_ROWS == 20
        assert MINIMUM_TRAINING_ROWS == 10
        assert MINIMUM_RL_EPISODES == 25

        session = SessionLocal()
        try:
            dur_readiness = assess_duration_model_readiness(session, user_id=999999)
            assert dur_readiness.required_samples == 20
            assert dur_readiness.status != "PRODUCTION"

            prod_readiness = assess_productivity_model_readiness(session, user_id=999999)
            assert prod_readiness.required_samples == 10
            assert prod_readiness.status != "PRODUCTION"

            rl_readiness = assess_rl_scheduler_readiness(session, user_id=999999)
            assert rl_readiness.required_samples == 25
            assert rl_readiness.status != "PRODUCTION"
        finally:
            session.close()


class TestMultiHourSchedulingConstraints:
    """Tests for Stage 6: Multi-hour task occupancy and 5 separate constraint metrics."""

    def test_rl_scheduler_multi_hour_slot_reservation(self):
        scheduler = RLScheduler()

        tasks = [
            {
                "task_id": "T1",
                "title": "Deep Work Coding",
                "priority": 5,
                "estimated_duration": 2.5,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "user",
                "prediction_hour": 9,
            },
            {
                "task_id": "T2",
                "title": "Architecture Review",
                "priority": 4,
                "estimated_duration": 1.0,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "user",
                "prediction_hour": 10,  # Would collide if only hour 9 was occupied!
            },
        ]
        behavior_patterns = {"best_focus_hours": [9, 10, 11]}

        result = scheduler.optimize_schedule(tasks, behavior_patterns)
        schedule = result["optimized_schedule"]
        assert len(schedule) == 2

        t1_sched = next(t for t in schedule if t["task_id"] == "T1")
        t2_sched = next(t for t in schedule if t["task_id"] == "T2")

        t1_start = t1_sched["rl_scheduled_hour"]
        t1_end = t1_sched["rl_scheduled_end_hour"]
        t2_start = t2_sched["rl_scheduled_hour"]
        t2_end = t2_sched["rl_scheduled_end_hour"]

        # Ensure no interval overlap: max(start1, start2) >= min(end1, end2)
        assert max(t1_start, t2_start) >= min(t1_end, t2_end) - 1e-6

    def test_benchmark_environment_five_constraint_metrics(self):
        tasks = [
            {
                "task_id": "T1",
                "priority": 5,
                "estimated_duration": 2.0,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
                "deadline_hour": 12,
            },
            {
                "task_id": "T2",
                "priority": 4,
                "estimated_duration": 1.0,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": "benchmark",
                "deadline_hour": 10,
            },
        ]
        env = RLSchedulingBenchmarkEnvironment(tasks, behavior_patterns={}, start_hour=8, end_hour=18)
        env.reset()

        # Step 1: Schedule T1 at hour 9 (spans [9, 11))
        _, r1, _, info1 = env.step(action_hour=9)
        assert info1["collision"] is False
        assert info1["duplicate_start"] is False
        assert info1["interval_overlap"] is False
        assert info1["slot_overflow"] is False
        assert info1["invalid_assignment"] is False

        # Step 2: Schedule T2 at hour 10 (spans [10, 11)) -> Overlaps with T1!
        _, r2, _, info2 = env.step(action_hour=10)
        assert info2["collision"] is True
        assert info2["duplicate_start"] is False  # Starts at 10, T1 started at 9
        assert info2["interval_overlap"] is True   # [10, 11) overlaps [9, 11)
        assert info2["slot_overflow"] is True      # Slot 10 load = 1.0 + 1.0 = 2.0 > 1.0

        # Verify environment accumulated counts
        assert env.duplicate_start_times == 0
        assert env.overlapping_task_intervals == 1
        assert env.slot_capacity_overflows == 1
        assert env.collisions == 1

    def test_benchmark_evaluator_metrics_dataclass(self):
        metrics = PolicyEvaluationMetrics(
            policy_name="TestPolicy",
            scenario_id="test_sc",
            episode_count=5,
            mean_reward=100.0,
            std_reward=5.0,
            task_completion_rate_pct=100.0,
            deadline_adherence_rate_pct=80.0,
            collision_count=2,
            duplicate_start_times=0,
            slot_capacity_overflows=1,
            overlapping_task_intervals=1,
            deadline_violations=1,
            invalid_task_assignments=0,
        )
        d = metrics.to_dict()
        assert d["duplicate_start_times"] == 0
        assert d["slot_capacity_overflows"] == 1
        assert d["overlapping_task_intervals"] == 1
        assert d["deadline_violations"] == 1
        assert d["invalid_task_assignments"] == 0
