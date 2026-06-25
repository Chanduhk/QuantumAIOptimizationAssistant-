from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime

import pytest

from backend.app.domain.autonomous_planning_model import (
    AutonomousPlan,
    ContingencyPlan,
    PlanMilestone,
    PlanObjective,
    PlanTask,
    RecoveryPlan,
)
from backend.app.domain.goal_model import Goal, Milestone
from backend.app.engines.autonomous_planning_engine import AutonomousPlanningEngine
from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine
from backend.app.engines.goal_intelligence_engine import GoalIntelligenceEngine
from backend.app.engines.personal_knowledge_engine import PersonalKnowledgeEngine
from backend.app.engines.strategic_planning_engine import StrategicPlanningEngine
from backend.app.knowledge.goal_graph import GoalGraph
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_autonomous_planning_domain_validation() -> None:
    objective = PlanObjective("o1", "Launch", priority=2, success_criteria=["Done", "Done"])
    milestone = PlanMilestone("m1", "o1", "Alpha", 1, progress=120)
    task = PlanTask("t1", "m1", "Ship alpha", 1, estimated_duration=0)
    recovery = RecoveryPlan("r1", "risk", ["Act"], 1, 120, "Recover safely")
    contingency = ContingencyPlan("c1", "Normal", ["Act"], -10, 120)

    assert objective.success_criteria == ["Done"]
    assert milestone.progress == 100.0
    assert task.estimated_duration == 0.1
    assert recovery.expected_impact == 100.0
    assert contingency.risk_score == 0.0
    assert contingency.confidence_score == 100.0

    with pytest.raises(ValueError, match="title"):
        PlanObjective("o2", "")

    with pytest.raises(ValueError, match="priority"):
        PlanTask("t2", "m1", "Task", 1, priority=0)

    with pytest.raises(ValueError, match="actions"):
        RecoveryPlan("r2", "risk", [], 1, 10, "Reason")

    with pytest.raises(ValueError, match="risk_score"):
        ContingencyPlan("c2", "Bad", ["Act"], math.inf, 50)


def test_goal_decomposition_creates_objective_milestones_and_tasks() -> None:
    engine = AutonomousPlanningEngine()

    plan = engine.decompose_goal(
        {
            "goal_id": "g1",
            "title": "Build AI Assistant",
            "priority": 8,
            "progress": 20,
            "milestones": [{"title": "Prototype"}, {"title": "Launch"}],
        },
        created_at=datetime(2026, 1, 1),
    )

    assert plan.plan_id == "autonomous-g1-20260101"
    assert plan.objective.goal_id == "g1"
    assert [milestone.title for milestone in plan.milestones] == ["Prototype", "Launch"]
    assert len(plan.tasks) == 4
    assert plan.overall_plan_score > 0
    assert engine.summarize_autonomous_planning()["autonomous_plan_summary"]["task_count"] == 4


def test_default_milestone_and_task_creation() -> None:
    plan = AutonomousPlanningEngine().decompose_goal(
        {"goal_id": "g1", "title": "Research", "priority": 3},
        created_at=datetime(2026, 1, 1),
    )

    assert len(plan.milestones) == 3
    assert len(plan.tasks) == 6
    assert plan.tasks[0].reasoning == "Generated from goal decomposition."


def test_next_best_action_uses_dependency_risk_simulation_optimization_and_knowledge() -> None:
    knowledge = PersonalKnowledgeEngine()
    knowledge.add_entity("goal", "g1", "Goal")
    engine = AutonomousPlanningEngine(personal_knowledge_engine=knowledge)

    blocked = engine.determine_next_best_action(
        goal_health={"progress": 80, "risk_score": 10},
        dependency_state={"blocked_tasks": ["t1"]},
        simulation_results=[{"risk_score": 20}],
        optimization_results={"selected_future": {"scenario_name": "Balanced"}},
    )
    risky = engine.determine_next_best_action(
        goal_health={"progress": 80, "risk_score": 70},
        dependency_state={},
        simulation_results=[],
        optimization_results={},
    )
    early = engine.determine_next_best_action(
        goal_health={"progress": 5, "risk_score": 10},
        dependency_state={},
        simulation_results=[],
        optimization_results={},
    )

    assert blocked["recommended_action"] == "Unblock the highest-impact dependency"
    assert blocked["confidence"] > 0.6
    assert risky["recommended_action"] == "Execute recovery action for the at-risk goal"
    assert early["recommended_action"] == "Create first measurable progress on the primary goal"


def test_progress_gap_analysis_detects_missing_blocked_stalled_and_risky_plans() -> None:
    engine = AutonomousPlanningEngine()

    gaps = engine.analyze_progress_gaps(
        None,
        goal_health={"progress": 5, "risk_score": 70},
        dependency_state={"blocked_tasks": ["t1", "t2"]},
        simulation_results=[{"risk_score": 80}],
    )

    assert gaps["missing_milestones"] is True
    assert gaps["missing_tasks"] is True
    assert gaps["stalled_goals"] is True
    assert gaps["blocked_dependencies"] == 2
    assert gaps["risk_heavy_plan"] is True
    assert gaps["gaps"] == sorted(gaps["gaps"])


def test_recovery_plan_for_blockage_and_simulation_failure() -> None:
    engine = AutonomousPlanningEngine()

    recovery = engine.create_recovery_plan(
        goal_health={"risk_score": 70},
        simulation_result={"success_probability": 0.3, "risk_score": 80},
        dependency_state={"blocked_tasks": ["t1"]},
    )

    assert recovery.trigger == "simulation_failure"
    assert "Unblock critical dependency" in recovery.actions
    assert recovery.priority == 1
    assert engine.summarize_autonomous_planning()["recovery_plan_summary"]["trigger"] == "simulation_failure"


def test_contingency_plans_include_plan_a_b_and_c() -> None:
    engine = AutonomousPlanningEngine()
    plan = engine.decompose_goal({"goal_id": "g1", "title": "Goal"}, created_at=datetime(2026, 1, 1))

    contingencies = engine.create_contingency_plans(plan)

    assert [item.scenario for item in contingencies] == [
        "Normal execution",
        "Reduced capacity",
        "Dependency failure",
    ]
    assert engine.summarize_autonomous_planning()["contingency_plan_summary"][2]["scenario"] == "Dependency failure"


def test_roadmap_generation_consumes_strategic_planning_engine() -> None:
    goal_graph = GoalGraph()
    goal_graph.add_goal(Goal(goal_id="g1", title="Launch", priority=5, progress=10))
    goal_graph.add_milestone(Milestone(milestone_id="m1", goal_id="g1", title="Alpha"))
    goal_engine = GoalIntelligenceEngine(goal_graph)
    dependency_engine = DependencyIntelligenceEngine()
    strategic_engine = StrategicPlanningEngine(goal_engine, dependency_engine)
    engine = AutonomousPlanningEngine(strategic_planning_engine=strategic_engine)

    roadmaps = engine.generate_roadmaps(
        [{"id": "t1", "title": "Task", "goal_id": "g1", "estimated_duration": 1}],
        {"available_hours": 4},
        now=datetime(2026, 1, 1),
    )

    assert roadmaps["7_day"]["horizon_days"] == 7
    assert roadmaps["30_day"]["horizon_days"] == 30
    assert roadmaps["90_day"]["horizon_days"] == 90


def test_plan_scoring_is_bounded_and_accounts_for_blockers() -> None:
    engine = AutonomousPlanningEngine()

    scores = engine.score_plan(
        tasks=[{"id": "t1", "blocked": True}, {"id": "t2"}],
        goal_health={"progress": 40, "risk_score": 30},
        dependency_state={"blocked_tasks": ["t3"]},
        simulation_results=[{"risk_score": 50}],
    )

    assert set(scores) == {
        "feasibility_score",
        "dependency_score",
        "risk_score",
        "goal_alignment_score",
        "overall_plan_score",
    }
    assert all(0.0 <= value <= 100.0 for value in scores.values())
    assert scores["dependency_score"] < 100.0


def test_plan_explainability_for_empty_and_generated_plan() -> None:
    engine = AutonomousPlanningEngine()

    empty = engine.explain_plan()
    plan = engine.decompose_goal({"goal_id": "g1", "title": "Goal"}, created_at=datetime(2026, 1, 1))
    explanation = engine.explain_plan(plan)

    assert empty["title"] == "No autonomous plan available"
    assert "Why this task" in explanation["reasoning"][0]
    assert "Why recovery" in explanation["reasoning"][3]


def test_autonomous_plan_accepts_dict_payloads() -> None:
    plan = AutonomousPlan(
        plan_id="p1",
        objective={"objective_id": "o1", "title": "Goal"},
        milestones=[{"milestone_id": "m1", "objective_id": "o1", "title": "Milestone", "sequence": 1}],
        tasks=[{"task_id": "t1", "milestone_id": "m1", "title": "Task", "sequence": 1}],
        feasibility_score=80,
        dependency_score=90,
        risk_score=10,
        goal_alignment_score=85,
        overall_plan_score=88,
        reasoning="Reason",
    )

    assert plan.objective.objective_id == "o1"
    assert plan.milestones[0].milestone_id == "m1"
    assert plan.tasks[0].task_id == "t1"


def test_malformed_inputs_are_rejected() -> None:
    engine = AutonomousPlanningEngine()

    with pytest.raises(ValueError, match="goal"):
        engine.decompose_goal([])

    with pytest.raises(ValueError, match="behavior_patterns"):
        engine.decompose_goal({"goal_id": "g1", "title": "Goal"}, behavior_patterns=[])

    with pytest.raises(ValueError, match="tasks"):
        engine.score_plan(tasks={"id": "bad"})

    with pytest.raises(ValueError, match="simulation_results"):
        engine.determine_next_best_action(simulation_results={})

    with pytest.raises(ValueError, match="plan"):
        engine.explain_plan([])


def test_deterministic_outputs() -> None:
    def build() -> dict:
        engine = AutonomousPlanningEngine()
        plan = engine.decompose_goal({"goal_id": "g1", "title": "Goal"}, created_at=datetime(2026, 1, 1))
        engine.determine_next_best_action(goal_health={"progress": 20, "risk_score": 10})
        engine.create_contingency_plans(plan)
        return {
            "plan": asdict(plan),
            "summary": engine.summarize_autonomous_planning(),
            "explanation": engine.explain_plan(plan),
        }

    assert build() == build()


def test_orchestrator_autonomous_planning_outputs_are_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.autonomous_planning_engine = AutonomousPlanningEngine()

    assert orchestrator._autonomous_planning_outputs() is None

    orchestrator.autonomous_planning_engine.decompose_goal(
        {"goal_id": "g1", "title": "Goal"},
        created_at=datetime(2026, 1, 1),
    )
    outputs = orchestrator._autonomous_planning_outputs()

    assert outputs is not None
    assert "autonomous_plan_summary" in outputs


def test_orchestrator_rejects_malformed_autonomous_planning_outputs() -> None:
    class BadAutonomousPlanningEngine:
        def summarize_autonomous_planning(self):
            return {"unsupported": {"score": math.inf}}

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.autonomous_planning_engine = BadAutonomousPlanningEngine()

    with pytest.raises(ValueError, match="unsupported"):
        orchestrator._autonomous_planning_outputs()
