from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Any, Dict, List

from backend.app.domain.behavior_learning_model import (
    BehaviorInsight,
    BehaviorObservation,
    BehaviorPattern,
    BehaviorTrend,
    LearningSnapshot,
)


class BehaviorLearningEngine:
    """Passive deterministic learner for long-running behavioral patterns."""

    def __init__(self, max_history_size: int = 1000) -> None:
        if not isinstance(max_history_size, int) or isinstance(max_history_size, bool) or max_history_size <= 0:
            raise ValueError("max_history_size must be a positive integer.")
        self.max_history_size = max_history_size
        self.observations: List[BehaviorObservation] = []
        self.latest_snapshot: LearningSnapshot | None = None

    def record_observation(
        self,
        observation_type: str,
        *,
        productivity_score: float = 0.0,
        hour_of_day: int | str | None = None,
        task_type: str = "general",
        goal_id: str | None = None,
        completed: bool = False,
        deferred: bool = False,
        metadata: Dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> BehaviorObservation:
        """Record one bounded in-memory behavior observation."""
        metadata = {} if metadata is None else metadata
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary.")
        observation = BehaviorObservation(
            observation_id=f"behavior-observation-{len(self.observations) + 1}",
            observation_type=observation_type,
            timestamp=timestamp or datetime.utcnow(),
            productivity_score=productivity_score,
            hour_of_day=hour_of_day,
            task_type=task_type,
            goal_id=goal_id,
            completed=completed,
            deferred=deferred,
            metadata=dict(metadata),
        )
        self.observations.append(observation)
        if len(self.observations) > self.max_history_size:
            overflow = len(self.observations) - self.max_history_size
            self.observations = self.observations[overflow:]
        return observation

    def record_task_completion(self, task: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Record completed task behavior."""
        task = self._dict(task, "task")
        return self.record_observation(
            "task_completion",
            productivity_score=self._safe_float(task.get("productivity_score", task.get("predicted_productivity")), 70.0),
            hour_of_day=task.get("hour_of_day", task.get("scheduled_hour")),
            task_type=str(task.get("task_type", task.get("type", "general"))),
            goal_id=task.get("goal_id"),
            completed=True,
            deferred=False,
            metadata=task,
            timestamp=timestamp,
        )

    def record_schedule_adherence(self, schedule_event: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Record schedule adherence or drift behavior."""
        event = self._dict(schedule_event, "schedule_event")
        scheduled = self._safe_float(event.get("scheduled_hour"), 0.0)
        actual = self._safe_float(event.get("actual_execution_hour"), scheduled)
        drift = abs(actual - scheduled)
        return self.record_observation(
            "schedule_adherence",
            productivity_score=max(0.0, 100.0 - drift * 15.0),
            hour_of_day=event.get("actual_execution_hour", event.get("scheduled_hour")),
            task_type=str(event.get("task_type", "general")),
            goal_id=event.get("goal_id"),
            completed=drift <= 1.0,
            metadata={**event, "schedule_drift": drift},
            timestamp=timestamp,
        )

    def record_goal_progress(self, goal: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Record goal progress behavior."""
        goal = self._dict(goal, "goal")
        return self.record_observation(
            "goal_progress",
            productivity_score=self._safe_float(goal.get("progress"), 0.0),
            goal_id=str(goal.get("goal_id", goal.get("id", "goal"))),
            task_type="goal",
            completed=self._safe_float(goal.get("progress"), 0.0) >= 100.0,
            metadata=goal,
            timestamp=timestamp,
        )

    def record_deferral(self, task: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Record task deferral behavior."""
        task = self._dict(task, "task")
        return self.record_observation(
            "deferral",
            productivity_score=0.0,
            hour_of_day=task.get("hour_of_day", task.get("scheduled_hour")),
            task_type=str(task.get("task_type", task.get("type", "general"))),
            goal_id=task.get("goal_id"),
            completed=False,
            deferred=True,
            metadata=task,
            timestamp=timestamp,
        )

    def record_missed_plan(self, plan: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Record missed plan behavior."""
        plan = self._dict(plan, "plan")
        return self.record_observation(
            "missed_plan",
            productivity_score=0.0,
            task_type="planning",
            goal_id=plan.get("goal_id"),
            metadata=plan,
            timestamp=timestamp,
        )

    def record_recovery_period(self, recovery: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Record recovery period behavior."""
        recovery = self._dict(recovery, "recovery")
        return self.record_observation(
            "recovery_period",
            productivity_score=self._safe_float(recovery.get("recovery_score"), 60.0),
            task_type="recovery",
            goal_id=recovery.get("goal_id"),
            completed=True,
            metadata=recovery,
            timestamp=timestamp,
        )

    def discover_patterns(self) -> List[BehaviorPattern]:
        """Detect work-hour, task-type, delay, blocker, and burnout patterns."""
        if not self.observations:
            return []
        patterns: List[BehaviorPattern] = []
        hourly = self._group_scores("hour_of_day")
        if hourly:
            best_hour, best_score = max(hourly.items(), key=lambda item: (mean(item[1]), -int(item[0])))
            worst_hour, worst_score = min(hourly.items(), key=lambda item: (mean(item[1]), int(item[0])))
            patterns.append(self._pattern("best-work-hour", "focus", f"Best work hour is {best_hour}.", best_score))
            patterns.append(self._pattern("worst-work-hour", "focus", f"Worst work hour is {worst_hour}.", worst_score))
        task_scores = self._group_scores("task_type")
        if task_scores:
            best_type, best_values = max(task_scores.items(), key=lambda item: (mean(item[1]), item[0]))
            worst_type, worst_values = min(task_scores.items(), key=lambda item: (mean(item[1]), item[0]))
            patterns.append(self._pattern("most-productive-task-type", "task_type", f"Most productive task type is {best_type}.", best_values))
            patterns.append(self._pattern("least-productive-task-type", "task_type", f"Least productive task type is {worst_type}.", worst_values))
        deferrals = [obs for obs in self.observations if obs.deferred or obs.observation_type == "deferral"]
        if len(deferrals) >= 2:
            patterns.append(
                BehaviorPattern(
                    pattern_id="pattern-recurring-delays",
                    pattern_type="delay",
                    description="Recurring delays detected from repeated deferrals.",
                    confidence=min(1.0, len(deferrals) / max(3.0, len(self.observations))),
                    evidence_count=len(deferrals),
                    metadata={"deferred_count": len(deferrals)},
                )
            )
        blockers = self._metadata_frequency("blocker")
        for blocker, count in blockers.items():
            if count >= 2:
                patterns.append(
                    BehaviorPattern(
                        pattern_id=f"pattern-blocker-{blocker}",
                        pattern_type="blocker",
                        description=f"Recurring blocker detected: {blocker}.",
                        confidence=min(1.0, 0.45 + count * 0.15),
                        evidence_count=count,
                        metadata={"blocker": blocker},
                    )
                )
        burnout = [obs for obs in self.observations if obs.metadata.get("burnout_signal") or obs.metadata.get("stress_level") in {"high", "critical"}]
        if burnout:
            patterns.append(
                BehaviorPattern(
                    pattern_id="pattern-burnout-signals",
                    pattern_type="burnout",
                    description="Recurring burnout signals detected.",
                    confidence=min(1.0, 0.4 + len(burnout) * 0.1),
                    evidence_count=len(burnout),
                    metadata={"burnout_signal_count": len(burnout)},
                )
            )
        return sorted(patterns, key=lambda item: item.pattern_id)

    def analyze_trends(self) -> List[BehaviorTrend]:
        """Analyze productivity and consistency trends."""
        productivity = self._productivity_trend()
        consistency = self._consistency_trend()
        return sorted([productivity, consistency], key=lambda item: item.trend_id)

    def generate_insights(self) -> List[BehaviorInsight]:
        """Generate deterministic behavior insights and recommendations."""
        patterns = self.discover_patterns()
        trends = self.analyze_trends()
        insights: List[BehaviorInsight] = []
        for index, pattern in enumerate(patterns, start=1):
            recommendation = self._recommendation_for_pattern(pattern)
            insights.append(
                BehaviorInsight(
                    insight_id=f"behavior-insight-{index}",
                    title=pattern.description,
                    confidence=pattern.confidence,
                    evidence=[f"{pattern.evidence_count} observations support this pattern."],
                    recommendation=recommendation,
                )
            )
        for trend in trends:
            if trend.direction in {"improving", "declining"}:
                insights.append(
                    BehaviorInsight(
                        insight_id=f"behavior-insight-trend-{trend.trend_type}",
                        title=f"{trend.trend_type.replace('_', ' ').title()} is {trend.direction}",
                        confidence=max(0.4, trend.strength),
                        evidence=trend.evidence,
                        recommendation=self._recommendation_for_trend(trend),
                    )
                )
        return sorted(insights, key=lambda item: item.insight_id)

    def calculate_habit_stability(self) -> Dict[str, float]:
        """Calculate consistency, habit strength, volatility, and learning confidence."""
        if not self.observations:
            return {
                "consistency_score": 0.0,
                "habit_strength": 0.0,
                "behavior_volatility": 0.0,
                "learning_confidence": 0.0,
            }
        scores = [obs.productivity_score for obs in self.observations]
        volatility = min(100.0, pstdev(scores) if len(scores) > 1 else 0.0)
        consistency = max(0.0, 100.0 - volatility)
        completions = sum(1 for obs in self.observations if obs.completed)
        non_deferred = sum(1 for obs in self.observations if not obs.deferred)
        habit_strength = ((completions + non_deferred) / (len(self.observations) * 2.0)) * 100.0
        confidence = min(1.0, len(self.observations) / 20.0)
        return {
            "consistency_score": round(consistency, 2),
            "habit_strength": round(habit_strength, 2),
            "behavior_volatility": round(volatility, 2),
            "learning_confidence": round(confidence, 4),
        }

    def predict_tendencies(self) -> Dict[str, Any]:
        """Estimate future productivity, risk, burnout, and completion tendencies deterministically."""
        if not self.observations:
            return {
                "future_productivity_tendency": "insufficient_data",
                "future_risk_tendency": "insufficient_data",
                "future_burnout_tendency": "insufficient_data",
                "future_completion_tendency": "insufficient_data",
            }
        trends = {trend.trend_type: trend.direction for trend in self.analyze_trends()}
        deferral_rate = sum(1 for obs in self.observations if obs.deferred) / len(self.observations)
        burnout_rate = sum(1 for obs in self.observations if obs.metadata.get("burnout_signal")) / len(self.observations)
        completion_rate = sum(1 for obs in self.observations if obs.completed) / len(self.observations)
        return {
            "future_productivity_tendency": trends.get("productivity", "stable"),
            "future_risk_tendency": "rising" if deferral_rate >= 0.3 else "stable",
            "future_burnout_tendency": "rising" if burnout_rate >= 0.2 else "stable",
            "future_completion_tendency": "strong" if completion_rate >= 0.7 else "weak" if completion_rate < 0.4 else "moderate",
        }

    def generate_learning_snapshot(
        self,
        period: str = "weekly",
        *,
        created_at: datetime | None = None,
    ) -> LearningSnapshot:
        """Generate a weekly or monthly learning snapshot."""
        period = self._period(period)
        observations = self._observations_for_period(period, created_at or datetime.utcnow())
        original = self.observations
        self.observations = observations
        try:
            patterns = self.discover_patterns()
            trends = self.analyze_trends()
            insights = self.generate_insights()
            stability = self.calculate_habit_stability()
        finally:
            self.observations = original
        snapshot = LearningSnapshot(
            snapshot_id=f"learning-snapshot-{period}-{(created_at or datetime.utcnow()).strftime('%Y%m%d')}",
            period=period,
            observation_count=len(observations),
            patterns=patterns,
            trends=trends,
            insights=insights,
            created_at=created_at or datetime.utcnow(),
            **stability,
        )
        self.latest_snapshot = snapshot
        return snapshot

    def explain_learning(self) -> Dict[str, Any]:
        """Explain why patterns, trends, and recommendations were generated."""
        patterns = self.discover_patterns()
        trends = self.analyze_trends()
        insights = self.generate_insights()
        return {
            "pattern_reasoning": [
                f"{pattern.pattern_id}: detected from {pattern.evidence_count} matching observations."
                for pattern in patterns
            ],
            "trend_reasoning": [
                f"{trend.trend_id}: {trend.direction} with strength {trend.strength:.2f}."
                for trend in trends
            ],
            "recommendation_reasoning": [
                f"{insight.insight_id}: {insight.recommendation}"
                for insight in insights
            ],
        }

    def ingest_goal_update(self, goal: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Integrate a goal progress update as a learning observation."""
        return self.record_goal_progress(goal, timestamp=timestamp)

    def ingest_reflection(self, reflection: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Integrate a reflection record as a learning observation."""
        reflection = self._dict(reflection, "reflection")
        return self.record_observation(
            "reflection",
            productivity_score=max(0.0, 100.0 - self._safe_float(reflection.get("error_score"), 0.0)),
            task_type=str(reflection.get("engine_name", "reflection")),
            metadata=reflection,
            timestamp=timestamp,
        )

    def ingest_adaptive_signal(self, signal: Dict[str, Any], *, timestamp: datetime | None = None) -> BehaviorObservation:
        """Integrate Adaptive Life Operating System signal data."""
        signal = self._dict(signal, "signal")
        severity = str(signal.get("severity", "low")).lower()
        productivity = {"critical": 20.0, "high": 40.0, "medium": 60.0, "low": 80.0}.get(severity, 60.0)
        return self.record_observation(
            "adaptive_signal",
            productivity_score=productivity,
            task_type=str(signal.get("signal_type", "adaptive")),
            metadata={**signal, "burnout_signal": signal.get("signal_type") == "burnout"},
            timestamp=timestamp,
        )

    def summarize_behavior_learning(self) -> Dict[str, Any] | None:
        """Return optional orchestrator-ready behavioral learning outputs."""
        if not self.observations:
            return None
        snapshot_time = max(observation.timestamp for observation in self.observations)
        snapshot = self.latest_snapshot or self.generate_learning_snapshot("weekly", created_at=snapshot_time)
        trends = [asdict(trend) for trend in self.analyze_trends()]
        insights = [asdict(insight) for insight in self.generate_insights()]
        return {
            "behavior_learning_summary": {
                "observation_count": len(self.observations),
                "pattern_count": len(snapshot.patterns),
                "insight_count": len(insights),
                **self.calculate_habit_stability(),
            },
            "behavior_trends": trends,
            "behavior_insights": insights,
            "learning_snapshot": asdict(snapshot),
        }

    def _productivity_trend(self) -> BehaviorTrend:
        if len(self.observations) < 3:
            return BehaviorTrend("trend-productivity", "productivity", "insufficient_data", 0.0, [])
        ordered = sorted(self.observations, key=lambda item: (item.timestamp, item.observation_id))
        midpoint = len(ordered) // 2
        early = mean(obs.productivity_score for obs in ordered[:midpoint])
        recent = mean(obs.productivity_score for obs in ordered[midpoint:])
        delta = recent - early
        direction = "improving" if delta >= 5.0 else "declining" if delta <= -5.0 else "stable"
        return BehaviorTrend(
            "trend-productivity",
            "productivity",
            direction,
            min(1.0, abs(delta) / 50.0),
            [f"early_average={early:.2f}", f"recent_average={recent:.2f}"],
        )

    def _consistency_trend(self) -> BehaviorTrend:
        if len(self.observations) < 4:
            return BehaviorTrend("trend-consistency", "consistency", "insufficient_data", 0.0, [])
        ordered = sorted(self.observations, key=lambda item: (item.timestamp, item.observation_id))
        midpoint = len(ordered) // 2
        early_volatility = pstdev([obs.productivity_score for obs in ordered[:midpoint]]) if midpoint > 1 else 0.0
        recent_values = [obs.productivity_score for obs in ordered[midpoint:]]
        recent_volatility = pstdev(recent_values) if len(recent_values) > 1 else 0.0
        delta = early_volatility - recent_volatility
        direction = "improving" if delta >= 5.0 else "declining" if delta <= -5.0 else "stable"
        return BehaviorTrend(
            "trend-consistency",
            "consistency",
            direction,
            min(1.0, abs(delta) / 50.0),
            [f"early_volatility={early_volatility:.2f}", f"recent_volatility={recent_volatility:.2f}"],
        )

    def _group_scores(self, field_name: str) -> Dict[str, List[float]]:
        grouped: Dict[str, List[float]] = {}
        for obs in self.observations:
            value = getattr(obs, field_name)
            if value is None:
                continue
            grouped.setdefault(str(value), []).append(obs.productivity_score)
        return grouped

    def _metadata_frequency(self, key: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for obs in self.observations:
            value = obs.metadata.get(key)
            if value is None:
                continue
            normalized = str(value).strip().lower()
            counts[normalized] = counts.get(normalized, 0) + 1
        return dict(sorted(counts.items()))

    def _pattern(self, pattern_id: str, pattern_type: str, description: str, values: List[float]) -> BehaviorPattern:
        return BehaviorPattern(
            pattern_id=f"pattern-{pattern_id}",
            pattern_type=pattern_type,
            description=description,
            confidence=min(1.0, 0.45 + len(values) * 0.1),
            evidence_count=len(values),
            metadata={"average_score": round(mean(values), 2)},
        )

    def _recommendation_for_pattern(self, pattern: BehaviorPattern) -> str:
        if pattern.pattern_id == "pattern-best-work-hour":
            return "Place deep work during this hour when possible."
        if pattern.pattern_id == "pattern-worst-work-hour":
            return "Avoid high-stakes work during this hour."
        if pattern.pattern_type == "delay":
            return "Reduce recurring deferrals by shrinking the next action."
        if pattern.pattern_type == "blocker":
            return "Resolve the recurring blocker before expanding scope."
        if pattern.pattern_type == "burnout":
            return "Protect recovery capacity before adding commitments."
        return "Use this pattern to improve future planning."

    def _recommendation_for_trend(self, trend: BehaviorTrend) -> str:
        if trend.direction == "improving":
            return "Preserve the conditions associated with this improvement."
        if trend.direction == "declining":
            return "Reduce load and investigate the recent decline."
        return "Continue monitoring this trend."

    def _observations_for_period(self, period: str, now: datetime) -> List[BehaviorObservation]:
        days = 7 if period == "weekly" else 30
        cutoff = now - timedelta(days=days)
        return [obs for obs in self.observations if obs.timestamp >= cutoff]

    def _period(self, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("period must be weekly or monthly.")
        normalized = value.strip().lower()
        if normalized not in {"weekly", "monthly"}:
            raise ValueError("period must be weekly or monthly.")
        return normalized

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        return dict(value)

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number
