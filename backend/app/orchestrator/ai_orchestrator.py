from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.ai_rl import RLScheduler
from backend.app.cognitive import CognitiveEngine
from backend.app.context import ContextEngine
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.engines.learning_engine import LearningEngine
from backend.app.engines.optimization_engine import OptimizationEngine
from backend.app.engines.planning_engine import PlanningEngine
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.knowledge import AIKnowledgeGraph
from backend.app.memory import VectorMemorySystem
from backend.app.ml import FeatureStore
from backend.app.monitoring import AIMonitor
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine


class AIOrchestrator:
    """Central request-driven orchestrator for Quantum Life AI."""

    def __init__(
        self,
        session: Session,
        *,
        days_back: int = 90,
        memory_storage_directory: Optional[str] = None,
        rl_policy_path: Optional[str] = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.memory_storage_directory = memory_storage_directory
        self.rl_policy_path = rl_policy_path
        self.initialize_engines()

    def initialize_engines(self) -> None:
        """Instantiate all engines used by the central orchestration pipeline."""
        self.behavior_engine = BehaviorIntelligenceEngine(session=self.session)
        self.prediction_engine = PredictionEngine()
        self.decision_engine = DecisionEngine()
        self.planning_engine = PlanningEngine()
        self.optimization_engine = OptimizationEngine()
        self.learning_engine = LearningEngine()
        self.memory_system = VectorMemorySystem(storage_directory=self.memory_storage_directory)
        self.context_engine = ContextEngine(memory_system=self.memory_system)
        self.rl_scheduler = RLScheduler(policy_path=self.rl_policy_path)
        self.feature_store = FeatureStore()
        self.ai_monitor = AIMonitor()
        self.knowledge_graph = AIKnowledgeGraph()
        self.cognitive_engine = CognitiveEngine(
            behavior_engine=self.behavior_engine,
            knowledge_graph=self.knowledge_graph,
        )

    def process_tasks(
        self,
        tasks: List[Dict[str, Any]],
        user_id: int,
        *,
        query: Optional[str] = None,
        update_learning: bool = False,
        days_back: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the full AI decision pipeline for transient task input."""
        normalized_tasks = self._normalize_tasks(tasks)
        behavior_patterns = self._load_behavior_patterns(user_id=user_id, days_back=days_back)
        self._cache_features(user_id=user_id, behavior_patterns=behavior_patterns)
        self._seed_knowledge_graph(user_id=user_id, tasks=normalized_tasks)

        # Build the runtime context from memory, current tasks, and user history.
        context_started = perf_counter()
        ai_context = self.context_engine.build_context(
            user_id=user_id,
            behavior_patterns=behavior_patterns,
            current_tasks=normalized_tasks,
            query=query or self._default_query(normalized_tasks),
        )
        self.ai_monitor.log_engine_execution("ContextEngine", perf_counter() - context_started)

        # Predict outcomes and create a recommended task order.
        prediction_started = perf_counter()
        predicted_tasks = self.prediction_engine.predict_batch(
            self.behavior_engine,
            normalized_tasks,
            behavior_patterns,
        )
        self.ai_monitor.log_engine_execution("PredictionEngine", perf_counter() - prediction_started)
        for task in predicted_tasks:
            self.ai_monitor.log_prediction(
                "PredictionEngine",
                float(task.get("predicted_productivity", 0.0)),
            )

        decision_started = perf_counter()
        prioritized_tasks = self.decision_engine.prioritize_tasks(
            normalized_tasks,
            predicted_tasks,
            behavior_patterns,
        )
        self.ai_monitor.log_engine_execution("DecisionEngine", perf_counter() - decision_started)
        recommended_task_order = prioritized_tasks

        # Generate a plan draft before schedule-specific optimization begins.
        planning_started = perf_counter()
        daily_plan = self.planning_engine.generate_daily_plan(
            prioritized_tasks,
            behavior_patterns,
        )
        self.ai_monitor.log_engine_execution("PlanningEngine", perf_counter() - planning_started)

        # Learn an execution slot plan and then refine it with deterministic optimization.
        rl_started = perf_counter()
        rl_result = self.rl_scheduler.optimize_schedule(
            prioritized_tasks,
            behavior_patterns,
            train_before_optimize=False,
        )
        self.ai_monitor.log_engine_execution("RLScheduler", perf_counter() - rl_started)

        optimizer_input = self._prepare_optimizer_input(rl_result["optimized_schedule"])
        optimization_started = perf_counter()
        optimization_result = self.optimization_engine.optimize_schedule(
            optimizer_input,
            behavior_patterns,
        )
        self.ai_monitor.log_engine_execution(
            "OptimizationEngine",
            perf_counter() - optimization_started,
        )

        memory_event_payload = self._build_memory_event(
            user_id=user_id,
            predicted_tasks=predicted_tasks,
            prioritized_tasks=prioritized_tasks,
            optimized_schedule=optimization_result["optimized_schedule"],
        )
        memory_event = self.store_memory(memory_event_payload)
        self.ai_monitor.log_event("ORCHESTRATION_MEMORY_STORED")

        learning_update = None
        if update_learning:
            learning_started = perf_counter()
            learning_update = self.update_learning_models(user_id=user_id, days_back=days_back)
            self.ai_monitor.log_engine_execution("LearningEngine", perf_counter() - learning_started)
            self.ai_monitor.log_training_metrics("LearningEngine", learning_update)

        return {
            "context": ai_context,
            "predicted_tasks": predicted_tasks,
            "recommended_task_order": recommended_task_order,
            "daily_plan": daily_plan,
            "rl_schedule": rl_result["optimized_schedule"],
            "optimized_schedule": optimization_result["optimized_schedule"],
            "memory_event": memory_event,
            "learning_update": learning_update,
            "system_metrics": self.ai_monitor.report_system_metrics(),
        }

    def generate_daily_plan(
        self,
        tasks: List[Dict[str, Any]],
        user_id: int,
        *,
        query: Optional[str] = None,
        days_back: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return the planning-focused view of the orchestration pipeline."""
        result = self.process_tasks(
            tasks,
            user_id,
            query=query,
            update_learning=False,
            days_back=days_back,
        )
        return {
            "context": result["context"],
            "predicted_tasks": result["predicted_tasks"],
            "recommended_task_order": result["recommended_task_order"],
            "daily_plan": result["daily_plan"],
        }

    def optimize_schedule(
        self,
        tasks: List[Dict[str, Any]],
        user_id: int,
        *,
        query: Optional[str] = None,
        days_back: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return the schedule-focused view of the orchestration pipeline."""
        result = self.process_tasks(
            tasks,
            user_id,
            query=query,
            update_learning=False,
            days_back=days_back,
        )
        return {
            "context": result["context"],
            "predicted_tasks": result["predicted_tasks"],
            "recommended_task_order": result["recommended_task_order"],
            "rl_schedule": result["rl_schedule"],
            "optimized_schedule": result["optimized_schedule"],
        }

    def update_learning_models(
        self,
        *,
        user_id: int,
        days_back: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Refresh productivity and RL models using persisted user history."""
        return self.learning_engine.update_model(
            self.behavior_engine,
            self.rl_scheduler,
            user_id=user_id,
            days_back=days_back or self.days_back,
        )

    def store_memory(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Store an orchestration event in semantic memory."""
        event_description = str(event.get("task_description") or event.get("summary") or "AI orchestration event")
        metadata = dict(event.get("metadata", {}))
        metadata.setdefault("event_type", event.get("event_type", "orchestration"))
        return self.memory_system.store_memory(event_description, metadata)

    def search_memory(
        self,
        query: str,
        *,
        user_id: Optional[int] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Search semantic memory, optionally filtering to one user."""
        results = self.memory_system.search_similar_tasks(query, limit=limit)
        if user_id is not None:
            results = [
                record
                for record in results
                if record.get("metadata", {}).get("user_id") == user_id
            ]
        return {
            "query": query,
            "results": results[:limit],
        }

    def _normalize_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tasks:
            raise ValueError("At least one task is required.")

        normalized_tasks: List[Dict[str, Any]] = []
        for index, task in enumerate(tasks, start=1):
            title = str(task.get("title") or "").strip()
            task_type = str(task.get("task_type") or task.get("type") or "general").strip().lower()
            if not title:
                raise ValueError("Each task requires a title.")

            estimated_duration = task.get("estimated_duration", task.get("duration", 1.0))
            normalized_tasks.append(
                {
                    "id": f"input-{index}",
                    "user_id": None,
                    "title": title,
                    "task_type": task_type,
                    "priority": int(task.get("priority") or 1),
                    "estimated_duration": float(estimated_duration),
                    "actual_duration": None,
                    "start_time": None,
                    "end_time": None,
                    "completed": False,
                    "source": "transient_request",
                    "original_payload": dict(task),
                }
            )

        return normalized_tasks

    def _load_behavior_patterns(self, *, user_id: int, days_back: Optional[int]) -> Dict[str, Any]:
        task_history = self.behavior_engine.collect_behavior_data(
            user_id=user_id,
            days_back=days_back or self.days_back,
        )
        if task_history.empty:
            raise ValueError("No completed tasks found for the user.")

        self.behavior_engine.extract_features()
        return self.behavior_engine.get_user_patterns()

    def _cache_features(self, *, user_id: int, behavior_patterns: Dict[str, Any]) -> None:
        self.feature_store.store_features(
            user_id,
            {
                "user_focus_hours": behavior_patterns.get("best_focus_hours", []),
                "average_task_duration": behavior_patterns.get("average_duration_by_task_type", {}),
                "energy_curve": behavior_patterns.get("average_energy_level"),
                "task_completion_rate": behavior_patterns.get("average_completion_time"),
                "productivity_trends": behavior_patterns.get("hourly_productivity", {}),
            },
        )

    def _seed_knowledge_graph(self, *, user_id: int, tasks: List[Dict[str, Any]]) -> None:
        user_node = self.knowledge_graph.add_user(user_id)
        transient_goal_id = self.knowledge_graph.add_goal(
            user_id,
            "Transient orchestration goal",
        )
        for task in tasks:
            task_id = self.knowledge_graph.add_task(transient_goal_id, task)
            preferred_hour = int(
                task.get("hour_of_day")
                or getattr(self.behavior_engine, "user_patterns", {}).get("best_focus_hours", [10])[0]
            )
            self.knowledge_graph.link_task_time(task_id, preferred_hour)

    def _prepare_optimizer_input(self, rl_schedule: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        optimizer_input: List[Dict[str, Any]] = []
        for task in rl_schedule:
            adapted_task = dict(task)
            adapted_task["scheduled_hour"] = int(task.get("rl_scheduled_hour", 10))
            adapted_task["schedule_score"] = float(task.get("rl_reward_estimate", 0.0))
            optimizer_input.append(adapted_task)
        return optimizer_input

    def _build_memory_event(
        self,
        *,
        user_id: int,
        predicted_tasks: List[Dict[str, Any]],
        prioritized_tasks: List[Dict[str, Any]],
        optimized_schedule: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        top_titles = [task["title"] for task in prioritized_tasks[:3]]
        productivity_summary = [
            {
                "task_id": task.get("id"),
                "title": task.get("title"),
                "predicted_productivity": task.get("predicted_productivity"),
            }
            for task in predicted_tasks[:5]
        ]
        return {
            "event_type": "orchestration",
            "task_description": f"Optimized plan for user {user_id}: {', '.join(top_titles)}",
            "summary": "Central AI orchestrator generated a transient optimized task plan.",
            "metadata": {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "top_recommended_tasks": top_titles,
                "optimized_schedule_snapshot": optimized_schedule[:5],
                "predicted_productivity_summary": productivity_summary,
            },
        }

    def _default_query(self, tasks: List[Dict[str, Any]]) -> Optional[str]:
        titles = [task["title"] for task in tasks if task.get("title")]
        return ", ".join(titles[:3]) if titles else None
