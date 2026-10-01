import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from backend.app.orchestrator.ai_brain_controller import AIBrainController
from backend.app.orchestrator.brain_models import BrainRequest, BrainResponse, QuantumStatus

@pytest.fixture
def mock_session():
    return MagicMock()

@pytest.fixture
def mock_engine_registry():
    registry = MagicMock()
    registry.get_behavior_engine.return_value = MagicMock()
    
    mock_context_engine = MagicMock()
    mock_context_engine.get_context.return_value = {"key": "value"}
    registry.get_context_engine.return_value = mock_context_engine
    
    return registry

@pytest.fixture
def brain_controller(mock_session, mock_engine_registry, monkeypatch):
    controller = AIBrainController(
        session=mock_session,
        engine_registry=mock_engine_registry
    )
    
    # Mock pipelines to prevent actual database/engine calls during routing tests
    controller._decision_pipeline = MagicMock()
    controller._decision_pipeline.run_pipeline = AsyncMock(return_value={"status": "planned", "schedule": []})
    
    controller._adaptive_scheduler = MagicMock()
    controller._adaptive_scheduler.adapt_schedule = AsyncMock(return_value={"status": "adapted", "updated_schedule": []})
    
    controller._learning_loop = MagicMock()
    controller._learning_loop.run_learning_cycle = AsyncMock(return_value={"status": "learned"})
    
    controller._recommendation_engine = MagicMock()
    controller._recommendation_engine.generate_recommendations = AsyncMock(return_value={"status": "recommended"})
    
    mock_exec_brain_cls = MagicMock()
    mock_exec_brain_inst = MagicMock()
    mock_exec_brain_inst.execute_planning_request.return_value = {"executive_summary": "mock summary"}
    mock_exec_brain_cls.return_value = mock_exec_brain_inst
    monkeypatch.setattr("backend.app.orchestrator.executive_cognitive_brain.ExecutiveCognitiveBrain", mock_exec_brain_cls)
    
    return controller

@pytest.mark.anyio
async def test_brain_initialization(mock_session):
    controller = AIBrainController(session=mock_session)
    assert controller.session == mock_session
    assert controller._decision_pipeline is None

@pytest.mark.anyio
async def test_process_intent_plan_day(brain_controller):
    req = BrainRequest(request_id="test", user_id=1, intent="plan_day", parameters={"goal": "Plan my day"})
    result = await brain_controller.process_intent(req)
    assert result.success is True
    assert result.intent == "plan_day"
    brain_controller._decision_pipeline.run_pipeline.assert_awaited_once_with(
        goal_text="Plan my day",
        user_id=1
    )

@pytest.mark.anyio
async def test_process_intent_replan(brain_controller):
    req = BrainRequest(request_id="test", user_id=1, intent="optimize_schedule", parameters={"schedule": [{"task": 1}]})
    result = await brain_controller.process_intent(req)
    assert result.success is True
    assert result.intent == "optimize_schedule"
    brain_controller._adaptive_scheduler.adapt_schedule.assert_awaited_once_with(
        schedule=[{"task": 1}],
        user_id=1
    )

@pytest.mark.anyio
async def test_process_intent_unsupported(brain_controller):
    req = BrainRequest(request_id="test", user_id=1, intent="bad_intent")
    result = await brain_controller.process_intent(req)
    assert result.success is False
    assert "Unsupported intent: bad_intent" in result.executive_summary

@pytest.mark.anyio
async def test_pipeline_exception_handling(brain_controller):
    brain_controller._decision_pipeline.run_pipeline.side_effect = RuntimeError("Pipeline crashed")
    req = BrainRequest(request_id="test", user_id=1, intent="plan_day")
    result = await brain_controller.process_intent(req)
    assert result.success is False
    assert "Pipeline crashed" in result.executive_summary
