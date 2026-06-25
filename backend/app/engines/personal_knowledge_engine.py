from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.personal_knowledge_model import (
    KnowledgeInsight,
    KnowledgeNode,
    KnowledgeRelationship,
)
from backend.app.knowledge.personal_knowledge_graph import PersonalKnowledgeGraph


class PersonalKnowledgeEngine:
    """Evolves an in-memory personal knowledge graph across intelligence outputs."""

    def __init__(self, graph: PersonalKnowledgeGraph | None = None) -> None:
        self.graph = graph or PersonalKnowledgeGraph()
        self.history: Dict[str, List[str]] = {
            "goal": [],
            "task": [],
            "decision": [],
            "conversation": [],
            "simulation": [],
            "recommendation": [],
            "risk": [],
            "opportunity": [],
            "reflection": [],
        }

    def add_entity(
        self,
        entity_type: str,
        entity_id: str,
        name: str,
        metadata: Dict[str, Any] | None = None,
    ) -> KnowledgeNode:
        """Add a typed knowledge entity and record it in history."""
        entity_type = self._required_text(entity_type, "entity_type").lower()
        node = self.graph.add_node(
            KnowledgeNode(
                node_id=self._required_text(entity_id, "entity_id"),
                node_type=entity_type,
                name=self._required_text(name, "name"),
                metadata=dict(metadata or {}),
            )
        )
        self.history.setdefault(entity_type, [])
        if node.node_id not in self.history[entity_type]:
            self.history[entity_type].append(node.node_id)
            self.history[entity_type].sort()
        return node

    def link_entities(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        strength: float = 1.0,
    ) -> KnowledgeRelationship:
        """Create a deterministic relationship between two existing entities."""
        source_id = self._required_text(source_id, "source_id")
        target_id = self._required_text(target_id, "target_id")
        relationship_type = self._required_text(relationship_type, "relationship_type").lower()
        relationship_id = f"{source_id}->{relationship_type}->{target_id}"
        return self.graph.add_relationship(
            KnowledgeRelationship(
                relationship_id=relationship_id,
                source_id=source_id,
                target_id=target_id,
                relationship_type=relationship_type,
                strength=strength,
            )
        )

    def link_goal_task(self, goal: Dict[str, Any], task: Dict[str, Any]) -> KnowledgeRelationship:
        """Link a goal to a task snapshot."""
        goal_node = self._node_from_payload(goal, "goal", "goal_id", "title")
        task_node = self._node_from_payload(task, "task", "id", "title")
        return self.link_entities(goal_node.node_id, task_node.node_id, "advances", 0.9)

    def link_goal_milestone(self, goal: Dict[str, Any], milestone: Dict[str, Any]) -> KnowledgeRelationship:
        """Link a goal to a milestone snapshot."""
        goal_node = self._node_from_payload(goal, "goal", "goal_id", "title")
        milestone_node = self._node_from_payload(milestone, "milestone", "milestone_id", "title")
        return self.link_entities(goal_node.node_id, milestone_node.node_id, "contains", 0.9)

    def link_task_dependency(self, task: Dict[str, Any], dependency: Dict[str, Any]) -> KnowledgeRelationship:
        """Link a task to a prerequisite dependency."""
        task_node = self._node_from_payload(task, "task", "id", "title")
        dependency_node = self._node_from_payload(dependency, "dependency", "dependency_id", "dependency_type")
        return self.link_entities(task_node.node_id, dependency_node.node_id, "depends_on", 0.85)

    def link_conversation_goal(self, conversation: Dict[str, Any], goal: Dict[str, Any]) -> KnowledgeRelationship:
        """Link a conversation turn or context to a goal."""
        conversation_node = self._node_from_payload(conversation, "conversation", "conversation_id", "message")
        goal_node = self._node_from_payload(goal, "goal", "goal_id", "title")
        return self.link_entities(conversation_node.node_id, goal_node.node_id, "mentions", 0.75)

    def link_conversation_recommendation(
        self,
        conversation: Dict[str, Any],
        recommendation: Dict[str, Any],
    ) -> KnowledgeRelationship:
        """Link a conversation to a recommendation."""
        conversation_node = self._node_from_payload(conversation, "conversation", "conversation_id", "message")
        recommendation_node = self._node_from_payload(recommendation, "recommendation", "recommendation_id", "action")
        return self.link_entities(conversation_node.node_id, recommendation_node.node_id, "discusses", 0.7)

    def link_risk_goal(self, risk: Dict[str, Any], goal: Dict[str, Any]) -> KnowledgeRelationship:
        """Link a risk alert to an affected goal."""
        risk_node = self._node_from_payload(risk, "risk", "alert_id", "risk_type")
        goal_node = self._node_from_payload(goal, "goal", "goal_id", "title")
        return self.link_entities(risk_node.node_id, goal_node.node_id, "threatens", 0.9)

    def link_opportunity_goal(self, opportunity: Dict[str, Any], goal: Dict[str, Any]) -> KnowledgeRelationship:
        """Link an opportunity to a goal it can advance."""
        opportunity_node = self._node_from_payload(opportunity, "opportunity", "opportunity_id", "category")
        goal_node = self._node_from_payload(goal, "goal", "goal_id", "title")
        return self.link_entities(opportunity_node.node_id, goal_node.node_id, "supports", 0.8)

    def link_reflection_decision(self, reflection: Dict[str, Any], decision: Dict[str, Any]) -> KnowledgeRelationship:
        """Link a reflection record to a decision record."""
        reflection_node = self._node_from_payload(reflection, "reflection", "record_id", "engine_name")
        decision_node = self._node_from_payload(decision, "decision", "decision_id", "title")
        return self.link_entities(reflection_node.node_id, decision_node.node_id, "evaluates", 0.75)

    def link_simulation_goal(self, simulation: Dict[str, Any], goal: Dict[str, Any]) -> KnowledgeRelationship:
        """Link a simulation outcome to a goal."""
        simulation_node = self._node_from_payload(simulation, "simulation", "scenario_id", "scenario_name")
        goal_node = self._node_from_payload(goal, "goal", "goal_id", "title")
        return self.link_entities(simulation_node.node_id, goal_node.node_id, "forecasts", 0.8)

    def discover_patterns(self) -> Dict[str, Any]:
        """Discover repeated deterministic patterns across knowledge nodes."""
        patterns: Dict[str, List[Dict[str, Any]]] = {
            "repeated_goal_failures": [],
            "repeated_risk_categories": [],
            "repeated_bottlenecks": [],
            "repeated_dependency_issues": [],
            "repeated_conversation_topics": [],
            "repeated_opportunity_types": [],
        }
        grouped: Dict[str, Dict[str, List[str]]] = {
            "risk": {},
            "dependency": {},
            "conversation": {},
            "opportunity": {},
            "goal_failure": {},
            "bottleneck": {},
        }
        for node_id in sorted(self.graph.nodes):
            node = self.graph.nodes[node_id]
            metadata = node.metadata
            if node.node_type == "risk":
                self._group(grouped["risk"], str(metadata.get("risk_type", node.name)).lower(), node_id)
            if node.node_type == "dependency":
                self._group(grouped["dependency"], str(metadata.get("dependency_type", node.name)).lower(), node_id)
                if metadata.get("blocked") or metadata.get("bottleneck"):
                    self._group(grouped["bottleneck"], str(metadata.get("task_id", node.name)).lower(), node_id)
            if node.node_type == "conversation":
                self._group(grouped["conversation"], str(metadata.get("topic", metadata.get("intent", node.name))).lower(), node_id)
            if node.node_type == "opportunity":
                self._group(grouped["opportunity"], str(metadata.get("category", node.name)).lower(), node_id)
            if node.node_type == "goal" and str(metadata.get("status", "")).lower() in {"failed", "blocked", "critical"}:
                self._group(grouped["goal_failure"], node.name.lower(), node_id)
        patterns["repeated_risk_categories"] = self._repeated(grouped["risk"])
        patterns["repeated_dependency_issues"] = self._repeated(grouped["dependency"])
        patterns["repeated_bottlenecks"] = self._repeated(grouped["bottleneck"])
        patterns["repeated_conversation_topics"] = self._repeated(grouped["conversation"])
        patterns["repeated_opportunity_types"] = self._repeated(grouped["opportunity"])
        patterns["repeated_goal_failures"] = self._repeated(grouped["goal_failure"])
        return patterns

    def generate_insights(self) -> List[KnowledgeInsight]:
        """Generate deterministic insights from patterns and relationships."""
        patterns = self.discover_patterns()
        insights: List[KnowledgeInsight] = []
        sequence = 1
        labels = {
            "repeated_goal_failures": "Repeated goal failure detected for {key}.",
            "repeated_risk_categories": "Risk type {key} appears repeatedly across personal knowledge.",
            "repeated_bottlenecks": "Dependency bottleneck {key} appears repeatedly.",
            "repeated_dependency_issues": "Dependency type {key} recurs across tasks.",
            "repeated_conversation_topics": "Conversation topic {key} appears repeatedly.",
            "repeated_opportunity_types": "Opportunity type {key} appears repeatedly.",
        }
        for category in sorted(patterns):
            for item in patterns[category]:
                insights.append(
                    KnowledgeInsight(
                        insight_id=f"insight-{sequence}",
                        category=category,
                        description=labels[category].format(key=item["key"]),
                        confidence=min(1.0, 0.55 + (item["count"] * 0.1)),
                        related_nodes=item["node_ids"],
                    )
                )
                sequence += 1
        return insights

    def goal_memory_summary(self) -> Dict[str, Any]:
        """Return goal memory counts and connected goal ids."""
        return self._type_summary("goal")

    def conversation_memory_summary(self) -> Dict[str, Any]:
        """Return conversation memory counts and connected conversation ids."""
        return self._type_summary("conversation")

    def risk_memory_summary(self) -> Dict[str, Any]:
        """Return risk memory counts and connected risk ids."""
        return self._type_summary("risk")

    def opportunity_memory_summary(self) -> Dict[str, Any]:
        """Return opportunity memory counts and connected opportunity ids."""
        return self._type_summary("opportunity")

    def recommendation_memory_summary(self) -> Dict[str, Any]:
        """Return recommendation memory counts and connected recommendation ids."""
        return self._type_summary("recommendation")

    def knowledge_health(self) -> Dict[str, float]:
        """Compute completeness, density, and connectivity scores on a 0-100 scale."""
        node_count = len(self.graph.nodes)
        relationship_count = len(self.graph.relationships)
        if node_count == 0:
            return {
                "knowledge_completeness_score": 0.0,
                "knowledge_density_score": 0.0,
                "knowledge_connectivity_score": 0.0,
            }
        metadata_nodes = sum(1 for node in self.graph.nodes.values() if node.metadata)
        connected_node_ids = {
            relationship.source_id
            for relationship in self.graph.relationships.values()
        } | {
            relationship.target_id
            for relationship in self.graph.relationships.values()
        }
        max_relationships = max(1, node_count * (node_count - 1))
        return {
            "knowledge_completeness_score": round((metadata_nodes / node_count) * 100.0, 2),
            "knowledge_density_score": round(min(1.0, relationship_count / max_relationships) * 100.0, 2),
            "knowledge_connectivity_score": round((len(connected_node_ids) / node_count) * 100.0, 2),
        }

    def generate_evolution_report(self) -> Dict[str, Any]:
        """Return a complete personal knowledge evolution report."""
        insights = self.generate_insights()
        summary = self.graph.graph_summary()
        return {
            "knowledge_summary": {
                **summary,
                "goal_memory_summary": self.goal_memory_summary(),
                "conversation_memory_summary": self.conversation_memory_summary(),
                "risk_memory_summary": self.risk_memory_summary(),
                "opportunity_memory_summary": self.opportunity_memory_summary(),
                "recommendation_memory_summary": self.recommendation_memory_summary(),
            },
            "knowledge_insights": [asdict(insight) for insight in insights],
            "knowledge_health": self.knowledge_health(),
            "emerging_patterns": self.discover_patterns(),
        }

    def summarize_personal_knowledge(self) -> Dict[str, Any] | None:
        """Return optional orchestrator-ready knowledge outputs."""
        if not self.graph.nodes:
            return None
        report = self.generate_evolution_report()
        return {
            "knowledge_summary": report["knowledge_summary"],
            "knowledge_insights": report["knowledge_insights"],
            "knowledge_health": report["knowledge_health"],
        }

    def _node_from_payload(
        self,
        payload: Dict[str, Any],
        node_type: str,
        id_key: str,
        name_key: str,
    ) -> KnowledgeNode:
        if not isinstance(payload, dict):
            raise ValueError(f"{node_type} payload must be a dictionary.")
        node_id = str(payload.get(id_key) or payload.get("id") or f"{node_type}-{len(self.graph.nodes) + 1}")
        name = str(payload.get(name_key) or payload.get("title") or payload.get("name") or node_id)
        return self.add_entity(node_type, node_id, name, payload)

    def _type_summary(self, node_type: str) -> Dict[str, Any]:
        node_ids = sorted(node_id for node_id, node in self.graph.nodes.items() if node.node_type == node_type)
        related_count = sum(1 for node_id in node_ids if self.graph.get_relationships(node_id=node_id))
        return {
            "count": len(node_ids),
            "connected_count": related_count,
            "node_ids": node_ids,
        }

    def _group(self, groups: Dict[str, List[str]], key: str, node_id: str) -> None:
        normalized = key.strip().lower() or "unknown"
        groups.setdefault(normalized, [])
        if node_id not in groups[normalized]:
            groups[normalized].append(node_id)
            groups[normalized].sort()

    def _repeated(self, groups: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        return [
            {"key": key, "count": len(node_ids), "node_ids": list(node_ids)}
            for key, node_ids in sorted(groups.items())
            if len(node_ids) >= 2
        ]

    def _required_text(self, value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()
