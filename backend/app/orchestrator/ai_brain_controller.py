from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Dict, List, Optional
import time

from sqlalchemy.orm import Session

from backend.app.adaptive import AdaptiveScheduler
from backend.app.core.engine_registry import EngineRegistry
from backend.app.learning import AutonomousLearningLoop
from backend.app.memory import VectorMemorySystem
from backend.app.monitoring import AIMonitor
from backend.app.pipeline import DecisionPipeline
from backend.app.recommendation import RecommendationEngine
from backend.app.orchestrator.brain_models import (
    BrainRequest,
    BrainResponse,
    BrainExecutionTrace,
    StageTrace,
    TraceStatus,
    QuantumStatus
)

class AIBrainController:
    """Central AI Brain Orchestrator that coordinates multiple specialized pipelines."""

    def __init__(
        self,
        session: Session,
        *,
        days_back: int = 90,
        engine_registry: Optional[EngineRegistry] = None,
        monitor: Optional[AIMonitor] = None,
        memory_system: Optional[VectorMemorySystem] = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.engine_registry = engine_registry or EngineRegistry(session)
        self.monitor = monitor or AIMonitor()
        self.memory_system = memory_system or VectorMemorySystem()
        self.logger = logging.getLogger(__name__)

        self._decision_pipeline: Optional[DecisionPipeline] = None
        self._adaptive_scheduler: Optional[AdaptiveScheduler] = None
        self._learning_loop: Optional[AutonomousLearningLoop] = None
        self._recommendation_engine: Optional[RecommendationEngine] = None

    def _get_decision_pipeline(self) -> DecisionPipeline:
        if self._decision_pipeline is None:
            self._decision_pipeline = DecisionPipeline(
                session=self.session,
                days_back=self.days_back,
                engine_registry=self.engine_registry,
            )
        return self._decision_pipeline

    def _get_adaptive_scheduler(self) -> AdaptiveScheduler:
        if self._adaptive_scheduler is None:
            self._adaptive_scheduler = AdaptiveScheduler(
                session=self.session,
                days_back=self.days_back,
                decision_pipeline=self._get_decision_pipeline(),
            )
        return self._adaptive_scheduler

    def _get_learning_loop(self) -> AutonomousLearningLoop:
        if self._learning_loop is None:
            self._learning_loop = AutonomousLearningLoop(
                session=self.session,
                days_back=self.days_back,
                engine_registry=self.engine_registry,
                monitor=self.monitor,
            )
        return self._learning_loop

    def _get_recommendation_engine(self) -> RecommendationEngine:
        if self._recommendation_engine is None:
            self._recommendation_engine = RecommendationEngine(
                session=self.session,
                days_back=self.days_back,
                engine_registry=self.engine_registry,
                monitor=self.monitor,
            )
        return self._recommendation_engine

    async def process_intent(self, request: BrainRequest) -> BrainResponse:
        """Route a formal BrainRequest to the appropriate AI subsystem and execute."""
        started_cpu = perf_counter()
        started_wall = time.time()
        
        trace = BrainExecutionTrace(
            request_id=request.request_id,
            started_at=started_wall,
        )
            
        try:
            response = await self._route_and_execute(request, trace)
            self.monitor.log_engine_execution("AIBrainController", perf_counter() - started_cpu)
            return response
        except Exception as exc:
            self.logger.exception("AIBrainController execution failed for user %s with intent %s", request.user_id, request.intent)
            
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            
            return BrainResponse(
                success=False,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=f"Brain execution failed: {exc}",
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                errors=[str(exc)]
            )

    async def _route_and_execute(self, request: BrainRequest, trace: BrainExecutionTrace) -> BrainResponse:
        """Internal routing logic mapping intents to pipelines."""
        if request.intent == "plan_day":
            return await self._execute_central_planning(request, trace)

        if request.intent == "optimize_schedule":
            schedule = request.parameters.get("schedule") or self._latest_schedule_from_memory(request.user_id)
            if not schedule:
                # Fallback to planning the day
                pipeline_result = await self._execute_central_planning(request, trace)
                schedule = pipeline_result.schedule
            
            adapted = await self._get_adaptive_scheduler().adapt_schedule(schedule=schedule, user_id=request.user_id)
            
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                schedule=adapted.get("updated_schedule", []),
                executive_summary="Schedule adapted based on optimization rules.",
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result=adapted
            )

        if request.intent == "get_recommendations":
            recs = await self._get_recommendation_engine().generate_recommendations(request.user_id)
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary="Recommendations generated.",
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                recommendation=recs,
                trace=trace,
                raw_result=recs
            )

        if request.intent == "analyze_productivity":
            behavior_engine = self.engine_registry.get_behavior_engine()
            task_history = behavior_engine.collect_behavior_data(
                user_id=request.user_id,
                days_back=self.days_back,
            )
            if task_history.empty:
                raise ValueError("No completed tasks found for the user.")
            behavior_engine.extract_features()
            raw = {
                "patterns": behavior_engine.get_user_patterns(),
                "report": behavior_engine.generate_report(),
            }
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary="Productivity analyzed.",
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result=raw
            )

        if request.intent == "run_learning_cycle":
            raw = await self._get_learning_loop().run_learning_cycle(request.user_id)
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary="Learning cycle completed.",
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result=raw
            )

        raise ValueError(f"Unsupported intent: {request.intent}")

    async def _execute_central_planning(self, request: BrainRequest, trace: BrainExecutionTrace) -> BrainResponse:
        """
        The Central AI Brain Pipeline.
        Implements the full Synopsis Architecture Flow rigorously.
        """
        user_id = request.user_id
        goal_text = str(request.parameters.get("goal") or request.parameters.get("command") or "Plan my day")
        
        # ---------------------------------------------------------
        # Pre-Stage: Gather Intelligence Context (F8)
        # ---------------------------------------------------------
        st_intel = time.time()
        from backend.app.orchestrator.intelligence_models import (
            IntelligenceContext, MemoryState, BehavioralInsights, PredictiveForecast,
            GoalAlignment, DependencyGraph, SimulationResults, StrategicHorizon
        )
        
        intel_context = IntelligenceContext()
        
        # 1. Memory State
        try:
            mem_data = self.memory_system.retrieve_context(user_id=user_id)
            intel_context.memory_state = MemoryState(
                available=True,
                context_keys=list(mem_data.keys()),
                recent_memories=mem_data.get("recent_memories", [])
            )
        except Exception as e:
            intel_context.memory_state = MemoryState(available=False, error=str(e))
            
        # 2. Behavioral Insights
        try:
            behavior_engine = self.engine_registry.get_behavior_engine()
            patterns = behavior_engine.get_user_patterns()
            intel_context.behavioral_insights = BehavioralInsights(
                available=True,
                patterns_identified=len(patterns),
                insights=patterns.get("insights", [])
            )
        except Exception as e:
            intel_context.behavioral_insights = BehavioralInsights(available=False, error=str(e))

        et_intel = time.time()
        trace.stages.append(StageTrace(
            stage="INTELLIGENCE_GATHERING",
            status=TraceStatus.SUCCESS,
            started_at=st_intel,
            completed_at=et_intel,
            duration_ms=(et_intel - st_intel) * 1000
        ))

        # ---------------------------------------------------------
        # Stage 1: Classical Optimization
        # ---------------------------------------------------------
        st_class = time.time()
        decision_pipeline = self._get_decision_pipeline()
        pipeline_result = await decision_pipeline.run_pipeline(
            goal_text=goal_text,
            user_id=user_id,
        )
        classical_schedule = pipeline_result.get("schedule", [])
        et_class = time.time()
        trace.stages.append(StageTrace(
            stage="CLASSICAL_OPTIMIZATION",
            status=TraceStatus.SUCCESS,
            started_at=st_class,
            completed_at=et_class,
            duration_ms=(et_class - st_class) * 1000,
            metadata={"tasks_scheduled": len(classical_schedule)}
        ))
        
        # ---------------------------------------------------------
        # Stage 2: Quantum Suitability Check
        # ---------------------------------------------------------
        st_quant = time.time()
        from backend.app.quantum.integration.suitability import QuantumSuitabilityAnalyzer
        from backend.app.quantum.integration.models import QuantumSuitabilityResult
        
        suitability_analyzer = QuantumSuitabilityAnalyzer()
        # Mocked unsupported formulation for generic schedules
        suitability = QuantumSuitabilityResult("UNSUPPORTED", ("No QUBO formulation for general schedules.",), 0, 0, "classical_schedule")
        
        et_quant = time.time()
        trace.stages.append(StageTrace(
            stage="QUANTUM_SUITABILITY",
            status=TraceStatus.SUCCESS,
            started_at=st_quant,
            completed_at=et_quant,
            duration_ms=(et_quant - st_quant) * 1000,
            metadata={"decision": suitability.decision}
        ))
        
        # ---------------------------------------------------------
        # Stage 3: Hybrid/Quantum Optimization
        # ---------------------------------------------------------
        final_schedule = classical_schedule
        quantum_status = QuantumStatus.CLASSICAL_ONLY
        if suitability.decision == "UNSUPPORTED":
            quantum_status = QuantumStatus.QUANTUM_CONSIDERED_BUT_REJECTED
        
        # ---------------------------------------------------------
        # Stage 4: Executive Cognitive Brain
        # ---------------------------------------------------------
        st_exec = time.time()
        from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
        
        executive_brain = ExecutiveCognitiveBrain(
            context_engine=self.engine_registry.get_context_engine(),
            behavior_engine=self.engine_registry.get_behavior_engine(),
            prediction_engine=self.engine_registry.get_prediction_engine(),
            planning_engine=self.engine_registry.get_planning_engine(),
            decision_engine=self.engine_registry.get_decision_engine(),
            scheduling_engine=self.engine_registry.get_scheduling_engine(),
            optimization_engine=self.engine_registry.get_optimization_engine(),
            goal_intelligence_engine=self.engine_registry.get_goal_intelligence_engine(),
            dependency_intelligence_engine=self.engine_registry.get_dependency_intelligence_engine(),
            future_simulation_engine=self.engine_registry.get_future_simulation_engine(),
            strategic_planning_engine=self.engine_registry.get_strategic_planning_engine(),
        )
        
        executive_result = executive_brain.execute_planning_request(
            tasks=final_schedule,
            user_id=user_id,
            query=goal_text,
            intelligence_context=intel_context,
        )
        
        et_exec = time.time()
        trace.stages.append(StageTrace(
            stage="EXECUTIVE_REVIEW",
            status=TraceStatus.SUCCESS,
            started_at=st_exec,
            completed_at=et_exec,
            duration_ms=(et_exec - st_exec) * 1000
        ))
        
        # Finalize Trace
        trace.completed_at = time.time()
        trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
        
        # Assemble Final Response
        raw_result = {
            **pipeline_result,
            "schedule": final_schedule,
            "quantum_suitability": suitability.decision,
            "executive_summary": executive_result.get("executive_summary", "Classical schedule generated."),
            "brain_orchestration": True,
            "executive_trace": executive_result.get("executive_trace", {})
        }
        
        return BrainResponse(
            success=True,
            request_id=request.request_id,
            intent=request.intent,
            schedule=final_schedule,
            executive_summary=executive_result.get("executive_summary", "Classical schedule generated."),
            quantum_status=quantum_status,
            quantum_suitability_result=None,
            trace=trace,
            executive_trace=executive_result.get("executive_trace", {}),
            raw_result=raw_result
        )

    def _latest_schedule_from_memory(self, user_id: int) -> List[Dict[str, Any]]:
        memory_context = self.memory_system.retrieve_context(user_id=user_id)
        for record in reversed(memory_context.get("recent_memories", [])):
            metadata = record.get("metadata", {})
            for key in ("schedule", "optimized_schedule_snapshot", "payload"):
                schedule = metadata.get(key)
                if isinstance(schedule, list) and schedule:
                    return schedule
        return []
