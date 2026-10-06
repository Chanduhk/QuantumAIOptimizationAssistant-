from __future__ import annotations

import math
import tempfile
import unittest
from types import MethodType

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.domain.optimization_input_contract import OptimizationInputError, adapt_task_for_optimization
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


class _Frame:
    empty = False
    columns = []


class FakeBehaviorEngine:
    user_patterns = {"best_focus_hours": [10]}

    def __init__(self, patterns=None, task_history=None):
        self.patterns = patterns if patterns is not None else {"best_focus_hours": [10], "hourly_productivity": {10: 80}}
        self.task_history = task_history if task_history is not None else _Frame()

    def collect_behavior_data(self, user_id, days_back=90):
        return self.task_history

    def extract_features(self):
        return _Frame()

    def get_user_patterns(self):
        self.user_patterns = self.patterns
        return self.patterns


class FakeFeatureStore:
    def store_features(self, user_id, features):
        return None


class FakeKnowledgeGraph:
    def __init__(self, bad=False):
        self.bad = bad

    def add_user(self, user_id):
        return "" if self.bad else f"user:{user_id}"

    def add_goal(self, user_id, goal):
        return "goal:1"

    def add_task(self, goal_id, task):
        return f"task:{task['id']}"

    def link_task_time(self, task_id, hour):
        return f"time:{hour}"


class FakeContextEngine:
    def __init__(self, output=None):
        self.output = output if output is not None else {"context": True}

    def build_context(self, **kwargs):
        return self.output


class FakePredictionEngine:
    def __init__(self, output=None):
        self.output = output

    def predict_batch(self, behavior_engine, tasks, behavior_patterns):
        if self.output is not None:
            return self.output
        return [{**task, "predicted_productivity": 75.0} for task in tasks]


class FakeDecisionEngine:
    def __init__(self, output=None):
        self.output = output

    def prioritize_tasks(self, tasks, predicted_tasks, behavior_patterns):
        return self.output if self.output is not None else list(predicted_tasks)


class FakePlanningEngine:
    def __init__(self, output=None):
        self.output = output if output is not None else {"tasks": []}

    def generate_daily_plan(self, prioritized_tasks, behavior_patterns):
        return self.output


class FakeRLScheduler:
    def __init__(self, output=None):
        self.output = output

    def optimize_schedule(self, prioritized_tasks, behavior_patterns, train_before_optimize=False):
        if self.output is not None:
            return self.output
        return {
            "optimized_schedule": [
                {**task, "rl_scheduled_hour": 10, "rl_reward_estimate": 50.0}
                for task in prioritized_tasks
            ]
        }


class FakeOptimizationEngine:
    def __init__(self, output=None):
        self.output = output

    def optimize_schedule(self, optimizer_input, behavior_patterns):
        if self.output is not None:
            return self.output
        return {"optimized_schedule": list(optimizer_input), "projected_productivity_gain": 0.0}


class FakeMemorySystem:
    def __init__(self, output=None, search_output=None):
        self.output = output if output is not None else {"stored": True}
        self.search_output = search_output if search_output is not None else []

    def store_memory(self, description, metadata):
        return self.output

    def search_similar_tasks(self, query, limit=5):
        return self.search_output


class FakeMonitor:
    def __init__(self, metrics=None):
        self.metrics = metrics if metrics is not None else {"engine_execution_count": 0, "average_engine_duration": 0.0}

    def log_engine_execution(self, engine_name, duration):
        if not math.isfinite(float(duration)):
            raise ValueError("bad duration")

    def log_prediction(self, engine_name, prediction_value):
        return None

    def log_event(self, event_name):
        return None

    def log_training_metrics(self, engine_name, metrics):
        return None

    def report_system_metrics(self):
        return self.metrics


class FakeLearningEngine:
    def __init__(self, output=None):
        self.output = output if output is not None else {
            "drift": {"drift_score": 0.0},
            "retraining": {"metrics": {"mae": 1.0}},
            "rl_policy_update": {"average_reward": 1.0},
        }

    def update_model(self, behavior_engine, rl_scheduler, user_id, days_back=90):
        return self.output


def build_fake_orchestrator(**overrides):
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.days_back = 90
    orchestrator.behavior_engine = overrides.get("behavior_engine", FakeBehaviorEngine())
    orchestrator.feature_store = overrides.get("feature_store", FakeFeatureStore())
    orchestrator.knowledge_graph = overrides.get("knowledge_graph", FakeKnowledgeGraph())
    orchestrator.context_engine = overrides.get("context_engine", FakeContextEngine())
    orchestrator.prediction_engine = overrides.get("prediction_engine", FakePredictionEngine())
    orchestrator.decision_engine = overrides.get("decision_engine", FakeDecisionEngine())
    orchestrator.planning_engine = overrides.get("planning_engine", FakePlanningEngine())
    orchestrator.rl_scheduler = overrides.get("rl_scheduler", FakeRLScheduler())
    orchestrator.optimization_engine = overrides.get("optimization_engine", FakeOptimizationEngine())
    orchestrator.memory_system = overrides.get("memory_system", FakeMemorySystem())
    orchestrator.ai_monitor = overrides.get("ai_monitor", FakeMonitor())
    orchestrator.learning_engine = overrides.get("learning_engine", FakeLearningEngine())
    return orchestrator


class TestAIOrchestrator(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session = self.SessionLocal()

        self._seed_behavior_history()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.orchestrator = AIOrchestrator(
            session=self.session,
            memory_storage_directory=self.temp_dir.name,
            rl_policy_path=f"{self.temp_dir.name}/policy.json",
        )

        original_set_active_user = self.orchestrator.behavior_engine._set_active_user

        def set_active_user_with_single_thread(engine_self, user_id):
            original_set_active_user(user_id)
            if (
                engine_self.productivity_model is not None
                and engine_self.productivity_model.model is not None
            ):
                engine_self.productivity_model.model.n_jobs = 1

        # Patch the method with single-thread enforcement
        self.orchestrator.behavior_engine._set_active_user = MethodType(
            set_active_user_with_single_thread,
            self.orchestrator.behavior_engine,
        )

    def tearDown(self) -> None:
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_normalize_tasks_maps_request_fields_without_persisting(self) -> None:
        tasks = [
            {
                "title": "Write research paper",
                "type": "writing",
                "priority": 9,
                "duration": 120,
            }
        ]

        before_count = self.session.query(Task).count()
        normalized = self.orchestrator._normalize_tasks(tasks)
        after_count = self.session.query(Task).count()

        self.assertEqual(before_count, after_count)
        self.assertEqual(normalized[0]["id"], "input-1")
        self.assertEqual(normalized[0]["task_type"], "writing")
        self.assertEqual(normalized[0]["estimated_duration"], 120.0)
        self.assertEqual(normalized[0]["estimated_duration_unit"], "minutes")
        self.assertEqual(normalized[0]["estimated_duration_source"], "transient_request")
        self.assertEqual(normalized[0]["source"], "transient_request")
        optimization_input = dict(normalized[0])
        optimization_input["priority"] = 3
        with self.assertRaises(OptimizationInputError) as raised:
            self.orchestrator._adapt_task_for_optimization(optimization_input)
        self.assertEqual(raised.exception.code, "LEGACY_UNTYPED_DURATION")

    def test_process_tasks_returns_expected_contract(self) -> None:
        result = self.orchestrator.process_tasks(
            tasks=[
                {
                    "title": "Write research paper",
                    "type": "writing",
                    "priority": 9,
                    "duration": 120,
                },
                {
                    "title": "Code experiment",
                    "type": "coding",
                    "priority": 8,
                    "duration": 90,
                },
            ],
            user_id=1,
        )

        self.assertIn("context", result)
        self.assertIn("predicted_tasks", result)
        self.assertIn("recommended_task_order", result)
        self.assertIn("daily_plan", result)
        self.assertIn("rl_schedule", result)
        self.assertIn("optimized_schedule", result)
        self.assertEqual(result["classical_candidate"]["status"], "NOT_READY")
        self.assertIsNone(result["classical_candidate"]["candidate"])
        self.assertIn("memory_event", result)
        self.assertIsNone(result["learning_update"])
        self.assertEqual(len(result["predicted_tasks"]), 2)
        self.assertEqual(len(result["recommended_task_order"]), 2)

    def _seed_behavior_history(self) -> None:
        from datetime import datetime, timedelta

        base_time = datetime.utcnow() - timedelta(days=3)
        task_types = ["writing", "coding", "research", "writing", "coding", "admin"]

        for index, task_type in enumerate(task_types, start=1):
            start_time = base_time + timedelta(hours=index * 2)
            task = Task(
                user_id=1,
                title=f"Historical Task {index}",
                task_type=task_type,
                priority=(index % 5) + 1,
                estimated_duration=60.0 + index * 5,
                actual_duration=55.0 + index * 5,
                start_time=start_time,
                end_time=start_time + timedelta(minutes=60),
                completed=True,
            )
            self.session.add(task)

        self.session.commit()


if __name__ == "__main__":
    unittest.main()


def test_fake_process_tasks_is_deterministic() -> None:
    tasks = [{"title": "Write plan", "type": "writing", "priority": 3, "duration": 1}]

    first = build_fake_orchestrator().process_tasks(tasks, user_id=1)
    second = build_fake_orchestrator().process_tasks(tasks, user_id=1)

    assert first == second


@pytest.mark.parametrize(
    "tasks",
    [
        None,
        {"title": "bad"},
        [None],
        [{"title": "", "duration": 1}],
        [{"title": "Task", "duration": 0}],
        [{"title": "Task", "duration": math.nan}],
        [{"title": "Task", "priority": 0, "duration": 1}],
        [{"title": "Task", "type": 12, "duration": 1}],
    ],
)
def test_process_tasks_rejects_invalid_task_payloads(tasks) -> None:
    with pytest.raises(ValueError):
        build_fake_orchestrator().process_tasks(tasks, user_id=1)


@pytest.mark.parametrize("user_id", [0, -1, "1", math.nan, math.inf, True])
def test_process_tasks_rejects_invalid_user_ids(user_id) -> None:
    with pytest.raises(ValueError, match="user_id"):
        build_fake_orchestrator().process_tasks([{"title": "Task", "duration": 1}], user_id=user_id)


def test_process_tasks_rejects_malformed_prediction_output() -> None:
    orchestrator = build_fake_orchestrator(prediction_engine=FakePredictionEngine(output=[{"id": "x"}]))

    with pytest.raises(ValueError, match="predicted_productivity"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1)


def test_process_tasks_rejects_malformed_decision_output() -> None:
    orchestrator = build_fake_orchestrator(decision_engine=FakeDecisionEngine(output={"bad": "shape"}))

    with pytest.raises(ValueError, match="recommended_task_order"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1)


def test_process_tasks_rejects_malformed_daily_plan() -> None:
    orchestrator = build_fake_orchestrator(planning_engine=FakePlanningEngine(output={"tasks": "bad"}))

    with pytest.raises(ValueError, match="daily_plan"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1)


def test_process_tasks_rejects_malformed_rl_schedule() -> None:
    orchestrator = build_fake_orchestrator(rl_scheduler=FakeRLScheduler(output={"policy_states": 1}))

    with pytest.raises(ValueError, match="optimized_schedule"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1)


def test_prepare_optimizer_input_rejects_invalid_rl_fields() -> None:
    orchestrator = build_fake_orchestrator()

    with pytest.raises(ValueError, match="rl_scheduled_hour"):
        orchestrator._prepare_optimizer_input([{"rl_scheduled_hour": 99}])

    with pytest.raises(ValueError, match="rl_reward_estimate"):
        orchestrator._prepare_optimizer_input([{"rl_scheduled_hour": 10, "rl_reward_estimate": math.inf}])


def test_process_tasks_rejects_malformed_optimization_output() -> None:
    orchestrator = build_fake_orchestrator(optimization_engine=FakeOptimizationEngine(output={"bad": []}))

    with pytest.raises(ValueError, match="optimized_schedule"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1)


def test_process_tasks_rejects_malformed_memory_result() -> None:
    orchestrator = build_fake_orchestrator(memory_system=FakeMemorySystem(output=["bad"]))

    with pytest.raises(ValueError, match="memory system"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1)


def test_process_tasks_rejects_malformed_knowledge_graph_output() -> None:
    orchestrator = build_fake_orchestrator(knowledge_graph=FakeKnowledgeGraph(bad=True))

    with pytest.raises(ValueError, match="user node"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1)


def test_process_tasks_rejects_malformed_learning_update() -> None:
    orchestrator = build_fake_orchestrator(learning_engine=FakeLearningEngine(output={"drift": {}}))

    with pytest.raises(ValueError, match="learning_update"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1, update_learning=True)


def test_process_tasks_rejects_malformed_monitor_metrics() -> None:
    orchestrator = build_fake_orchestrator(ai_monitor=FakeMonitor(metrics={"average_engine_duration": math.nan}))

    with pytest.raises(ValueError, match="system_metrics"):
        orchestrator.process_tasks([{"title": "Task", "duration": 1}], user_id=1)
