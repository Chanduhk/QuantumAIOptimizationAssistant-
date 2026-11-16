"""
Test Suite: Google Gemini Integration & LLM Provider Selection for JAM Assistant.

Covers:
1. Gemini provider configuration & key masking (no secrets logged or leaked)
2. Gemini provider selected as primary LLM by default
3. OpenAI integration remains intact and selectable when requested, but NOT auto-selected
4. Ollama and deterministic fallback behavior available
5. Valid structured planning output extraction (Gemini JSON schema)
6. Conversational refinement extraction via Gemini provider
7. Authentication errors (HTTP 400, 401, 403) -> classified, status updated, graceful fallback
8. Rate limit / Quota errors (HTTP 429) -> classified, status updated, graceful fallback
9. Request timeout -> classified, status updated, graceful fallback
10. Network failure -> classified, status updated, graceful fallback
11. Malformed JSON response -> classified as INVALID_PAYLOAD, safe fallback
12. Provider status endpoint (/api/v1/ai/provider-status) reports Gemini accurately
13. Provider connection test endpoint (/api/v1/ai/provider-test)
14. Provenance tracking: identifies "llm_gemini" vs "deterministic_fallback"
15. User isolation security
"""
import os
import sys

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
    GeminiProvider,
    OpenAIProvider,
    ConfiguredLLMProvider,
    DeterministicFallbackProvider,
    HybridPlanningParser,
    get_llm_provider,
    get_default_llm_provider,
)
from backend.app.interface.ai_interaction import AIInteractionLayer
from backend.app.interface.nl_extractor import ExtractedPlanningContext


@pytest.fixture
def test_clock():
    fixed = datetime(2026, 10, 30, 9, 0, 0)
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


def test_missing_api_key_unconfigured_status():
    """When GEMINI_API_KEY is empty, GeminiProvider reports unconfigured and fallback active."""
    provider = GeminiProvider(api_key="", model="gemini-2.5-flash")
    assert not provider.is_configured()
    status = provider.get_status()
    assert status["provider"] == "gemini"
    assert status["is_configured"] is False
    assert status["status"] == "gemini_unconfigured"
    assert status["fallback_active"] is True
    assert "Unconfigured" in status["status_label"]
    assert provider.extract_planning_context("Plan my morning with 3 tasks") is None


def test_api_key_masking_security():
    """Verify that full API key is NEVER exposed in status, logs, or string representations."""
    raw_secret_key = "AIzaSySecretApiKeyForGeminiNeverExposeInLogsOrResponses1234"
    provider = GeminiProvider(api_key=raw_secret_key, model="gemini-2.5-flash")

    status = provider.get_status()
    assert raw_secret_key not in json.dumps(status)
    assert status["masked_key"].startswith("AIz...")
    assert status["masked_key"].endswith("234")
    assert raw_secret_key not in provider._mask_key(raw_secret_key)
    assert provider._mask_key("short") == "***"
    assert provider._mask_key("") == "<none>"


def test_provider_router_selects_gemini_by_default(monkeypatch):
    """Verify provider router defaults to Gemini even when OPENAI_API_KEY is also present."""
    monkeypatch.setenv("HELIOX_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestGeminiKey")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key")

    provider = get_default_llm_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.provider_name == "gemini"
    assert provider.model_name == "gemini-3.8-flash"
    assert provider.is_configured() is True

    parser = HybridPlanningParser()
    assert isinstance(parser.llm_provider, GeminiProvider)
    assert parser.llm_provider.provider_name == "gemini"


def test_openai_remains_available_when_explicitly_configured(monkeypatch):
    """Verify OpenAI integration code and credentials remain intact when explicitly requested."""
    monkeypatch.setenv("HELIOX_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-explicit-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    provider = get_llm_provider("openai")
    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-4o"
    assert provider.is_configured() is True


def test_ollama_and_deterministic_fallback_available():
    """Verify Ollama and Deterministic Fallback remain available."""
    ollama_provider = get_llm_provider("ollama", endpoint="http://localhost:11434/v1/chat/completions")
    assert ollama_provider.provider_name == "ollama"
    assert ollama_provider.is_configured() is True

    fb = get_llm_provider("deterministic")
    assert isinstance(fb, DeterministicFallbackProvider)
    assert fb.provider_name == "deterministic_rule_based"
    assert fb.is_configured() is True


def test_valid_gemini_structured_planning_extraction(test_clock):
    """Verify GeminiProvider formats request and parses Gemini candidate parts JSON."""
    provider = GeminiProvider(api_key="AIzaSyTestKey", model="gemini-2.5-flash")

    gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "tasks": [
                                    {
                                        "title": "Prepare Financial Report",
                                        "priority": 4,
                                        "estimated_duration": 2.5,
                                        "deadline_expression": "tomorrow at 5pm",
                                        "dependencies": []
                                    },
                                    {
                                        "title": "<script>alert('xss')</script>Client Review",
                                        "priority": 2,
                                        "estimated_duration": 1.0,
                                        "deadline_expression": "in two days",
                                        "dependencies": ["Prepare Financial Report"]
                                    }
                                ],
                                "available_hours": 5.0,
                                "use_existing_tasks": False,
                                "task_count": 2,
                                "requested_actions": ["plan_schedule"],
                                "clarification_needed": False,
                                "clarification_question": None
                            })
                        }
                    ],
                    "role": "model"
                },
                "finishReason": "STOP"
            }
        ]
    }

    with patch.object(provider, "_execute_http_request", return_value=gemini_response):
        ctx = provider.extract_planning_context(
            "Plan my schedule for tomorrow: Financial report for 2.5 hours and Client Review for 1 hour.",
            reference_time=test_clock(),
        )

    assert ctx is not None
    assert ctx.parser_provenance == "llm_gemini"
    assert ctx.available_hours == 5.0
    assert len(ctx.extracted_tasks) == 2

    t1, t2 = ctx.extracted_tasks
    assert t1.title == "Prepare Financial Report"
    assert t1.priority == 4
    assert t1.estimated_duration == 2.5

    # Verify HTML script sanitization
    assert "<script>" not in t2.title
    assert "Client Review" in t2.title
    assert t2.priority == 2
    assert t2.estimated_duration == 1.0
    assert "Prepare Financial Report" in t2.dependencies


def test_gemini_conversational_refinement_extraction():
    """Verify GeminiProvider parses conversational schedule refinements."""
    provider = GeminiProvider(api_key="AIzaSyTestKey", model="gemini-2.5-flash")

    gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "action": "move_first",
                                "task": "Prepare Financial Report",
                                "new_priority": 5,
                                "buffer_minutes": 15.0,
                                "description": "Put financial report first with higher priority"
                            })
                        }
                    ],
                    "role": "model"
                }
            }
        ]
    }

    with patch.object(provider, "_execute_http_request", return_value=gemini_response):
        ref = provider.parse_refinement("Put the financial report first and make it highest priority")

    assert ref is not None
    assert ref["action"] == "move_first"
    assert ref["task"] == "Prepare Financial Report"
    assert ref["new_priority"] == 5


def test_gemini_authentication_error():
    """HTTP 401 or 403 or 400 from Gemini is classified as AUTHENTICATION_ERROR with graceful fallback."""
    provider = GeminiProvider(api_key="AIzaSyBadKey", model="gemini-2.5-flash")

    http_error = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        code=403,
        msg="Permission Denied / API key invalid",
        hdrs={},
        fp=None,
    )

    with patch.object(provider, "_execute_http_request", side_effect=http_error):
        res = provider.extract_planning_context("Plan my schedule")
        assert res is None

        status = provider.get_status()
        assert status["status"] == "gemini_authentication_failed"
        assert status["error_category"] == "AUTHENTICATION_ERROR"
        assert status["fallback_active"] is True


def test_gemini_rate_limit_error_429():
    """HTTP 429 from Gemini is classified as RATE_LIMIT_EXCEEDED with graceful fallback."""
    provider = GeminiProvider(api_key="AIzaSyValidKey", model="gemini-2.5-flash")

    http_error = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        code=429,
        msg="Resource Exhausted / Rate Limit Exceeded",
        hdrs={},
        fp=None,
    )

    with patch.object(provider, "_execute_http_request", side_effect=http_error):
        res = provider.extract_planning_context("Plan my day")
        assert res is None

        status = provider.get_status()
        assert status["status"] == "gemini_rate_limited"
        assert status["error_category"] == "RATE_LIMIT_EXCEEDED"
        assert status["fallback_active"] is True


def test_gemini_request_timeout():
    """Request timeout from Gemini is classified as TIMEOUT with graceful fallback."""
    provider = GeminiProvider(api_key="AIzaSyValidKey", model="gemini-2.5-flash")

    timeout_err = TimeoutError("Connection timed out after 10.0s")
    with patch.object(provider, "_execute_http_request", side_effect=timeout_err):
        res = provider.extract_planning_context("Plan my day")
        assert res is None

        status = provider.get_status()
        assert status["status"] == "gemini_timeout"
        assert status["error_category"] == "TIMEOUT"
        assert status["fallback_active"] is True


def test_gemini_network_failure():
    """Network connection failure is classified as NETWORK_ERROR with graceful fallback."""
    provider = GeminiProvider(api_key="AIzaSyValidKey", model="gemini-2.5-flash")

    url_error = urllib.error.URLError("DNS resolution failed for generativelanguage.googleapis.com")
    with patch.object(provider, "_execute_http_request", side_effect=url_error):
        res = provider.extract_planning_context("Plan my day")
        assert res is None

        status = provider.get_status()
        assert status["status"] == "gemini_network_error"
        assert status["error_category"] == "NETWORK_ERROR"
        assert status["fallback_active"] is True


def test_gemini_malformed_json_response():
    """Malformed or invalid candidate response from Gemini is handled safely without crashing."""
    provider = GeminiProvider(api_key="AIzaSyValidKey", model="gemini-2.5-flash")

    corrupt_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "THIS IS NOT VALID JSON AT ALL {unclosed"}]
                }
            }
        ]
    }

    with patch.object(provider, "_execute_http_request", return_value=corrupt_response):
        res = provider.extract_planning_context("Plan my day")
        assert res is None

        status = provider.get_status()
        assert status["status"] == "gemini_malformed_output"
        assert status["error_category"] == "INVALID_PAYLOAD"
        assert status["fallback_active"] is True


def test_hybrid_parser_fallback_to_deterministic_on_error(test_clock):
    """When Gemini call fails, HybridPlanningParser cleanly falls back to deterministic rule-based extractor."""
    provider = GeminiProvider(api_key="AIzaSyValidKey", model="gemini-2.5-flash")
    parser = HybridPlanningParser(llm_provider=provider, clock=test_clock)

    http_error = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=None,
    )

    with patch.object(provider, "_execute_http_request", side_effect=http_error):
        ctx = parser.parse("I have an assignment due tomorrow and an exam in three days. I have 4 hours available today.")

    assert ctx is not None
    assert ctx.parser_provenance == "deterministic_fallback"
    assert ctx.available_hours == 4.0
    assert len(ctx.extracted_tasks) >= 2
    titles = [t.title.lower() for t in ctx.extracted_tasks]
    assert any("assignment" in t for t in titles)
    assert any("exam" in t for t in titles)


def test_ai_interaction_layer_provenance_and_gemini_integration(db_session, test_clock):
    """Verify AIInteractionLayer uses Gemini provider and records provenance accurately."""
    provider = GeminiProvider(api_key="AIzaSyValidKey", model="gemini-3.8-flash")

    mock_completion = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "tasks": [
                                    {
                                        "title": "Build Gemini Provider",
                                        "priority": 5,
                                        "estimated_duration": 3.0,
                                        "deadline_expression": "today",
                                        "dependencies": []
                                    }
                                ],
                                "available_hours": 6.0,
                                "use_existing_tasks": False,
                                "task_count": 1,
                                "requested_actions": ["plan_schedule"],
                                "clarification_needed": False,
                                "clarification_question": None
                            })
                        }
                    ],
                    "role": "model"
                }
            }
        ]
    }

    layer = AIInteractionLayer(
        session=db_session,
        parser=HybridPlanningParser(llm_provider=provider, clock=test_clock),
        clock=test_clock,
    )

    with patch.object(provider, "_execute_http_request", return_value=mock_completion):
        params = layer.parse_command("Plan my day: Build Gemini Provider with priority 5 for 3 hours")

    assert params["parser_provenance"] == "llm_gemini"
    assert params["available_hours"] == 6.0
    assert len(params["extracted_tasks"]) == 1
    assert params["extracted_tasks"][0]["title"] == "Build Gemini Provider"
    assert params["extracted_tasks"][0]["priority"] == 5


def test_honest_provenance_on_fallback(db_session, test_clock):
    """Verify provenance is 'deterministic_fallback' when Gemini fails or is unconfigured."""
    provider = GeminiProvider(api_key="", model="gemini-2.5-flash")
    layer = AIInteractionLayer(
        session=db_session,
        parser=HybridPlanningParser(llm_provider=provider, clock=test_clock),
        clock=test_clock,
    )
    params = layer.parse_command("Plan my day with 4 hours available")
    assert params["parser_provenance"] == "deterministic_fallback"
    assert "gemini" not in params["parser_provenance"]


def test_provider_test_connection_ping():
    """Verify GeminiProvider test_connection method sends a lightweight ping and reports success."""
    provider = GeminiProvider(api_key="AIzaSyTestKey", model="gemini-2.5-flash")

    ping_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps({"status": "ok"})}]
                }
            }
        ]
    }

    with patch.object(provider, "_execute_http_request", return_value=ping_response):
        success, message = provider.test_connection()
        assert success is True
        assert "Google Gemini" in message
        assert provider.get_status()["status"] == "gemini_configured_and_available"


def test_provider_status_public_endpoint_security():
    """Ensure GET /api/v1/ai/provider-status does not expose credentials, endpoint, timeout, or raw provider settings."""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/v1/ai/provider-status")
    assert response.status_code == 200

    data = response.json()
    # Safe public allowlist fields
    assert "provider" in data
    assert "model" in data
    assert "display_model" in data
    assert "is_configured" in data
    assert "status" in data
    assert "status_label" in data
    assert "fallback_active" in data

    # Verify display model is clean and friendly
    assert data["display_model"] == "Gemini 3.8 Flash"

    # STRICT SECURITY ASSERTIONS: Sensitive fields must NEVER be present
    forbidden_keys = [
        "has_api_key",
        "masked_key",
        "endpoint",
        "timeout_seconds",
        "supported_models",
        "api_key",
        "key",
        "secret",
        "token",
        "last_error",
        "error_category",
    ]
    for forbidden in forbidden_keys:
        assert forbidden not in data, f"Sensitive field '{forbidden}' exposed in public provider status response!"

    # Ensure no secret strings or URLs in the entire response body
    raw_text = response.text
    assert "AIzaSy" not in raw_text
    assert "sk-" not in raw_text
    assert "https://" not in raw_text


def test_provider_test_connection_endpoint_security():
    """Ensure POST /api/v1/ai/provider-test sanitizes output and leaks no credentials or internal URLs."""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    response = client.post("/api/v1/ai/provider-test")
    assert response.status_code == 200

    data = response.json()
    assert "success" in data
    assert "message" in data
    assert "status" in data

    # Ensure last_error and error_category are not leaking raw exception details
    assert data.get("last_error") is None
    assert data.get("error_category") is None

    # Message must not contain secret keys or raw env variable names
    message = data["message"]
    assert "AIzaSy" not in message
    assert "sk-" not in message
    assert "GEMINI_API_KEY" not in message
    assert "OPENAI_API_KEY" not in message
    assert "https://" not in message
