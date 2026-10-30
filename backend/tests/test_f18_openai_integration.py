"""
Phase F18 Test Suite: OpenAI API Integration & Real Conversational Planning.

Covers:
1. Provider configuration & key masking (no secrets logged or leaked)
2. Missing API key -> graceful unconfigured status & deterministic fallback
3. Valid structured planning output extraction (JSON schema adherence)
4. Conversational refinement extraction via OpenAI provider
5. Malformed/invalid structured response -> safe fallback without crash
6. Authentication error (HTTP 401) -> classified, status updated, graceful fallback
7. Rate limit (HTTP 429) -> classified, status updated, graceful fallback
8. Request timeout -> classified, status updated, graceful fallback
9. Network failure -> classified, status updated, graceful fallback
10. Provider status reporting (/api/v1/ai/provider-status contract)
11. Proposal provenance and workflow integrity (distinguishing OpenAI from deterministic)
12. User isolation security (ensuring model responses cannot bypass auth or breach boundaries)
"""
import os
import sys

# Ensure repository root is on sys.path for direct script execution and testing
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import json
import urllib.error
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.base import Base
from backend.app.models.task import Task
from backend.app.models.auth import User
from backend.app.models.plan_proposal import PlanProposal
from backend.app.services.task_lifecycle_service import TaskLifecycleService
from backend.app.services.plan_proposal_service import PlanProposalService
from backend.app.interface.llm_provider import (
    OpenAIProvider,
    ConfiguredLLMProvider,
    DeterministicFallbackProvider,
    HybridPlanningParser,
)
from backend.app.interface.ai_interaction import AIInteractionLayer
from backend.app.interface.nl_extractor import ExtractedPlanningContext


@pytest.fixture
def test_clock():
    fixed = datetime(2026, 10, 18, 9, 0, 0)
    return lambda: fixed


@pytest.fixture
def db_session():
    """In-memory SQLite database session isolated per test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    u1 = User(id=1, email="user1@example.com", password_hash="hash1", is_active=True, created_at=datetime.now())
    u2 = User(id=2, email="user2@example.com", password_hash="hash2", is_active=True, created_at=datetime.now())
    session.add_all([u1, u2])
    session.commit()

    yield session
    session.close()


# -------------------------------------------------------------------------
# 1. Missing API Key & Unconfigured Status
# -------------------------------------------------------------------------

def test_missing_api_key_unconfigured_status():
    """When OPENAI_API_KEY is not set or empty, provider reports unconfigured without claiming to be active."""
    provider = OpenAIProvider(api_key="", model="gpt-4o-mini")
    assert not provider.is_configured()
    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-4o-mini"
    
    status = provider.get_status()
    assert status["provider"] == "openai"
    assert status.get("is_configured", status.get("configured")) is False
    assert status["status"] in ("unconfigured", "openai_unconfigured")
    assert status["masked_key"] == "<none>"
    assert status["last_error"] is None

    # Extraction returns None and delegates cleanly
    ctx = provider.extract_planning_context("I have an assignment due tomorrow.")
    assert ctx is None

    ref = provider.parse_refinement("Move the assignment first.")
    assert ref is None


def test_api_key_masking_security():
    """Ensure raw credentials are never exposed through status, serialization, or masking."""
    provider = OpenAIProvider(api_key="sk-proj-1234567890abcdefghijklmnop", model="gpt-4o-mini")
    assert provider.is_configured()
    
    masked = provider._mask_key("sk-proj-1234567890abcdefghijklmnop")
    assert masked.startswith("sk-")
    assert masked.endswith("nop") or masked.endswith("mnop")
    assert "1234567890abcdef" not in masked
    assert len(masked) < 20

    status = provider.get_status()
    assert status.get("is_configured", status.get("configured")) is True
    assert status["status"] in ("ready", "openai_configured")
    assert status["masked_key"] == masked
    # Raw key is strictly absent from the status payload
    assert "sk-proj-1234567890abcdefghijklmnop" not in str(status)


# -------------------------------------------------------------------------
# 2. Valid Structured Response Interpretation
# -------------------------------------------------------------------------

def test_valid_structured_planning_extraction(test_clock):
    """Test full parsing and validation of a mock OpenAI Chat Completions structured response."""
    provider = OpenAIProvider(api_key="sk-test-valid-key", model="gpt-4o-mini")

    mock_chat_completion = {
        "id": "chatcmpl-test-1",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "tasks": [
                            {
                                "title": "Math Assignment",
                                "priority": 5,
                                "estimated_duration": 1.5,
                                "deadline_expression": "tomorrow",
                                "dependencies": []
                            },
                            {
                                "title": "History Exam Prep",
                                "priority": 4,
                                "estimated_duration": 2.0,
                                "deadline_expression": "in 3 days",
                                "dependencies": []
                            }
                        ],
                        "available_hours": 4.0,
                        "clarification_needed": False,
                        "use_existing_tasks": False
                    })
                }
            }
        ]
    }

    with patch.object(provider, "_execute_http_request", return_value=mock_chat_completion):
        ctx = provider.extract_planning_context(
            "I have a math assignment due tomorrow and history exam prep in 3 days. I have 4 hours available today.",
            reference_time=test_clock()
        )

        assert ctx is not None
        assert ctx.parser_provenance == "llm_openai"
        assert ctx.available_hours == 4.0
        assert not ctx.clarification_needed
        assert len(ctx.extracted_tasks) == 2

        t1 = ctx.extracted_tasks[0]
        assert t1.title == "Math Assignment"
        assert t1.priority == 5
        assert t1.estimated_duration == 1.5
        assert t1.deadline_expression == "tomorrow"
        assert t1.deadline_dt.date() == datetime(2026, 10, 19).date()

        t2 = ctx.extracted_tasks[1]
        assert t2.title == "History Exam Prep"
        assert t2.priority == 4
        assert t2.estimated_duration == 2.0
        assert t2.deadline_expression == "in 3 days"
        assert t2.deadline_dt.date() == datetime(2026, 10, 21).date()


def test_conversational_refinement_extraction():
    """Test structured extraction of follow-up refinement commands via OpenAI provider."""
    provider = OpenAIProvider(api_key="sk-test-valid-key", model="gpt-4o-mini")

    mock_refinement_completion = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "action": "move_first",
                        "task": "Math Assignment",
                        "first_task": None,
                        "second_task": None,
                        "new_available_hours": None,
                        "buffer_minutes": None,
                        "new_priority": None,
                        "new_duration_hours": None,
                        "description": "Moved Math Assignment to execute first in today's window."
                    })
                }
            }
        ]
    }

    with patch.object(provider, "_execute_http_request", return_value=mock_refinement_completion):
        ref = provider.parse_refinement(
            "Move the assignment ahead of my exam preparation.",
            existing_schedule=[{"title": "Math Assignment"}, {"title": "History Exam Prep"}]
        )

        assert ref is not None
        assert ref["action"] == "move_first"
        assert ref["task"] == "Math Assignment"
        assert "Math Assignment" in ref["description"]


# -------------------------------------------------------------------------
# 3. Error Handling and Classifications
# -------------------------------------------------------------------------

def test_authentication_error_401():
    """HTTP 401 must classify as AUTHENTICATION_ERROR and set status to authentication_error without crashing."""
    provider = OpenAIProvider(api_key="sk-invalid-bad-key", model="gpt-4o-mini")

    http_error = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=None
    )

    with patch.object(provider, "_execute_http_request", side_effect=http_error):
        res = provider.extract_planning_context("Plan my schedule")
        assert res is None

        status = provider.get_status()
        assert status["status"] in ("authentication_error", "openai_authentication_failed")
        assert status["error_category"] == "AUTHENTICATION_ERROR"
        assert "401" in str(status["last_error"]) or "Unauthorized" in str(status["last_error"])
        # Ensure raw key is never placed into error message
        assert "sk-invalid-bad-key" not in status["last_error"]


def test_rate_limit_error_429():
    """HTTP 429 must classify as RATE_LIMIT_EXCEEDED and report rate_limited."""
    provider = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")

    http_error = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=429,
        msg="Rate limit reached",
        hdrs={},
        fp=None
    )

    with patch.object(provider, "_execute_http_request", side_effect=http_error):
        res = provider.extract_planning_context("Plan my day")
        assert res is None

        status = provider.get_status()
        assert status["status"] in ("rate_limited", "openai_rate_limited")
        assert status["error_category"] == "RATE_LIMIT_EXCEEDED"


def test_request_timeout():
    """Timeout exceptions must classify as TIMEOUT and report timed_out."""
    provider = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")

    timeout_err = TimeoutError("Request timed out after 10.0 seconds")

    with patch.object(provider, "_execute_http_request", side_effect=timeout_err):
        res = provider.extract_planning_context("Plan my day")
        assert res is None

        status = provider.get_status()
        assert status["status"] in ("timed_out", "openai_timeout")
        assert status["error_category"] == "TIMEOUT"


def test_network_failure():
    """URLError network disconnections must classify as NETWORK_ERROR."""
    provider = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")

    url_error = urllib.error.URLError("Connection reset by peer: dial tcp")

    with patch.object(provider, "_execute_http_request", side_effect=url_error):
        res = provider.extract_planning_context("Plan my day")
        assert res is None

        status = provider.get_status()
        assert status["status"] in ("network_error", "openai_network_error", "openai_temporarily_unavailable")
        assert status["error_category"] == "NETWORK_ERROR"


def test_malformed_json_response():
    """Malformed or invalid non-JSON output from the model must not raise unhandled exceptions."""
    provider = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")

    corrupt_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is raw unformatted text without any JSON structure at all: {broken, 'tasks': ["
                }
            }
        ]
    }

    with patch.object(provider, "_execute_http_request", return_value=corrupt_response):
        res = provider.extract_planning_context("Plan my day")
        assert res is None

        status = provider.get_status()
        assert status["status"] in ("malformed_output", "openai_malformed_output")
        assert status["error_category"] == "INVALID_PAYLOAD"


# -------------------------------------------------------------------------
# 4. Hybrid Parser Seamless Fallback
# -------------------------------------------------------------------------

def test_hybrid_parser_fallback_to_deterministic_on_error(test_clock):
    """When OpenAI call fails with any network/auth error, HybridPlanningParser cleanly falls back to deterministic."""
    provider = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")
    parser = HybridPlanningParser(llm_provider=provider, clock=test_clock)

    http_error = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=503,
        msg="Service Unavailable",
        hdrs={},
        fp=None
    )

    with patch.object(provider, "_execute_http_request", side_effect=http_error):
        ctx = parser.extract_planning_context(
            "I have an assignment due tomorrow and an exam in three days. I have 4 hours available today."
        )

        assert ctx is not None
        assert ctx.parser_provenance in ("deterministic", "deterministic_fallback")
        assert ctx.available_hours == 4.0
        assert len(ctx.extracted_tasks) >= 2


def test_conversational_refinement_fallback_to_deterministic():
    """When OpenAI refinement parsing fails, fallback parser extracts intent deterministically."""
    provider = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")
    parser = HybridPlanningParser(llm_provider=provider)

    with patch.object(provider, "_execute_http_request", side_effect=Exception("API failure")):
        ref = parser.parse_refinement(
            "I only have two hours available now. Adjust the plan.",
            existing_schedule=[{"title": "Math Assignment"}]
        )

        assert ref is not None
        assert ref["action"] == "reduce_available_hours"
        assert ref["new_available_hours"] == 2.0


# -------------------------------------------------------------------------
# 5. End-to-End Planning & Proposal Lifecycle Integration
# -------------------------------------------------------------------------

def test_ai_interaction_layer_provenance_and_openai_integration(db_session, test_clock):
    """Verify that AIInteractionLayer delegates to configured OpenAI provider and records parser_provenance."""
    provider = OpenAIProvider(api_key="sk-test-key", model="gpt-4o-mini")
    mock_memory = MagicMock()
    mock_memory.retrieve_context.return_value = {"recent_memories": []}
    layer = AIInteractionLayer(
        session=db_session,
        clock=test_clock,
        parser=HybridPlanningParser(llm_provider=provider, clock=test_clock),
        memory_system=mock_memory,
    )

    mock_completion = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "tasks": [
                            {"title": "Assignment", "priority": 5, "estimated_duration": 1.5, "deadline_expression": "tomorrow"},
                            {"title": "Exam Prep", "priority": 4, "estimated_duration": 2.0, "deadline_expression": "in 3 days"}
                        ],
                        "available_hours": 4.0,
                        "clarification_needed": False,
                        "use_existing_tasks": False
                    })
                }
            }
        ]
    }

    with patch.object(provider, "_execute_http_request", return_value=mock_completion):
        intent, params = layer.extract_parameters("I have an assignment due tomorrow, an exam in three days. I have four hours today. Plan my schedule.")

        assert intent == "plan_day"
        assert params["parser_provenance"] == "llm_openai"
        assert params["available_hours"] == 4.0
        assert len(params["extracted_tasks"]) == 2


def test_user_isolation_security_in_proposals(db_session, test_clock):
    """Verify strict user isolation: User 2 cannot access, refine, or accept User 1's proposals."""
    proposal_service = PlanProposalService(db_session, clock=test_clock)

    # Create proposal for User 1
    p1 = proposal_service.create_proposal(
        user_id=1,
        schedule=[{"title": "User 1 Private Task", "scheduled_hour": 9.0}],
        tasks=[{"title": "User 1 Private Task", "priority": 5, "estimated_duration": 1.0}],
        constraints={},
        provenance={"provider": "openai", "parser_provenance": "llm_openai"},
        raw_result={"test": True},
        available_hours=4.0
    )

    # User 2 attempts to retrieve User 1's proposal by ID
    p2_attempt = proposal_service.get_proposal_by_id(p1.id, user_id=2)
    assert p2_attempt is None, "User 2 should not be able to retrieve User 1's proposal"

    # User 2 attempts to get active proposal
    u2_active = proposal_service.get_active_proposal(user_id=2)
    assert u2_active is None

    # User 2 attempts to accept User 1's proposal
    with pytest.raises(ValueError, match="not found or belongs to another user"):
        proposal_service.accept_proposal(p1.id, user_id=2)


if __name__ == "__main__":
    import time
    print("=====================================================================", flush=True)
    print("Running Phase F18 OpenAI API Integration & Conversational Planning Test Suite", flush=True)
    print("=====================================================================", flush=True)
    
    clock_fn = lambda: datetime(2026, 10, 18, 9, 0, 0)
    
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    u1 = User(id=1, email="user1@example.com", password_hash="hash1", is_active=True, created_at=datetime.now())
    u2 = User(id=2, email="user2@example.com", password_hash="hash2", is_active=True, created_at=datetime.now())
    session.add_all([u1, u2])
    session.commit()

    tests = [
        ("Missing API Key Unconfigured Status", lambda: test_missing_api_key_unconfigured_status()),
        ("API Key Masking Security & Zero Leakage", lambda: test_api_key_masking_security()),
        ("Valid Structured Planning Extraction", lambda: test_valid_structured_planning_extraction(clock_fn)),
        ("Conversational Refinement Extraction", lambda: test_conversational_refinement_extraction()),
        ("Authentication Error 401 Classification", lambda: test_authentication_error_401()),
        ("Rate Limit Error 429 Classification", lambda: test_rate_limit_error_429()),
        ("Request Timeout Classification", lambda: test_request_timeout()),
        ("Network Failure Classification", lambda: test_network_failure()),
        ("Malformed JSON Response Fallback", lambda: test_malformed_json_response()),
        ("Hybrid Parser Deterministic Fallback on Error", lambda: test_hybrid_parser_fallback_to_deterministic_on_error(clock_fn)),
        ("Refinement Fallback to Deterministic", lambda: test_conversational_refinement_fallback_to_deterministic()),
        ("AI Interaction Layer & OpenAI Provenance", lambda: test_ai_interaction_layer_provenance_and_openai_integration(session, clock_fn)),
        ("User Isolation Security in Proposals", lambda: test_user_isolation_security_in_proposals(session, clock_fn)),
    ]

    passed = 0
    failed = 0
    t0 = time.time()
    for name, fn in tests:
        try:
            fn()
            print(f"  [PASS] {name}", flush=True)
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}", flush=True)
            failed += 1

    total_time = time.time() - t0
    print("---------------------------------------------------------------------", flush=True)
    print(f"Results: {passed} passed, {failed} failed in {total_time:.3f}s", flush=True)
    print("=====================================================================", flush=True)
    if failed > 0:
        exit(1)

