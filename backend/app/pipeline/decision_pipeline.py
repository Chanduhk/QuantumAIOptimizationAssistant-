from __future__ import annotations

import logging
from datetime import datetime
from statistics import mean
from time import perf_counter
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.engine_registry import EngineRegistry
from backend.app.core.events import EventBus
from backend.app.monitoring import AIMonitor
from backend.app.orchestrator import AIOrchestrator

GOAL_RECEIVED = "GOAL_RECEIVED"
CONTEXT_READY = "CONTEXT_READY"
PREDICTIONS_READY = "PREDICTIONS_READY"
TASK_PRIORITY_READY = "TASK_PRIORITY_READY"
PLAN_GENERATED = "PLAN_GENERATED"
SCHEDULE_OPTIMIZED = "SCHEDULE_OPTIMIZED"


class DecisionPipeline:
    """Central async reasoning workflow for goal-driven planning and scheduling."""

    def __init__(
        self,
        session: Session,
        *,
        days_back: int = 90,
        engine_registry: Optional[EngineRegistry] = None,
        orchestrator: Optional[AIOrchestrator] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.engine_registry = engine_registry
        self.orchestrator = orchestrator
        self.event_bus = event_bus or EventBus()
        self.logger = logging.getLogger(__name__)
        self.ai_monitor: Optional[AIMonitor] = None
        self._initialized = False

        self._latest_goal_text: Optional[str] = None
        self._latest_goal_metadata: Dict[str, Any] = {}
        self._latest_tasks: List[Dict[str, Any]] = []
        self._latest_context: Dict[str, Any] = {}
        self._latest_predictions: List[Dict[str, Any]] = []
        self._latest_plan: Dict[str, Any] = {}
        self._latest_schedule: List[Dict[str, Any]] = []

    async def initialize_pipeline(self) -> None:
        """Initialize all engine references from the registry and orchestrator."""
        if self._initialized:
            return

        self.engine_registry = self.engine_registry or EngineRegistry(self.session)
        self.orchestrator = self.orchestrator or AIOrchestrator(
            session=self.session,
            days_back=self.days_back,
        )

        self.behavior_engine = self.engine_registry.get_behavior_engine()
        self.decision_engine = self.engine_registry.get_decision_engine()
        self.prediction_engine = self.engine_registry.get_prediction_engine()
        self.planning_engine = self.engine_registry.get_planning_engine()
        self.optimization_engine = self.engine_registry.get_optimization_engine()

        self.cognitive_engine = self.orchestrator.cognitive_engine
        self.context_engine = self.orchestrator.context_engine
        self.rl_scheduler = self.orchestrator.rl_scheduler
        self.memory_system = self.orchestrator.memory_system
        self.feature_store = self.orchestrator.feature_store
        self.knowledge_graph = self.orchestrator.knowledge_graph
        self.ai_monitor = self.orchestrator.ai_monitor

        self._initialized = True

    async def process_goal(self, goal_text: str, user_id: int) -> List[Dict[str, Any]]:
        """Parse, decompose, and prioritize a goal into structured tasks."""
        await self.initialize_pipeline()
        started = perf_counter()

        goal_text = goal_text.strip()
        if not goal_text:
            raise ValueError("goal_text is required.")

        parsed_goal = self.cognitive_engine.parse_goal(goal_text)
        decomposed_goal = self.cognitive_engine.decompose_goal(goal_text)
        prioritized_goal_tasks = self.cognitive_engine.prioritize_goal_tasks(
            decomposed_goal.get("tasks", []),
        )

        structured_tasks = [
            self._normalize_goal_task(task, index=index, user_id=user_id, goal_metadata=parsed_goal)
            for index, task in enumerate(prioritized_goal_tasks, start=1)
        ]

        self._latest_goal_text = goal_text
        self._latest_goal_metadata = parsed_goal
        self._latest_tasks = structured_tasks
        self._monitor().log_engine_execution("CognitiveEngine", perf_counter() - started)
        return structured_tasks

    async def build_context(self, user_id: int) -> Dict[str, Any]:
        """Build a runtime context from context, behavior, features, graph, and memory."""
        await self.initialize_pipeline()
        current_tasks = list(self._latest_tasks)

        context_started = perf_counter()
        base_context = self.context_engine.build_context(
            user_id=user_id,
            behavior_patterns={},
            current_tasks=current_tasks,
            query=self._latest_goal_text,
        )
        self._monitor().log_engine_execution("ContextEngine", perf_counter() - context_started)

        behavior_started = perf_counter()
        behavior_patterns = self._load_behavior_patterns(user_id)
        self._monitor().log_engine_execution(
            "BehaviorIntelligenceEngine",
            perf_counter() - behavior_started,
        )

        feature_started = perf_counter()
        stored_features = self.feature_store.get_all_features(user_id)
        if not stored_features:
            stored_features = self.feature_store.store_features(
                user_id,
                self._build_feature_bundle(behavior_patterns),
            )
        self._monitor().log_engine_execution("FeatureStore", perf_counter() - feature_started)

        graph_started = perf_counter()
        knowledge_graph_relations = {
            "goals": self.knowledge_graph.get_user_goals(user_id),
        }
        self._monitor().log_engine_execution("AIKnowledgeGraph", perf_counter() - graph_started)

        memory_started = perf_counter()
        recent_memory_context = self.memory_system.retrieve_context(user_id=user_id)
        self._monitor().log_engine_execution("VectorMemory", perf_counter() - memory_started)

        combined_context = {
            **base_context,
            "user_id": user_id,
            "goal": self._latest_goal_text,
            "behavior_patterns": behavior_patterns,
            "stored_features": stored_features,
            "knowledge_graph_relations": knowledge_graph_relations,
            "recent_memory_context": recent_memory_context,
        }
        self._latest_context = combined_context
        return combined_context

    async def predict_task_performance(
        self,
        tasks: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Predict productivity, completion probability, and duration for tasks."""
        await self.initialize_pipeline()
        started = perf_counter()

        behavior_patterns = dict(context.get("behavior_patterns", {}))
        predictions: List[Dict[str, Any]] = []
        for task in tasks:
            try:
                prediction = self.prediction_engine.predict_productivity(
                    self.behavior_engine,
                    task,
                    behavior_patterns,
                )
            except Exception:
                self.logger.exception("Prediction fallback activated for task '%s'", task.get("title"))
                prediction = self._fallback_prediction(task, behavior_patterns)

            prediction["completion_probability"] = round(
                float(
                    prediction.get("task_success_probability")
                    or prediction.get("completion_probability")
                    or 0.0
                ),
                4,
            )
            prediction["estimated_duration"] = round(
                float(
                    prediction.get("completion_time_prediction")
                    or prediction.get("estimated_duration")
                    or task.get("estimated_duration")
                    or 1.0
                ),
                2,
            )
            predictions.append(prediction)

        self._latest_predictions = predictions
        self._record_prediction_statistics(predictions)
        self._monitor().log_engine_execution("PredictionEngine", perf_counter() - started)
        return predictions

    async def prioritize_tasks(
        self,
        tasks: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Prioritize tasks using decision intelligence and prediction signals."""
        await self.initialize_pipeline()
        started = perf_counter()

        behavior_patterns = dict(self._latest_context.get("behavior_patterns", {}))
        prioritized_tasks = self.decision_engine.prioritize_tasks(
            tasks,
            predictions,
            behavior_patterns,
        )
        prediction_by_id = {str(item.get("id")): item for item in predictions}
        merged_tasks = []
        for task in prioritized_tasks:
            prediction = prediction_by_id.get(str(task.get("id")), {})
            merged_tasks.append(
                {
                    **prediction,
                    **task,
                    "completion_probability": prediction.get("completion_probability", 0.0),
                    "estimated_duration": prediction.get(
                        "estimated_duration",
                        task.get("estimated_duration"),
                    ),
                }
            )

        self._latest_tasks = merged_tasks
        self._monitor().log_engine_execution("DecisionEngine", perf_counter() - started)
        return merged_tasks

    async def generate_plan(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert prioritized tasks into a structured daily plan."""
        await self.initialize_pipeline()
        started = perf_counter()

        behavior_patterns = dict(self._latest_context.get("behavior_patterns", {}))
        plan = self.planning_engine.generate_daily_plan(tasks, behavior_patterns)
        self._latest_plan = plan
        self._monitor().log_engine_execution("PlanningEngine", perf_counter() - started)
        return plan

    async def optimize_schedule(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run RL scheduling followed by deterministic schedule optimization."""
        await self.initialize_pipeline()
        behavior_patterns = dict(self._latest_context.get("behavior_patterns", {}))

        rl_input = [
            {
                "id": item.get("task_id") or item.get("id"),
                "title": item.get("title"),
                "task_type": item.get("task_type"),
                "priority": item.get("priority"),
                "estimated_duration": item.get("estimated_duration"),
                "predicted_productivity": item.get("predicted_productivity"),
                "scheduled_hour": item.get("recommended_hour"),
            }
            for item in plan.get("tasks", [])
        ]

        rl_started = perf_counter()
        rl_result = self.rl_scheduler.optimize_schedule(
            rl_input,
            behavior_patterns,
            train_before_optimize=False,
        )
        self._monitor().log_engine_execution("RLScheduler", perf_counter() - rl_started)

        optimization_input = [
            {
                **task,
                "scheduled_hour": int(task.get("rl_scheduled_hour", task.get("scheduled_hour", 10))),
                "schedule_score": float(task.get("rl_reward_estimate", 0.0)),
            }
            for task in rl_result["optimized_schedule"]
        ]

        optimization_started = perf_counter()
        optimized_result = self.optimization_engine.optimize_schedule(
            optimization_input,
            behavior_patterns,
        )
        self._monitor().log_engine_execution(
            "OptimizationEngine",
            perf_counter() - optimization_started,
        )

        prediction_by_id = {str(item.get("id")): item for item in self._latest_predictions}
        optimized_schedule = []
        for task in optimized_result["optimized_schedule"]:
            prediction = prediction_by_id.get(str(task.get("id")), {})
            optimized_schedule.append(
                {
                    "task_id": task.get("id"),
                    "title": task.get("title"),
                    "task_type": task.get("task_type"),
                    "priority": task.get("priority"),
                    "scheduled_hour": task.get("optimized_hour", task.get("scheduled_hour")),
                    "scheduled_end_hour": task.get(
                        "optimized_end_hour",
                        task.get("rl_scheduled_end_hour"),
                    ),
                    "predicted_productivity": prediction.get(
                        "predicted_productivity",
                        task.get("predicted_productivity"),
                    ),
                    "completion_probability": prediction.get("completion_probability", 0.0),
                    "estimated_duration": prediction.get(
                        "estimated_duration",
                        task.get("estimated_duration"),
                    ),
                    "decision_score": task.get("decision_score"),
                    "rl_reward_estimate": task.get("rl_reward_estimate"),
                    "hour_productivity_score": task.get("hour_productivity_score"),
                }
            )

        optimized_schedule.sort(key=lambda item: float(item.get("scheduled_hour") or 0.0))
        self._latest_schedule = optimized_schedule
        return optimized_schedule

    async def store_results(self, user_id: int, schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Persist planning results in vector memory and the knowledge graph."""
        await self.initialize_pipeline()
        if not schedule:
            raise ValueError("schedule is required.")

        top_titles = [item["title"] for item in schedule[:3] if item.get("title")]
        summary = (
            f"Decision pipeline plan for user {user_id}: {', '.join(top_titles)}"
            if top_titles
            else f"Decision pipeline plan for user {user_id}"
        )

        memory_started = perf_counter()
        memory_result = self.memory_system.store_memory(
            summary,
            {
                "user_id": user_id,
                "goal": self._latest_goal_text,
                "event_type": "decision_pipeline",
                "created_at": datetime.utcnow().isoformat(),
                "schedule": schedule,
            },
        )
        self._monitor().log_engine_execution("VectorMemory", perf_counter() - memory_started)

        graph_started = perf_counter()
        goal_id = self.knowledge_graph.add_goal(
            user_id,
            self._latest_goal_text or "Decision pipeline goal",
        )
        task_node_ids: List[str] = []
        for item in schedule:
            task_id = self.knowledge_graph.add_task(
                goal_id,
                {
                    "id": item.get("task_id"),
                    "title": item.get("title"),
                    "task_type": item.get("task_type"),
                    "priority": item.get("priority"),
                    "completed": False,
                },
            )
            task_node_ids.append(task_id)
            if item.get("scheduled_hour") is not None:
                self.knowledge_graph.link_task_time(task_id, int(float(item["scheduled_hour"])))
        self._monitor().log_engine_execution("AIKnowledgeGraph", perf_counter() - graph_started)

        return {
            "memory": memory_result,
            "goal_id": goal_id,
            "task_node_ids": task_node_ids,
        }

    async def run_pipeline(self, goal_text: str, user_id: int) -> Dict[str, Any]:
        """Execute the full decision pipeline from goal intake to optimized schedule."""
        await self.initialize_pipeline()
        pipeline_started = perf_counter()

        try:
            await self._emit_event(
                GOAL_RECEIVED,
                {
                    "user_id": user_id,
                    "goal": goal_text,
                },
            )
            tasks = await self.process_goal(goal_text, user_id)

            context = await self.build_context(user_id)
            await self._emit_event(
                CONTEXT_READY,
                {
                    "user_id": user_id,
                    "task_count": len(tasks),
                    "has_behavior_patterns": bool(context.get("behavior_patterns")),
                },
            )

            predictions = await self.predict_task_performance(tasks, context)
            await self._emit_event(
                PREDICTIONS_READY,
                {
                    "user_id": user_id,
                    "prediction_count": len(predictions),
                },
            )

            prioritized_tasks = await self.prioritize_tasks(tasks, predictions)
            await self._emit_event(
                TASK_PRIORITY_READY,
                {
                    "user_id": user_id,
                    "task_count": len(prioritized_tasks),
                },
            )

            plan = await self.generate_plan(prioritized_tasks)
            await self._emit_event(
                PLAN_GENERATED,
                {
                    "user_id": user_id,
                    "planned_tasks": len(plan.get("tasks", [])),
                },
            )

            optimized_schedule = await self.optimize_schedule(plan)
            await self._emit_event(
                SCHEDULE_OPTIMIZED,
                {
                    "user_id": user_id,
                    "scheduled_tasks": len(optimized_schedule),
                },
            )

            await self.store_results(user_id, optimized_schedule)

            pipeline_latency = perf_counter() - pipeline_started
            self._monitor().log_engine_execution("DecisionPipeline", pipeline_latency)
            self._monitor().log_training_metrics(
                "DecisionPipeline",
                {
                    "pipeline_latency_seconds": round(pipeline_latency, 4),
                    "task_count": len(prioritized_tasks),
                    "scheduled_task_count": len(optimized_schedule),
                },
            )

            return {
                "tasks": prioritized_tasks,
                "schedule": optimized_schedule,
                "predictions": predictions,
            }
        except Exception as exc:
            self.logger.exception("Decision pipeline failed for user %s", user_id)
            raise ValueError(f"Decision pipeline failed: {exc}") from exc

    async def _emit_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        await self.event_bus.publish_event(event_name, payload)
        self._monitor().log_event(event_name)

    def _build_feature_bundle(self, behavior_patterns: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_focus_hours": behavior_patterns.get("best_focus_hours", []),
            "average_task_duration": behavior_patterns.get("average_duration_by_task_type", {}),
            "energy_curve": behavior_patterns.get("average_energy_level"),
            "task_completion_rate": behavior_patterns.get("average_completion_time"),
            "productivity_trends": behavior_patterns.get("hourly_productivity", {}),
        }

    def _load_behavior_patterns(self, user_id: int) -> Dict[str, Any]:
        try:
            task_history = self.behavior_engine.collect_behavior_data(
                user_id=user_id,
                days_back=self.days_back,
            )
            if task_history.empty:
                return self._default_behavior_patterns(user_id)

            self.behavior_engine.extract_features()
            return self.behavior_engine.get_user_patterns()
        except Exception:
            self.logger.exception("Behavior pattern fallback activated for user %s", user_id)
            return self._default_behavior_patterns(user_id)

    def _default_behavior_patterns(self, user_id: int) -> Dict[str, Any]:
        default_hours = {9: 58.0, 11: 68.0, 14: 72.0, 16: 64.0}
        return {
            "user_id": user_id,
            "tasks_analyzed": 0,
            "average_productivity": 60.0,
            "average_focus_score": 58.0,
            "average_energy_level": 62.0,
            "average_completion_time": 1.0,
            "best_focus_hours": [9, 11, 14],
            "preferred_task_types": [],
            "hourly_productivity": default_hours,
            "productivity_by_task_type": {},
            "average_duration_by_task_type": {},
        }

    def _normalize_goal_task(
        self,
        task: Dict[str, Any],
        *,
        index: int,
        user_id: int,
        goal_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        task_type = str(task.get("task_type") or task.get("type") or "general").strip().lower() or "general"
        estimated_duration = float(
            task.get("estimated_duration") or self._default_duration_for_task_type(task_type),
        )

        return {
            "id": str(task.get("id") or f"goal-task-{user_id}-{index}"),
            "user_id": user_id,
            "title": str(task.get("title") or f"Task {index}").strip(),
            "task_type": task_type,
            "type": task_type,
            "priority": int(task.get("priority") or 5),
            "estimated_duration": estimated_duration,
            "goal": goal_metadata.get("goal"),
            "goal_type": goal_metadata.get("goal_type"),
            "time_horizon": goal_metadata.get("time_horizon"),
            "completed": bool(task.get("completed", False)),
            "source": "decision_pipeline",
        }

    def _default_duration_for_task_type(self, task_type: str) -> float:
        default_durations = {
            "analysis": 1.5,
            "general": 1.5,
            "learning": 2.0,
            "planning": 1.0,
            "research": 2.0,
            "review": 1.0,
            "writing": 2.5,
        }
        return default_durations.get(task_type, 1.5)

    def _fallback_prediction(
        self,
        task: Dict[str, Any],
        behavior_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        baseline_productivity = float(behavior_patterns.get("average_productivity", 60.0))
        priority = float(task.get("priority") or 3.0)
        duration = float(task.get("estimated_duration") or 1.0)
        adjusted_productivity = max(35.0, min(95.0, baseline_productivity + (priority * 2.5) - (duration * 3.0)))
        completion_probability = max(
            0.1,
            min(0.98, (adjusted_productivity / 100.0) * 0.75 + min(priority, 5.0) * 0.05),
        )
        completion_time_prediction = max(
            0.25,
            duration * float(behavior_patterns.get("average_completion_time", 1.0)),
        )

        return {
            **task,
            "prediction_hour": behavior_patterns.get("best_focus_hours", [10])[0],
            "predicted_productivity": round(adjusted_productivity, 2),
            "task_success_probability": round(completion_probability, 4),
            "completion_time_prediction": round(completion_time_prediction, 2),
        }

    def _record_prediction_statistics(self, predictions: List[Dict[str, Any]]) -> None:
        if not predictions:
            return

        productivity_scores = [
            float(item.get("predicted_productivity", 0.0))
            for item in predictions
        ]
        completion_probabilities = [
            float(
                item.get("completion_probability")
                or item.get("task_success_probability")
                or 0.0
            )
            for item in predictions
        ]
        estimated_durations = [
            float(
                item.get("estimated_duration")
                or item.get("completion_time_prediction")
                or 0.0
            )
            for item in predictions
        ]

        for score in productivity_scores:
            self._monitor().log_prediction("PredictionEngine", score)

        self._monitor().log_training_metrics(
            "PredictionEngine",
            {
                "prediction_count": len(predictions),
                "average_productivity_score": round(mean(productivity_scores), 2),
                "average_completion_probability": round(mean(completion_probabilities), 4),
                "average_estimated_duration": round(mean(estimated_durations), 2),
            },
        )

    def _monitor(self) -> AIMonitor:
        if self.ai_monitor is None:
            raise RuntimeError("Pipeline monitor is not initialized.")
        return self.ai_monitor
