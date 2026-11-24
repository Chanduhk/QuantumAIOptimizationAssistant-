"""Intelligent Deadline Risk Assessment Engine for HELIOX AI.

Analyzes task deadlines, estimated and ML-predicted durations, dependency chains,
user workloads, and progress to produce operational, explainable risk classifications.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple


class DeadlineRiskLevel:
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    OVERDUE = "overdue"
    NONE = "none"


@dataclass
class TaskRiskAssessment:
    task_id: int | str
    title: str
    risk_level: str
    risk_score: float
    remaining_minutes: Optional[float]
    predicted_duration_minutes: float
    is_overdue: bool
    reasons: List[str] = field(default_factory=list)
    mitigation_suggestion: Optional[str] = None
    deadline_iso: Optional[str] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DeadlineRiskEngine:
    """Evaluates quantitative risk of missing task deadlines."""

    def __init__(self, duration_predictor: Optional[Any] = None) -> None:
        self.duration_predictor = duration_predictor

    def _now(self, ref: Optional[datetime] = None) -> datetime:
        if ref is None:
            return datetime.now(timezone.utc)
        if ref.tzinfo is None:
            return ref.replace(tzinfo=timezone.utc)
        return ref.astimezone(timezone.utc)

    def _to_utc(self, dt: Any) -> Optional[datetime]:
        if dt is None:
            return None
        if isinstance(dt, str):
            try:
                # Handle ISO string
                clean = dt.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(clean)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except Exception:
                return None
        if isinstance(dt, datetime):
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return None

    def _resolve_predicted_duration_minutes(self, task: Dict[str, Any] | Any) -> float:
        """Resolve expected duration in minutes, factoring in DurationRatioModel if present."""
        def read(key: str, default: Any = None) -> Any:
            if isinstance(task, dict):
                return task.get(key, default)
            return getattr(task, key, default)

        est = read("estimated_duration")
        unit = str(read("estimated_duration_unit") or "minutes").lower()
        
        try:
            base_mins = float(est) if est is not None else 60.0
        except (ValueError, TypeError):
            base_mins = 60.0

        if unit in ("hours", "hour", "h"):
            base_mins *= 60.0

        base_mins = max(5.0, base_mins)

        # Apply personalized DurationRatioModel if available
        try:
            from backend.app.ml.model_registry import get_model_registry
            reg = get_model_registry()
            dur_rec = reg.get_latest_model("DurationRatioModel")
            if dur_rec and getattr(dur_rec.metadata, "status", None) == "production":
                dur_obj = dur_rec.model_object
                if hasattr(dur_obj, "predict_ratio"):
                    ratio = float(dur_obj.predict_ratio(base_mins))
                    if 0.25 <= ratio <= 4.0:
                        return round(base_mins * ratio, 1)
        except Exception:
            pass

        return round(base_mins, 1)

    def assess_task_risk(
        self,
        task: Dict[str, Any] | Any,
        all_tasks: Optional[List[Dict[str, Any] | Any]] = None,
        now: Optional[datetime] = None,
    ) -> TaskRiskAssessment:
        """Assess the deadline risk for a single task."""
        current_time = self._now(now)

        def read(key: str, default: Any = None) -> Any:
            if isinstance(task, dict):
                return task.get(key, default)
            return getattr(task, key, default)

        task_id = read("id", read("task_id", 0))
        title = str(read("title", f"Task {task_id}"))
        completed = bool(read("completed", False)) or str(read("lifecycle_state", "")).lower() == "completed"
        deadline_raw = read("deadline")
        deadline_dt = self._to_utc(deadline_raw)

        predicted_mins = self._resolve_predicted_duration_minutes(task)

        # Completed tasks have zero deadline risk
        if completed:
            return TaskRiskAssessment(
                task_id=task_id,
                title=title,
                risk_level=DeadlineRiskLevel.LOW,
                risk_score=0.0,
                remaining_minutes=None if deadline_dt is None else round((deadline_dt - current_time).total_seconds() / 60.0, 1),
                predicted_duration_minutes=predicted_mins,
                is_overdue=False,
                reasons=["Task completed successfully."],
                mitigation_suggestion=None,
                deadline_iso=deadline_dt.isoformat() if deadline_dt else None,
            )

        # Tasks without deadlines
        if deadline_dt is None:
            return TaskRiskAssessment(
                task_id=task_id,
                title=title,
                risk_level=DeadlineRiskLevel.NONE,
                risk_score=0.0,
                remaining_minutes=None,
                predicted_duration_minutes=predicted_mins,
                is_overdue=False,
                reasons=["No explicit deadline set."],
                mitigation_suggestion="Set a target completion deadline to enable proactive scheduling.",
                deadline_iso=None,
            )

        remaining_mins = (deadline_dt - current_time).total_seconds() / 60.0
        reasons: List[str] = []

        # 1. Check if already overdue
        if remaining_mins < 0:
            overdue_mins = abs(remaining_mins)
            if overdue_mins < 60:
                time_str = f"{int(overdue_mins)}m"
            else:
                time_str = f"{overdue_mins / 60.0:.1f}h"
            reasons.append(f"Deadline passed {time_str} ago ({deadline_dt.strftime('%b %d, %H:%M UTC')}).")
            return TaskRiskAssessment(
                task_id=task_id,
                title=title,
                risk_level=DeadlineRiskLevel.OVERDUE,
                risk_score=1.0,
                remaining_minutes=round(remaining_mins, 1),
                predicted_duration_minutes=predicted_mins,
                is_overdue=True,
                reasons=reasons,
                mitigation_suggestion="Prioritize immediately or reschedule deadline with user confirmation.",
                deadline_iso=deadline_dt.isoformat() if deadline_dt else None,
            )

        # 2. Check dependencies
        dep_ids_raw = read("dependencies", [])
        dep_ids: List[int] = []
        if isinstance(dep_ids_raw, str):
            try:
                import json
                parsed = json.loads(dep_ids_raw)
                if isinstance(parsed, list):
                    dep_ids = [int(x) for x in parsed if str(x).isdigit()]
            except Exception:
                pass
        elif isinstance(dep_ids_raw, list):
            dep_ids = [int(x) for x in dep_ids_raw if str(x).isdigit()]

        blocked_by_incomplete = False
        blocked_by_overdue = False
        incomplete_dep_titles: List[str] = []

        if dep_ids and all_tasks:
            task_map = {}
            for t in all_tasks:
                tid = t.get("id") if isinstance(t, dict) else getattr(t, "id", None)
                if tid is not None:
                    task_map[int(tid)] = t

            for did in dep_ids:
                dep_task = task_map.get(did)
                if dep_task:
                    dep_done = bool(dep_task.get("completed") if isinstance(dep_task, dict) else getattr(dep_task, "completed", False))
                    if not dep_done:
                        blocked_by_incomplete = True
                        dep_title = str(dep_task.get("title") if isinstance(dep_task, dict) else getattr(dep_task, "title", f"Task {did}"))
                        incomplete_dep_titles.append(f"#{did} '{dep_title}'")
                        dep_deadline = self._to_utc(dep_task.get("deadline") if isinstance(dep_task, dict) else getattr(dep_task, "deadline", None))
                        if dep_deadline and dep_deadline < current_time:
                            blocked_by_overdue = True

        # 3. Calculate risk ratio and score
        buffer_ratio = remaining_mins / max(5.0, predicted_mins)
        priority = int(read("priority", 3))

        # Base score from ratio:
        # buffer_ratio <= 1.0 means remaining time <= needed duration -> score >= 0.8
        # buffer_ratio == 2.0 means 2x duration available -> score ~ 0.4
        # buffer_ratio >= 4.0 means plenty of time -> score <= 0.2
        if buffer_ratio <= 1.0:
            score = 0.85 + (1.0 - min(1.0, buffer_ratio)) * 0.15
            reasons.append(f"Estimated duration ({int(predicted_mins)}m) exceeds or matches remaining time ({int(remaining_mins)}m).")
        elif buffer_ratio < 1.75:
            score = 0.55 + (1.75 - buffer_ratio) * 0.35
            reasons.append(f"Tight buffer: only {remaining_mins / 60.0:.1f}h remaining for {predicted_mins / 60.0:.1f}h of estimated work.")
        elif buffer_ratio < 3.0:
            score = 0.30 + (3.0 - buffer_ratio) * 0.15
            reasons.append(f"Moderate window: {remaining_mins / 60.0:.1f}h remaining before deadline.")
        else:
            score = max(0.05, 0.25 - (buffer_ratio - 3.0) * 0.03)

        # Apply priority and dependency adjustments
        if blocked_by_overdue:
            score = min(1.0, score + 0.30)
            reasons.append(f"Prerequisite {', '.join(incomplete_dep_titles)} is already overdue!")
        elif blocked_by_incomplete:
            score = min(0.95, score + 0.20)
            reasons.append(f"Waiting on incomplete prerequisite(s): {', '.join(incomplete_dep_titles)}.")

        if priority >= 4:
            score = min(1.0, score + 0.08)

        score = round(max(0.0, min(1.0, score)), 3)

        # Classify level
        if score >= 0.70 or buffer_ratio <= 1.15:
            level = DeadlineRiskLevel.HIGH
            mitigation = "Schedule this task in the next immediate focus block; clear prerequisite blockers."
        elif score >= 0.40 or buffer_ratio <= 2.2:
            level = DeadlineRiskLevel.MODERATE
            mitigation = "Plan to start today before competing tasks consume available working hours."
        else:
            level = DeadlineRiskLevel.LOW
            mitigation = "On track. Standard schedule alignment is sufficient."

        return TaskRiskAssessment(
            task_id=task_id,
            title=title,
            risk_level=level,
            risk_score=score,
            remaining_minutes=round(remaining_mins, 1),
            predicted_duration_minutes=predicted_mins,
            is_overdue=False,
            reasons=reasons,
            mitigation_suggestion=mitigation,
            deadline_iso=deadline_dt.isoformat() if deadline_dt else None,
        )

    def assess_all_tasks(
        self,
        tasks: List[Dict[str, Any] | Any],
        now: Optional[datetime] = None,
    ) -> List[TaskRiskAssessment]:
        """Assess all tasks in batch."""
        return [self.assess_task_risk(t, all_tasks=tasks, now=now) for t in tasks]

    def compute_daily_workload(
        self,
        user_id: int,
        tasks: List[Dict[str, Any] | Any],
        now: Optional[datetime] = None,
        working_hours_per_day: float = 8.0,
        target_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Compute an authoritative daily workload and capacity summary."""
        ref_time = target_date or now
        current_time = self._now(ref_time)
        today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        next_48h = current_time + timedelta(hours=48)

        assessments = self.assess_all_tasks(tasks, now=current_time)
        risk_map = {str(a.task_id): a for a in assessments}

        today_scheduled_tasks: List[Dict[str, Any]] = []
        overdue_tasks: List[Dict[str, Any]] = []
        high_risk_tasks: List[Dict[str, Any]] = []
        upcoming_deadline_tasks: List[Dict[str, Any]] = []

        total_workload_mins = 0.0
        completed_workload_mins = 0.0
        remaining_workload_mins = 0.0

        for t in tasks:
            def read(key: str, default: Any = None) -> Any:
                if isinstance(t, dict):
                    return t.get(key, default)
                return getattr(t, key, default)

            tid = str(read("id", read("task_id", 0)))
            title = str(read("title", f"Task {tid}"))
            completed = bool(read("completed", False)) or str(read("lifecycle_state", "")).lower() == "completed"
            
            # Times
            sched_start = self._to_utc(read("scheduled_start_time"))
            sched_end = self._to_utc(read("scheduled_end_time"))
            actual_start = self._to_utc(read("start_time"))
            actual_end = self._to_utc(read("end_time"))
            deadline_dt = self._to_utc(read("deadline"))

            # Effective scheduled time (or start time)
            is_today_scheduled = False
            effective_start = sched_start or actual_start
            if effective_start and today_start <= effective_start < today_end:
                is_today_scheduled = True
            elif actual_end and today_start <= actual_end < today_end:
                is_today_scheduled = True
            elif deadline_dt and today_start <= deadline_dt < today_end:
                # Due today is also counted in today's active workload
                is_today_scheduled = True

            predicted_mins = self._resolve_predicted_duration_minutes(t)
            actual_mins = float(read("actual_duration") or 0.0) if completed else 0.0

            risk = risk_map.get(tid)
            risk_dict = risk.to_dict() if risk else {
                "risk_level": "none", "risk_score": 0.0, "is_overdue": False, "reasons": []
            }

            task_summary_item = {
                "id": tid,
                "title": title,
                "task_type": str(read("task_type", "general")),
                "priority": int(read("priority", 3)),
                "estimated_duration": float(read("estimated_duration") or 60.0),
                "predicted_duration_minutes": predicted_mins,
                "actual_duration": actual_mins if completed else None,
                "completed": completed,
                "lifecycle_state": str(read("lifecycle_state", "created")),
                "scheduled_start_time": sched_start.isoformat() if sched_start else None,
                "scheduled_end_time": sched_end.isoformat() if sched_end else None,
                "deadline": deadline_dt.isoformat() if deadline_dt else None,
                "deadline_risk": risk_dict,
            }

            if is_today_scheduled:
                today_scheduled_tasks.append(task_summary_item)
                total_workload_mins += predicted_mins
                if completed:
                    completed_workload_mins += actual_mins if actual_mins > 0 else predicted_mins
                else:
                    remaining_workload_mins += predicted_mins

            if not completed:
                if risk and risk.is_overdue:
                    overdue_tasks.append(task_summary_item)
                elif risk and risk.risk_level == DeadlineRiskLevel.HIGH:
                    high_risk_tasks.append(task_summary_item)

                if deadline_dt and current_time <= deadline_dt <= next_48h:
                    upcoming_deadline_tasks.append(task_summary_item)

        # Capacity calculations
        available_work_minutes = max(60.0, working_hours_per_day * 60.0)
        # If part of today has passed (e.g. 14:00 and day ends at 20:00), remaining day capacity
        end_of_workday = today_start.replace(hour=20)
        if current_time < end_of_workday:
            remaining_day_minutes = max(60.0, (end_of_workday - max(today_start.replace(hour=8), current_time)).total_seconds() / 60.0)
        else:
            remaining_day_minutes = 60.0

        utilization_pct = round((remaining_workload_mins / max(1.0, available_work_minutes)) * 100.0, 1)

        # Cognitive energy budgeting
        deep_work_types = frozenset({
            "coding", "programming", "architecture", "design", "research",
            "analysis", "writing", "study", "engineering", "deep_work"
        })
        deep_work_mins = sum(
            t["predicted_duration_minutes"]
            for t in today_scheduled_tasks
            if str(t.get("task_type", "")).lower() in deep_work_types and not t.get("completed")
        )
        sustainable_deep_work_mins = 240.0
        cognitive_utilization = round((deep_work_mins / sustainable_deep_work_mins) * 100.0, 1)
        fatigue_risk = "high" if deep_work_mins > 300.0 else "moderate" if deep_work_mins > 210.0 else "low"

        cognitive_budget = {
            "deep_work_minutes": round(deep_work_mins, 1),
            "deep_work_hours": round(deep_work_mins / 60.0, 2),
            "sustainable_limit_minutes": sustainable_deep_work_mins,
            "sustainable_limit_hours": 4.0,
            "cognitive_utilization_pct": min(200.0, cognitive_utilization),
            "fatigue_risk": fatigue_risk,
            "deep_work_task_count": sum(
                1 for t in today_scheduled_tasks
                if str(t.get("task_type", "")).lower() in deep_work_types and not t.get("completed")
            ),
        }

        if overdue_tasks or (remaining_workload_mins > remaining_day_minutes * 1.2 and high_risk_tasks):
            verdict = "CRITICAL"
            verdict_message = f"Immediate action required: {len(overdue_tasks)} overdue task(s) and {len(high_risk_tasks)} high-risk task(s)."
        elif utilization_pct > 100.0 or high_risk_tasks:
            verdict = "AT_RISK"
            verdict_message = f"Workload exceeds standard day capacity ({utilization_pct}%). Consider rescheduling non-urgent items."
        elif fatigue_risk == "high":
            verdict = "FATIGUE_RISK"
            verdict_message = f"Cognitive budget warning: {round(deep_work_mins / 60.0, 1)}h of deep work scheduled exceeds sustainable limit."
        else:
            verdict = "FEASIBLE"
            verdict_message = f"Schedule is healthy ({utilization_pct}% utilized). All today's commitments fit within available working hours."

        return {
            "user_id": user_id,
            "date": today_start.strftime("%Y-%m-%d"),
            "as_of_time": current_time.isoformat(),
            "total_tasks": len(today_scheduled_tasks),
            "total_tasks_today": len(today_scheduled_tasks),
            "today_tasks_count": len(today_scheduled_tasks),
            "completed_tasks_today": sum(1 for t in today_scheduled_tasks if t["completed"]),
            "pending_tasks_today": sum(1 for t in today_scheduled_tasks if not t["completed"]),
            "total_workload_minutes": round(total_workload_mins, 1),
            "total_workload_hours": round(total_workload_mins / 60.0, 2),
            "completed_workload_minutes": round(completed_workload_mins, 1),
            "completed_workload_hours": round(completed_workload_mins / 60.0, 2),
            "remaining_workload_minutes": round(remaining_workload_mins, 1),
            "remaining_workload_hours": round(remaining_workload_mins / 60.0, 2),
            "available_work_minutes": round(available_work_minutes, 1),
            "available_work_hours": round(available_work_minutes / 60.0, 2),
            "capacity_hours": round(available_work_minutes / 60.0, 2),
            "capacity_utilization_pct": min(200.0, utilization_pct),
            "cognitive_budget": cognitive_budget,
            "workload_status": "overloaded" if utilization_pct > 100 else "near_capacity" if utilization_pct > 80 else "light" if utilization_pct < 40 else "balanced",
            "overdue_tasks_count": len(overdue_tasks),
            "high_risk_tasks_count": len(high_risk_tasks),
            "upcoming_deadlines_count": len(upcoming_deadline_tasks),
            "verdict": verdict,
            "verdict_message": verdict_message,
            "today_scheduled_tasks": today_scheduled_tasks,
            "overdue_tasks": overdue_tasks,
            "high_risk_tasks": high_risk_tasks,
            "upcoming_deadlines": upcoming_deadline_tasks,
            "upcoming_deadline_tasks": upcoming_deadline_tasks,
            "scheduled_timeline": today_scheduled_tasks,
        }
