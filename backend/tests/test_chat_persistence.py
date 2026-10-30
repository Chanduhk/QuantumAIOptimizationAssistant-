import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.models.base import Base
from backend.app.models.auth import User, AuthSession
from backend.app.models.chat import Conversation, ChatMessage
from backend.app.services.chat_service import ChatService
from backend.app.database.db import get_db
from backend.main import app


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_chat_service_crud_and_isolation(test_db):
    service = ChatService(test_db)

    # Create users
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    u1 = User(id=101, email="user1@example.com", password_hash="dummy", created_at=now)
    u2 = User(id=102, email="user2@example.com", password_hash="dummy", created_at=now)
    test_db.add_all([u1, u2])
    test_db.commit()

    # User 1 creates conversation
    conv1 = service.create_conversation(101, title="User 1 Project Chat")
    assert conv1.id is not None
    assert conv1.title == "User 1 Project Chat"

    # User 1 adds messages
    msg1 = service.add_user_message(101, conv1.id, "Plan my day with 4 hours")
    assert msg1.id is not None
    assert msg1.role == "user"
    assert msg1.content == "Plan my day with 4 hours"

    msg2 = service.add_assistant_message(
        101, conv1.id, "Here is your plan for today.", intent="plan_day", metadata={"scheduled": True}
    )
    assert msg2.id is not None
    assert msg2.role == "assistant"
    assert msg2.intent == "plan_day"

    # Verify User 1 can list their conversations
    convs_u1 = service.list_conversations(101)
    assert len(convs_u1) == 1
    assert convs_u1[0]["id"] == conv1.id

    # Verify User 2 sees 0 conversations
    convs_u2 = service.list_conversations(102)
    assert len(convs_u2) == 0

    # User 2 cannot access User 1's conversation
    assert service.get_conversation(102, conv1.id) is None
    assert len(service.get_messages(102, conv1.id)) == 0

    # User 1 retrieves turns
    turns = service.get_conversation_turns(101, conv1.id, max_turns=5)
    assert len(turns) == 2
    assert turns[0] == {"role": "user", "content": "Plan my day with 4 hours"}
    assert turns[1] == {"role": "assistant", "content": "Here is your plan for today."}

    # Delete conversation
    assert service.delete_conversation(101, conv1.id) is True
    assert service.get_conversation(101, conv1.id) is None
    assert len(service.list_conversations(101)) == 0


def test_general_question_returns_grounded_answer(test_db):
    from backend.app.interface.ai_interaction import AIInteractionLayer

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    u = User(id=201, email="test@example.com", password_hash="dummy", created_at=now)
    test_db.add(u)
    test_db.commit()

    layer = AIInteractionLayer(test_db)
    # Asking a general question should NOT raise ValueError("Open-ended JAM chat is not available yet")
    import asyncio
    result = asyncio.run(layer.process_command(user_id=201, command="Hello, what can you do?"))
    assert result["intent"] == "general_question"
    assert result["result"]["action"] == "general_answer"
    assert len(result["result"]["executive_summary"]) > 10


def test_provider_status_and_test_endpoints(monkeypatch):
    client = TestClient(app)

    # Provider status is public
    res = client.get("/api/v1/ai/provider-status")
    assert res.status_code == 200
    data = res.json()
    assert "provider" in data
    assert "is_configured" in data
    assert "fallback_active" in data

    # Provider test endpoint
    res_test = client.post("/api/v1/ai/provider-test")
    assert res_test.status_code == 200
    test_data = res_test.json()
    assert "success" in test_data
    assert "message" in test_data
