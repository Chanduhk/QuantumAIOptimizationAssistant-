import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as main
from backend.app.context.context_engine import ContextEngine
from backend.app.database.db import get_db
from backend.app.interface.ai_interaction import AIInteractionLayer
from backend.app.memory.vector_memory import VectorMemorySystem
from backend.app.models.base import Base
from backend.app.orchestrator.ai_brain_controller import AIBrainController
from backend.app.orchestrator.brain_models import BrainExecutionTrace, BrainRequest
from backend.app.services.auth_service import CSRF_COOKIE


@pytest.fixture
def jam_environment():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(main.app)
    try:
        yield client
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def register_user(client: TestClient, email: str = "jam@example.com") -> int:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure jam test password"},
    )
    assert response.status_code == 201
    return response.json()["user"]["id"]


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token
    return {"X-CSRF-Token": token}


def test_authenticated_jam_command_response_and_user_identity(jam_environment, monkeypatch):
    client = jam_environment
    user_id = register_user(client)
    calls = []

    class StubInteraction:
        async def process_command(self, *, user_id: int, command: str):
            calls.append((user_id, command))
            return {"intent": "get_recommendations", "result": {"message": "Recommendation result"}}

    monkeypatch.setattr(main, "_build_interaction_layer", lambda db, days_back: StubInteraction())
    response = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={"user_id": user_id, "command": "get recommendations", "days_back": 90},
    )
    assert response.status_code == 200
    assert response.json() == {
        "intent": "get_recommendations",
        "result": {"message": "Recommendation result"},
    }
    assert calls == [(user_id, "get recommendations")]


def test_jam_command_authentication_and_backend_error(jam_environment, monkeypatch):
    client = jam_environment
    assert client.post(
        "/api/v1/ai/command",
        json={"user_id": 1234, "command": "recommend", "days_back": 90},
    ).status_code == 401
    user_id = register_user(client)

    class FailedInteraction:
        async def process_command(self, *, user_id: int, command: str):
            raise ValueError("AI engine unavailable")

    monkeypatch.setattr(main, "_build_interaction_layer", lambda db, days_back: FailedInteraction())
    failed = client.post(
        "/api/v1/ai/command",
        headers=csrf_headers(client),
        json={"user_id": user_id, "command": "recommend", "days_back": 90},
    )
    assert failed.status_code == 400
    assert "AI engine unavailable" in failed.json()["detail"]


def test_open_ended_command_is_not_routed_to_planning_or_optimization():
    interaction = AIInteractionLayer(session=None, memory_system=object())
    assert interaction.detect_intent("Hello, can you explain this idea?") == "general_question"

    controller = AIBrainController(session=None)
    controller._execute_central_planning = AsyncMock()
    request = BrainRequest(
        request_id="f4-general-chat",
        user_id=1234,
        intent="general_question",
        command="Hello, can you explain this idea?",
    )
    trace = BrainExecutionTrace(request_id=request.request_id, started_at=time.time())
    with pytest.raises(ValueError, match="Open-ended JAM chat is not available"):
        asyncio.run(controller._route_and_execute(request, trace))
    controller._execute_central_planning.assert_not_awaited()


def test_context_semantic_memory_search_is_scoped_to_user(tmp_path):
    memory = VectorMemorySystem(storage_directory=str(tmp_path), model_name=None)
    memory.store_memory("schedule preference private to first user", {"user_id": 101})
    memory.store_memory("schedule preference private to second user", {"user_id": 202})
    context = ContextEngine(memory).build_context(
        user_id=101,
        behavior_patterns={},
        current_tasks=[],
        query="schedule preference",
    )
    assert context["semantic_matches"]
    assert all(item["metadata"]["user_id"] == 101 for item in context["semantic_matches"])
