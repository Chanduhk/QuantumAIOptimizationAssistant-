from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List

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

    def _load_inline_dependencies(self, tasks: List[Dict[str, Any]]) -> None:
        task_ids = {task["id"] for task in tasks}
        for task_id in task_ids:
            self.dependency_graph.tasks.add(task_id)
        for task in tasks:
            task_id = task["id"]
            for depends_on_task_id in self._inline_dependency_ids(task):
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
        if isinstance(raw_dependencies, str):
            raw_values: Iterable[Any] = [raw_dependencies]
        elif isinstance(raw_dependencies, list):
            raw_values = raw_dependencies
        else:
            raise ValueError("depends_on_task_ids must be a list of task ids.")
        dependency_ids: List[str] = []
        for value in raw_values:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("depends_on_task_ids must contain non-empty strings.")
            dependency_ids.append(value.strip())
        return sorted(set(dependency_ids))

    def _validate_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        normalized: List[Dict[str, Any]] = []
        seen_ids = set()
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            task_id = task.get("id")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("Each task requires a non-empty string id.")
            task_id = task_id.strip()
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
        return {task["id"] for task in tasks if bool(task.get("completed"))}

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
