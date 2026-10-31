from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional
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

    _active_proposals: Dict[int, Dict[str, Any]] = {}

    def __init__(
        self,
        session: Session,
        *,
        days_back: int = 90,
        engine_registry: Optional[EngineRegistry] = None,
        monitor: Optional[AIMonitor] = None,
        memory_system: Optional[VectorMemorySystem] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.engine_registry = engine_registry or EngineRegistry(session)
        self.monitor = monitor or AIMonitor()
        self.memory_system = memory_system or VectorMemorySystem()
        self.clock = clock
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

    async def execute_intent(self, request: BrainRequest) -> BrainResponse:
        """Alias for process_intent for backwards compatibility."""
        return await self.process_intent(request)

    async def _route_and_execute(self, request: BrainRequest, trace: BrainExecutionTrace) -> BrainResponse:
        """Internal routing logic mapping intents to pipelines."""
        if request.intent == "general_question":
            from backend.app.models.task import Task
            from backend.app.services.plan_proposal_service import PlanProposalService
            from backend.app.interface.llm_provider import HybridPlanningParser

            pending_count = (
                self.session.query(Task.id)
                .filter(Task.user_id == request.user_id, Task.completed.is_(False))
                .count()
            ) if self.session is not None else 0
            proposal = PlanProposalService(self.session).get_active_proposal(request.user_id) if self.session is not None else None
            context_bits = [f"User has {pending_count} active pending tasks."]
            if proposal:
                context_bits.append(f"There is an active schedule proposal ({len(proposal.tasks_snapshot or [])} scheduled tasks).")
            system_context = " ".join(context_bits)

            turns = request.parameters.get("conversation_turns") or []
            parser = HybridPlanningParser(clock=self.clock)
            answer_text, provenance = parser.generate_chat_response(
                prompt=request.command,
                conversation_history=turns,
                system_context=system_context,
            )

            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=answer_text,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result={
                    "action": "general_answer",
                    "answer": answer_text,
                    "executive_summary": answer_text,
                    "provenance": provenance,
                },
            )

        if request.intent == "create_task":
            from backend.app.services.task_lifecycle_service import TaskLifecycleService
            task_service = TaskLifecycleService(self.session)
            title = str(request.parameters.get("title") or request.parameters.get("command") or "New Task").strip()
            task_type = str(request.parameters.get("task_type") or "general").strip()
            priority = int(request.parameters.get("priority") or 3)
            duration_minutes = float(request.parameters.get("estimated_duration") or 60.0)
            created_task = task_service.create_task(
                user_id=request.user_id,
                title=title,
                task_type=task_type,
                priority=priority,
                estimated_duration=duration_minutes,
                estimated_duration_unit="minutes",
                estimated_duration_source="conversational_input",
            )
            serialized = task_service.serialize_task(created_task)
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            summary = f"Created task '{title}' (priority {priority}, duration {int(duration_minutes)} min)."
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=summary,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result={"task": serialized, "action": "task_created", "executive_summary": summary}
            )

        if request.intent == "list_tasks":
            from backend.app.services.task_lifecycle_service import TaskLifecycleService
            task_service = TaskLifecycleService(self.session)
            all_tasks = task_service.get_all_tasks(user_id=request.user_id)
            pending_tasks = [task_service.serialize_task(t) for t in all_tasks if not t.completed]
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            summary = f"Found {len(pending_tasks)} pending task(s) in your workspace."
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=summary,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result={"tasks": pending_tasks, "total_pending": len(pending_tasks), "executive_summary": summary}
            )

        if request.intent == "prioritize_tasks":
            from backend.app.services.task_lifecycle_service import TaskLifecycleService
            task_service = TaskLifecycleService(self.session)
            all_tasks = task_service.get_all_tasks(user_id=request.user_id)
            active_tasks = [t for t in all_tasks if not t.completed]
            if not active_tasks:
                trace.completed_at = time.time()
                trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
                summary = "No active pending tasks found to prioritize. Create a task first."
                return BrainResponse(
                    success=True,
                    request_id=request.request_id,
                    intent=request.intent,
                    executive_summary=summary,
                    quantum_status=QuantumStatus.CLASSICAL_ONLY,
                    trace=trace,
                    raw_result={"tasks": [], "executive_summary": summary}
                )
            active_serialized = [
                {
                    "id": t.id,
                    "title": t.title,
                    "task_type": t.task_type,
                    "priority": t.priority,
                    "estimated_duration": t.estimated_duration or 60.0,
                    "estimated_duration_unit": t.estimated_duration_unit or "minutes",
                    "estimated_duration_source": t.estimated_duration_source or "task_api",
                }
                for t in active_tasks
            ]
            behavior_engine = self.engine_registry.get_behavior_engine()
            behavior_engine.collect_behavior_data(user_id=request.user_id, days_back=self.days_back)
            behavior_patterns = behavior_engine.get_user_patterns() if hasattr(behavior_engine, "get_user_patterns") else {}
            predicted_tasks = self.engine_registry.get_prediction_engine().predict_batch(
                behavior_engine, active_serialized, behavior_patterns
            )
            prioritized = self.engine_registry.get_decision_engine().prioritize_tasks(
                active_serialized, predicted_tasks, behavior_patterns
            )
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            summary = f"Prioritized {len(prioritized)} active task(s) by priority and estimated outcome."
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=summary,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result={
                    "prioritized_tasks": prioritized,
                    "tasks": prioritized,
                    "total_pending": len(prioritized),
                    "executive_summary": summary,
                }
            )

        if request.intent == "accept_plan":
            from backend.app.services.plan_proposal_service import PlanProposalService
            proposal_service = PlanProposalService(self.session, clock=self.clock)
            
            # Retrieve proposal by explicit ID, or fallback to active proposal for user
            proposal_id = request.parameters.get("proposal_id")
            db_proposal = None
            if proposal_id:
                db_proposal = proposal_service.get_proposal_by_id(proposal_id, request.user_id)
            if not db_proposal:
                db_proposal = proposal_service.get_active_proposal(request.user_id)

            if db_proposal:
                try:
                    success, summary, persisted_tasks, accepted_prop = proposal_service.accept_proposal(
                        proposal_id=db_proposal.id,
                        user_id=request.user_id,
                        expected_version=request.parameters.get("version"),
                        override_schedule=request.parameters.get("schedule"),
                    )
                except ValueError as ve:
                    trace.completed_at = time.time()
                    trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
                    return BrainResponse(
                        success=False,
                        request_id=request.request_id,
                        intent=request.intent,
                        executive_summary=str(ve),
                        quantum_status=QuantumStatus.CLASSICAL_ONLY,
                        trace=trace,
                        errors=[str(ve)],
                        raw_result={"success": False, "error": str(ve)}
                    )

                self._active_proposals.pop(request.user_id, None)
                trace.completed_at = time.time()
                trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
                return BrainResponse(
                    success=True,
                    request_id=request.request_id,
                    intent=request.intent,
                    schedule=accepted_prop.schedule,
                    executive_summary=summary,
                    quantum_status=QuantumStatus.CLASSICAL_ONLY,
                    trace=trace,
                    raw_result={
                        "success": True,
                        "action": "plan_accepted",
                        "plan_accepted": True,
                        "plan_rejected": False,
                        "proposal_id": accepted_prop.id,
                        "proposal_version": accepted_prop.version,
                        "proposal_status": accepted_prop.status,
                        "persisted_task_ids": persisted_tasks,
                        "persisted_count": len(persisted_tasks),
                        "schedule": accepted_prop.schedule,
                        "executive_summary": summary,
                    }
                )

            # Fallback for memory-based proposals without DB row
            active_prop = self._active_proposals.get(request.user_id, {})
            schedule = request.parameters.get("schedule") or active_prop.get("schedule") or self._latest_schedule_from_memory(request.user_id)
            if not schedule:
                trace.completed_at = time.time()
                trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
                return BrainResponse(
                    success=False,
                    request_id=request.request_id,
                    intent=request.intent,
                    executive_summary="No active plan proposal found to accept. Generate a plan first.",
                    quantum_status=QuantumStatus.CLASSICAL_ONLY,
                    trace=trace,
                    errors=["No active plan proposal found to accept."]
                )
            from backend.app.models.task import Task
            from backend.app.services.task_lifecycle_service import TaskLifecycleService
            from datetime import datetime, timezone
            task_service = TaskLifecycleService(self.session, clock=self.clock)
            ref_dt = self.clock() if self.clock else datetime.now(timezone.utc).replace(tzinfo=None)
            now = ref_dt.replace(minute=0, second=0, microsecond=0)
            persisted_tasks = []

            for item in schedule:
                tid = item.get("task_id") or item.get("id")
                origin = item.get("origin")
                sched_hour = float(item.get("scheduled_hour", 9.0))
                sched_end = float(item.get("scheduled_end_hour", sched_hour + 1.0))
                start_dt = now.replace(hour=int(sched_hour) % 24, minute=int((sched_hour % 1) * 60))
                end_dt = now.replace(hour=int(sched_end) % 24, minute=int((sched_end % 1) * 60))

                if tid and isinstance(tid, (int, str)) and str(tid).isdigit():
                    task_obj = self.session.query(Task).filter(Task.id == int(tid), Task.user_id == request.user_id).one_or_none()
                    if task_obj:
                        task_obj.start_time = start_dt
                        task_obj.end_time = end_dt
                        persisted_tasks.append(task_obj.id)
                elif origin == "proposed" or (isinstance(tid, str) and tid.startswith("proposed:")):
                    title_clean = str(item.get("title", "New Task")).strip()
                    existing_match = self.session.query(Task).filter(
                        Task.user_id == request.user_id,
                        Task.title == title_clean,
                        Task.completed == False,
                    ).first()
                    if existing_match:
                        existing_match.start_time = start_dt
                        existing_match.end_time = end_dt
                        persisted_tasks.append(existing_match.id)
                    else:
                        dur_mins = float(item.get("estimated_duration", 1.0))
                        if item.get("estimated_duration_unit") == "hours":
                            dur_mins *= 60.0
                        created_task = task_service.create_task(
                            user_id=request.user_id,
                            title=title_clean,
                            task_type=str(item.get("task_type", "general")),
                            priority=int(item.get("priority", 3)),
                            estimated_duration=dur_mins,
                            estimated_duration_unit="minutes",
                            estimated_duration_source=str(item.get("estimated_duration_source") or "conversational_input"),
                        )
                        created_task.start_time = start_dt
                        created_task.end_time = end_dt
                        persisted_tasks.append(created_task.id)

            self.session.commit()
            self._active_proposals.pop(request.user_id, None)
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            summary = f"Plan accepted and persisted for {len(persisted_tasks)} task(s)."
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                schedule=schedule,
                executive_summary=summary,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result={
                    "success": True,
                    "action": "plan_accepted",
                    "plan_accepted": True,
                    "plan_rejected": False,
                    "persisted_task_ids": persisted_tasks,
                    "persisted_count": len(persisted_tasks),
                    "schedule": schedule,
                    "executive_summary": summary,
                }
            )

        if request.intent == "reject_plan":
            from backend.app.services.plan_proposal_service import PlanProposalService
            proposal_service = PlanProposalService(self.session, clock=self.clock)
            proposal_id = request.parameters.get("proposal_id")
            db_proposal = None
            if proposal_id:
                db_proposal = proposal_service.get_proposal_by_id(proposal_id, request.user_id)
            if not db_proposal:
                db_proposal = proposal_service.get_active_proposal(request.user_id)

            if db_proposal:
                try:
                    proposal_service.reject_proposal(db_proposal.id, request.user_id)
                except Exception as e:
                    logger.warning("Error rejecting db proposal: %s", e)

            self._active_proposals.pop(request.user_id, None)
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            summary = "Plan proposal rejected and discarded. No changes were made to your tasks or database."
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=summary,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result={
                    "success": True,
                    "action": "plan_rejected",
                    "plan_accepted": False,
                    "plan_rejected": True,
                    "proposal_id": db_proposal.id if db_proposal else None,
                    "proposal_status": "REJECTED",
                    "executive_summary": summary,
                }
            )

        if request.intent == "refine_plan":
            return await self._execute_proposal_refinement(request, trace)

        if request.intent == "plan_day":
            return await self._execute_central_planning(request, trace)

        if request.intent == "optimize_schedule":
            schedule = request.parameters.get("schedule") or self._latest_schedule_from_memory(request.user_id)
            if not schedule:
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

    async def _execute_central_planning(
        self,
        request: BrainRequest,
        trace: BrainExecutionTrace,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> BrainResponse:
        """
        The Central AI Brain Pipeline.
        Implements the full Synopsis Architecture Flow rigorously.
        """
        user_id = request.user_id
        goal_text = str(request.parameters.get("goal") or request.parameters.get("command") or "Plan my day")
        available_hours = request.parameters.get("available_hours")
        task_count = request.parameters.get("task_count")

        # ---------------------------------------------------------
        # Pre-Stage: Gather Intelligence Context & Active User Tasks
        # ---------------------------------------------------------
        st_intel = time.time()
        from backend.app.orchestrator.intelligence_models import (
            IntelligenceContext, MemoryState, BehavioralInsights, PredictiveForecast,
            GoalAlignment, DependencyGraph, SimulationResults, StrategicHorizon
        )
        from backend.app.services.task_lifecycle_service import TaskLifecycleService
        from backend.app.ml.readiness import assess_full_ml_system_readiness
        import re

        task_service = TaskLifecycleService(self.session, clock=self.clock)
        all_user_tasks = task_service.get_all_tasks(user_id=user_id)
        active_user_tasks = [t for t in all_user_tasks if not t.completed]

        use_existing = bool(request.parameters.get("use_existing_tasks", False))
        extracted_tasks_raw = request.parameters.get("extracted_tasks") or []
        explicit_tasks: List[Dict[str, Any]] = []

        if use_existing or (not extracted_tasks_raw and active_user_tasks):
            active_user_tasks.sort(key=lambda t: t.priority, reverse=True)
            if task_count and task_count > 0:
                active_user_tasks = active_user_tasks[:task_count]

            explicit_tasks = [
                {
                    "id": t.id,
                    "title": t.title,
                    "task_type": t.task_type,
                    "priority": t.priority,
                    "estimated_duration": (t.estimated_duration / 60.0) if (t.estimated_duration_unit == "minutes" and t.estimated_duration) else (t.estimated_duration or 1.0),
                    "estimated_duration_unit": "hours",
                    "estimated_duration_source": t.estimated_duration_source or "existing_database",
                    "completed": False,
                    "origin": "existing",
                    "deadline": None,
                    "dependencies": [],
                }
                for t in active_user_tasks
            ]
        elif extracted_tasks_raw:
            for idx, ext in enumerate(extracted_tasks_raw, start=1):
                ext_title = str(ext.get("title", "")).strip()
                matched_db_task = None
                for t in active_user_tasks:
                    if t.title.lower() == ext_title.lower() or (len(ext_title) > 3 and ext_title.lower() in t.title.lower()):
                        matched_db_task = t
                        break

                if matched_db_task:
                    tid = matched_db_task.id
                    origin = "existing"
                    prio = ext.get("priority") or matched_db_task.priority
                    dur = ext.get("estimated_duration") or (matched_db_task.estimated_duration / 60.0 if matched_db_task.estimated_duration else 1.0)
                    dur_src = ext.get("estimated_duration_source") or matched_db_task.estimated_duration_source or "existing_database"
                    ttype = matched_db_task.task_type
                else:
                    slug = re.sub(r"[^a-zA-Z0-9_]", "_", ext_title.lower())[:24]
                    tid = str(ext.get("id") or f"proposed:{slug}_{idx}")
                    origin = ext.get("origin", "proposed")
                    prio = ext.get("priority", 3)
                    dur = ext.get("estimated_duration", 1.0)
                    dur_src = ext.get("estimated_duration_source", "conversational_input")
                    ttype = ext.get("task_type", "general")

                explicit_tasks.append({
                    "id": tid,
                    "title": ext_title or f"Task {idx}",
                    "task_type": ttype,
                    "priority": int(prio),
                    "estimated_duration": float(dur),
                    "estimated_duration_unit": "hours",
                    "estimated_duration_source": dur_src,
                    "completed": False,
                    "origin": origin,
                    "deadline": ext.get("deadline"),
                    "deadline_expression": ext.get("deadline_expression"),
                    "deadline_dt": ext.get("deadline_dt"),
                    "deadline_precision": ext.get("deadline_precision"),
                    "dependencies": ext.get("dependencies") or [],
                    "scheduling_preference": ext.get("scheduling_preference"),
                    "min_start_hour": ext.get("min_start_hour"),
                })

        if not explicit_tasks and request.parameters.get("clarification_needed"):
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            q = request.parameters.get("clarification_question") or "Please specify the tasks and deadlines you would like to schedule."
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=q,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result={
                    "action": "clarification_needed",
                    "clarification_question": q,
                    "schedule": [],
                    "executive_summary": q,
                }
            )

        # Check behavioral model readiness
        readiness = assess_full_ml_system_readiness(self.session, user_id=user_id)
        is_ml_ready = readiness.overall_status in ("READY_FOR_TRAINING", "TRAINED")
        provenance_label = "PERSONAL_MODEL" if is_ml_ready else "DETERMINISTIC_FALLBACK"
        provenance_details = (
            "Personal behavioral model predictions applied."
            if is_ml_ready
            else f"Personal models require {readiness.components.get('DurationRatioModel', {}).required_samples} completed tasks (currently {readiness.components.get('DurationRatioModel', {}).eligible_samples}); using deterministic heuristics."
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
        pipeline_kwargs = {}
        if explicit_tasks:
            pipeline_kwargs["tasks"] = explicit_tasks
        if available_hours is not None:
            pipeline_kwargs["available_hours"] = available_hours
        if constraints is not None:
            pipeline_kwargs["constraints"] = constraints

        pipeline_result = await decision_pipeline.run_pipeline(
            goal_text=goal_text,
            user_id=user_id,
            **pipeline_kwargs,
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
        from backend.app.quantum import QUBOFormulator, QuantumVariable, QuantumObjective

        suitability_analyzer = QuantumSuitabilityAnalyzer()
        task_count_scheduled = len(classical_schedule)
        if 1 <= task_count_scheduled <= 4:
            variables = tuple(QuantumVariable(f"x_{i}", f"Task_{i}", i) for i in range(task_count_scheduled))
            obj = QuantumObjective("min_schedule", "Schedule Objective", "MINIMIZE")
            mock_qubo = QUBOFormulator().formulate(
                problem_id="schedule_plan_qubo",
                name="Schedule Planning QUBO",
                variables=variables,
                linear_coefficients={f"x_{i}": 1.0 for i in range(task_count_scheduled)},
                quadratic_coefficients={},
                objective=obj,
            )
            suitability = suitability_analyzer.analyze(mock_qubo)
        else:
            suitability = QuantumSuitabilityResult(
                "UNSUPPORTED",
                (f"Schedule with {task_count_scheduled} tasks exceeds local simulated register capacity or lacks binary assignment formulation.",),
                task_count_scheduled,
                2 ** task_count_scheduled if task_count_scheduled < 30 else 0,
                "scale_limits"
            )

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
        # Stage 3: Hybrid/Quantum Optimization Selection
        # ---------------------------------------------------------
        final_schedule = classical_schedule
        quantum_status = QuantumStatus.CLASSICAL_ONLY
        if suitability.decision == "UNSUPPORTED":
            quantum_status = QuantumStatus.QUANTUM_CONSIDERED_BUT_REJECTED
        elif suitability.decision == "SUITABLE":
            quantum_status = QuantumStatus.SIMULATED_LOCAL

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

        # Formulate Rich Explainable Summary
        feasibility_status = pipeline_result.get("feasibility_status", "FEASIBLE")
        infeasible_tasks = pipeline_result.get("infeasible_tasks", [])
        deadline_risk_tasks = pipeline_result.get("deadline_risk_tasks", [])
        demanded_hours = pipeline_result.get("total_demanded_hours", 0.0)
        avail_h = available_hours or 8.0

        if feasibility_status == "FEASIBLE":
            exec_summary = (
                f"Proposed feasible plan for {len(classical_schedule)} task(s) within {avail_h:.1f} available hours "
                f"(total workload: {demanded_hours:.1f}h). Tasks scheduled non-overlapping in high-focus slots."
            )
        elif feasibility_status == "DEADLINE_RISK":
            exec_summary = (
                f"Deadline risk detected: {len(deadline_risk_tasks)} task(s) scheduled past or close to declared deadline. "
                f"Review order or prioritize urgent work."
            )
        else:
            exec_summary = (
                f"Workload overload detected: Demanded {demanded_hours:.1f}h exceeds available horizon of {avail_h:.1f}h. "
                f"{len(infeasible_tasks)} task(s) cannot fit and require deferral or scope reduction."
            )

        # Assemble Final Response
        raw_result = {
            **pipeline_result,
            "schedule": final_schedule,
            "feasibility_status": feasibility_status,
            "infeasible_tasks": infeasible_tasks,
            "unscheduled_tasks": infeasible_tasks,
            "deadline_risk_tasks": deadline_risk_tasks,
            "total_demanded_hours": demanded_hours,
            "available_hours": avail_h,
            "behavioral_provenance": provenance_label,
            "behavioral_details": provenance_details,
            "parser_provenance": request.parameters.get("parser_provenance", "deterministic_fallback"),
            "quantum_suitability": suitability.decision,
            "quantum_reasons": list(suitability.reasons),
            "executive_summary": exec_summary,
            "brain_orchestration": True,
            "executive_trace": executive_result.get("executive_trace", {})
        }

        # Cache proposal for conversational refinement and safe acceptance
        from backend.app.services.plan_proposal_service import PlanProposalService
        proposal_service = PlanProposalService(self.session, clock=self.clock)
        db_proposal = proposal_service.create_proposal(
            user_id=user_id,
            schedule=final_schedule,
            tasks=explicit_tasks,
            available_hours=avail_h,
            goal_text=goal_text,
            constraints=constraints or {},
            provenance={
                "behavioral_provenance": provenance_label,
                "behavioral_details": provenance_details,
                "parser_provenance": request.parameters.get("parser_provenance", "deterministic_fallback"),
            },
            raw_result=raw_result,
        )
        raw_result["proposal_id"] = db_proposal.id
        raw_result["proposal_version"] = db_proposal.version
        raw_result["proposal_status"] = db_proposal.status
        self._active_proposals[user_id] = db_proposal.to_dict()

        return BrainResponse(
            success=True,
            request_id=request.request_id,
            intent=request.intent,
            schedule=final_schedule,
            executive_summary=exec_summary,
            quantum_status=quantum_status,
            quantum_suitability_result=None,
            trace=trace,
            executive_trace=executive_result.get("executive_trace", {}),
            raw_result=raw_result
        )

    async def _execute_proposal_refinement(self, request: BrainRequest, trace: BrainExecutionTrace) -> BrainResponse:
        user_id = request.user_id
        from backend.app.services.plan_proposal_service import PlanProposalService
        proposal_service = PlanProposalService(self.session, clock=self.clock)

        db_prop = None
        req_prop_id = request.parameters.get("proposal_id")
        if req_prop_id:
            db_prop = proposal_service.get_proposal_by_id(req_prop_id, user_id)
        if not db_prop:
            db_prop = proposal_service.get_active_proposal(user_id)

        active = db_prop.to_dict() if db_prop else self._active_proposals.get(user_id)
        if not active:
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            msg = "No active plan proposal found to refine. Please generate a schedule first."
            return BrainResponse(
                success=False,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=msg,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                errors=[msg]
            )

        from backend.app.interface.nl_extractor import NaturalLanguageExtractor
        extractor = NaturalLanguageExtractor(clock=self.clock)
        refinement = request.parameters.get("refinement") or extractor.parse_refinement(request.command, active.get("schedule", []))
        action = refinement.get("action")

        if action in ("unrecognized", "clarification_needed"):
            trace.completed_at = time.time()
            trace.total_duration_ms = (trace.completed_at - trace.started_at) * 1000
            msg = refinement.get("clarification_question") or (
                "I couldn't identify which specific task or constraint to adjust. Could you specify which task to reorder, delay, or adjust?"
            )
            return BrainResponse(
                success=True,
                request_id=request.request_id,
                intent=request.intent,
                executive_summary=msg,
                quantum_status=QuantumStatus.CLASSICAL_ONLY,
                trace=trace,
                raw_result={
                    "action": "refinement_clarification_needed",
                    "clarification_needed": True,
                    "clarification_question": msg,
                    "executive_summary": msg,
                    "schedule": active.get("schedule", []),
                    "proposal_id": active.get("id"),
                    "proposal_version": active.get("version", 1),
                }
            )

        # Clone current constraints & tasks
        current_constraints = dict(active.get("constraints") or {})
        tasks = [dict(t) for t in active.get("tasks", [])]
        avail_hours = float(active.get("available_hours", 8.0))

        if action == "reduce_available_hours":
            avail_hours = float(refinement["new_available_hours"])
            request.parameters["available_hours"] = avail_hours

        elif action == "reorder":
            first_t = refinement["first_task"]
            second_t = refinement["second_task"]
            order_overrides = list(current_constraints.get("order_overrides") or [])
            order_overrides.append((first_t, second_t))
            current_constraints["order_overrides"] = order_overrides

        elif action == "move_first":
            target_t = refinement["task"].lower()
            order_overrides = list(current_constraints.get("order_overrides") or [])
            matched_title = None
            for t in tasks:
                t_title = str(t.get("title", ""))
                if target_t in t_title.lower():
                    matched_title = t_title
                    break
            if matched_title:
                for other in tasks:
                    o_title = str(other.get("title", ""))
                    if o_title != matched_title:
                        order_overrides.append((matched_title, o_title))
            current_constraints["order_overrides"] = order_overrides

        elif action == "add_buffer":
            current_constraints["buffer_minutes"] = float(refinement["buffer_minutes"])
            current_constraints["buffer_label"] = refinement.get("buffer_label", "revision")

        elif action == "set_start_hour":
            target_t = refinement["task"]
            min_hours = dict(current_constraints.get("min_start_hours") or {})
            min_hours[target_t] = float(refinement["min_start_hour"])
            current_constraints["min_start_hours"] = min_hours

        elif action == "reprioritize":
            target_t = refinement["task"].lower()
            for t in tasks:
                if target_t in t.get("title", "").lower() or target_t in str(t.get("id", "")).lower():
                    t["priority"] = int(refinement.get("new_priority", 5))
                    t["origin"] = "modified"

        elif action == "reduce_duration":
            target_t = refinement["task"].lower()
            for t in tasks:
                if target_t in t.get("title", "").lower() or target_t in str(t.get("id", "")).lower():
                    if refinement.get("new_duration_hours"):
                        t["estimated_duration"] = float(refinement["new_duration_hours"])
                    else:
                        t["estimated_duration"] = max(0.5, round(float(t.get("estimated_duration", 1.0)) * 0.5, 2))
                    t["origin"] = "modified"
                    t["estimated_duration_source"] = "conversational_input"

        elif action == "alternative_schedule":
            # Generate an alternative sequencing by prioritizing earliest deadline with secondary shortest-job-first
            current_constraints["alternative_option"] = True
            current_constraints["strategy"] = "shortest_first" if current_constraints.get("strategy") != "shortest_first" else "deadline_first"

        # Update request parameters to pass refined tasks
        request.parameters["extracted_tasks"] = tasks
        request.parameters["available_hours"] = avail_hours

        # Re-execute central planning with new constraints
        response = await self._execute_central_planning(request, trace, constraints=current_constraints)
        response.executive_summary = f"Refined proposal ({refinement.get('description', 'applied adjustment')}): {response.executive_summary}"

        # Update database-backed proposal versioning
        if db_prop:
            updated_prop = proposal_service.update_proposal_refinement(
                proposal_id=db_prop.id,
                user_id=user_id,
                new_schedule=response.schedule,
                new_tasks=tasks,
                new_constraints=current_constraints,
                new_provenance=db_prop.provenance,
                raw_result=response.raw_result,
                expected_version=active.get("version"),
                new_available_hours=avail_hours,
            )
            self._active_proposals[user_id] = updated_prop.to_dict()
            if hasattr(response, "raw_result") and isinstance(response.raw_result, dict):
                response.raw_result["proposal_id"] = updated_prop.id
                response.raw_result["proposal_version"] = updated_prop.version
                response.raw_result["proposal_status"] = updated_prop.status
                response.raw_result["executive_summary"] = response.executive_summary
                response.raw_result["refinement_applied"] = refinement
        elif hasattr(response, "raw_result") and isinstance(response.raw_result, dict):
            response.raw_result["executive_summary"] = response.executive_summary
            response.raw_result["refinement_applied"] = refinement

        return response

    def _latest_schedule_from_memory(self, user_id: int) -> List[Dict[str, Any]]:
        memory_context = self.memory_system.retrieve_context(user_id=user_id)
        for record in reversed(memory_context.get("recent_memories", [])):
            metadata = record.get("metadata", {})
            for key in ("schedule", "optimized_schedule_snapshot", "payload"):
                schedule = metadata.get(key)
                if isinstance(schedule, list) and schedule:
                    return schedule
        return []
