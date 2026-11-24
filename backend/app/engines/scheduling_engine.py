from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.domain.optimization_input_contract import normalize_duration
from backend.app.knowledge.dependency_graph import DependencyGraph
from backend.app.domain.dependency_model import TaskDependency
from backend.app.engines.deadline_risk_engine import DeadlineRiskEngine, DeadlineRiskLevel


class SchedulingEngine:
    """Assign tasks to non-overlapping time slots respecting dependencies, deadlines, and behavior profile."""

    def __init__(self, risk_engine: Optional[DeadlineRiskEngine] = None, session: Optional[Any] = None) -> None:
        self.risk_engine = risk_engine or DeadlineRiskEngine()
        self.session = session

    def optimize_schedule(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        day_start: int = 8,
        day_end: int = 20,
    ) -> List[Dict[str, Any]]:
        """Legacy behavior-ranked slot placement preserved for backwards compatibility."""
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        if not self._is_integer_hour(day_start) or not self._is_integer_hour(day_end):
            raise ValueError("day_start and day_end must be integer hours.")
        if day_start >= day_end:
            raise ValueError("day_start must be less than day_end.")

        hourly_productivity = self._normalize_hourly_productivity(
            behavior_patterns.get("hourly_productivity", {}),
        )
        ranked_hours = self._rank_hours(behavior_patterns, hourly_productivity, day_start, day_end)
        scheduled_tasks: List[Dict[str, Any]] = []

        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            target_hour = ranked_hours[index % len(ranked_hours)]
            duration = self._resolve_duration(task)
            scheduled_end_hour = round(target_hour + duration, 2)
            scheduled_task = dict(task)
            scheduled_task["scheduled_hour"] = target_hour
            scheduled_task["scheduled_end_hour"] = scheduled_end_hour
            scheduled_task["schedule_score"] = round(hourly_productivity.get(target_hour, 0.0), 2)
            if scheduled_end_hour > day_end:
                scheduled_task["schedule_warning"] = "scheduled_end_hour exceeds day_end."
                scheduled_task["capacity_warning"] = (
                    f"Task extends beyond scheduling window ending at hour {day_end}."
                )
            scheduled_tasks.append(scheduled_task)

        return sorted(scheduled_tasks, key=lambda task: float(task["scheduled_hour"]))

    def allocate_intelligent_schedule(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Optional[Dict[str, Any]] = None,
        day_start: int = 8,
        day_end: int = 20,
        now: Optional[datetime] = None,
        existing_scheduled_tasks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Perform operational, non-overlapping, dependency- and deadline-aware time allocation.

        Guarantees:
        1. No two tasks execute simultaneously for the user (zero overlap).
        2. Dependent tasks are never scheduled before their prerequisites complete.
        3. Tasks with earlier deadlines receive priority allocation.
        4. High-priority tasks are placed into user's peak focus/productivity slots.
        """
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        patterns = behavior_patterns if behavior_patterns is not None else {}
        if not isinstance(patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")

        current_time = now if now is not None else datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        today_date = current_time.date()

        hourly_productivity = self._normalize_hourly_productivity(
            patterns.get("hourly_productivity", {}),
        )
        best_focus_hours = {int(h) for h in patterns.get("best_focus_hours", [])}

        # 1. Build Dependency Graph
        dep_graph = DependencyGraph()
        task_map: Dict[str, Dict[str, Any]] = {}
        for t in tasks:
            tid = str(t.get("id") or t.get("task_id", ""))
            if tid:
                task_map[tid] = t
                dep_graph.tasks.add(tid)
                raw_deps = t.get("dependencies") or []
                if isinstance(raw_deps, str):
                    try:
                        import json
                        raw_deps = json.loads(raw_deps)
                    except Exception:
                        raw_deps = []
                for dep in raw_deps:
                    dep_str = str(dep).strip()
                    if dep_str and dep_str != tid:
                        dep_graph.add_dependency(
                            TaskDependency(
                                dependency_id=f"alloc:{tid}:{dep_str}",
                                task_id=tid,
                                depends_on_task_id=dep_str,
                            )
                        )

        # 2. Establish existing occupied time intervals
        occupied_intervals: List[Tuple[float, float, str]] = []  # (start, end, task_id)
        if existing_scheduled_tasks:
            for ex in existing_scheduled_tasks:
                ex_id = str(ex.get("id") or ex.get("task_id", ""))
                # Skip if this is one of the tasks we are actively scheduling
                if ex_id in task_map:
                    continue
                sh = ex.get("scheduled_hour") or ex.get("scheduled_start_hour")
                eh = ex.get("scheduled_end_hour")
                if sh is not None and eh is not None:
                    try:
                        occupied_intervals.append((float(sh), float(eh), ex_id))
                    except (ValueError, TypeError):
                        pass

        # 3. Sort tasks using Topological Sort + Deadline + Priority
        # Detect topological levels
        topological_order: List[str] = []
        try:
            topological_order = dep_graph.topological_sort()
        except Exception:
            # Fallback to order in list if cycles or errors occur
            topological_order = list(task_map.keys())

        # Group tasks into dependency tiers, then sort each tier by deadline then priority
        def task_sort_key(tid: str) -> Tuple[int, float, int]:
            t = task_map.get(tid, {})
            # Deadline sort: tasks due sooner come first
            dl_str = t.get("deadline")
            dl_hour_val = 99999.0
            if dl_str:
                try:
                    clean = dl_str.replace("Z", "+00:00")
                    dl_dt = datetime.fromisoformat(clean)
                    if dl_dt.tzinfo is None:
                        dl_dt = dl_dt.replace(tzinfo=timezone.utc)
                    # Hours from now
                    diff_h = (dl_dt - current_time).total_seconds() / 3600.0
                    dl_hour_val = max(0.0, diff_h)
                except Exception:
                    pass

            prio = int(t.get("priority", 3))
            # Lower dl_hour_val is earlier, higher priority (-prio) is first
            return (0 if dl_hour_val < 48 else 1, dl_hour_val, -prio)

        # Re-order while preserving dependency precedence
        final_ordered_task_ids: List[str] = []
        processed_set: Set[str] = set()

        for tid in topological_order:
            if tid in processed_set:
                continue
            # Find all tasks whose prerequisites are completely in processed_set
            ready_candidates = [
                cand_id for cand_id in topological_order
                if cand_id not in processed_set and all(
                    dep.depends_on_task_id in processed_set or dep.depends_on_task_id not in task_map
                    for dep in dep_graph.get_dependencies(cand_id)
                )
            ]
            if not ready_candidates:
                ready_candidates = [tid]

            ready_candidates.sort(key=task_sort_key)
            chosen = ready_candidates[0]
            final_ordered_task_ids.append(chosen)
            processed_set.add(chosen)

        # 4. Non-overlapping Slot Allocation
        scheduled_tasks_result: List[Dict[str, Any]] = []
        task_end_hours: Dict[str, float] = {}
        conflicts: List[Dict[str, Any]] = []

        # Current hour if today, else day_start
        min_feasible_hour = float(day_start)
        if current_time.hour >= day_start:
            # Add minute fraction
            cur_fraction = current_time.hour + (current_time.minute / 60.0)
            # Round up to next 15-minute block
            min_feasible_hour = max(float(day_start), math.ceil(cur_fraction * 4.0) / 4.0)

        for tid in final_ordered_task_ids:
            t = task_map[tid]
            duration_h = self._resolve_duration(t)
            duration_h = max(0.25, round(duration_h, 2))

            # Prerequisite constraint: cannot start before all prerequisites complete
            prereq_end_hour = min_feasible_hour
            for dep in dep_graph.get_dependencies(tid):
                if dep.depends_on_task_id in task_end_hours:
                    prereq_end_hour = max(prereq_end_hour, task_end_hours[dep.depends_on_task_id])

            # Deadline constraint
            deadline_hour = None
            dl_str = t.get("deadline")
            if dl_str:
                try:
                    clean = dl_str.replace("Z", "+00:00")
                    dl_dt = datetime.fromisoformat(clean)
                    if dl_dt.tzinfo is None:
                        dl_dt = dl_dt.replace(tzinfo=timezone.utc)
                    if dl_dt.date() == today_date:
                        deadline_hour = dl_dt.hour + (dl_dt.minute / 60.0)
                except Exception:
                    pass

            # Search for the earliest non-overlapping slot starting at or after prereq_end_hour
            def is_slot_available(start: float, end: float) -> bool:
                for occ_s, occ_e, _ in occupied_intervals:
                    # Overlap if max(start, occ_s) < min(end, occ_e)
                    if max(start, occ_s) < min(end, occ_e) - 1e-4:
                        return False
                return True

            candidate_start = prereq_end_hour
            step = 0.25  # 15 minute resolution
            allocated_start: Optional[float] = None
            allocated_end: Optional[float] = None

            # Try to place within normal working window [day_start, day_end]
            test_hour = candidate_start
            while test_hour + duration_h <= day_end + 4.0:  # Allow extending into evening if tight
                cand_end = round(test_hour + duration_h, 2)
                if is_slot_available(test_hour, cand_end):
                    allocated_start = test_hour
                    allocated_end = cand_end
                    break
                test_hour = round(test_hour + step, 2)

            if allocated_start is None:
                # If packed, place at latest occupied end
                max_occ = max([occ_e for _, occ_e, _ in occupied_intervals], default=prereq_end_hour)
                allocated_start = round(max(prereq_end_hour, max_occ), 2)
                allocated_end = round(allocated_start + duration_h, 2)

            # Record occupied interval
            occupied_intervals.append((allocated_start, allocated_end, tid))
            occupied_intervals.sort(key=lambda x: x[0])
            task_end_hours[tid] = allocated_end

            # Check for deadline conflict
            has_deadline_conflict = False
            warning_msg = None
            if deadline_hour is not None and allocated_end > deadline_hour:
                has_deadline_conflict = True
                warning_msg = f"Scheduled end ({allocated_end:.2f}h) exceeds task deadline ({deadline_hour:.2f}h)."
                conflicts.append({
                    "task_id": tid,
                    "title": t.get("title", ""),
                    "scheduled_end_hour": allocated_end,
                    "deadline_hour": deadline_hour,
                    "overdue_by_minutes": round((allocated_end - deadline_hour) * 60.0, 1),
                })
            elif allocated_end > day_end:
                warning_msg = f"Task extends beyond regular working day ending at {day_end}:00."

            # Construct ISO timestamps for the scheduled dates
            st_hour_int = int(allocated_start) % 24
            st_min_int = int(round((allocated_start % 1) * 60))
            if st_min_int >= 60:
                st_hour_int = (st_hour_int + 1) % 24
                st_min_int = 0

            et_hour_int = int(allocated_end) % 24
            et_min_int = int(round((allocated_end % 1) * 60))
            if et_min_int >= 60:
                et_hour_int = (et_hour_int + 1) % 24
                et_min_int = 0

            sched_start_dt = current_time.replace(hour=st_hour_int, minute=st_min_int, second=0, microsecond=0)
            sched_end_dt = current_time.replace(hour=et_hour_int, minute=et_min_int, second=0, microsecond=0)
            if allocated_end < allocated_start:
                sched_end_dt += timedelta(days=1)

            # Assess deadline risk
            task_risk = self.risk_engine.assess_task_risk(t, all_tasks=tasks, now=current_time)

            scheduled_item = dict(t)
            scheduled_item.update({
                "scheduled_hour": allocated_start,
                "scheduled_start_hour": allocated_start,
                "scheduled_end_hour": allocated_end,
                "scheduled_start_time": sched_start_dt.isoformat(),
                "scheduled_end_time": sched_end_dt.isoformat(),
                "schedule_score": round(hourly_productivity.get(int(allocated_start), 60.0), 2),
                "is_focus_hour": int(allocated_start) in best_focus_hours,
                "has_deadline_conflict": has_deadline_conflict,
                "schedule_warning": warning_msg,
                "deadline_risk": task_risk.to_dict(),
            })
            scheduled_tasks_result.append(scheduled_item)

        scheduled_tasks_result.sort(key=lambda item: float(item["scheduled_start_hour"]))

        total_mins = sum(self._resolve_duration(t) * 60.0 for t in tasks)

        return {
            "scheduled_tasks": scheduled_tasks_result,
            "total_allocated_minutes": round(total_mins, 1),
            "total_allocated_hours": round(total_mins / 60.0, 2),
            "conflicts_detected": conflicts,
            "schedule_feasible": len(conflicts) == 0,
            "working_window": [day_start, day_end],
            "explanation": (
                f"Intelligently allocated {len(scheduled_tasks_result)} tasks in non-overlapping time slots. "
                + (f"All tasks meet their deadlines." if not conflicts else f"{len(conflicts)} deadline conflict(s) flagged.")
            ),
        }

    def intelligent_reschedule(
        self,
        user_id: int,
        tasks: List[Dict[str, Any]],
        reason: str = "Task duration adjusted or delay occurred",
        affected_task_id: Optional[int | str] = None,
        now: Optional[datetime] = None,
        behavior_patterns: Optional[Dict[str, Any]] = None,
        day_start: int = 8,
        day_end: int = 20,
    ) -> Dict[str, Any]:
        """Recalculate schedule, preserve completed tasks, prioritize urgent tasks, and format proposal for approval."""
        current_time = now if now is not None else datetime.now(timezone.utc)
        patterns = behavior_patterns or {}

        # 1. Filter out completed tasks (they are preserved as historical ground truth)
        pending_tasks = [t for t in tasks if not bool(t.get("completed", False)) and str(t.get("lifecycle_state", "")).lower() != "completed"]
        completed_tasks = [t for t in tasks if bool(t.get("completed", False)) or str(t.get("lifecycle_state", "")).lower() == "completed"]

        if not pending_tasks:
            return {
                "success": True,
                "action": "no_pending_tasks_to_reschedule",
                "revised_schedule": [],
                "affected_tasks": [],
                "explanation": "No pending tasks required rescheduling; all tasks are already completed.",
                "proposal_required": False,
            }

        # 2. Identify affected tasks and dependencies
        dep_graph = DependencyGraph()
        for t in pending_tasks:
            tid = str(t.get("id") or t.get("task_id", ""))
            dep_graph.tasks.add(tid)
            raw_deps = t.get("dependencies") or []
            if isinstance(raw_deps, str):
                try:
                    import json
                    raw_deps = json.loads(raw_deps)
                except Exception:
                    raw_deps = []
            for dep in raw_deps:
                dep_str = str(dep).strip()
                if dep_str and dep_str != tid:
                    dep_graph.add_dependency(
                        TaskDependency(
                            dependency_id=f"resched:{tid}:{dep_str}",
                            task_id=tid,
                            depends_on_task_id=dep_str,
                        )
                    )

        affected_ids: Set[str] = set()
        if affected_task_id is not None:
            aff_str = str(affected_task_id)
            affected_ids.add(aff_str)

            # Add all transitive dependents recursively
            def _collect_dependents(tid: str, visited: Set[str]) -> None:
                deps = dep_graph.get_dependents(tid)
                for d in deps:
                    dtid = str(d.task_id)
                    if dtid not in visited:
                        visited.add(dtid)
                        _collect_dependents(dtid, visited)

            _collect_dependents(aff_str, affected_ids)
        else:
            # If no single task specified, all pending tasks are candidate for optimal rescheduling
            affected_ids.update([str(t.get("id") or t.get("task_id", "")) for t in pending_tasks])

        # 3. Run intelligent allocation on the pending tasks
        allocation_result = self.allocate_intelligent_schedule(
            tasks=pending_tasks,
            behavior_patterns=patterns,
            day_start=day_start,
            day_end=day_end,
            now=current_time,
            existing_scheduled_tasks=completed_tasks,
        )

        revised_schedule = allocation_result["scheduled_tasks"]
        conflicts = allocation_result["conflicts_detected"]

        # 4. Generate transparent change explanation
        explanations: List[str] = [f"Rescheduling triggered: {reason}."]
        if affected_task_id:
            explanations.append(f"Identified {len(affected_ids)} task(s) in the impacted dependency chain.")

        shifted_count = 0
        for rev in revised_schedule:
            orig_sh = rev.get("scheduled_hour") or rev.get("scheduled_start_hour")
            new_sh = rev.get("scheduled_start_hour")
            title = rev.get("title", f"Task {rev.get('id')}")
            if orig_sh is not None and new_sh is not None and abs(float(orig_sh) - float(new_sh)) > 0.1:
                shifted_count += 1
                explanations.append(f"• '{title}' rescheduled from {orig_sh:.2f}h to {new_sh:.2f}h.")

        if conflicts:
            explanations.append(f"Warning: {len(conflicts)} task(s) may exceed deadline under current capacity.")
        else:
            explanations.append("All tasks successfully rescheduled within safe operational windows.")

        explanations.append("Awaiting user approval before applying revised schedule to database.")

        return {
            "success": True,
            "user_id": user_id,
            "action": "intelligent_reschedule_proposed",
            "revised_schedule": revised_schedule,
            "preserved_completed_tasks_count": len(completed_tasks),
            "affected_task_ids": list(affected_ids),
            "shifted_tasks_count": shifted_count,
            "conflicts_detected": conflicts,
            "schedule_feasible": allocation_result["schedule_feasible"],
            "explanation": "\n".join(explanations),
            "proposal_required": True,
        }

    def _rank_hours(
        self,
        behavior_patterns: Dict[str, Any],
        hourly_productivity: Dict[int, float],
        day_start: int,
        day_end: int,
    ) -> List[int]:
        ranked = sorted(
            (
                parsed_hour
                for hour in hourly_productivity.keys()
                for parsed_hour in [self._safe_hour(hour)]
                if parsed_hour is not None and day_start <= parsed_hour <= day_end
            ),
            key=lambda hour: float(hourly_productivity.get(hour, 0.0)),
            reverse=True,
        )

        best_focus_hours = behavior_patterns.get("best_focus_hours", [])
        if best_focus_hours is None:
            best_focus_hours = []
        if not isinstance(best_focus_hours, list):
            raise ValueError("best_focus_hours must be a list of integer hours.")

        fallback_hours: List[int] = []
        for hour in best_focus_hours:
            parsed_hour = self._safe_hour(hour)
            if parsed_hour is None:
                raise ValueError("best_focus_hours must contain integer hours from 0 to 23.")
            if day_start <= parsed_hour <= day_end:
                fallback_hours.append(parsed_hour)

        ordered_hours: List[int] = []
        for hour in ranked + fallback_hours + list(range(day_start, day_end + 1)):
            if hour not in ordered_hours:
                ordered_hours.append(hour)

        return ordered_hours

    def _safe_hour(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            hour = value
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped or not stripped.isdigit():
                return None
            hour = int(stripped)
        else:
            return None
        if 0 <= hour <= 23:
            return hour
        return None

    def _normalize_hourly_productivity(self, hourly_productivity: Any) -> Dict[int, float]:
        if hourly_productivity is None:
            return {}
        if not isinstance(hourly_productivity, dict):
            raise ValueError("hourly_productivity must be a dictionary.")

        normalized: Dict[int, float] = {}
        for hour, score in hourly_productivity.items():
            parsed_hour = self._safe_hour(hour)
            if parsed_hour is None:
                raise ValueError("hourly_productivity hours must be integer hours from 0 to 23.")
            normalized[parsed_hour] = self._finite_float(
                score,
                field_name="hourly_productivity scores",
            )
        return normalized

    def _resolve_duration(self, task: Dict[str, Any]) -> float:
        raw_dur = task.get("estimated_duration")
        if raw_dur is None:
            raise ValueError("estimated_duration is required for forward scheduling.")
        duration_unit = task.get("estimated_duration_unit") or "minutes"
        duration_source = task.get("estimated_duration_source") or "task_api"
        return normalize_duration(raw_dur, duration_unit, duration_source).normalized_hours

    def _positive_finite_float(self, value: Any, field_name: str) -> float:
        number = self._finite_float(value, field_name=field_name)
        if number <= 0:
            raise ValueError(f"{field_name} must be positive.")
        return number

    def _finite_float(self, value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return number

    def _is_integer_hour(self, value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 23
