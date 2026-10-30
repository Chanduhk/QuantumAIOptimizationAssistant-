import asyncio
import time
from threading import Event
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
def jam_environment(monkeypatch):
    monkeypatch.setattr(VectorMemorySystem, "preload_model_async", lambda model_name="all-MiniLM-L6-v2": None)
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


def test_vector_memory_reuses_loaded_embedding_model(tmp_path, monkeypatch):
    model_name = "f10-runtime-cache-regression"
    VectorMemorySystem._model_cache.pop(model_name, None)
    calls = []
    loaded_model = object()

    def load_model(self):
        calls.append(self.model_name)
        return loaded_model

    monkeypatch.setattr(VectorMemorySystem, "_load_model_uncached", load_model)
    first = VectorMemorySystem(storage_directory=str(tmp_path / "first"), model_name=model_name)
    second = VectorMemorySystem(storage_directory=str(tmp_path / "second"), model_name=model_name)

    assert first.model is loaded_model
    assert second.model is loaded_model
    assert calls == [model_name]


def test_vector_memory_directory_can_be_isolated_by_runtime_configuration(tmp_path, monkeypatch):
    path = tmp_path / "isolated-memory"
    monkeypatch.setenv("HELIOX_VECTOR_MEMORY_DIR", str(path))
    memory = VectorMemorySystem(model_name=None)
    assert memory.storage_directory == path


def test_vector_memory_load_is_local_only(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace

    calls = []

    def sentence_transformer(name, *, local_files_only):
        calls.append((name, local_files_only))
        return object()

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=sentence_transformer),
    )
    model_name = "f10-local-only-regression"
    VectorMemorySystem._model_cache.pop(model_name, None)

    VectorMemorySystem(storage_directory=str(tmp_path), model_name=model_name)

    assert calls == [(model_name, True)]


def test_async_local_model_preload_starts_once_per_process(monkeypatch):
    from backend.app.memory import vector_memory

    model_name = "f11-3-single-background-preload"
    started_threads = []

    class DeferredThread:
        def __init__(self, *, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self):
            started_threads.append(self)

    monkeypatch.setattr(VectorMemorySystem, "_model_cache", {})
    monkeypatch.setattr(VectorMemorySystem, "_model_load_started", set())
    monkeypatch.setattr(VectorMemorySystem, "_model_load_events", {})
    monkeypatch.setattr(vector_memory, "Thread", DeferredThread)

    VectorMemorySystem.preload_model_async(model_name)
    VectorMemorySystem.preload_model_async(model_name)

    assert len(started_threads) == 1
    assert started_threads[0].name == "heliox-local-embedding-warmup"
    assert started_threads[0].daemon is True


def test_brain_factory_schedules_model_warmup_before_memory_construction(monkeypatch):
    calls = []

    class Brain:
        def __init__(self, *, session):
            calls.append(("brain", session))

    monkeypatch.setattr(
        VectorMemorySystem,
        "preload_model_async",
        lambda: calls.append(("preload", None)),
    )
    monkeypatch.setattr(main, "QuantumLifeBrain", Brain)

    session = object()
    assert main._build_brain(session) is not None
    assert calls == [("preload", None), ("brain", session)]


def test_vector_memory_uses_fallback_while_local_model_loads_and_reindexes(tmp_path, monkeypatch):
    import numpy as np

    model_name = "f11-3-async-local-model"
    entered = Event()
    release = Event()
    model = type(
        "FakeEmbeddingModel",
        (),
        {"encode": lambda self, texts, **kwargs: np.ones((len(texts), 384), dtype=np.float32)},
    )()

    def load_model(self):
        entered.set()
        assert release.wait(10)
        return model

    monkeypatch.setattr(VectorMemorySystem, "_load_model_uncached", load_model)
    VectorMemorySystem.preload_model_async(model_name)
    assert entered.wait(10)

    storage = tmp_path / "memory"
    cold = VectorMemorySystem(storage_directory=str(storage), model_name=model_name)
    assert cold.model is None
    first = cold._embed(["repeatable fallback"])
    assert np.array_equal(first, cold._embed(["repeatable fallback"]))
    cold.store_memory("private user memory", {"user_id": 41})
    assert '"mode": "deterministic_fallback"' in cold.embedding_metadata_path.read_text()

    release.set()
    assert VectorMemorySystem.wait_for_model_load(model_name, timeout=10)
    warm = VectorMemorySystem(storage_directory=str(storage), model_name=model_name)
    assert warm.model is model
    assert '"mode": "sentence_transformer:f11-3-async-local-model"' in warm.embedding_metadata_path.read_text()
    assert len(warm.records) == 1

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


def test_memory_search_normalizes_numpy_indices_and_uses_authenticated_user(jam_environment, monkeypatch):
    import numpy as np

    client = jam_environment
    user_id = register_user(client)
    calls = []

    class MemoryBrain:
        def search_memory(self, *, query, limit, user_id):
            calls.append((query, limit, user_id))
            return {"matches": [{"memory_id": np.int64(3), "similarity_score": np.float32(0.75)}]}

    monkeypatch.setattr(main, "_build_brain", lambda db: MemoryBrain())
    response = client.post(
        "/api/v1/ai/memory/search",
        headers=csrf_headers(client),
        json={"query": "private task memory", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json() == {"result": {"matches": [{"memory_id": 3, "similarity_score": 0.75}]}}
    assert calls == [("private task memory", 5, user_id)]


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

    controller = AIBrainController(session=None, memory_system=VectorMemorySystem(model_name=None))
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
