import os
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.app.database.db import get_db
from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.services.task_lifecycle_service import TaskLifecycleService


class TestAPIExposure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:", 
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine)
        
        def override_get_db():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()
                
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    def setUp(self) -> None:
        self.session = self.SessionLocal()
        self.session.query(Task).delete()
        self.session.commit()
        self.lifecycle = TaskLifecycleService(self.session)
        
    def tearDown(self) -> None:
        self.session.close()

    def test_cors_behavior(self) -> None:
        response = self.client.options(
            "/api/v1/system/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_get_tasks_success(self) -> None:
        self.lifecycle.create_task(
            user_id=1, title="Test 1", task_type="coding", priority=1, estimated_duration=30.0
        )
        response = self.client.get("/api/v1/tasks?user_id=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tasks", data)
        self.assertEqual(len(data["tasks"]), 1)
        self.assertEqual(data["tasks"][0]["title"], "Test 1")

    def test_get_tasks_empty(self) -> None:
        response = self.client.get("/api/v1/tasks?user_id=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["tasks"]), 0)

    def test_get_tasks_validation_error(self) -> None:
        response = self.client.get("/api/v1/tasks")
        self.assertEqual(response.status_code, 422) # Missing user_id
        
        response = self.client.get("/api/v1/tasks?user_id=0")
        self.assertEqual(response.status_code, 422) # user_id ge=1

    def test_get_task_by_id_success(self) -> None:
        task = self.lifecycle.create_task(
            user_id=1, title="Test Single", task_type="coding", priority=2, estimated_duration=60.0
        )
        response = self.client.get(f"/api/v1/tasks/{task.id}?user_id=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["task"]["title"], "Test Single")

    def test_get_task_by_id_not_found(self) -> None:
        response = self.client.get("/api/v1/tasks/999?user_id=1")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Task not found")

    def test_get_task_by_id_user_isolation(self) -> None:
        task = self.lifecycle.create_task(
            user_id=1, title="Test Single", task_type="coding", priority=2, estimated_duration=60.0
        )
        response = self.client.get(f"/api/v1/tasks/{task.id}?user_id=2")
        self.assertEqual(response.status_code, 404)

    @patch("backend.app.orchestrator.ai_orchestrator.AIOrchestrator.execute_executive_planning")
    def test_executive_plan_success(self, mock_execute: MagicMock) -> None:
        mock_execute.return_value = {"executive_summary": "Test summary", "recommended_plan": {}}
        payload = {
            "user_id": 1,
            "tasks": [{"title": "Task 1", "type": "coding", "priority": 1, "duration": 30.0}],
            "query": "Plan this",
            "days_back": 90
        }
        response = self.client.post("/api/v1/ai/executive-plan", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["executive_summary"], "Test summary")

    @patch("backend.app.orchestrator.ai_orchestrator.AIOrchestrator.execute_executive_planning")
    def test_executive_plan_failure(self, mock_execute: MagicMock) -> None:
        mock_execute.side_effect = ValueError("Invalid tasks")
        payload = {
            "user_id": 1,
            "tasks": [{"title": "Task 1", "type": "coding", "priority": 1, "duration": 30.0}]
        }
        response = self.client.post("/api/v1/ai/executive-plan", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid tasks")

    def test_system_health_operational(self) -> None:
        response = self.client.get("/api/v1/system/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "operational")
        self.assertTrue(data["database_connected"])

    @patch("sqlalchemy.orm.Session.execute")
    def test_system_health_db_failure(self, mock_execute: MagicMock) -> None:
        mock_execute.side_effect = Exception("DB error")
        response = self.client.get("/api/v1/system/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "degraded")
        self.assertFalse(data["database_connected"])

    def test_system_status_success(self) -> None:
        response = self.client.get("/api/v1/system/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "operational")

    def test_quantum_status(self) -> None:
        response = self.client.get("/api/v1/quantum/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["available"])
        self.assertFalse(data["direct_execution_exposed"])
        self.assertIn("allow_quantum", data["config"])

    @patch("backend.app.quantum.integration.models.AIQuantumIntegrationConfig", side_effect=ImportError)
    def test_quantum_status_unavailable(self, mock_import: MagicMock) -> None:
        response = self.client.get("/api/v1/quantum/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["available"])

    def test_model_status(self) -> None:
        response = self.client.get("/api/v1/ml/model-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "uninitialized")
        self.assertTrue(data["in_memory_only"])
        self.assertEqual(data["models_registered"], 0)

if __name__ == "__main__":
    unittest.main()
