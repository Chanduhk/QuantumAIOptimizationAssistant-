from __future__ import annotations

import tempfile
import unittest
from types import MethodType

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


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
        self.assertEqual(normalized[0]["source"], "transient_request")

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
