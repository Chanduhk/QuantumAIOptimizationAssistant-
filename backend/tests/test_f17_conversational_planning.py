"""
Phase F17 Test Suite: Real Conversational Intelligence & Advanced Personal Planning.
Covers:
1. LLM structured-output validation & sanitization (OpenAI, Gemini, Anthropic)
2. Provider failure, timeouts, malformed JSON, and deterministic fallback
3. Multi-task interpretation, relative deadlines, and timezone handling with controllable clock
4. Scheduling constraints, multi-hour intervals, and dependency sequencing
5. Decision policy evaluation, overload detection, unscheduled tasks, and realistic alternatives
6. Conversational proposal refinement (reorder, move first, prioritize, add buffer, alternative option, reduce hours)
7. Acceptance idempotency, duplicate prevention, and user isolation security
8. Honest prediction and quantum provenance (simulation vs classical baseline, no false advantage)
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import json
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
from backend.app.interface.nl_extractor import NaturalLanguageExtractor, ExtractedPlanningContext
from backend.app.interface.llm_provider import (
    ConfiguredLLMProvider,
    DeterministicFallbackProvider,
    HybridPlanningParser,
)
from backend.app.orchestrator.ai_brain_controller import AIBrainController
from backend.app.orchestrator.brain_models import BrainRequest


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


def test_llm_provider_configuration_and_key_masking():
    """Test LLM provider auto-detection, configuration checks, and API key masking."""
    # 1. Unconfigured
    provider_none = ConfiguredLLMProvider(provider="", api_key="", endpoint="")
    assert not provider_none.is_configured()
    assert provider_none._mask_key("") == "<none>"
    assert provider_none._mask_key("short") == "***"
    assert provider_none._mask_key("sk-abcdefghijklmnop1234") == "sk-...234"

    # 2. Configured OpenAI
    provider_openai = ConfiguredLLMProvider(
        provider="openai",
        api_key="sk-test-key-12345",
        endpoint="https://api.openai.com/v1/chat/completions",
    )
    assert provider_openai.is_configured()
    assert provider_openai.provider_name == "openai"

    # 3. Configured Gemini
    provider_gemini = ConfiguredLLMProvider(
        provider="gemini",
        api_key="AIzaSyTestKey5678",
        endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
    )
    assert provider_gemini.is_configured()
    assert provider_gemini.provider_name == "gemini"


def test_llm_structured_output_validation_and_sanitization(test_clock):
    """Test runtime schema validation, sanitization of HTML, and clamping of priority and duration."""
    mock_payload = {
        "tasks": [
            {
                "title": "<b>Finish Project Report</b><script>alert(1)</script>",
                "priority": 99,  # Should clamp to 5
                "estimated_duration": -2.0,  # Should clamp to min 0.25
                "deadline_expression": "tomorrow",
                "dependencies": ["Task Alpha"],
            },
            {
                "title": "",  # Empty title should be skipped
                "priority": 1,
                "estimated_duration": 1.0,
            },
            {
                "title": "Study for Exam",
                "priority": 0,  # Should clamp to 1
                "estimated_duration": 100.0,  # Should clamp to max 24.0
                "deadline_expression": "in 3 days",
            }
        ],
        "available_hours": 4.0,
        "clarification_needed": False,
        "use_existing_tasks": False,
    }

    provider = ConfiguredLLMProvider(
        provider="openai",
        api_key="sk-test-key",
        endpoint="https://api.openai.com/v1/chat/completions",
    )
    with patch.object(provider, "_execute_provider_call", return_value=mock_payload):
        ctx = provider.extract_planning_context(
            "I have an assignment and exam.", reference_time=test_clock()
        )
        assert ctx is not None
        assert ctx.parser_provenance == "llm_openai"
        assert len(ctx.extracted_tasks) == 2  # Empty title task was stripped
        
        t1 = ctx.extracted_tasks[0]
        assert t1.title == "Finish Project Report"  # HTML stripped
        assert t1.priority == 5  # Clamped to 5
        assert t1.estimated_duration == 0.25  # Clamped to 0.25
        assert t1.deadline_expression == "tomorrow"
        assert t1.deadline_dt is not None
        assert t1.dependencies == ["Task Alpha"]

        t2 = ctx.extracted_tasks[1]
        assert t2.title == "Study for Exam"
        assert t2.priority == 1  # Clamped to 1
        assert t2.estimated_duration == 24.0  # Clamped to 24.0


def test_provider_failure_and_deterministic_fallback(test_clock):
    """Test timeouts, network errors, malformed responses gracefully fall back to deterministic parser."""
    provider = ConfiguredLLMProvider(
        provider="openai",
        api_key="sk-test-key",
        endpoint="https://api.openai.com/v1/chat/completions",
    )
    
    # 1. Network timeout error
    with patch.object(provider, "_execute_provider_call", side_effect=TimeoutError("Request timed out")):
        parser = HybridPlanningParser(llm_provider=provider, clock=test_clock)
        prompt = "I have an assignment due tomorrow and an exam in three days. I have four hours available today."
        ctx = parser.parse(prompt)
        assert ctx.parser_provenance == "deterministic_fallback"
        assert len(ctx.extracted_tasks) == 2
        assert ctx.available_hours == 4.0

    # 2. Malformed non-dict JSON response
    with patch.object(provider, "_execute_provider_call", return_value="Malformed String"):
        parser = HybridPlanningParser(llm_provider=provider, clock=test_clock)
        ctx = parser.parse(prompt)
        assert ctx.parser_provenance == "deterministic_fallback"
        assert len(ctx.extracted_tasks) == 2


def test_multi_task_interpretation_and_deadlines(test_clock):
    """Test full multi-task extraction with relative deadlines and controllable clock."""
    extractor = NaturalLanguageExtractor(clock=test_clock)
    prompt = "I have an assignment due tomorrow, an exam in three days, and a project submission next week. I have four hours available today. Plan my schedule."
    
    ctx = extractor.parse_planning_request(prompt)
    assert ctx.available_hours == 4.0
    assert len(ctx.extracted_tasks) == 3

    t_map = {t.title.lower(): t for t in ctx.extracted_tasks}
    assert any("assignment" in k for k in t_map)
    assert any("exam" in k for k in t_map)
    assert any("project" in k for k in t_map)

    # Check relative deadline interpretation relative to reference 2026-10-18
    assignment = next(t for k, t in t_map.items() if "assignment" in k)
    assert assignment.deadline_expression == "tomorrow"
    assert assignment.deadline_dt.date() == datetime(2026, 10, 19).date()

    exam = next(t for k, t in t_map.items() if "exam" in k)
    assert "in 3 days" in exam.deadline_expression
    assert exam.deadline_dt.date() == datetime(2026, 10, 21).date()

    project = next(t for k, t in t_map.items() if "project" in k)
    assert project.deadline_expression == "next week"
    assert project.deadline_dt.date() == datetime(2026, 10, 25).date()


def test_scheduling_constraints_and_intervals(db_session, test_clock):
    """Test non-overlapping continuous multi-hour intervals and dependency adherence."""
    import asyncio

    async def _async_test():
        controller = AIBrainController(session=db_session, clock=test_clock)

        tasks = [
            {
                "id": "t1",
                "title": "Task A Foundation",
                "estimated_duration": 2.0,
                "estimated_duration_unit": "hours",
                "priority": 3,
                "origin": "proposed",
            },
            {
                "id": "t2",
                "title": "Task B Dependent",
                "estimated_duration": 1.5,
                "estimated_duration_unit": "hours",
                "priority": 4,
                "dependencies": ["t1"],
                "origin": "proposed",
            },
        ]

        req = BrainRequest(
            request_id="req-intervals",
            user_id=1,
            intent="plan_day",
            command="Plan my day",
            parameters={"extracted_tasks": tasks, "available_hours": 6.0},
        )
        res = await controller.execute_intent(req)
        assert res.success is True
        schedule = res.schedule
        assert len(schedule) == 2

        task_a = next(it for it in schedule if "Foundation" in it["title"])
        task_b = next(it for it in schedule if "Dependent" in it["title"])

        # Non-overlapping contiguous interval check
        assert task_a["scheduled_end_hour"] == task_a["scheduled_hour"] + 2.0
        # Dependency check: Task B cannot start before Task A ends
        assert task_b["scheduled_hour"] >= task_a["scheduled_end_hour"]

    asyncio.run(_async_test())


def test_decision_policy_overload_and_realistic_alternatives(db_session, test_clock):
    """Test that when demanded workload exceeds available horizon, overload is detected and realistic alternatives are returned."""
    import asyncio

    async def _async_test():
        controller = AIBrainController(session=db_session, clock=test_clock)

        # 3 tasks totaling 4.0 hours, but available horizon is only 2.0 hours
        tasks = [
            {"id": "t1", "title": "Urgent Assignment", "priority": 5, "estimated_duration": 1.5, "origin": "proposed", "deadline_expression": "tomorrow"},
            {"id": "t2", "title": "Exam Prep", "priority": 4, "estimated_duration": 1.5, "origin": "proposed", "deadline_expression": "in 3 days"},
            {"id": "t3", "title": "Project Work", "priority": 2, "estimated_duration": 1.0, "origin": "proposed", "deadline_expression": "next week"},
        ]

        req = BrainRequest(
            request_id="req-overload",
            user_id=1,
            intent="plan_day",
            command="Plan schedule with 2 hours",
            parameters={"extracted_tasks": tasks, "available_hours": 2.0},
        )
        res = await controller.execute_intent(req)
        assert res.success is True
        raw = res.raw_result

        assert raw["feasibility_status"] == "INFEASIBLE_OVERLOAD"
        assert len(raw["infeasible_tasks"]) > 0
        assert len(raw["unscheduled_tasks"]) > 0

        # Realistic alternatives generated
        assert len(raw["alternative_actions"]) >= 3
        alt_text = " ".join(raw["alternative_actions"])
        assert "Option A" in alt_text
        assert "Option B" in alt_text
        assert "Option C" in alt_text
        # Trade-offs explained
        assert len(raw["trade_offs"]) > 0

    asyncio.run(_async_test())


def test_conversational_refinement_actions(test_clock):
    """Test conversational refinement command parsing for F17 requirements."""
    extractor = NaturalLanguageExtractor(clock=test_clock)

    # 1. "Move the assignment first."
    r1 = extractor.parse_refinement("Move the assignment first.")
    assert r1["action"] == "move_first"
    assert "assignment" in r1["task"].lower()

    # 2. "Prioritize the exam instead."
    r2 = extractor.parse_refinement("Prioritize the exam instead.")
    assert r2["action"] == "reprioritize"
    assert "exam" in r2["task"].lower()

    # 3. "Show me another feasible option."
    r3 = extractor.parse_refinement("Show me another feasible option.")
    assert r3["action"] == "alternative_schedule"

    # 4. "Leave 30 minutes for revision."
    r4 = extractor.parse_refinement("Leave 30 minutes for revision.")
    assert r4["action"] == "add_buffer"
    assert r4["buffer_minutes"] == 30.0

    # 5. "I only have two hours available now."
    r5 = extractor.parse_refinement("I only have two hours available now.")
    assert r5["action"] == "reduce_available_hours"
    assert r5["new_available_hours"] == 2.0

    # 6. "Accept this plan."
    r6 = extractor.parse_refinement("Accept this plan.")
    assert r6["action"] == "accept_plan"

    # 7. "Reject this plan."
    r7 = extractor.parse_refinement("Reject this plan.")
    assert r7["action"] == "reject_plan"


def test_acceptance_idempotency_and_duplicate_prevention(db_session, test_clock):
    """Test idempotent acceptance, duplicate prevention, and user isolation."""
    service = PlanProposalService(db_session, clock=test_clock)

    proposal = service.create_proposal(
        user_id=1,
        schedule=[
            {
                "id": "proposed:writing_task",
                "title": "Writing Assignment",
                "scheduled_hour": 9.0,
                "scheduled_end_hour": 10.5,
                "estimated_duration": 1.5,
                "estimated_duration_unit": "hours",
                "priority": 4,
                "origin": "proposed",
            }
        ],
        tasks=[],
        available_hours=4.0,
    )

    # First accept: Creates task
    success1, msg1, ids1, p1 = service.accept_proposal(proposal_id=proposal.id, user_id=1)
    assert success1 is True
    assert p1.status == "ACCEPTED"
    assert len(ids1) == 1

    # Second accept: Idempotent return without duplicate creation
    success2, msg2, ids2, p2 = service.accept_proposal(proposal_id=proposal.id, user_id=1)
    assert success2 is True
    assert ids2 == ids1

    # Verify exactly 1 task in database
    tasks_in_db = db_session.query(Task).filter(Task.user_id == 1).all()
    assert len(tasks_in_db) == 1
    assert tasks_in_db[0].title == "Writing Assignment"

    # Security check: User 2 cannot access or accept User 1 proposal
    assert service.get_proposal_by_id(proposal.id, user_id=2) is None
    with pytest.raises(ValueError, match="unauthorized"):
        service.accept_proposal(proposal_id=proposal.id, user_id=2)


def test_honest_quantum_and_behavioral_provenance(db_session, test_clock):
    """Test that quantum and behavioral predictions report honest, unexaggerated provenance."""
    import asyncio

    async def _async_test():
        controller = AIBrainController(session=db_session, clock=test_clock)

        tasks = [
            {"id": "t1", "title": "Deep Work", "priority": 4, "estimated_duration": 1.0, "origin": "proposed"},
            {"id": "t2", "title": "Reading", "priority": 3, "estimated_duration": 1.0, "origin": "proposed"},
        ]

        req = BrainRequest(
            request_id="req-provenance",
            user_id=1,
            intent="plan_day",
            command="Plan my schedule",
            parameters={"extracted_tasks": tasks, "available_hours": 4.0},
        )
        res = await controller.execute_intent(req)
        assert res.success is True
        raw = res.raw_result

        # Honest provenance checks
        assert raw["quantum_suitability"] in ("SUITABLE", "UNSUPPORTED")
        # When suitable, local statevector simulation is identified as simulation, not hardware
        assert res.quantum_status.value.lower() in ("simulated_local", "classical_only", "quantum_considered_but_rejected")
        # Behavioral provenance explicitly tracked
        assert raw["behavioral_provenance"] in ("DETERMINISTIC_FALLBACK", "PERSONAL_MODEL")

    asyncio.run(_async_test())
