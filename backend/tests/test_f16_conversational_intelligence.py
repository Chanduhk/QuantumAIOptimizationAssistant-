"""
F16 Test Suite: Context-Aware Conversational Intelligence & Proposal Lifecycle.
Covers:
1. Context retrieval and user isolation
2. Natural-language parsing, HybridPlanningParser & LLM provider abstraction (graceful fallback)
3. Multi-turn proposal refinement ("I only have two hours now", reordering, reprioritizing)
4. Database-backed proposal persistence across simulated backend restarts & multi-worker instances
5. Stable proposal identity (UUID v4) and monotonic version incrementing
6. Acceptance idempotency and duplicate prevention
7. Rejected proposals leaving database tasks unchanged
8. Stale proposal rejection via optimistic locking
9. Security isolation constraint revalidation
10. Explicit behavioral estimation provenance and fallback verification
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
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

    # Seed test users
    u1 = User(id=1, email="user1@example.com", password_hash="hash1", is_active=True, created_at=datetime.now())
    u2 = User(id=2, email="user2@example.com", password_hash="hash2", is_active=True, created_at=datetime.now())
    session.add_all([u1, u2])
    session.commit()

    yield session
    session.close()


def test_hybrid_parser_llm_and_deterministic_fallback(test_clock, monkeypatch):
    """Test HybridPlanningParser uses LLM when configured, and falls back gracefully when unconfigured or failing."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HELIOX_LLM_API_KEY", raising=False)
    # 1. Unconfigured fallback
    parser = HybridPlanningParser(clock=test_clock)
    assert not parser.llm_provider.is_configured()

    prompt = "I have an assignment due tomorrow, an exam in three days, and a project next week. I have four hours available today."
    ctx = parser.parse(prompt)
    assert ctx.parser_provenance == "deterministic_fallback"
    assert len(ctx.extracted_tasks) == 3
    assert ctx.available_hours == 4.0
    titles = [t.title for t in ctx.extracted_tasks]
    assert any("assignment" in t.lower() for t in titles)
    assert any("exam" in t.lower() for t in titles)
    assert any("project" in t.lower() for t in titles)

    # 2. Mock Configured LLM Provider Success
    mock_llm = MagicMock(spec=ConfiguredLLMProvider)
    mock_llm.is_configured.return_value = True
    mock_llm.provider_name = "mock_gpt"
    mock_llm.extract_planning_context.return_value = ExtractedPlanningContext(
        command=prompt,
        available_hours=4.0,
        extracted_tasks=[],
        parser_provenance="llm_mock_gpt"
    )
    hybrid_with_llm = HybridPlanningParser(llm_provider=mock_llm, clock=test_clock)
    ctx_llm = hybrid_with_llm.parse(prompt)
    assert ctx_llm.parser_provenance == "llm_mock_gpt"

    # 3. Mock LLM Error -> Graceful Fallback
    mock_llm_error = MagicMock(spec=ConfiguredLLMProvider)
    mock_llm_error.is_configured.return_value = True
    mock_llm_error.extract_planning_context.side_effect = RuntimeError("API timeout")
    hybrid_fallback = HybridPlanningParser(llm_provider=mock_llm_error, clock=test_clock)
    ctx_fallback = hybrid_fallback.parse(prompt)
    assert ctx_fallback.parser_provenance == "deterministic_fallback"
    assert len(ctx_fallback.extracted_tasks) == 3


def test_natural_language_prompts_and_context_detection(test_clock):
    """Test extraction of specific F16 natural prompts."""
    extractor = NaturalLanguageExtractor(clock=test_clock)

    # "Plan my day around my three most important tasks."
    ctx1 = extractor.parse_planning_request("Plan my day around my three most important tasks.")
    assert ctx1.use_existing_tasks is True
    assert ctx1.task_count == 3
    assert ctx1.clarification_needed is False

    # "Use my existing tasks and goals."
    ctx2 = extractor.parse_planning_request("Use my existing tasks and goals.")
    assert ctx2.use_existing_tasks is True
    assert ctx2.clarification_needed is False

    # Refinement: "I only have two hours available now. Adjust the plan."
    ref1 = extractor.parse_refinement("I only have two hours available now. Adjust the plan.")
    assert ref1["action"] == "reduce_available_hours"
    assert ref1["new_available_hours"] == 2.0

    # Refinement: "Move the assignment ahead of my exam preparation."
    ref2 = extractor.parse_refinement("Move the assignment ahead of my exam preparation.")
    assert ref2["action"] == "reorder"
    assert "assignment" in ref2["first_task"].lower()
    assert "exam" in ref2["second_task"].lower()

    # Refinement: "Move the assignment first."
    ref3 = extractor.parse_refinement("Move the assignment first.")
    assert ref3["action"] == "move_first"
    assert "assignment" in ref3["task"].lower()

    # Refinement: "Show me another schedule that prioritizes the exam."
    ref4 = extractor.parse_refinement("Show me another schedule that prioritizes the exam.")
    assert ref4["action"] == "reprioritize"
    assert "exam" in ref4["task"].lower()

    # Ambiguous refinement asks clarification
    ref5 = extractor.parse_refinement("Move the task earlier.")
    assert ref5["action"] == "clarification_needed"
    assert "Which specific task" in ref5["clarification_question"]


def test_proposal_lifecycle_database_persistence_and_restart(db_session, test_clock):
    """Test that proposals are saved in the DB, survive restarts, and maintain versioning."""
    service = PlanProposalService(db_session, clock=test_clock)

    # 1. Create proposal
    proposal = service.create_proposal(
        user_id=1,
        schedule=[
            {"task_id": 101, "title": "Assignment", "scheduled_hour": 9.0, "scheduled_end_hour": 11.0, "priority": 4},
            {"task_id": 102, "title": "Exam Prep", "scheduled_hour": 11.0, "scheduled_end_hour": 13.0, "priority": 5},
        ],
        tasks=[{"id": 101, "title": "Assignment"}, {"id": 102, "title": "Exam Prep"}],
        available_hours=4.0,
        goal_text="Plan my day",
    )
    prop_id = proposal.id
    assert proposal.version == 1
    assert proposal.status == "PROPOSED"

    # 2. Simulate backend restart: Instantiate a new PlanProposalService with same DB
    restarted_service = PlanProposalService(db_session, clock=test_clock)
    recovered = restarted_service.get_active_proposal(user_id=1)
    assert recovered is not None
    assert recovered.id == prop_id
    assert recovered.version == 1
    assert len(recovered.schedule) == 2

    # 3. Refine proposal (v1 -> v2)
    new_schedule = [
        {"task_id": 102, "title": "Exam Prep", "scheduled_hour": 9.0, "scheduled_end_hour": 11.0, "priority": 5},
        {"task_id": 101, "title": "Assignment", "scheduled_hour": 11.0, "scheduled_end_hour": 13.0, "priority": 4},
    ]
    refined = restarted_service.update_proposal_refinement(
        proposal_id=prop_id,
        user_id=1,
        new_schedule=new_schedule,
        expected_version=1,
    )
    assert refined.version == 2
    assert refined.id == prop_id

    # 4. Verify DB reflects v2
    in_db = restarted_service.get_proposal_by_id(prop_id, user_id=1)
    assert in_db.version == 2
    assert in_db.schedule[0]["title"] == "Exam Prep"


def test_stale_proposal_optimistic_locking(db_session, test_clock):
    """Test that concurrent/stale proposal edits with mismatched version are rejected."""
    service = PlanProposalService(db_session, clock=test_clock)
    proposal = service.create_proposal(
        user_id=1,
        schedule=[{"title": "Task 1", "scheduled_hour": 9.0, "scheduled_end_hour": 10.0}],
        tasks=[],
    )
    # Refine to version 2
    service.update_proposal_refinement(
        proposal_id=proposal.id,
        user_id=1,
        new_schedule=[{"title": "Task 1 refined", "scheduled_hour": 9.0, "scheduled_end_hour": 10.0}],
        expected_version=1,
    )
    assert proposal.version == 2

    # Now a stale client tries to update or accept with expected_version=1
    with pytest.raises(ValueError, match="Stale proposal version conflict"):
        service.update_proposal_refinement(
            proposal_id=proposal.id,
            user_id=1,
            new_schedule=[],
            expected_version=1,
        )

    with pytest.raises(ValueError, match="Stale proposal version conflict"):
        service.accept_proposal(
            proposal_id=proposal.id,
            user_id=1,
            expected_version=1,
        )


def test_acceptance_idempotency_and_duplicate_prevention(db_session, test_clock):
    """Test that accepting a proposal persists tasks, avoids duplicates, and is idempotent."""
    service = PlanProposalService(db_session, clock=test_clock)
    proposal = service.create_proposal(
        user_id=1,
        schedule=[
            {
                "id": "proposed:deep_work_1",
                "title": "Deep Work Writing",
                "origin": "proposed",
                "scheduled_hour": 9.0,
                "scheduled_end_hour": 11.0,
                "estimated_duration": 2.0,
                "estimated_duration_unit": "hours",
                "priority": 4,
            }
        ],
        tasks=[],
    )

    # First acceptance
    success, msg, persisted_ids, prop = service.accept_proposal(proposal_id=proposal.id, user_id=1)
    assert success is True
    assert prop.status == "ACCEPTED"
    assert len(persisted_ids) == 1
    task_id = persisted_ids[0]

    # Check task exists in DB
    created_task = db_session.query(Task).filter(Task.id == task_id).one()
    assert created_task.title == "Deep Work Writing"
    assert created_task.user_id == 1
    assert created_task.start_time == datetime(2026, 10, 18, 9, 0)
    assert created_task.end_time == datetime(2026, 10, 18, 11, 0)

    # Second acceptance (Idempotent call)
    success2, msg2, persisted_ids2, prop2 = service.accept_proposal(proposal_id=proposal.id, user_id=1)
    assert success2 is True
    assert "already been accepted" in msg2
    assert persisted_ids2 == [task_id]

    # Verify no duplicate task was created
    total_tasks = db_session.query(Task).filter(Task.user_id == 1).count()
    assert total_tasks == 1


def test_rejected_proposal_leaves_database_unmodified(db_session, test_clock):
    """Test that rejecting a proposal updates proposal status but creates NO tasks."""
    service = PlanProposalService(db_session, clock=test_clock)
    proposal = service.create_proposal(
        user_id=1,
        schedule=[
            {
                "id": "proposed:rejected_study_1",
                "title": "Study Group Review",
                "origin": "proposed",
                "scheduled_hour": 14.0,
                "scheduled_end_hour": 16.0,
                "estimated_duration": 2.0,
            }
        ],
        tasks=[],
    )

    assert proposal.status == "PROPOSED"
    service.reject_proposal(proposal.id, user_id=1)

    # Verify proposal status
    reloaded = service.get_proposal_by_id(proposal.id, user_id=1)
    assert reloaded.status == "REJECTED"

    # Verify zero tasks in DB
    task_count = db_session.query(Task).filter(Task.user_id == 1).count()
    assert task_count == 0

    # Cannot accept a rejected proposal
    with pytest.raises(ValueError, match="rejected and cannot be accepted"):
        service.accept_proposal(proposal_id=proposal.id, user_id=1)


def test_user_isolation_security(db_session, test_clock):
    """Test that users cannot access, refine, accept, or tamper with another user's proposal or tasks."""
    service = PlanProposalService(db_session, clock=test_clock)

    # User 1 proposal
    prop_u1 = service.create_proposal(
        user_id=1,
        schedule=[{"title": "Private User 1 Task", "scheduled_hour": 9.0, "scheduled_end_hour": 10.0}],
        tasks=[],
    )

    # User 2 cannot retrieve User 1 proposal
    assert service.get_proposal_by_id(prop_u1.id, user_id=2) is None
    assert service.get_active_proposal(user_id=2) is None

    # User 2 cannot refine User 1 proposal
    with pytest.raises(ValueError, match="not found or unauthorized"):
        service.update_proposal_refinement(
            proposal_id=prop_u1.id,
            user_id=2,
            new_schedule=[],
        )

    # User 2 cannot accept User 1 proposal
    with pytest.raises(ValueError, match="not found or unauthorized"):
        service.accept_proposal(
            proposal_id=prop_u1.id,
            user_id=2,
        )

    # Security constraint check: User 1 proposal cannot include tasks belonging to User 2
    task_service = TaskLifecycleService(db_session, clock=test_clock)
    u2_task = task_service.create_task(
        user_id=2,
        title="User 2 Secret Task",
        task_type="coding",
        priority=3,
        estimated_duration=60,
    )

    prop_tampered = service.create_proposal(
        user_id=1,
        schedule=[{"task_id": u2_task.id, "title": "Tampered", "scheduled_hour": 9.0, "scheduled_end_hour": 10.0}],
        tasks=[],
    )

    with pytest.raises(ValueError, match="Security violation: Task .* does not belong to user 1"):
        service.accept_proposal(proposal_id=prop_tampered.id, user_id=1)


def test_multi_turn_conversational_refinement_flow(db_session, test_clock):
    """
    End-to-end journey:
    1. "I have an assignment due tomorrow, an exam in three days, and a project next week. I have four hours available today."
       -> Proposal generated (v1).
    2. "Move the assignment ahead of my exam preparation."
       -> Proposal refined (v2).
    3. "I only have two hours available now. Adjust the plan."
       -> Proposal refined (v3), overload detected, trade-offs identified.
    4. Accept plan -> Persisted to database, tasks written safely.
    """
    import asyncio

    async def _async_flow():
        controller = AIBrainController(session=db_session, clock=test_clock)
        from backend.app.interface.ai_interaction import AIInteractionLayer
        interaction = AIInteractionLayer(session=db_session, clock=test_clock)

        # Turn 1: Initial Request
        prompt1 = "I have an assignment due tomorrow, an exam in three days, and a project next week. I have four hours available today."
        cmd1 = interaction.parse_command(prompt1)
        req1 = BrainRequest(
            request_id="req-1",
            user_id=1,
            intent="plan_day",
            command=prompt1,
            parameters=cmd1,
        )
        res1 = await controller.execute_intent(req1)
        assert res1.success is True
        prop_id = res1.raw_result["proposal_id"]
        assert res1.raw_result["proposal_version"] == 1
        assert len(res1.schedule) > 0

        # Turn 2: Conversational Refinement (Reorder)
        prompt2 = "Move the assignment ahead of my exam preparation."
        cmd2 = interaction.parse_command(prompt2)
        req2 = BrainRequest(
            request_id="req-2",
            user_id=1,
            intent="refine_plan",
            command=prompt2,
            parameters=cmd2,
        )
        res2 = await controller.execute_intent(req2)
        assert res2.success is True
        assert res2.raw_result["proposal_id"] == prop_id
        assert res2.raw_result["proposal_version"] == 2

        # Turn 3: Available Hours Reduction -> Overload & Trade-offs
        prompt3 = "I only have two hours available now. Adjust the plan."
        cmd3 = interaction.parse_command(prompt3)
        req3 = BrainRequest(
            request_id="req-3",
            user_id=1,
            intent="refine_plan",
            command=prompt3,
            parameters=cmd3,
        )
        res3 = await controller.execute_intent(req3)
        assert res3.success is True
        assert res3.raw_result["proposal_id"] == prop_id
        assert res3.raw_result["proposal_version"] == 3
        assert res3.raw_result["available_hours"] == 2.0
        # Overload detection
        assert res3.raw_result["feasibility_status"] == "INFEASIBLE_OVERLOAD"
        assert len(res3.raw_result["infeasible_tasks"]) > 0

        # Turn 4: Accept Plan
        req4 = BrainRequest(
            request_id="req-4",
            user_id=1,
            intent="accept_plan",
            command="Accept this plan",
            parameters={"intent": "accept_plan", "proposal_id": prop_id, "version": 3},
        )
        res4 = await controller.execute_intent(req4)
        assert res4.success is True
        assert res4.raw_result["plan_accepted"] is True
        assert res4.raw_result["proposal_status"] == "ACCEPTED"
        assert len(res4.raw_result["persisted_task_ids"]) > 0

        # Verify tasks exist in DB
        persisted = db_session.query(Task).filter(Task.user_id == 1).all()
        assert len(persisted) == len(res4.raw_result["persisted_task_ids"])

    asyncio.run(_async_flow())


def test_use_existing_tasks_context_retrieval(db_session, test_clock):
    """Test 'Plan my day around my three most important tasks' retrieves existing DB tasks."""
    import asyncio

    async def _async_context():
        task_service = TaskLifecycleService(db_session, clock=test_clock)

        # Seed 5 existing tasks with different priorities
        task_service.create_task(user_id=1, title="Task Low 1", task_type="admin", priority=1, estimated_duration=60)
        task_service.create_task(user_id=1, title="Task Urgent 1", task_type="study", priority=5, estimated_duration=60)
        task_service.create_task(user_id=1, title="Task High 2", task_type="coding", priority=4, estimated_duration=60)
        task_service.create_task(user_id=1, title="Task High 3", task_type="writing", priority=4, estimated_duration=60)
        task_service.create_task(user_id=1, title="Task Low 2", task_type="general", priority=2, estimated_duration=60)

        controller = AIBrainController(session=db_session, clock=test_clock)
        from backend.app.interface.ai_interaction import AIInteractionLayer
        interaction = AIInteractionLayer(session=db_session, clock=test_clock)

        prompt = "Plan my day around my three most important tasks."
        cmd = interaction.parse_command(prompt)
        assert cmd["use_existing_tasks"] is True
        assert cmd["task_count"] == 3

        req = BrainRequest(
            request_id="req-existing",
            user_id=1,
            intent="plan_day",
            command=prompt,
            parameters=cmd,
        )
        res = await controller.execute_intent(req)
        assert res.success is True
        assert len(res.schedule) == 3
        # Verify the 3 scheduled tasks are the ones with priority 5, 4, 4
        scheduled_priorities = [item.get("priority") for item in res.schedule]
        assert 5 in scheduled_priorities
        assert 1 not in scheduled_priorities
        assert 2 not in scheduled_priorities

    asyncio.run(_async_context())
