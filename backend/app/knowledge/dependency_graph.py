from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Iterable, List, Set

from backend.app.domain.dependency_model import TaskDependency


class DependencyGraph:
    """Deterministic in-memory graph for task dependency analysis."""

    def __init__(self) -> None:
        self.dependencies: Dict[str, List[TaskDependency]] = {}
        self.dependents: Dict[str, List[TaskDependency]] = {}
        self.tasks: Set[str] = set()

    def add_dependency(self, dependency: TaskDependency | Dict[str, str]) -> TaskDependency:
        """Add or replace a dependency edge."""
        dependency_obj = dependency if isinstance(dependency, TaskDependency) else TaskDependency(**dependency)
        self.tasks.add(dependency_obj.task_id)
        self.tasks.add(dependency_obj.depends_on_task_id)
        current = [
            item
            for item in self.dependencies.get(dependency_obj.task_id, [])
            if item.dependency_id != dependency_obj.dependency_id
        ]
        current.append(dependency_obj)
        self.dependencies[dependency_obj.task_id] = self._sort_dependencies(current)

        downstream = [
            item
            for item in self.dependents.get(dependency_obj.depends_on_task_id, [])
            if item.dependency_id != dependency_obj.dependency_id
        ]
        downstream.append(dependency_obj)
        self.dependents[dependency_obj.depends_on_task_id] = self._sort_dependencies(downstream)
        return dependency_obj

    def remove_dependency(self, dependency_id: str) -> bool:
        """Remove a dependency by id and return whether anything changed."""
        if not isinstance(dependency_id, str) or not dependency_id.strip():
            raise ValueError("dependency_id must be a non-empty string.")
        dependency_id = dependency_id.strip()
        removed = False
        for task_id in list(self.dependencies):
            filtered = [item for item in self.dependencies[task_id] if item.dependency_id != dependency_id]
            removed = removed or len(filtered) != len(self.dependencies[task_id])
            if filtered:
                self.dependencies[task_id] = filtered
            else:
                del self.dependencies[task_id]
        for task_id in list(self.dependents):
            filtered = [item for item in self.dependents[task_id] if item.dependency_id != dependency_id]
            if filtered:
                self.dependents[task_id] = filtered
            else:
                del self.dependents[task_id]
        return removed

    def get_dependencies(self, task_id: str) -> List[TaskDependency]:
        """Return prerequisite edges for a task."""
        task_id = self._normalize_task_id(task_id)
        return list(self.dependencies.get(task_id, []))

    def get_dependents(self, task_id: str) -> List[TaskDependency]:
        """Return downstream edges that depend on a task."""
        task_id = self._normalize_task_id(task_id)
        return list(self.dependents.get(task_id, []))

    def is_blocked(self, task_id: str, completed_task_ids: Iterable[str] | None = None) -> bool:
        """Return True when a task has incomplete hard prerequisites."""
        completed = {str(task_id) for task_id in (completed_task_ids or [])}
        return any(
            dependency.dependency_type == "hard" and dependency.depends_on_task_id not in completed
            for dependency in self.get_dependencies(task_id)
        )

    def detect_cycles(self) -> List[List[str]]:
        """Return deterministic dependency cycles, if any."""
        visited: Set[str] = set()
        active: List[str] = []
        cycles: List[List[str]] = []

        def visit(task_id: str) -> None:
            if task_id in active:
                cycle = active[active.index(task_id) :] + [task_id]
                if cycle not in cycles:
                    cycles.append(cycle)
                return
            if task_id in visited:
                return
            active.append(task_id)
            for dependency in self.get_dependencies(task_id):
                visit(dependency.depends_on_task_id)
            active.pop()
            visited.add(task_id)

        for task_id in sorted(self.tasks):
            visit(task_id)
        return cycles

    def get_critical_path(self) -> List[str]:
        """Return the longest prerequisite chain in dependency-first order."""
        if self.detect_cycles():
            return []
        memo: Dict[str, List[str]] = {}

        def longest_to(task_id: str) -> List[str]:
            if task_id in memo:
                return memo[task_id]
            dependencies = self.get_dependencies(task_id)
            if not dependencies:
                memo[task_id] = [task_id]
                return memo[task_id]
            candidates = [longest_to(dependency.depends_on_task_id) + [task_id] for dependency in dependencies]
            memo[task_id] = max(candidates, key=lambda path: (len(path), list(reversed(path))))
            return memo[task_id]

        if not self.tasks:
            return []
        return max((longest_to(task_id) for task_id in sorted(self.tasks)), key=lambda path: (len(path), path))

    def topological_sort(self) -> List[str]:
        """Return dependency-first task ordering, or an empty list when cycles exist."""
        if self.detect_cycles():
            return []
        result: List[str] = []
        visited: Set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            visited.add(task_id)
            for dependency in self.get_dependencies(task_id):
                visit(dependency.depends_on_task_id)
            if task_id not in result:
                result.append(task_id)

        for task_id in sorted(self.tasks):
            visit(task_id)
        return result

    def snapshots(self) -> List[Dict[str, str]]:
        """Return dependency dictionaries in deterministic order."""
        edges = [dependency for dependencies in self.dependencies.values() for dependency in dependencies]
        return [
            asdict(dependency)
            for dependency in sorted(edges, key=lambda item: item.dependency_id)
        ]

    def _sort_dependencies(self, dependencies: List[TaskDependency]) -> List[TaskDependency]:
        return sorted(
            dependencies,
            key=lambda item: (item.dependency_type, item.depends_on_task_id, item.task_id, item.dependency_id),
        )

    def _normalize_task_id(self, task_id: str) -> str:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string.")
        return task_id.strip()
