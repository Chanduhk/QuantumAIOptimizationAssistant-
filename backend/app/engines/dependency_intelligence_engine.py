from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from backend.app.domain.dependency_model import TaskDependency
from backend.app.knowledge.dependency_graph import DependencyGraph


class DependencyIntelligenceEngine:
    """Analyze task dependencies and enrich tasks with dependency-aware signals."""

    def __init__(self, dependency_graph: DependencyGraph | None = None) -> None:
        self.dependency_graph = dependency_graph or DependencyGraph()

    def analyze_dependencies(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Return dependency health, ordering, critical path, and bottlenecks."""
        normalized_tasks = self._validate_tasks(tasks)
        self._load_inline_dependencies(normalized_tasks)
        completed_task_ids = self._completed_task_ids(normalized_tasks)
        critical_path = self.dependency_graph.get_critical_path()
        cycles = self.dependency_graph.detect_cycles()
        bottlenecks = self.detect_bottlenecks()
        enriched = self.enrich_tasks_with_dependencies(normalized_tasks)
        return {
            "blocked_tasks": [task["id"] for task in enriched if task.get("blocked")],
            "critical_path": critical_path,
            "critical_path_length": len(critical_path),
            "cycles": cycles,
            "execution_order": self.recommend_execution_order(normalized_tasks),
            "bottlenecks": bottlenecks,
            "completed_task_ids": sorted(completed_task_ids),
        }

    def detect_blocked_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return task copies that are blocked by incomplete hard dependencies."""
        return [task for task in self.enrich_tasks_with_dependencies(tasks) if task.get("blocked")]

    def detect_bottlenecks(self) -> List[Dict[str, Any]]:
        """Return tasks with downstream dependency impact."""
        bottlenecks: List[Dict[str, Any]] = []
        for task_id in sorted(self.dependency_graph.tasks):
            direct_dependents = self.dependency_graph.get_dependents(task_id)
            downstream_count = self._downstream_count(task_id)
            if direct_dependents:
                bottlenecks.append(
                    {
                        "task_id": task_id,
                        "direct_dependents": len(direct_dependents),
                        "downstream_dependents": downstream_count,
                        "dependency_impact_score": self._impact_score(downstream_count),
                    }
                )
        return sorted(
            bottlenecks,
            key=lambda item: (-item["dependency_impact_score"], str(item["task_id"])),
        )

    def recommend_execution_order(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """Return dependency-first task ids, excluding blocked cycles."""
        normalized_tasks = self._validate_tasks(tasks)
        self._load_inline_dependencies(normalized_tasks)
        task_ids = {task["id"] for task in normalized_tasks}
        for task_id in task_ids:
            self.dependency_graph.tasks.add(task_id)
        ordered = self.dependency_graph.topological_sort()
        return [task_id for task_id in ordered if task_id in task_ids]

    def enrich_tasks_with_dependencies(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add dependency metadata to task copies without modifying callers' task state."""
        normalized_tasks = self._validate_tasks(tasks)
        self._load_inline_dependencies(normalized_tasks)
        completed_task_ids = self._completed_task_ids(normalized_tasks)
        critical_path = self.dependency_graph.get_critical_path()
        critical_index = {task_id: index for index, task_id in enumerate(critical_path)}
        enriched: List[Dict[str, Any]] = []
        for task in normalized_tasks:
            task_id = task["id"]
            task_copy = dict(task)
            blocked = self.dependency_graph.is_blocked(task_id, completed_task_ids)
            downstream_count = self._downstream_count(task_id)
            critical_priority = self._critical_path_priority(task_id, critical_index, len(critical_path))
            task_copy["blocked"] = blocked
            task_copy["dependency_score"] = round(self._dependency_score(blocked, downstream_count, critical_priority), 2)
            task_copy["critical_path_priority"] = round(critical_priority, 2)
            task_copy["dependency_impact_score"] = self._impact_score(downstream_count)
            enriched.append(task_copy)
        return enriched

    def apply_goal_dependency_context(
        self,
        goal_health: Dict[str, Any],
        tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return a goal health copy enriched with dependency risk context."""
        if not isinstance(goal_health, dict):
            raise ValueError("goal_health must be a dictionary.")
        enriched_tasks = self.enrich_tasks_with_dependencies(tasks)
        blocked_count = sum(1 for task in enriched_tasks if task.get("blocked"))
        max_impact = max((float(task.get("dependency_impact_score", 0.0)) for task in enriched_tasks), default=0.0)
        result = dict(goal_health)
        result["blocked_task_count"] = blocked_count
        result["max_dependency_impact_score"] = round(max_impact, 2)
        result["dependency_risk_score"] = round(min(100.0, (blocked_count * 20.0) + max_impact), 2)
        if result["dependency_risk_score"] >= 40.0 and result.get("health_status") == "healthy":
            result["health_status"] = "at_risk"
        return result

    def compute_downstream_slack_hours(
        self, tasks: List[Dict[str, Any]], now: datetime | None = None
    ) -> Dict[str, Optional[float]]:
        """Calculate downstream slack buffer in hours for each task in the workload."""
        now = now or datetime.now(timezone.utc)
        normalized_tasks = self._validate_tasks(tasks)
        self._load_inline_dependencies(normalized_tasks)

        task_dict = {t["id"]: t for t in normalized_tasks}
        deadlines: Dict[str, Optional[datetime]] = {}
        durations_hours: Dict[str, float] = {}

        for tid, t in task_dict.items():
            dur_mins = float(t.get("estimated_duration") or 60.0)
            unit = str(t.get("estimated_duration_unit", "minutes")).lower()
            if unit in ("hours", "hour", "h"):
                dur_hours = dur_mins
            else:
                dur_hours = dur_mins / 60.0
            durations_hours[tid] = max(0.1, dur_hours)

            raw_dl = t.get("deadline")
            dl_dt = None
            if raw_dl:
                if isinstance(raw_dl, datetime):
                    dl_dt = raw_dl if raw_dl.tzinfo else raw_dl.replace(tzinfo=timezone.utc)
                elif isinstance(raw_dl, str) and raw_dl.strip():
                    try:
                        clean = raw_dl.replace("Z", "+00:00")
                        dl_dt = datetime.fromisoformat(clean)
                        if dl_dt.tzinfo is None:
                            dl_dt = dl_dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        dl_dt = None
            deadlines[tid] = dl_dt

        # Reverse topological order to propagate latest allowable finish backwards
        order = self.dependency_graph.topological_sort()
        reverse_order = list(reversed(order))

        latest_finish: Dict[str, Optional[datetime]] = {}
        for tid in reverse_order:
            if tid not in task_dict:
                continue
            downstream = self.dependency_graph.get_dependents(tid)
            candidate_finishes = []
            if deadlines.get(tid):
                candidate_finishes.append(deadlines[tid])

            for dep in downstream:
                dep_id = dep.task_id
                if dep_id in latest_finish and latest_finish[dep_id] is not None:
                    dep_start = latest_finish[dep_id] - timedelta(hours=durations_hours.get(dep_id, 1.0))
                    candidate_finishes.append(dep_start)
                elif deadlines.get(dep_id):
                    dep_start = deadlines[dep_id] - timedelta(hours=durations_hours.get(dep_id, 1.0))
                    candidate_finishes.append(dep_start)

            if candidate_finishes:
                latest_finish[tid] = min(candidate_finishes)
            else:
                latest_finish[tid] = None

        slack_by_task: Dict[str, Optional[float]] = {}
        for tid in task_dict:
            lf = latest_finish.get(tid)
            if lf is not None:
                earliest_finish = now + timedelta(hours=durations_hours.get(tid, 1.0))
                slack_secs = (lf - earliest_finish).total_seconds()
                slack_by_task[tid] = round(slack_secs / 3600.0, 2)
            else:
                slack_by_task[tid] = None

        return slack_by_task

    def get_dependency_graph_topology(
        self, tasks: List[Dict[str, Any]], now: datetime | None = None
    ) -> Dict[str, Any]:
        """Return full topology nodes, edges, critical path, bottlenecks, and slack."""
        now = now or datetime.now(timezone.utc)
        normalized_tasks = self._validate_tasks(tasks)
        self._load_inline_dependencies(normalized_tasks)
        completed_ids = self._completed_task_ids(normalized_tasks)
        critical_path = self.dependency_graph.get_critical_path()
        cycles = self.dependency_graph.detect_cycles()
        bottlenecks = self.detect_bottlenecks()
        slack_map = self.compute_downstream_slack_hours(normalized_tasks, now=now)

        nodes = []
        for task in normalized_tasks:
            tid = task["id"]
            blocked = self.dependency_graph.is_blocked(tid, completed_ids)
            downstream_count = self._downstream_count(tid)
            is_cp = tid in critical_path
            slack = slack_map.get(tid)
            nodes.append({
                "id": tid,
                "title": task.get("title", f"Task {tid}"),
                "task_type": task.get("task_type", "general"),
                "priority": task.get("priority", 3),
                "completed": bool(task.get("completed")),
                "is_blocked": blocked,
                "blocking_count": downstream_count,
                "is_critical_path": is_cp,
                "downstream_slack_hours": slack,
                "dependencies": self._inline_dependency_ids(task),
            })

        edges = []
        for src_id, dep_list in self.dependency_graph.dependencies.items():
            for dep in dep_list:
                edges.append({
                    "from": dep.depends_on_task_id,
                    "to": dep.task_id,
                    "type": dep.dependency_type,
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "critical_path": critical_path,
            "critical_path_length": len(critical_path),
            "cycles": cycles,
            "bottlenecks": bottlenecks,
            "summary": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "blocked_nodes": sum(1 for n in nodes if n["is_blocked"]),
                "critical_path_length": len(critical_path),
            },
        }

    def _load_inline_dependencies(self, tasks: List[Dict[str, Any]]) -> None:
        task_ids = {task["id"] for task in tasks}
        title_to_id = {str(task.get("title", "")).strip().lower(): task["id"] for task in tasks if task.get("title")}
        for task_id in task_ids:
            self.dependency_graph.tasks.add(task_id)
        for task in tasks:
            task_id = task["id"]
            for raw_dep in self._inline_dependency_ids(task):
                depends_on_task_id = raw_dep
                if depends_on_task_id not in task_ids and depends_on_task_id not in self.dependency_graph.tasks:
                    dep_lower = raw_dep.lower()
                    if dep_lower in title_to_id:
                        depends_on_task_id = title_to_id[dep_lower]
                    else:
                        matches = [tid for title, tid in title_to_id.items() if dep_lower in title or title in dep_lower]
                        if matches:
                            depends_on_task_id = matches[0]
                if depends_on_task_id not in task_ids and depends_on_task_id not in self.dependency_graph.tasks:
                    raise ValueError("depends_on_task_id must refer to a known task.")
                dependency_id = f"inline:{task_id}:{depends_on_task_id}"
                self.dependency_graph.add_dependency(
                    TaskDependency(
                        dependency_id=dependency_id,
                        task_id=task_id,
                        depends_on_task_id=depends_on_task_id,
                        dependency_type="hard",
                    )
                )

    def _inline_dependency_ids(self, task: Dict[str, Any]) -> List[str]:
        raw_dependencies = task.get("depends_on_task_ids", task.get("dependencies", []))
        if raw_dependencies in (None, ""):
            return []
        if isinstance(raw_dependencies, (str, int)) and not isinstance(raw_dependencies, bool):
            raw_values: Iterable[Any] = [raw_dependencies]
        elif isinstance(raw_dependencies, (list, tuple, set)):
            raw_values = raw_dependencies
        else:
            raise ValueError("depends_on_task_ids must be a list of task ids.")
        dependency_ids: List[str] = []
        for value in raw_values:
            if value is None or isinstance(value, bool):
                raise ValueError("depends_on_task_ids must contain non-empty strings.")
            if isinstance(value, (str, int)):
                s_val = str(value).strip()
                if not s_val:
                    raise ValueError("depends_on_task_ids must contain non-empty strings.")
                dependency_ids.append(s_val)
            else:
                raise ValueError("depends_on_task_ids must contain non-empty strings.")
        return sorted(set(dependency_ids))

    def _validate_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        normalized: List[Dict[str, Any]] = []
        seen_ids = set()
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            raw_id = task.get("id")
            if raw_id is None or isinstance(raw_id, bool):
                raise ValueError("Each task requires a non-empty string id.")
            task_id = str(raw_id).strip()
            if not task_id:
                raise ValueError("Each task requires a non-empty string id.")
            if task_id in seen_ids:
                raise ValueError("task ids must be unique.")
            seen_ids.add(task_id)
            if task.get("estimated_duration") is not None:
                self._finite_number(task["estimated_duration"], "estimated_duration")
            normalized_task = dict(task)
            normalized_task["id"] = task_id
            normalized.append(normalized_task)
        return normalized

    def _completed_task_ids(self, tasks: List[Dict[str, Any]]) -> set[str]:
        task_completed = {task["id"] for task in tasks if bool(task.get("completed"))}
        persisted = getattr(self, "persisted_completed_task_ids", set())
        return task_completed | {str(cid) for cid in persisted}

    def _downstream_count(self, task_id: str) -> int:
        visited = set()

        def visit(current_task_id: str) -> None:
            for dependency in self.dependency_graph.get_dependents(current_task_id):
                dependent_id = dependency.task_id
                if dependent_id in visited:
                    continue
                visited.add(dependent_id)
                visit(dependent_id)

        visit(task_id)
        return len(visited)

    def _critical_path_priority(self, task_id: str, critical_index: Dict[str, int], path_length: int) -> float:
        if path_length <= 1 or task_id not in critical_index:
            return 0.0
        remaining_chain = path_length - critical_index[task_id]
        return min(100.0, remaining_chain * 15.0)

    def _dependency_score(self, blocked: bool, downstream_count: int, critical_path_priority: float) -> float:
        if blocked:
            return -100.0
        return min(100.0, (downstream_count * 10.0) + critical_path_priority)

    def _impact_score(self, downstream_count: int) -> float:
        return round(min(100.0, downstream_count * 20.0), 2)

    def _finite_number(self, value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return number
