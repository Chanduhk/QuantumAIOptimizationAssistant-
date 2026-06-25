from __future__ import annotations

import math
from datetime import datetime

import pytest

from backend.app.domain.personal_knowledge_model import (
    KnowledgeInsight,
    KnowledgeNode,
    KnowledgeRelationship,
)
from backend.app.engines.personal_knowledge_engine import PersonalKnowledgeEngine
from backend.app.knowledge.personal_knowledge_graph import PersonalKnowledgeGraph
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_personal_knowledge_domain_model_validation() -> None:
    node = KnowledgeNode("g1", "Goal", "Build Platform", {"status": "active"})
    relationship = KnowledgeRelationship("r1", "g1", "t1", "advances", 2)
    insight = KnowledgeInsight("i1", "Risk", "Risk appears repeatedly.", 2, ["b", "a", "a"])

    assert node.node_type == "goal"
    assert relationship.strength == 1.0
    assert insight.confidence == 1.0
    assert insight.related_nodes == ["a", "b"]

    with pytest.raises(ValueError, match="node_id"):
        KnowledgeNode("", "goal", "Name")

    with pytest.raises(ValueError, match="metadata"):
        KnowledgeNode("n1", "goal", "Name", metadata=[])

    with pytest.raises(ValueError, match="differ"):
        KnowledgeRelationship("r2", "same", "same", "links")

    with pytest.raises(ValueError, match="confidence"):
        KnowledgeInsight("i2", "risk", "desc", math.inf)


def test_graph_node_creation_relationship_creation_and_removal() -> None:
    graph = PersonalKnowledgeGraph()
    graph.add_node(KnowledgeNode("g1", "goal", "Goal"))
    graph.add_node(KnowledgeNode("t1", "task", "Task"))
    graph.add_relationship(KnowledgeRelationship("r1", "g1", "t1", "advances", 0.8))

    assert graph.get_node("g1").name == "Goal"
    assert graph.get_relationships("g1")[0].relationship_id == "r1"
    assert graph.graph_summary()["node_type_counts"] == {"goal": 1, "task": 1}

    graph.remove_relationship("r1")
    assert graph.get_relationships() == []

    graph.add_relationship(KnowledgeRelationship("r2", "g1", "t1", "advances", 0.8))
    graph.remove_node("g1")
    assert graph.get_node("g1") is None
    assert graph.get_relationships() == []


def test_graph_rejects_malformed_inputs_and_bounds() -> None:
    graph = PersonalKnowledgeGraph(max_nodes=1, max_relationships=1)
    graph.add_node(KnowledgeNode("n1", "goal", "Goal"))

    with pytest.raises(ValueError, match="node limit"):
        graph.add_node(KnowledgeNode("n2", "task", "Task"))

    with pytest.raises(ValueError, match="source_id"):
        graph.add_relationship(KnowledgeRelationship("r1", "missing", "n1", "links"))

    with pytest.raises(ValueError, match="depth"):
        graph.find_related_nodes("n1", depth=-1)


def test_network_traversal_is_cycle_safe_and_deterministic() -> None:
    graph = PersonalKnowledgeGraph()
    for node_id, node_type in [("g1", "goal"), ("t1", "task"), ("c1", "conversation")]:
        graph.add_node(KnowledgeNode(node_id, node_type, node_id))
    graph.add_relationship(KnowledgeRelationship("r1", "g1", "t1", "advances"))
    graph.add_relationship(KnowledgeRelationship("r2", "t1", "c1", "discussed_in"))
    graph.add_relationship(KnowledgeRelationship("r3", "c1", "g1", "mentions"))

    first = [node.node_id for node in graph.find_related_nodes("g1", depth=2)]
    second = [node.node_id for node in graph.find_related_nodes("g1", depth=2)]

    assert first == second == ["c1", "t1"]


def test_goal_task_conversation_risk_and_opportunity_networks() -> None:
    engine = PersonalKnowledgeEngine()
    goal = {"goal_id": "g1", "title": "Launch", "status": "active"}
    task = {"id": "t1", "title": "Ship alpha"}
    conversation = {"conversation_id": "c1", "message": "Discuss launch", "topic": "launch"}
    risk = {"alert_id": "r1", "risk_type": "overload"}
    opportunity = {"opportunity_id": "o1", "category": "quick_win"}

    engine.link_goal_task(goal, task)
    engine.link_conversation_goal(conversation, goal)
    engine.link_risk_goal(risk, goal)
    engine.link_opportunity_goal(opportunity, goal)

    assert engine.graph.find_goal_network("g1")["root"]["node_id"] == "g1"
    assert engine.graph.find_task_network("t1")["root"]["node_id"] == "t1"
    assert engine.graph.find_conversation_network("c1")["root"]["node_id"] == "c1"
    assert engine.graph.find_risk_network("r1")["root"]["node_id"] == "r1"
    assert engine.graph.find_opportunity_network("o1")["root"]["node_id"] == "o1"


def test_all_required_entity_linking_paths() -> None:
    engine = PersonalKnowledgeEngine()
    goal = {"goal_id": "g1", "title": "Goal"}

    engine.link_goal_milestone(goal, {"milestone_id": "m1", "title": "Milestone"})
    engine.link_task_dependency(
        {"id": "t1", "title": "Task"},
        {"dependency_id": "d1", "dependency_type": "hard", "blocked": True, "task_id": "t1"},
    )
    engine.link_conversation_recommendation(
        {"conversation_id": "c1", "message": "Recommend this"},
        {"recommendation_id": "rec1", "action": "Do next"},
    )
    engine.link_reflection_decision(
        {"record_id": "ref1", "engine_name": "DecisionEngine"},
        {"decision_id": "dec1", "title": "Choose task"},
    )
    engine.link_simulation_goal({"scenario_id": "s1", "scenario_name": "Baseline"}, goal)

    summary = engine.graph.graph_summary()

    assert summary["node_type_counts"]["milestone"] == 1
    assert summary["node_type_counts"]["dependency"] == 1
    assert summary["node_type_counts"]["recommendation"] == 1
    assert summary["node_type_counts"]["reflection"] == 1
    assert summary["node_type_counts"]["simulation"] == 1


def test_pattern_discovery_and_insight_generation() -> None:
    engine = PersonalKnowledgeEngine()
    engine.add_entity("risk", "r1", "overload", {"risk_type": "overload"})
    engine.add_entity("risk", "r2", "overload", {"risk_type": "overload"})
    engine.add_entity("conversation", "c1", "productivity", {"topic": "productivity"})
    engine.add_entity("conversation", "c2", "productivity", {"topic": "productivity"})
    engine.add_entity("opportunity", "o1", "quick_win", {"category": "quick_win"})
    engine.add_entity("opportunity", "o2", "quick_win", {"category": "quick_win"})
    engine.add_entity("dependency", "d1", "hard", {"dependency_type": "hard"})
    engine.add_entity("dependency", "d2", "hard", {"dependency_type": "hard"})
    engine.add_entity("goal", "g1", "Launch", {"status": "failed"})
    engine.add_entity("goal", "g2", "Launch", {"status": "failed"})

    patterns = engine.discover_patterns()
    insights = engine.generate_insights()

    assert patterns["repeated_risk_categories"][0]["key"] == "overload"
    assert patterns["repeated_conversation_topics"][0]["count"] == 2
    assert any("Risk type overload" in insight.description for insight in insights)


def test_knowledge_summaries_health_and_evolution_report() -> None:
    engine = PersonalKnowledgeEngine()
    engine.link_goal_task(
        {"goal_id": "g1", "title": "Launch", "status": "active"},
        {"id": "t1", "title": "Ship alpha"},
    )

    report = engine.generate_evolution_report()
    summary = engine.summarize_personal_knowledge()

    assert report["knowledge_summary"]["node_count"] == 2
    assert engine.goal_memory_summary()["connected_count"] == 1
    assert engine.conversation_memory_summary()["count"] == 0
    assert engine.risk_memory_summary()["count"] == 0
    assert engine.opportunity_memory_summary()["count"] == 0
    assert engine.recommendation_memory_summary()["count"] == 0
    assert report["knowledge_health"]["knowledge_connectivity_score"] == 100.0
    assert summary["knowledge_summary"]["relationship_count"] == 1


def test_empty_graph_summary_and_health() -> None:
    engine = PersonalKnowledgeEngine()

    assert engine.summarize_personal_knowledge() is None
    assert engine.knowledge_health() == {
        "knowledge_completeness_score": 0.0,
        "knowledge_density_score": 0.0,
        "knowledge_connectivity_score": 0.0,
    }


def test_malformed_engine_inputs_are_rejected() -> None:
    engine = PersonalKnowledgeEngine()

    with pytest.raises(ValueError, match="entity_type"):
        engine.add_entity("", "id", "Name")

    with pytest.raises(ValueError, match="goal payload"):
        engine.link_goal_task([], {"id": "t1"})

    with pytest.raises(ValueError, match="source_id"):
        engine.link_entities("missing", "also-missing", "links")

    engine.add_entity("goal", "g1", "Goal")
    engine.add_entity("task", "t1", "Task")
    with pytest.raises(ValueError, match="relationship_type"):
        engine.link_entities("g1", "t1", "")


def test_deterministic_outputs() -> None:
    def build_report():
        engine = PersonalKnowledgeEngine()
        engine.link_goal_task(
            {"goal_id": "g1", "title": "Goal", "created_at": datetime(2026, 1, 1)},
            {"id": "t1", "title": "Task"},
        )
        return engine.generate_evolution_report()

    assert build_report() == build_report()


def test_orchestrator_personal_knowledge_outputs_are_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.personal_knowledge_engine = PersonalKnowledgeEngine()

    assert orchestrator._personal_knowledge_outputs() is None

    orchestrator.personal_knowledge_engine.link_goal_task(
        {"goal_id": "g1", "title": "Goal"},
        {"id": "t1", "title": "Task"},
    )
    outputs = orchestrator._personal_knowledge_outputs()

    assert outputs is not None
    assert set(outputs) == {"knowledge_summary", "knowledge_insights", "knowledge_health"}


def test_orchestrator_rejects_malformed_personal_knowledge_outputs() -> None:
    class BadKnowledgeEngine:
        def summarize_personal_knowledge(self):
            return {"knowledge_summary": {"bad": math.inf}, "knowledge_insights": [], "knowledge_health": {}}

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.personal_knowledge_engine = BadKnowledgeEngine()

    with pytest.raises(ValueError, match="finite"):
        orchestrator._personal_knowledge_outputs()
