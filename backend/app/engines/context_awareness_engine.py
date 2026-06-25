from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.context_awareness_model import (
    ContextConflict,
    ContextInsight,
    ContextShift,
    ContextSignal,
    ContextSnapshot,
)


class ContextAwarenessEngine:
    """Passive deterministic engine for current-state context intelligence."""

    def __init__(self, max_history_size: int = 100) -> None:
        if not isinstance(max_history_size, int) or isinstance(max_history_size, bool) or max_history_size <= 0:
            raise ValueError("max_history_size must be a positive integer.")
        self.max_history_size = max_history_size
        self.snapshots: List[ContextSnapshot] = []
        self.latest_conflicts: List[ContextConflict] = []
        self.latest_insights: List[ContextInsight] = []
        self._snapshot_sequence = 0

    def generate_snapshot(
        self,
        *,
        current_context: Dict[str, Any] | None = None,
        workload: Dict[str, Any] | None = None,
        goals: List[Dict[str, Any]] | None = None,
        behavior_learning_summary: Dict[str, Any] | None = None,
        adaptive_life_summary: Dict[str, Any] | None = None,
        meta_cognitive_summary: Dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ContextSnapshot:
        """Generate the current context snapshot."""
        current_context = self._dict({} if current_context is None else current_context, "current_context")
        workload = self._dict({} if workload is None else workload, "workload")
        goals = self._dict_list([] if goals is None else goals, "goals")
        behavior_learning_summary = self._dict({} if behavior_learning_summary is None else behavior_learning_summary, "behavior_learning_summary")
        adaptive_life_summary = self._dict({} if adaptive_life_summary is None else adaptive_life_summary, "adaptive_life_summary")
        meta_cognitive_summary = self._dict({} if meta_cognitive_summary is None else meta_cognitive_summary, "meta_cognitive_summary")
        timestamp = timestamp or datetime.utcnow()
        focus_score = self._focus_score(current_context, behavior_learning_summary)
        workload_ratio = self._workload_ratio(workload, adaptive_life_summary)
        goal_score = self._goal_score(goals)
        risk_score = self._risk_score(adaptive_life_summary, meta_cognitive_summary)
        energy_score = self._energy_score(current_context)
        momentum = self.analyze_momentum(
            goals=goals,
            behavior_learning_summary=behavior_learning_summary,
            adaptive_life_summary=adaptive_life_summary,
        )
        self._snapshot_sequence += 1
        signals = [
            ContextSignal("signal-focus", "focus", focus_score, 0.78, "ContextAwarenessEngine", timestamp),
            ContextSignal("signal-workload", "workload", min(100.0, workload_ratio * 100.0), 0.8, "ContextAwarenessEngine", timestamp),
            ContextSignal("signal-goal", "goal", goal_score, 0.76, "ContextAwarenessEngine", timestamp),
            ContextSignal("signal-risk", "risk", risk_score, 0.82, "ContextAwarenessEngine", timestamp),
            ContextSignal("signal-energy", "energy", energy_score, 0.74, "ContextAwarenessEngine", timestamp),
        ]
        snapshot = ContextSnapshot(
            snapshot_id=f"context-snapshot-{self._snapshot_sequence}",
            focus_state=self._focus_state(focus_score),
            workload_state=self._workload_state(workload_ratio),
            goal_state=self._goal_state(goal_score),
            momentum_state=momentum["momentum_state"],
            risk_state=self._risk_state(risk_score),
            energy_state=self._energy_state(energy_score),
            confidence=self._bounded(0.55 + min(0.4, len(signals) * 0.06), 0.0, 1.0),
            signals=signals,
            timestamp=timestamp,
        )
        self.snapshots.append(snapshot)
        if len(self.snapshots) > self.max_history_size:
            overflow = len(self.snapshots) - self.max_history_size
            self.snapshots = self.snapshots[overflow:]
        return snapshot

    def detect_context_shifts(self) -> List[ContextShift]:
        """Detect improving, declining, stable, and major context transitions."""
        if len(self.snapshots) < 2:
            return []
        previous = self.snapshots[-2]
        current = self.snapshots[-1]
        shifts: List[ContextShift] = []
        for shift_type in ("focus", "risk", "momentum"):
            previous_value = self._snapshot_value(previous, shift_type)
            current_value = self._snapshot_value(current, shift_type)
            delta = current_value - previous_value
            direction = self._direction(delta, shift_type)
            shifts.append(
                ContextShift(
                    shift_id=f"context-shift-{shift_type}-{len(self.snapshots)}",
                    from_snapshot_id=previous.snapshot_id,
                    to_snapshot_id=current.snapshot_id,
                    shift_type=shift_type,
                    direction=direction,
                    magnitude=abs(delta),
                    confidence=0.76,
                )
            )
        return sorted(shifts, key=lambda item: item.shift_id)

    def detect_context_conflicts(
        self,
        *,
        snapshot: ContextSnapshot | Dict[str, Any] | None = None,
        tasks: List[Dict[str, Any]] | None = None,
        goals: List[Dict[str, Any]] | None = None,
        dependency_state: Dict[str, Any] | None = None,
    ) -> List[ContextConflict]:
        """Detect goal, schedule, capacity, dependency, and priority conflicts."""
        snapshot_obj = self._snapshot(snapshot) if snapshot is not None else (self.snapshots[-1] if self.snapshots else None)
        tasks = self._dict_list([] if tasks is None else tasks, "tasks")
        goals = self._dict_list([] if goals is None else goals, "goals")
        dependency_state = self._dict({} if dependency_state is None else dependency_state, "dependency_state")
        conflicts: List[ContextConflict] = []
        if goals and tasks:
            goal_ids = {str(goal.get("goal_id", goal.get("id"))) for goal in goals if goal.get("goal_id", goal.get("id")) is not None}
            unaligned = [str(task.get("id", task.get("title", "task"))) for task in tasks if task.get("goal_id") not in goal_ids]
            if unaligned:
                conflicts.append(ContextConflict("conflict-goal", "goal", "medium", "Tasks are not aligned with active goals.", unaligned, 0.72))
        duplicate_hours = self._duplicate_scheduled_hours(tasks)
        if duplicate_hours:
            conflicts.append(ContextConflict("conflict-schedule", "schedule", "medium", "Multiple tasks compete for the same scheduled hour.", duplicate_hours, 0.75))
        if snapshot_obj is not None and snapshot_obj.workload_state == "overload":
            conflicts.append(ContextConflict("conflict-capacity", "capacity", "high", "Workload exceeds available capacity.", [], 0.84))
        blocked = dependency_state.get("blocked_tasks", [])
        if isinstance(blocked, list) and blocked:
            conflicts.append(ContextConflict("conflict-dependency", "dependency", "high", "Blocked dependencies constrain execution.", [str(item) for item in blocked], 0.82))
        high_priority_blocked = [str(task.get("id", task.get("title", "task"))) for task in tasks if self._safe_float(task.get("priority"), 0.0) >= 7.0 and task.get("blocked")]
        if high_priority_blocked:
            conflicts.append(ContextConflict("conflict-priority", "priority", "critical", "High-priority tasks are blocked.", high_priority_blocked, 0.86))
        self.latest_conflicts = sorted(conflicts, key=lambda item: item.conflict_id)
        return self.latest_conflicts

    def analyze_momentum(
        self,
        *,
        goals: List[Dict[str, Any]] | None = None,
        behavior_learning_summary: Dict[str, Any] | None = None,
        adaptive_life_summary: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Measure positive, negative, or neutral context momentum."""
        goals = self._dict_list([] if goals is None else goals, "goals")
        behavior_learning_summary = self._dict({} if behavior_learning_summary is None else behavior_learning_summary, "behavior_learning_summary")
        adaptive_life_summary = self._dict({} if adaptive_life_summary is None else adaptive_life_summary, "adaptive_life_summary")
        average_progress = sum(self._safe_float(goal.get("progress"), 0.0) for goal in goals) / len(goals) if goals else 50.0
        habit_strength = self._safe_float(behavior_learning_summary.get("habit_strength"), 50.0)
        risk_count = self._safe_float(adaptive_life_summary.get("risk_count"), 0.0)
        score = self._bounded((average_progress * 0.45) + (habit_strength * 0.45) - risk_count * 8.0 + 10.0, 0.0, 100.0)
        if score >= 65.0:
            state = "positive"
        elif score <= 35.0:
            state = "negative"
        else:
            state = "neutral"
        return {"momentum_score": round(score, 2), "momentum_state": state}

    def analyze_recovery(
        self,
        *,
        behavior_learning_summary: Dict[str, Any] | None = None,
        adaptive_life_summary: Dict[str, Any] | None = None,
        meta_cognitive_summary: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Detect burnout, overload, and performance recovery state."""
        behavior_learning_summary = self._dict({} if behavior_learning_summary is None else behavior_learning_summary, "behavior_learning_summary")
        adaptive_life_summary = self._dict({} if adaptive_life_summary is None else adaptive_life_summary, "adaptive_life_summary")
        meta_cognitive_summary = self._dict({} if meta_cognitive_summary is None else meta_cognitive_summary, "meta_cognitive_summary")
        burnout_probability = self._safe_float(adaptive_life_summary.get("burnout_probability"), 0.0)
        load_status = str(adaptive_life_summary.get("load_status", "healthy_load"))
        average_error = self._safe_float(meta_cognitive_summary.get("average_error"), 0.0)
        consistency = self._safe_float(behavior_learning_summary.get("consistency_score"), 50.0)
        return {
            "burnout_recovery": burnout_probability < 0.35,
            "overload_recovery": load_status != "overload",
            "performance_recovery": average_error < 25.0 and consistency >= 50.0,
        }

    def generate_context_insights(
        self,
        *,
        snapshot: ContextSnapshot | Dict[str, Any] | None = None,
        conflicts: List[ContextConflict | Dict[str, Any]] | None = None,
    ) -> List[ContextInsight]:
        """Generate context-aware insights and recommendations."""
        snapshot_obj = self._snapshot(snapshot) if snapshot is not None else (self.snapshots[-1] if self.snapshots else None)
        conflict_objs = [item if isinstance(item, ContextConflict) else ContextConflict(**item) for item in (conflicts if conflicts is not None else self.latest_conflicts)]
        insights: List[ContextInsight] = []
        if snapshot_obj is not None:
            if snapshot_obj.risk_state in {"high", "critical"}:
                insights.append(ContextInsight("context-insight-risk", "Risk state is elevated.", 0.82, [f"risk_state={snapshot_obj.risk_state}"], "Reduce load and resolve blockers before expanding commitments."))
            if snapshot_obj.momentum_state == "positive":
                insights.append(ContextInsight("context-insight-momentum", "Momentum is positive.", 0.76, ["Current momentum state is positive."], "Protect the current execution rhythm."))
            if snapshot_obj.energy_state == "low":
                insights.append(ContextInsight("context-insight-energy", "Energy is low.", 0.72, ["Energy state is low."], "Prefer recovery or low-friction work next."))
        for conflict in conflict_objs:
            insights.append(
                ContextInsight(
                    insight_id=f"context-insight-{conflict.conflict_type}",
                    insight=f"{conflict.conflict_type.title()} conflict detected.",
                    confidence=conflict.confidence,
                    evidence=[conflict.description],
                    recommendation=self._recommendation_for_conflict(conflict),
                )
            )
        self.latest_insights = sorted({item.insight_id: item for item in insights}.values(), key=lambda item: item.insight_id)
        return self.latest_insights

    def estimate_state_trajectory(self) -> Dict[str, Any]:
        """Estimate near-term context direction, stability, risk tendency, and focus tendency."""
        if len(self.snapshots) < 2:
            return {
                "near_term_direction": "insufficient_data",
                "stability": "insufficient_data",
                "risk_tendency": "insufficient_data",
                "focus_tendency": "insufficient_data",
            }
        shifts = self.detect_context_shifts()
        declining = sum(1 for shift in shifts if shift.direction == "declining")
        improving = sum(1 for shift in shifts if shift.direction == "improving")
        if improving > declining:
            direction = "improving"
        elif declining > improving:
            direction = "declining"
        else:
            direction = "stable"
        total_magnitude = sum(shift.magnitude for shift in shifts)
        return {
            "near_term_direction": direction,
            "stability": "volatile" if total_magnitude >= 60.0 else "stable",
            "risk_tendency": next((shift.direction for shift in shifts if shift.shift_type == "risk"), "stable"),
            "focus_tendency": next((shift.direction for shift in shifts if shift.shift_type == "focus"), "stable"),
        }

    def explain_context(self) -> Dict[str, Any]:
        """Explain why context, conflicts, shifts, and recommendations were produced."""
        shifts = self.detect_context_shifts()
        return {
            "context_reasoning": [f"{snapshot.snapshot_id}: focus={snapshot.focus_state}, workload={snapshot.workload_state}, risk={snapshot.risk_state}." for snapshot in self.snapshots[-3:]],
            "conflict_reasoning": [f"{conflict.conflict_id}: {conflict.description}" for conflict in self.latest_conflicts],
            "shift_reasoning": [f"{shift.shift_id}: {shift.direction} magnitude {shift.magnitude:.2f}." for shift in shifts],
            "recommendation_reasoning": [f"{insight.insight_id}: {insight.recommendation}" for insight in self.latest_insights],
        }

    def summarize_context_awareness(self) -> Dict[str, Any] | None:
        """Return optional orchestrator-ready context awareness outputs."""
        if not self.snapshots:
            return None
        latest = self.snapshots[-1]
        shifts = self.detect_context_shifts()
        insights = self.latest_insights or self.generate_context_insights(snapshot=latest)
        return {
            "context_snapshot": asdict(latest),
            "context_shifts": [asdict(shift) for shift in shifts],
            "context_conflicts": [asdict(conflict) for conflict in self.latest_conflicts],
            "context_insights": [asdict(insight) for insight in insights],
            "context_summary": {
                "focus_state": latest.focus_state,
                "workload_state": latest.workload_state,
                "goal_state": latest.goal_state,
                "momentum_state": latest.momentum_state,
                "risk_state": latest.risk_state,
                "energy_state": latest.energy_state,
                "conflict_count": len(self.latest_conflicts),
                "insight_count": len(insights),
            },
        }

    def _snapshot(self, value: ContextSnapshot | Dict[str, Any]) -> ContextSnapshot:
        return value if isinstance(value, ContextSnapshot) else ContextSnapshot(**self._dict(value, "snapshot"))

    def _focus_score(self, context: Dict[str, Any], behavior_summary: Dict[str, Any]) -> float:
        focus_hours = context.get("behavior_patterns", {}).get("best_focus_hours", [])
        current_hour = context.get("current_hour")
        base = 70.0 if isinstance(focus_hours, list) and current_hour in focus_hours else 50.0
        return self._bounded(base + self._safe_float(behavior_summary.get("consistency_score"), 0.0) * 0.2, 0.0, 100.0)

    def _workload_ratio(self, workload: Dict[str, Any], adaptive_summary: Dict[str, Any]) -> float:
        if "capacity_utilization" in workload:
            return self._safe_float(workload.get("capacity_utilization"), 1.0)
        if adaptive_summary.get("load_status") == "overload":
            return 1.25
        return self._safe_float(workload.get("projected_workload"), 1.0) / max(1.0, self._safe_float(workload.get("available_capacity"), 1.0))

    def _goal_score(self, goals: List[Dict[str, Any]]) -> float:
        if not goals:
            return 50.0
        return self._bounded(sum(self._safe_float(goal.get("progress"), 0.0) for goal in goals) / len(goals), 0.0, 100.0)

    def _risk_score(self, adaptive_summary: Dict[str, Any], meta_summary: Dict[str, Any]) -> float:
        burnout = self._safe_float(adaptive_summary.get("burnout_probability"), 0.0) * 100.0
        risk_count = self._safe_float(adaptive_summary.get("risk_count"), 0.0) * 12.0
        error = self._safe_float(meta_summary.get("average_error"), 0.0)
        return self._bounded(max(burnout, risk_count, error), 0.0, 100.0)

    def _energy_score(self, context: Dict[str, Any]) -> float:
        patterns = context.get("behavior_patterns", {})
        return self._bounded(self._safe_float(patterns.get("average_energy_level"), 60.0), 0.0, 100.0)

    def _focus_state(self, score: float) -> str:
        return "focused" if score >= 70.0 else "scattered" if score < 40.0 else "available"

    def _workload_state(self, ratio: float) -> str:
        return "overload" if ratio > 1.0 else "underload" if ratio < 0.5 else "healthy_load"

    def _goal_state(self, score: float) -> str:
        return "advancing" if score >= 65.0 else "stalled" if score < 25.0 else "active"

    def _risk_state(self, score: float) -> str:
        if score >= 75.0:
            return "critical"
        if score >= 50.0:
            return "high"
        if score >= 25.0:
            return "medium"
        return "low"

    def _energy_state(self, score: float) -> str:
        return "high" if score >= 70.0 else "low" if score < 40.0 else "moderate"

    def _snapshot_value(self, snapshot: ContextSnapshot, shift_type: str) -> float:
        if shift_type == "focus":
            return {"scattered": 20.0, "available": 55.0, "focused": 90.0}.get(snapshot.focus_state, 50.0)
        if shift_type == "risk":
            return {"low": 90.0, "medium": 60.0, "high": 30.0, "critical": 5.0}.get(snapshot.risk_state, 50.0)
        return {"negative": 20.0, "neutral": 55.0, "positive": 90.0}.get(snapshot.momentum_state, 50.0)

    def _direction(self, delta: float, shift_type: str) -> str:
        if abs(delta) >= 50.0:
            return "major_transition"
        if abs(delta) < 10.0:
            return "stable"
        return "improving" if delta > 0 else "declining"

    def _duplicate_scheduled_hours(self, tasks: List[Dict[str, Any]]) -> List[str]:
        counts: Dict[str, int] = {}
        for task in tasks:
            hour = task.get("scheduled_hour")
            if hour is None:
                continue
            key = str(hour)
            counts[key] = counts.get(key, 0) + 1
        return sorted(hour for hour, count in counts.items() if count > 1)

    def _recommendation_for_conflict(self, conflict: ContextConflict) -> str:
        return {
            "goal": "Move at least one active task toward a stated goal.",
            "schedule": "Separate competing tasks into distinct execution windows.",
            "capacity": "Reduce workload or expand the planning horizon.",
            "dependency": "Resolve blocked prerequisites before adding new work.",
            "priority": "Unblock high-priority work before lower-priority execution.",
        }.get(conflict.conflict_type, "Review the conflict before committing to the plan.")

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        return dict(value)

    def _dict_list(self, value: Any, field_name: str) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list of dictionaries.")
        if any(not isinstance(item, dict) for item in value):
            raise ValueError(f"{field_name} entries must be dictionaries.")
        return [dict(item) for item in value]

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number

    def _bounded(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
