from __future__ import annotations

import uuid
from typing import Any, Dict, List

try:
    import networkx as nx
except ImportError:  # pragma: no cover - runtime fallback
    nx = None


class _SimpleNodeView(dict):
    """Minimal node view compatible with the access patterns used here."""


class _SimpleDiGraph:
    """Fallback directed graph used when networkx is unavailable."""

    def __init__(self) -> None:
        self.nodes = _SimpleNodeView()
        self._successors: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._predecessors: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def add_node(self, node_id: str, **attributes: Any) -> None:
        self.nodes.setdefault(node_id, {}).update(attributes)
        self._successors.setdefault(node_id, {})
        self._predecessors.setdefault(node_id, {})

    def add_edge(self, source: str, target: str, **attributes: Any) -> None:
        self.add_node(source)
        self.add_node(target)
        self._successors[source][target] = attributes
        self._predecessors[target][source] = attributes

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def successors(self, node_id: str) -> List[str]:
        return list(self._successors.get(node_id, {}).keys())

    def predecessors(self, node_id: str) -> List[str]:
        return list(self._predecessors.get(node_id, {}).keys())


class AIKnowledgeGraph:
    """Lightweight graph of users, goals, tasks, and time blocks."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph() if nx is not None else _SimpleDiGraph()

    def add_user(self, user_id: int) -> str:
        """Add a user node if it does not already exist."""
        node_id = f"user:{user_id}"
        self.graph.add_node(node_id, node_type="User", user_id=user_id, label=f"User {user_id}")
        return node_id

    def add_goal(self, user_id: int, goal: str) -> str:
        """Add a goal node and link it to a user."""
        user_node = self.add_user(user_id)
        goal_id = f"goal:{uuid.uuid4().hex}"
        self.graph.add_node(goal_id, node_type="Goal", label=goal, user_id=user_id)
        self.graph.add_edge(user_node, goal_id, relationship="HAS_GOAL")
        return goal_id

    def add_task(self, goal_id: str, task: Dict[str, Any]) -> str:
        """Add a task node and link it to a goal."""
        task_id = str(task.get("id") or f"task:{uuid.uuid4().hex}")
        self.graph.add_node(
            task_id,
            node_type="Task",
            label=task.get("title"),
            task_type=task.get("type") or task.get("task_type"),
            priority=task.get("priority"),
            completed=task.get("completed", False),
            title=task.get("title"),
        )
        self.graph.add_edge(goal_id, task_id, relationship="HAS_TASK")

        for existing_task_id in self.get_related_tasks(goal_id):
            other_id = str(existing_task_id.get("id") or existing_task_id.get("node_id", ""))
            if other_id and other_id != task_id and self.graph.has_node(other_id):
                self.graph.add_edge(task_id, other_id, relationship="RELATED_TO")
                self.graph.add_edge(other_id, task_id, relationship="RELATED_TO")

        return task_id

    def link_task_time(self, task_id: str, hour: int) -> str:
        """Link a task node to a time block node."""
        time_id = f"time:{hour}"
        self.graph.add_node(time_id, node_type="TimeBlock", label=f"{hour}:00", hour=hour)
        self.graph.add_edge(task_id, time_id, relationship="SCHEDULED_AT")
        return time_id

    def get_related_tasks(self, task_id: str) -> List[Dict[str, Any]]:
        """Return task nodes connected to the given task or goal."""
        if not self.graph.has_node(task_id):
            return []

        related_nodes = []
        for neighbor in self.graph.successors(task_id):
            if self.graph.nodes[neighbor].get("node_type") == "Task":
                related_nodes.append({"node_id": neighbor, **self.graph.nodes[neighbor]})

        for predecessor in self.graph.predecessors(task_id):
            if self.graph.nodes[predecessor].get("node_type") == "Task":
                related_nodes.append({"node_id": predecessor, **self.graph.nodes[predecessor]})

        unique_by_node = {item["node_id"]: item for item in related_nodes}
        return list(unique_by_node.values())

    def get_user_goals(self, user_id: int) -> List[Dict[str, Any]]:
        """Return all goal nodes connected to a user."""
        user_node = f"user:{user_id}"
        if not self.graph.has_node(user_node):
            return []

        goals = []
        for goal_id in self.graph.successors(user_node):
            if self.graph.nodes[goal_id].get("node_type") == "Goal":
                goals.append({"goal_id": goal_id, **self.graph.nodes[goal_id]})
        return goals
