"""Multi-Criteria Decision Analysis (MCDA) Prioritization Engine for HELIOX AI.

Evaluates tasks dynamically across 6 quantitative pillars:
1. Urgency & Deadline Risk (25%)
2. Strategic Goal Alignment (20%)
3. Dependency Leverage & Downstream Impact (20%)
4. Base User Priority (15%)
5. Cognitive & Energy Match (10%)
6. Starvation & Reschedule Prevention (10%)

Enforces blocker gating (penalizing tasks with uncompleted prerequisites)
and provides an explainable score breakdown and actionable recommendation.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.engines.deadline_risk_engine import DeadlineRiskEngine, DeadlineRiskLevel


class MultiCriteriaPrioritizer:
    """Holistic dynamic task prioritization engine."""

    DEEP_WORK_TYPES = frozenset({
        "coding", "programming", "architecture", "design", "research",
        "analysis", "writing", "study", "engineering", "deep_work"
    })
    MEDIUM_LOAD_TYPES = frozenset({
        "meeting", "review", "communication", "planning", "discussion"
    })

    def __init__(
        self,
        risk_engine: Optional[DeadlineRiskEngine] = None,
    ) -> None:
        self.risk_engine = risk_engine or DeadlineRiskEngine()

    def prioritize_workload(
        self,
        tasks: List[Dict[str, Any]],
        goals: Optional[List[Dict[str, Any]]] = None,
        behavior_patterns: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Rank tasks by dynamic priority score, enriching each with an explainable breakdown."""
        now = now or datetime.now(timezone.utc)
        if not tasks:
            return []

        goals_map: Dict[int, Dict[str, Any]] = {}
        if goals:
            for g in goals:
                gid = g.get("id") or g.get("goal_id")
                if gid:
                    goals_map[int(gid)] = g

        # Compute completed task IDs for dependency resolution
        completed_ids = {
            int(t["id"]) for t in tasks
            if (bool(t.get("completed")) or str(t.get("lifecycle_state", "")).lower() == "completed")
            and str(t.get("id", "")).isdigit()
        }

        # Build reverse dependency map: task_id -> list of tasks that depend on it
        blocking_map: Dict[int, List[int]] = {}
        for t in tasks:
            tid = int(t["id"]) if str(t.get("id", "")).isdigit() else None
            if tid is None:
                continue
            deps = self._extract_dependencies(t)
            for dep in deps:
                blocking_map.setdefault(dep, []).append(tid)

        # Assess deadline risks
        risk_assessments = self.risk_engine.assess_all_tasks(tasks, now=now)
        risk_by_id = {str(a.task_id): a for a in risk_assessments}

        current_hour = now.hour
        best_focus_hours = set(behavior_patterns.get("best_focus_hours", [9, 10, 11, 14, 15])) if behavior_patterns else {9, 10, 11, 14, 15}

        evaluated: List[Dict[str, Any]] = []
        for t in tasks:
            tid_str = str(t.get("id", "0"))
            tid_int = int(tid_str) if tid_str.isdigit() else None

            # Skip completed tasks from active prioritization ranking
            is_completed = bool(t.get("completed")) or str(t.get("lifecycle_state", "")).lower() == "completed"

            # 1. Urgency & Deadline Risk (Weight: 0.25)
            risk = risk_by_id.get(tid_str)
            urgency_score = self._compute_urgency_score(risk)

            # 2. Goal Alignment (Weight: 0.20)
            goal_id = t.get("goal_id")
            goal = goals_map.get(int(goal_id)) if (goal_id and str(goal_id).isdigit()) else None
            goal_score, goal_title = self._compute_goal_score(goal)

            # 3. Dependency Leverage & Downstream Impact (Weight: 0.20)
            dependents = blocking_map.get(tid_int, []) if tid_int is not None else []
            leverage_score = min(100.0, len(dependents) * 35.0)

            # Check if task is blocked by incomplete dependencies
            deps = self._extract_dependencies(t)
            is_blocked = any(d not in completed_ids for d in deps)

            # 4. Base User Priority (Weight: 0.15)
            raw_prio = float(t.get("priority") or 3)
            base_prio_score = min(100.0, max(0.0, raw_prio * 20.0))

            # 5. Cognitive & Energy Match (Weight: 0.10)
            task_type = str(t.get("task_type", "general")).lower()
            energy_score = self._compute_energy_score(task_type, current_hour, best_focus_hours)

            # 6. Starvation & Reschedule Prevention (Weight: 0.10)
            reschedule_count = int(t.get("reschedule_count", 0) or 0)
            starvation_score = min(100.0, reschedule_count * 25.0)

            # Blocker penalty
            blocker_penalty = -50.0 if is_blocked else 0.0

            # Composite Dynamic Priority Score
            raw_composite = (
                (urgency_score * 0.25) +
                (goal_score * 0.20) +
                (leverage_score * 0.20) +
                (base_prio_score * 0.15) +
                (energy_score * 0.10) +
                (starvation_score * 0.10) +
                blocker_penalty
            )
            dynamic_priority = round(min(100.0, max(5.0, raw_composite)), 1)

            # Actionable Recommendation explanation
            recommendation = self._generate_recommendation(
                is_completed=is_completed,
                is_blocked=is_blocked,
                risk=risk,
                dependents_count=len(dependents),
                goal_title=goal_title,
                energy_score=energy_score,
                reschedule_count=reschedule_count,
            )

            breakdown = {
                "urgency_score": round(urgency_score, 1),
                "goal_alignment_score": round(goal_score, 1),
                "dependency_leverage_score": round(leverage_score, 1),
                "base_priority_score": round(base_prio_score, 1),
                "energy_match_score": round(energy_score, 1),
                "starvation_score": round(starvation_score, 1),
                "blocker_penalty": round(blocker_penalty, 1),
            }

            enriched_task = dict(t)
            enriched_task["dynamic_priority"] = dynamic_priority
            enriched_task["priority_breakdown"] = breakdown
            enriched_task["is_blocked"] = is_blocked
            enriched_task["blocking_count"] = len(dependents)
            enriched_task["goal_title"] = goal_title
            enriched_task["recommended_action"] = recommendation
            if risk:
                enriched_task["deadline_risk"] = risk.to_dict()

            evaluated.append(enriched_task)

        # Sort: pending first, then by dynamic_priority desc, then by id asc
        return sorted(
            evaluated,
            key=lambda item: (
                1 if (bool(item.get("completed")) or str(item.get("lifecycle_state", "")).lower() == "completed") else 0,
                -float(item.get("dynamic_priority", 0.0)),
                int(item.get("id", 0)) if str(item.get("id", "")).isdigit() else 0,
            ),
        )

    def _compute_urgency_score(self, risk: Optional[Any]) -> float:
        if not risk:
            return 15.0
        level = getattr(risk, "risk_level", "none")
        if level == DeadlineRiskLevel.OVERDUE:
            return 100.0
        if level == DeadlineRiskLevel.HIGH:
            return 85.0
        if level == DeadlineRiskLevel.MODERATE:
            return 55.0
        if level == DeadlineRiskLevel.LOW:
            return 25.0
        return 10.0

    def _compute_goal_score(self, goal: Optional[Dict[str, Any]]) -> Tuple[float, Optional[str]]:
        if not goal:
            return 30.0, None
        title = goal.get("title")
        prio = float(goal.get("priority", 1))
        base_goal_score = min(75.0, prio * 18.0)
        status = str(goal.get("health_status", "on_track")).lower()
        if status in ("behind", "critical"):
            base_goal_score += 25.0
        elif status == "at_risk":
            base_goal_score += 15.0
        return min(100.0, base_goal_score), title

    def _compute_energy_score(
        self, task_type: str, current_hour: int, best_focus_hours: set[int]
    ) -> float:
        is_deep_work = task_type in self.DEEP_WORK_TYPES
        is_peak_hour = current_hour in best_focus_hours

        if is_deep_work and is_peak_hour:
            return 95.0
        if is_deep_work and not is_peak_hour:
            return 35.0
        if not is_deep_work and not is_peak_hour:
            return 80.0
        return 60.0

    def _extract_dependencies(self, task: Dict[str, Any]) -> List[int]:
        deps = task.get("dependencies")
        if not deps:
            return []
        if isinstance(deps, list):
            res = []
            for d in deps:
                if isinstance(d, int):
                    res.append(d)
                elif isinstance(d, str) and d.strip().isdigit():
                    res.append(int(d.strip()))
            return res
        if isinstance(deps, str):
            import json
            text = deps.strip()
            if text.startswith("["):
                try:
                    arr = json.loads(text)
                    return [int(x) for x in arr if str(x).isdigit()]
                except Exception:
                    pass
            out = []
            for part in text.split(","):
                part = part.strip()
                if part.isdigit():
                    out.append(int(part))
            return out
        return []

    def _generate_recommendation(
        self,
        is_completed: bool,
        is_blocked: bool,
        risk: Optional[Any],
        dependents_count: int,
        goal_title: Optional[str],
        energy_score: float,
        reschedule_count: int,
    ) -> str:
        if is_completed:
            return "Task completed."
        if is_blocked:
            return "Blocked by prerequisite task(s) — unblock prerequisites first."
        if risk and getattr(risk, "is_overdue", False):
            return "Overdue deadline — execute immediately to prevent cascading delays."
        if risk and getattr(risk, "risk_level", "") == DeadlineRiskLevel.HIGH:
            return "High deadline risk — schedule in the next available focus block."
        if dependents_count > 0:
            return f"Key bottleneck: completing this unblocks {dependents_count} dependent task(s)."
        if goal_title and goal_title.strip():
            return f"Directly advances strategic goal '{goal_title}'."
        if energy_score >= 90.0:
            return "Aligned with your current peak focus window."
        if reschedule_count >= 2:
            return f"Rescheduled {reschedule_count} times — complete now to prevent starvation."
        return "Optimal next step based on priority and workload."
