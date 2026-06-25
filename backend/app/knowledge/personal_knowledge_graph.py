from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Set

from backend.app.domain.personal_knowledge_model import KnowledgeNode, KnowledgeRelationship


class PersonalKnowledgeGraph:
    """Bounded deterministic in-memory graph for personal knowledge evolution."""

    def __init__(self, max_nodes: int = 1000, max_relationships: int = 5000) -> None:
        if not isinstance(max_nodes, int) or isinstance(max_nodes, bool) or max_nodes <= 0:
            raise ValueError("max_nodes must be a positive integer.")
        if not isinstance(max_relationships, int) or isinstance(max_relationships, bool) or max_relationships <= 0:
            raise ValueError("max_relationships must be a positive integer.")
        self.max_nodes = max_nodes
        self.max_relationships = max_relationships
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.relationships: Dict[str, KnowledgeRelationship] = {}

    def add_node(self, node: KnowledgeNode | Dict[str, Any]) -> KnowledgeNode:
        """Add or replace a node while enforcing the configured graph bound."""
        node_obj = node if isinstance(node, KnowledgeNode) else KnowledgeNode(**node)
        if node_obj.node_id not in self.nodes and len(self.nodes) >= self.max_nodes:
            raise ValueError("personal knowledge graph node limit exceeded.")
        self.nodes[node_obj.node_id] = node_obj
        return node_obj

    def add_relationship(self, relationship: KnowledgeRelationship | Dict[str, Any]) -> KnowledgeRelationship:
        """Add or replace a relationship between existing nodes."""
        relationship_obj = (
            relationship
            if isinstance(relationship, KnowledgeRelationship)
            else KnowledgeRelationship(**relationship)
        )
        if relationship_obj.source_id not in self.nodes:
            raise ValueError("relationship source_id must reference an existing node.")
        if relationship_obj.target_id not in self.nodes:
            raise ValueError("relationship target_id must reference an existing node.")
        if relationship_obj.relationship_id not in self.relationships and len(self.relationships) >= self.max_relationships:
            raise ValueError("personal knowledge graph relationship limit exceeded.")
        self.relationships[relationship_obj.relationship_id] = relationship_obj
        return relationship_obj

    def remove_node(self, node_id: str) -> None:
        """Remove a node and every relationship connected to it."""
        node_id = self._required_id(node_id, "node_id")
        self.nodes.pop(node_id, None)
        for relationship_id in sorted(
            relationship_id
            for relationship_id, relationship in self.relationships.items()
            if relationship.source_id == node_id or relationship.target_id == node_id
        ):
            self.relationships.pop(relationship_id, None)

    def remove_relationship(self, relationship_id: str) -> None:
        """Remove one relationship if present."""
        self.relationships.pop(self._required_id(relationship_id, "relationship_id"), None)

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        """Return a node by id, or None when it does not exist."""
        return self.nodes.get(self._required_id(node_id, "node_id"))

    def get_relationships(
        self,
        node_id: str | None = None,
        relationship_type: str | None = None,
    ) -> List[KnowledgeRelationship]:
        """Return deterministic relationships, optionally filtered by node or type."""
        normalized_node = self._required_id(node_id, "node_id") if node_id is not None else None
        normalized_type = relationship_type.strip().lower() if isinstance(relationship_type, str) and relationship_type.strip() else None
        relationships = []
        for relationship_id in sorted(self.relationships):
            relationship = self.relationships[relationship_id]
            if normalized_node and normalized_node not in {relationship.source_id, relationship.target_id}:
                continue
            if normalized_type and relationship.relationship_type != normalized_type:
                continue
            relationships.append(relationship)
        return relationships

    def find_related_nodes(self, node_id: str, depth: int = 1) -> List[KnowledgeNode]:
        """Find related nodes with cycle-safe breadth-first traversal."""
        start_id = self._required_id(node_id, "node_id")
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
            raise ValueError("depth must be a non-negative integer.")
        if start_id not in self.nodes:
            return []
        visited: Set[str] = {start_id}
        frontier: List[str] = [start_id]
        for _ in range(depth):
            next_frontier: List[str] = []
            for current_id in frontier:
                for related_id in self._neighbors(current_id):
                    if related_id not in visited:
                        visited.add(related_id)
                        next_frontier.append(related_id)
            frontier = sorted(next_frontier)
            if not frontier:
                break
        return [self.nodes[node_id] for node_id in sorted(visited - {start_id})]

    def find_goal_network(self, goal_id: str) -> Dict[str, Any]:
        """Return a goal-centered network snapshot."""
        return self._network(goal_id, "goal")

    def find_task_network(self, task_id: str) -> Dict[str, Any]:
        """Return a task-centered network snapshot."""
        return self._network(task_id, "task")

    def find_conversation_network(self, conversation_id: str) -> Dict[str, Any]:
        """Return a conversation-centered network snapshot."""
        return self._network(conversation_id, "conversation")

    def find_risk_network(self, risk_id: str) -> Dict[str, Any]:
        """Return a risk-centered network snapshot."""
        return self._network(risk_id, "risk")

    def find_opportunity_network(self, opportunity_id: str) -> Dict[str, Any]:
        """Return an opportunity-centered network snapshot."""
        return self._network(opportunity_id, "opportunity")

    def graph_summary(self) -> Dict[str, Any]:
        """Return deterministic graph counts and node type distribution."""
        node_type_counts: Dict[str, int] = {}
        relationship_type_counts: Dict[str, int] = {}
        for node in self.nodes.values():
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1
        for relationship in self.relationships.values():
            relationship_type_counts[relationship.relationship_type] = relationship_type_counts.get(relationship.relationship_type, 0) + 1
        return {
            "node_count": len(self.nodes),
            "relationship_count": len(self.relationships),
            "node_type_counts": dict(sorted(node_type_counts.items())),
            "relationship_type_counts": dict(sorted(relationship_type_counts.items())),
        }

    def _network(self, node_id: str, expected_type: str) -> Dict[str, Any]:
        node_id = self._required_id(node_id, f"{expected_type}_id")
        node = self.nodes.get(node_id)
        if node is None:
            return {"root": None, "nodes": [], "relationships": []}
        if node.node_type != expected_type:
            raise ValueError(f"{expected_type}_id must reference a {expected_type} node.")
        related_nodes = self.find_related_nodes(node_id, depth=2)
        related_ids = {node.node_id for node in related_nodes} | {node_id}
        relationships = [
            relationship
            for relationship in self.get_relationships()
            if relationship.source_id in related_ids and relationship.target_id in related_ids
        ]
        return {
            "root": asdict(node),
            "nodes": [asdict(item) for item in related_nodes],
            "relationships": [asdict(item) for item in relationships],
        }

    def _neighbors(self, node_id: str) -> List[str]:
        neighbors = set()
        for relationship in self.relationships.values():
            if relationship.source_id == node_id:
                neighbors.add(relationship.target_id)
            if relationship.target_id == node_id:
                neighbors.add(relationship.source_id)
        return sorted(neighbors)

    def _required_id(self, value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()
