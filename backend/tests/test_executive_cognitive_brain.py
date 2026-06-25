import pytest

from backend.app.orchestrator.ai_orchestrator import AIOrchestrator
from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain


def sample_tasks():
    return [
        {
            "id": "task-1",
            "title": "Write architecture brief",
            "task_type": "deep_work",
            "priority": 4,
            "estimated_duration": 2.0,
            "goal_id": "goal-1",
        },
        {
            "id": "task-2",
            "title": "Review dependency blockers",
            "task_type": "planning",
            "priority": 3,
            "estimated_duration": 1.0,
        },
    ]


class FakeContextEngine:
    def __init__(self, calls):
        self.calls = calls

    def build_context(self, **kwargs):
        self.calls.append("context")
        return {
            "user_id": kwargs["user_id"],
            "current_tasks": kwargs["current_tasks"],
            "query": kwargs["query"],
            "behavior_patterns": kwargs["behavior_patterns"],
        }


class FakeContextAwarenessEngine:
    def __init__(self, calls):
        self.calls = calls

    def generate_snapshot(self, **kwargs):
        self.calls.append("context_awareness")
        return {
            "snapshot_id": "context-1",
            "risk_state": "low",
            "momentum_state": "positive",
            "workload": kwargs["workload"],
        }


class FakeBehaviorLearningEngine:
    def __init__(self, calls):
        self.calls = calls

    def summarize_behavior_learning(self):
        self.calls.append("behavior_learning")
        return {
            "behavior_learning_summary": {"habit_strength": 80.0},
            "behavior_trends": [],
            "behavior_insights": [{"insight_id": "insight-1", "confidence": 0.8}],
            "learning_snapshot": {"sample_count": 3},
        }


class FakeAdaptiveLifeOperatingSystem:
    def __init__(self, calls):
        self.calls = calls

    def summarize_adaptive_life(self):
        self.calls.append("adaptive")
        return {
            "risk_count": 1,
            "burnout_probability": 0.1,
            "load_status": "healthy_load",
        }


class FakeMetaCognitiveEngine:
    def __init__(self, calls):
        self.calls = calls

    def summarize_meta_cognition(self):
        self.calls.append("meta")
        return {"average_error": 5.0, "risk_level": "low"}


class FakeGoalIntelligenceEngine:
    def __init__(self, calls):
        self.calls = calls

    def prioritize_goals(self):
        self.calls.append("goal")
        return [{"goal_id": "goal-1", "title": "Ship platform", "priority": 9}]


class FakeDependencyIntelligenceEngine:
    def __init__(self, calls):
        self.calls = calls

    def analyze_dependencies(self, tasks):
        self.calls.append("dependency")
        return {
            "blocked_tasks": [],
            "critical_path": [task.get("id") for task in tasks],
            "critical_path_length": len(tasks),
        }


class FakePersonalKnowledgeEngine:
    def __init__(self, calls):
        self.calls = calls

    def summarize_personal_knowledge(self):
        self.calls.append("knowledge")
        return {
            "knowledge_summary": {"node_count": 2, "relationship_count": 1},
            "knowledge_insights": [],
            "knowledge_health": {"knowledge_connectivity_score": 75.0},
        }


class FakeBehaviorEngine:
    def __init__(self, calls):
        self.calls = calls

    def get_user_patterns(self):
        self.calls.append("behavior")
        return {
            "average_productivity": 80.0,
            "hourly_productivity": {9: 85.0, 10: 80.0},
            "best_focus_hours": [9, 10],
        }


class FakePredictionEngine:
    def __init__(self, calls):
        self.calls = calls

    def predict_batch(self, behavior_engine, tasks, behavior_patterns):
        self.calls.append("prediction")
        return [
            {
                **task,
                "predicted_productivity": 82.0 - index,
            }
            for index, task in enumerate(tasks)
        ]


class FakeDecisionEngine:
    def __init__(self, calls):
        self.calls = calls

    def prioritize_tasks(self, tasks, predicted_tasks, behavior_patterns):
        self.calls.append("decision")
        return sorted(predicted_tasks, key=lambda task: (-task["priority"], task["id"]))


class FakePlanningEngine:
    def __init__(self, calls):
        self.calls = calls

    def generate_daily_plan(self, tasks, behavior_patterns):
        self.calls.append("planning")
        return {"tasks": list(tasks), "rationale": "Highest-value work first."}


class FakeSchedulingEngine:
    def __init__(self, calls):
        self.calls = calls

    def optimize_schedule(self, tasks, behavior_patterns):
        self.calls.append("scheduling")
        return [
            {
                **task,
                "scheduled_hour": 9 + index,
                "scheduled_end_hour": 10 + index,
                "schedule_score": 85.0 - index,
            }
            for index, task in enumerate(tasks)
        ]


class FakeOptimizationEngine:
    def __init__(self, calls):
        self.calls = calls

    def optimize_schedule(self, tasks, behavior_patterns):
        self.calls.append("optimization")
        return {
            "optimized_schedule": [
                {
                    **task,
                    "optimized_hour": 9 + index,
                    "optimized_end_hour": 10 + index,
                    "projected_productivity_gain": 5.0,
                }
                for index, task in enumerate(tasks)
            ],
            "projected_productivity_gain": 5.0,
        }


class FakeStrategicPlanningEngine:
    def __init__(self, calls):
        self.calls = calls

    def recommend_next_week(self, tasks, behavior_patterns):
        self.calls.append("strategic")
        return {"recommendations": [{"task_id": "task-1", "priority_score": 90.0}]}


class FakeFutureSimulationEngine:
    def __init__(self, calls):
        self.calls = calls

    def simulate_baseline(self, tasks, behavior_patterns):
        self.calls.append("simulation")
        return {
            "scenario_id": "scenario-baseline",
            "scenario_name": "Baseline",
            "success_probability": 0.82,
            "goal_completion_probability": 0.78,
            "milestone_completion_probability": 0.74,
            "workload_score": 18.0,
            "risk_score": 12.0,
            "confidence_score": 84.0,
            "projected_state": {
                "projected_goal_state": "on_track",
                "blocked_task_count": 0,
            },
            "recommendations": ["Maintain current trajectory"],
        }


class FakeMultiObjectiveOptimizationEngine:
    def __init__(self, calls):
        self.calls = calls

    def optimize(self, futures):
        self.calls.append("multi_objective")
        return {
            "selected_scenario_id": futures[0]["scenario_id"],
            "selected_scenario_name": futures[0]["scenario_name"],
            "overall_score": 86.0,
            "objective_scores": {"Productivity": 82.0, "Risk Reduction": 88.0},
            "tradeoffs": ["No major tradeoffs detected"],
            "recommendations": ["Select baseline"],
            "optimization_summary": {"ranking": [{"rank": 1, "scenario_id": futures[0]["scenario_id"]}]},
        }


class FakeDecisionIntelligenceEngine:
    def __init__(self, calls):
        self.calls = calls

    def analyze_decisions(self, options, **kwargs):
        self.calls.append("decision_intelligence")
        best = options[-1]
        return {
            "analysis_id": "decision-analysis-1",
            "options": options,
            "evaluations": [
                {
                    "option_id": option["option_id"],
                    "overall_score": 90.0 if option == best else 70.0,
                    "risk_score": 8.0 if option == best else 20.0,
                    "confidence_score": 88.0,
                }
                for option in options
            ],
            "tradeoffs": [{"description": "Higher certainty with modest effort."}],
            "recommendations": [
                {
                    "recommendation_id": "recommendation-1",
                    "option_id": best["option_id"],
                    "title": best["title"],
                    "reasoning": "Best validated option across planning, risk, and strategic inputs.",
                    "confidence": 0.88,
                    "priority": 1,
                }
            ],
            "ranking": [best["option_id"]],
            "executive_summary": "Use the optimized plan.",
            "confidence": 0.88,
        }


class FakeConversationalIntelligenceEngine:
    def __init__(self, calls):
        self.calls = calls

    def explain_risk(self, risk_summary):
        self.calls.append("conversational_risk")
        return {
            "explanation_type": "risk",
            "title": "Risk explanation",
            "summary": f"Risk is {risk_summary['risk_level']}.",
            "key_factors": ["low risk score"],
            "recommendations": ["Proceed"],
            "confidence": 0.9,
        }

    def explain_optimization(self, optimization_summary):
        self.calls.append("conversational_optimization")
        return {
            "explanation_type": "optimization",
            "title": "Tradeoff explanation",
            "summary": "The selected plan balances effort and outcome.",
            "key_factors": ["objective score"],
            "recommendations": ["Use optimized schedule"],
            "confidence": 0.88,
        }


def build_brain(calls=None, **overrides):
    calls = [] if calls is None else calls
    engines = {
        "context_engine": FakeContextEngine(calls),
        "context_awareness_engine": FakeContextAwarenessEngine(calls),
        "behavior_learning_engine": FakeBehaviorLearningEngine(calls),
        "adaptive_life_operating_system": FakeAdaptiveLifeOperatingSystem(calls),
        "meta_cognitive_engine": FakeMetaCognitiveEngine(calls),
        "goal_intelligence_engine": FakeGoalIntelligenceEngine(calls),
        "dependency_intelligence_engine": FakeDependencyIntelligenceEngine(calls),
        "personal_knowledge_engine": FakePersonalKnowledgeEngine(calls),
        "behavior_engine": FakeBehaviorEngine(calls),
        "prediction_engine": FakePredictionEngine(calls),
        "decision_engine": FakeDecisionEngine(calls),
        "planning_engine": FakePlanningEngine(calls),
        "scheduling_engine": FakeSchedulingEngine(calls),
        "optimization_engine": FakeOptimizationEngine(calls),
        "strategic_planning_engine": FakeStrategicPlanningEngine(calls),
        "future_simulation_engine": FakeFutureSimulationEngine(calls),
        "multi_objective_optimization_engine": FakeMultiObjectiveOptimizationEngine(calls),
        "decision_intelligence_engine": FakeDecisionIntelligenceEngine(calls),
        "conversational_intelligence_engine": FakeConversationalIntelligenceEngine(calls),
    }
    engines.update(overrides)
    return ExecutiveCognitiveBrain(**engines)


def test_executive_brain_executes_pipeline_in_order():
    calls = []
    brain = build_brain(calls)

    result = brain.execute_planning_request(
        sample_tasks(),
        user_id=7,
        behavior_patterns={},
        goals=[{"goal_id": "goal-1", "title": "Ship platform"}],
        query="What should I do next?",
    )

    assert result["recommended_plan"]["title"] == "Optimized Schedule"
    assert result["risk_summary"]["risk_level"] == "low"
    assert result["explanations"]["risk_explanation"]["title"] == "Risk explanation"
    assert calls[:18] == [
        "context",
        "behavior_learning",
        "adaptive",
        "meta",
        "context_awareness",
        "goal",
        "dependency",
        "knowledge",
        "behavior",
        "prediction",
        "decision",
        "planning",
        "scheduling",
        "optimization",
        "strategic",
        "simulation",
        "multi_objective",
        "decision_intelligence",
    ]
    assert "conversational_risk" in calls
    assert calls.count("meta") >= 2


def test_executive_brain_is_deterministic_for_identical_inputs():
    first = build_brain().execute_planning_request(sample_tasks(), user_id=7, behavior_patterns={})
    second = build_brain().execute_planning_request(sample_tasks(), user_id=7, behavior_patterns={})

    assert first == second


def test_executive_brain_handles_missing_optional_engines_and_empty_tasks():
    result = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])

    assert result["candidate_plans"]["plans"] == [{"plan_type": "task_order", "plan": {"tasks": []}}]
    assert result["recommended_plan"]["option_id"] == "candidate-1"
    assert result["future_analysis"]["ranked_futures"] == []
    assert result["executive_summary"]


def test_executive_brain_rejects_malformed_task_container():
    with pytest.raises(ValueError, match="tasks must be a list"):
        ExecutiveCognitiveBrain().execute_planning_request({"id": "bad"})


def test_executive_brain_rejects_malformed_engine_outputs():
    class BadPredictionEngine:
        def predict_batch(self, behavior_engine, tasks, behavior_patterns):
            return {"not": "a list"}

    brain = build_brain(prediction_engine=BadPredictionEngine())

    with pytest.raises(ValueError, match="predicted_tasks"):
        brain.execute_planning_request(sample_tasks(), user_id=7, behavior_patterns={})


def test_executive_brain_rejects_malformed_explanations():
    class BadConversationalEngine:
        def explain_risk(self, risk_summary):
            return ["not", "a", "dict"]

    brain = build_brain(conversational_intelligence_engine=BadConversationalEngine())

    with pytest.raises(ValueError, match="risk explanation"):
        brain.execute_planning_request(sample_tasks(), user_id=7, behavior_patterns={})


def test_executive_brain_summary_only_exists_after_execution():
    brain = build_brain()

    assert brain.summarize_executive_brain() is None

    brain.execute_planning_request(sample_tasks(), user_id=7, behavior_patterns={})
    summary = brain.summarize_executive_brain()

    assert summary == {
        "recommended_option_id": "candidate-3",
        "recommended_title": "Optimized Schedule",
        "overall_score": 90.0,
        "risk_level": "low",
        "candidate_plan_count": 3,
        "future_count": 1,
    }


def test_executive_brain_integrates_goals_dependencies_context_and_reflection():
    result = build_brain().execute_planning_request(
        sample_tasks(),
        user_id=7,
        behavior_patterns={},
        goals=[{"goal_id": "goal-1", "title": "Ship platform"}],
    )

    assert result["executive_context"]["context_snapshot"]["momentum_state"] == "positive"
    assert result["executive_objectives"]["goals"][0]["goal_id"] == "goal-1"
    assert result["executive_objectives"]["dependency_state"]["critical_path_length"] == 2
    assert result["future_analysis"]["strategic_plan"]["recommendations"][0]["task_id"] == "task-1"
    assert result["reflection"]["context_available"] is True
    assert result["reflection"]["recommended_option_id"] == "candidate-3"


def test_orchestrator_executive_summary_preserves_backward_compatibility():
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.executive_cognitive_brain = ExecutiveCognitiveBrain()

    assert orchestrator._executive_brain_summary() is None

    orchestrator.executive_cognitive_brain = build_brain()
    orchestrator.executive_cognitive_brain.execute_planning_request(
        sample_tasks(),
        user_id=7,
        behavior_patterns={},
    )

    assert orchestrator._executive_brain_summary()["recommended_title"] == "Optimized Schedule"


def test_orchestrator_optional_execution_path_uses_executive_brain():
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.executive_cognitive_brain = build_brain()
    orchestrator._validate_user_id = lambda user_id: None
    orchestrator._normalize_tasks = lambda tasks: tasks
    orchestrator._validate_behavior_patterns = lambda patterns: None

    result = orchestrator.execute_executive_planning(
        sample_tasks(),
        user_id=7,
        behavior_patterns={},
        goals=[{"goal_id": "goal-1"}],
    )

    assert set(result) == ExecutiveCognitiveBrain.OUTPUT_KEYS
    assert result["recommended_plan"]["title"] == "Optimized Schedule"


def test_orchestrator_rejects_malformed_executive_brain_result():
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)

    with pytest.raises(ValueError, match="executive brain result has invalid fields"):
        orchestrator._validate_executive_brain_result({"executive_summary": "bad"})
