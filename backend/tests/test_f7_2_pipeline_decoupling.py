import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.app.pipeline.decision_pipeline import DecisionPipeline
from backend.app.core.engine_registry import EngineRegistry
from backend.app.orchestrator.ai_brain_controller import AIBrainController


@pytest.fixture
def mock_session():
    return MagicMock()

@pytest.fixture
def test_engine_registry(mock_session):
    return EngineRegistry(mock_session)

@pytest.mark.anyio
async def test_decision_pipeline_no_orchestrator(mock_session, test_engine_registry):
    # Verify DecisionPipeline can be constructed without AIOrchestrator
    pipeline = DecisionPipeline(
        session=mock_session,
        engine_registry=test_engine_registry
    )
    assert not hasattr(pipeline, "orchestrator")
    
    # Verify AIOrchestrator is NOT imported or used during initialize_pipeline
    with patch("backend.app.orchestrator.ai_orchestrator.AIOrchestrator") as MockOrchestrator:
        await pipeline.initialize_pipeline()
        MockOrchestrator.assert_not_called()

@pytest.mark.anyio
async def test_engine_registry_provides_all_dependencies(test_engine_registry):
    # Verify EngineRegistry provides the dependencies required by DecisionPipeline
    assert test_engine_registry.get_cognitive_engine() is not None
    assert test_engine_registry.get_context_engine() is not None
    assert test_engine_registry.get_rl_scheduler() is not None
    assert test_engine_registry.get_memory_system() is not None
    assert test_engine_registry.get_feature_store() is not None
    assert test_engine_registry.get_knowledge_graph() is not None
    assert test_engine_registry.get_ai_monitor() is not None
    assert test_engine_registry.get_behavior_engine() is not None
    assert test_engine_registry.get_prediction_engine() is not None

@pytest.mark.anyio
async def test_brain_controller_constructs_pipeline(mock_session, test_engine_registry):
    controller = AIBrainController(
        session=mock_session,
        engine_registry=test_engine_registry
    )
    
    pipeline = controller._get_decision_pipeline()
    assert isinstance(pipeline, DecisionPipeline)
    assert pipeline.engine_registry is test_engine_registry

@pytest.mark.anyio
async def test_plan_day_intent_works(mock_session, test_engine_registry, monkeypatch):
    controller = AIBrainController(session=mock_session, engine_registry=test_engine_registry)
    # Mock pipeline execution so we don't need real DB state for this functional routing test
    controller._decision_pipeline = MagicMock()
    controller._decision_pipeline.run_pipeline = AsyncMock(return_value={"schedule": [{"task_id": 1, "predicted_productivity": 85.0}]})
    
    mock_exec_brain_cls = MagicMock()
    mock_exec_brain_inst = MagicMock()
    mock_exec_brain_inst.execute_planning_request.return_value = {"executive_summary": "mock summary", "candidate_plans": {"plans": [{"plan": {"schedule": [{"task_id": 1}]}}]}}
    mock_exec_brain_cls.return_value = mock_exec_brain_inst
    monkeypatch.setattr("backend.app.orchestrator.executive_cognitive_brain.ExecutiveCognitiveBrain", mock_exec_brain_cls)
    
    from backend.app.orchestrator.brain_models import BrainRequest
    req = BrainRequest(request_id="test1", user_id=1, intent="plan_day", parameters={"goal": "plan my day"})
    result = await controller.process_intent(req)
    assert result.success is True
    controller._decision_pipeline.run_pipeline.assert_awaited_once_with(goal_text="plan my day", user_id=1)

@pytest.mark.anyio
async def test_exception_propagation(mock_session, test_engine_registry, monkeypatch):
    controller = AIBrainController(session=mock_session, engine_registry=test_engine_registry)
    controller._decision_pipeline = MagicMock()
    controller._decision_pipeline.run_pipeline = AsyncMock(side_effect=ValueError("Pipeline simulated error"))
    
    mock_exec_brain_cls = MagicMock()
    mock_exec_brain_inst = MagicMock()
    mock_exec_brain_inst.execute_planning_request.return_value = {"executive_summary": "mock summary"}
    mock_exec_brain_cls.return_value = mock_exec_brain_inst
    monkeypatch.setattr("backend.app.orchestrator.executive_cognitive_brain.ExecutiveCognitiveBrain", mock_exec_brain_cls)
    
    from backend.app.orchestrator.brain_models import BrainRequest
    req = BrainRequest(request_id="test2", user_id=1, intent="plan_day", parameters={"goal": "plan my day"})
    
    result = await controller.process_intent(req)
    assert result.success is False
    assert "Pipeline simulated error" in result.executive_summary

@pytest.mark.anyio
async def test_real_pipeline_fallback_behavior(mock_session, test_engine_registry):
    """
    Test real cold-start behavior ensuring it still provides the 3 fallback tasks
    with fractional scheduling, unknown type fallback, etc., without AIOrchestrator.
    """
    pipeline = DecisionPipeline(session=mock_session, engine_registry=test_engine_registry)
    
    # We mock the database extraction to return empty to force cold-start
    test_engine_registry.get_behavior_engine().extract_features = MagicMock(
        return_value=({"unknown_task_type": "other"}, [], {})
    )
    
    tasks = [
        {"title": "Define sub-goals", "type": "planning", "priority": 7, "estimated_duration": 1.0, "estimated_duration_unit": "hours", "estimated_duration_source": "user_goal"},
        {"title": "Execute main work block", "type": "general", "priority": 8, "estimated_duration": 1.5, "estimated_duration_unit": "hours", "estimated_duration_source": "user_goal"},
        {"title": "Review completion criteria", "type": "review", "priority": 6, "estimated_duration": 1.0, "estimated_duration_unit": "hours", "estimated_duration_source": "user_goal"},
    ]
    # We let the real pipeline run.
    result = await pipeline.run_pipeline(goal_text="plan my day", user_id=1, tasks=tasks)
    
    # Verify cold-start generated 3 tasks
    assert "schedule" in result
    schedule = result["schedule"]
    assert len(schedule) == 3
    
    # Verify fractional scheduling and unknown tasks fallbacks exist
    for task in schedule:
        assert isinstance(task.get("estimated_duration"), float)
        assert task.get("task_type") in ("general", "planning", "review", "other")
