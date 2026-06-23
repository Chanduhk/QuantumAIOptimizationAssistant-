from __future__ import annotations

import math
from datetime import datetime
from time import perf_counter
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.ai_rl import RLScheduler
from backend.app.cognitive import CognitiveEngine
from backend.app.context import ContextEngine
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine
from backend.app.engines.future_simulation_engine import FutureSimulationEngine
from backend.app.engines.goal_intelligence_engine import GoalIntelligenceEngine
from backend.app.engines.learning_engine import LearningEngine
from backend.app.engines.multi_objective_optimization_engine import MultiObjectiveOptimizationEngine
from backend.app.engines.optimization_engine import OptimizationEngine
from backend.app.engines.planning_engine import PlanningEngine
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.engines.strategic_planning_engine import StrategicPlanningEngine
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
        self.dependency_intelligence_engine = DependencyIntelligenceEngine()
        self.goal_intelligence_engine = GoalIntelligenceEngine(
            dependency_engine=self.dependency_intelligence_engine,
        )
        self.strategic_planning_engine = StrategicPlanningEngine(
            goal_intelligence_engine=self.goal_intelligence_engine,
            dependency_intelligence_engine=self.dependency_intelligence_engine,
        )
        self.future_simulation_engine = FutureSimulationEngine(
            goal_intelligence_engine=self.goal_intelligence_engine,
            dependency_intelligence_engine=self.dependency_intelligence_engine,
            strategic_planning_engine=self.strategic_planning_engine,
        )
        self.multi_objective_optimization_engine = MultiObjectiveOptimizationEngine()
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
        self._validate_user_id(user_id)
        self._validate_days_back(days_back)
        normalized_tasks = self._normalize_tasks(tasks)
        normalized_tasks = self._enrich_tasks_with_goals(normalized_tasks)
        normalized_tasks = self._enrich_tasks_with_dependencies(normalized_tasks)
        behavior_patterns = self._load_behavior_patterns(user_id=user_id, days_back=days_back)
        self._validate_behavior_patterns(behavior_patterns)
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
        self._validate_context_output(ai_context)
        self.ai_monitor.log_engine_execution("ContextEngine", self._duration_since(context_started))

        # Predict outcomes and create a recommended task order.
        prediction_started = perf_counter()
        predicted_tasks = self.prediction_engine.predict_batch(
            self.behavior_engine,
            normalized_tasks,
            behavior_patterns,
        )
        self._validate_task_list(predicted_tasks, "predicted_tasks")
        for task in predicted_tasks:
            self._finite_number(task.get("predicted_productivity"), field_name="predicted_productivity")
        self.ai_monitor.log_engine_execution("PredictionEngine", self._duration_since(prediction_started))
        for task in predicted_tasks:
            self.ai_monitor.log_prediction(
                "PredictionEngine",
                self._finite_number(task.get("predicted_productivity", 0.0), field_name="predicted_productivity"),
            )

        decision_started = perf_counter()
        prioritized_tasks = self.decision_engine.prioritize_tasks(
            normalized_tasks,
            predicted_tasks,
            behavior_patterns,
        )
        self._validate_task_list(prioritized_tasks, "recommended_task_order")
        self.ai_monitor.log_engine_execution("DecisionEngine", self._duration_since(decision_started))
        recommended_task_order = prioritized_tasks

        # Generate a plan draft before schedule-specific optimization begins.
        planning_started = perf_counter()
        daily_plan = self.planning_engine.generate_daily_plan(
            prioritized_tasks,
            behavior_patterns,
        )
        self._validate_daily_plan(daily_plan)
        self.ai_monitor.log_engine_execution("PlanningEngine", self._duration_since(planning_started))

        # Learn an execution slot plan and then refine it with deterministic optimization.
        rl_started = perf_counter()
        rl_result = self.rl_scheduler.optimize_schedule(
            prioritized_tasks,
            behavior_patterns,
            train_before_optimize=False,
        )
        self._validate_rl_schedule_result(rl_result)
        self.ai_monitor.log_engine_execution("RLScheduler", self._duration_since(rl_started))

        optimizer_input = self._prepare_optimizer_input(rl_result["optimized_schedule"])
        optimization_started = perf_counter()
        optimization_result = self.optimization_engine.optimize_schedule(
            optimizer_input,
            behavior_patterns,
        )
        self._validate_optimization_result(optimization_result)
        self.ai_monitor.log_engine_execution(
            "OptimizationEngine",
            self._duration_since(optimization_started),
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
            self._validate_learning_update(learning_update)
            self.ai_monitor.log_engine_execution("LearningEngine", self._duration_since(learning_started))
            self.ai_monitor.log_training_metrics("LearningEngine", learning_update)

        system_metrics = self.ai_monitor.report_system_metrics()
        self._validate_monitor_metrics(system_metrics)

        result = {
            "context": ai_context,
            "predicted_tasks": predicted_tasks,
            "recommended_task_order": recommended_task_order,
            "daily_plan": daily_plan,
            "rl_schedule": rl_result["optimized_schedule"],
            "optimized_schedule": optimization_result["optimized_schedule"],
            "memory_event": memory_event,
            "learning_update": learning_update,
            "system_metrics": system_metrics,
        }
        strategic_plan_summary = self._strategic_plan_summary()
        if strategic_plan_summary is not None:
            result["strategic_plan_summary"] = strategic_plan_summary
        future_projection_summary = self._future_projection_summary()
        if future_projection_summary is not None:
            result["future_projection_summary"] = future_projection_summary
        optimization_projection = self._multi_objective_optimization_summary()
        if optimization_projection is not None:
            result.update(optimization_projection)
        return result

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
        self._validate_user_id(user_id)
        self._validate_days_back(days_back)
        result = self.learning_engine.update_model(
            self.behavior_engine,
            self.rl_scheduler,
            user_id=user_id,
            days_back=days_back or self.days_back,
        )
        self._validate_learning_update(result)
        return result

    def store_memory(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Store an orchestration event in semantic memory."""
        if not isinstance(event, dict):
            raise ValueError("memory event must be a dictionary.")
        event_description = str(event.get("task_description") or event.get("summary") or "AI orchestration event")
        metadata = dict(event.get("metadata", {}))
        metadata.setdefault("event_type", event.get("event_type", "orchestration"))
        result = self.memory_system.store_memory(event_description, metadata)
        if not isinstance(result, dict):
            raise ValueError("memory system must return a dictionary.")
        return result

    def search_memory(
        self,
        query: str,
        *,
        user_id: Optional[int] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Search semantic memory, optionally filtering to one user."""
        results = self.memory_system.search_similar_tasks(query, limit=limit)
        if not isinstance(results, list):
            raise ValueError("memory search results must be a list.")
        if user_id is not None:
            self._validate_user_id(user_id)
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
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a non-empty list of dictionaries.")
        if not tasks:
            raise ValueError("At least one task is required.")

        normalized_tasks: List[Dict[str, Any]] = []
        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            raw_title = task.get("title")
            if not isinstance(raw_title, str):
                raise ValueError("Each task requires a title.")
            title = raw_title.strip()
            raw_task_type = task.get("task_type", task.get("type", "general"))
            if not isinstance(raw_task_type, str):
                raise ValueError("task_type must be a string.")
            task_type = raw_task_type.strip().lower() or "general"
            if not title:
                raise ValueError("Each task requires a title.")

            estimated_duration = task.get("estimated_duration", task.get("duration", 1.0))
            duration = self._positive_finite_number(estimated_duration, field_name="duration")
            priority = self._positive_integer(task.get("priority", 1), field_name="priority")
            normalized_tasks.append(
                {
                    "id": f"input-{index}",
                    "original_task_id": task.get("id"),
                    "goal_id": task.get("goal_id"),
                    "depends_on_task_ids": task.get("depends_on_task_ids", task.get("dependencies", [])),
                    "user_id": None,
                    "title": title,
                    "task_type": task_type,
                    "priority": priority,
                    "estimated_duration": duration,
                    "actual_duration": None,
                    "start_time": None,
                    "end_time": None,
                    "completed": False,
                    "source": "transient_request",
                    "original_payload": dict(task),
                }
            )

        id_map = {
            str(task["original_task_id"]): task["id"]
            for task in normalized_tasks
            if task.get("original_task_id") is not None
        }
        for task in normalized_tasks:
            dependencies = task.get("depends_on_task_ids")
            if isinstance(dependencies, list):
                task["depends_on_task_ids"] = [
                    id_map.get(str(dependency), dependency)
                    for dependency in dependencies
                ]
            elif isinstance(dependencies, str):
                task["depends_on_task_ids"] = [id_map.get(dependencies, dependencies)]

        return normalized_tasks

    def _enrich_tasks_with_goals(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        goal_engine = getattr(self, "goal_intelligence_engine", None)
        goal_graph = getattr(goal_engine, "goal_graph", None)
        goals = getattr(goal_graph, "goals", None)
        if goal_engine is None or not goals:
            return tasks
        enrich = getattr(goal_engine, "enrich_tasks_with_goal_alignment", None)
        if not callable(enrich):
            raise ValueError("goal_intelligence_engine must provide enrich_tasks_with_goal_alignment.")
        enriched_tasks = enrich(tasks)
        self._validate_task_list(enriched_tasks, "goal enriched tasks")
        return enriched_tasks

    def _enrich_tasks_with_dependencies(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        dependency_engine = getattr(self, "dependency_intelligence_engine", None)
        dependency_graph = getattr(dependency_engine, "dependency_graph", None)
        graph_has_edges = bool(getattr(dependency_graph, "dependencies", None))
        task_has_dependencies = any(
            bool(task.get("depends_on_task_ids") or task.get("dependencies"))
            for task in tasks
            if isinstance(task, dict)
        )
        if dependency_engine is None or not (graph_has_edges or task_has_dependencies):
            return tasks
        enrich = getattr(dependency_engine, "enrich_tasks_with_dependencies", None)
        if not callable(enrich):
            raise ValueError("dependency_intelligence_engine must provide enrich_tasks_with_dependencies.")
        enriched_tasks = enrich(tasks)
        self._validate_task_list(enriched_tasks, "dependency enriched tasks")
        return enriched_tasks

    def _strategic_plan_summary(self) -> Optional[Dict[str, Any]]:
        strategic_engine = getattr(self, "strategic_planning_engine", None)
        summarize = getattr(strategic_engine, "summarize_active_plans", None)
        if not callable(summarize):
            return None
        summary = summarize()
        if summary is None:
            return None
        if not isinstance(summary, dict):
            raise ValueError("strategic_plan_summary must be a dictionary.")
        self._validate_numeric_payload(summary, field_name="strategic_plan_summary")
        return summary

    def _future_projection_summary(self) -> Optional[Dict[str, Any]]:
        simulation_engine = getattr(self, "future_simulation_engine", None)
        summarize = getattr(simulation_engine, "summarize_future_projection", None)
        if not callable(summarize):
            return None
        summary = summarize()
        if summary is None:
            return None
        if not isinstance(summary, dict):
            raise ValueError("future_projection_summary must be a dictionary.")
        self._validate_numeric_payload(summary, field_name="future_projection_summary")
        return summary

    def _multi_objective_optimization_summary(self) -> Optional[Dict[str, Any]]:
        optimization_engine = getattr(self, "multi_objective_optimization_engine", None)
        summarize = getattr(optimization_engine, "summarize_latest_optimization", None)
        if not callable(summarize):
            return None
        summary = summarize()
        if summary is None:
            return None
        if not isinstance(summary, dict):
            raise ValueError("multi_objective optimization summary must be a dictionary.")
        if "selected_future" not in summary or "optimization_summary" not in summary:
            raise ValueError("multi_objective optimization summary missing required fields.")
        self._validate_numeric_payload(summary, field_name="multi_objective_optimization")
        return summary

    def _load_behavior_patterns(self, *, user_id: int, days_back: Optional[int]) -> Dict[str, Any]:
        task_history = self.behavior_engine.collect_behavior_data(
            user_id=user_id,
            days_back=days_back or self.days_back,
        )
        if task_history is None or not hasattr(task_history, "empty"):
            raise ValueError("Behavior engine must return a DataFrame-like task history.")
        if task_history.empty:
            raise ValueError("No completed tasks found for the user.")

        self.behavior_engine.extract_features()
        patterns = self.behavior_engine.get_user_patterns()
        self._validate_behavior_patterns(patterns)
        return patterns

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
        self._validate_graph_id(user_node, "user node")
        transient_goal_id = self.knowledge_graph.add_goal(
            user_id,
            "Transient orchestration goal",
        )
        self._validate_graph_id(transient_goal_id, "goal node")
        for task in tasks:
            task_id = self.knowledge_graph.add_task(transient_goal_id, task)
            self._validate_graph_id(task_id, "task node")
            preferred_hour = self._resolve_preferred_hour(task)
            time_id = self.knowledge_graph.link_task_time(task_id, preferred_hour)
            self._validate_graph_id(time_id, "time node")

    def _prepare_optimizer_input(self, rl_schedule: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(rl_schedule, list):
            raise ValueError("RL optimized_schedule must be a list.")
        optimizer_input: List[Dict[str, Any]] = []
        for task in rl_schedule:
            if not isinstance(task, dict):
                raise ValueError("Each RL schedule entry must be a dictionary.")
            adapted_task = dict(task)
            adapted_task["scheduled_hour"] = self._resolve_hour(
                task.get("rl_scheduled_hour", 10),
                field_name="rl_scheduled_hour",
            )
            adapted_task["schedule_score"] = self._finite_number(
                task.get("rl_reward_estimate", 0.0),
                field_name="rl_reward_estimate",
            )
            if adapted_task.get("estimated_duration") is not None:
                self._positive_finite_number(adapted_task["estimated_duration"], field_name="duration")
            if adapted_task.get("actual_duration") is not None:
                self._positive_finite_number(adapted_task["actual_duration"], field_name="duration")
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

    def _validate_user_id(self, user_id: int) -> None:
        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            raise ValueError("user_id must be a positive integer.")

    def _validate_days_back(self, days_back: Optional[int]) -> None:
        if days_back is None:
            return
        if not isinstance(days_back, int) or isinstance(days_back, bool) or days_back <= 0:
            raise ValueError("days_back must be a positive integer.")

    def _validate_behavior_patterns(self, behavior_patterns: Dict[str, Any]) -> None:
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        self._validate_numeric_payload(behavior_patterns, field_name="behavior_patterns")

    def _validate_context_output(self, context: Any) -> None:
        if not isinstance(context, dict):
            raise ValueError("ContextEngine must return a dictionary.")

    def _validate_task_list(self, tasks: Any, field_name: str) -> None:
        if not isinstance(tasks, list):
            raise ValueError(f"{field_name} must be a list.")
        if any(not isinstance(task, dict) for task in tasks):
            raise ValueError(f"{field_name} entries must be dictionaries.")
        self._validate_numeric_payload(tasks, field_name=field_name)

    def _validate_daily_plan(self, daily_plan: Any) -> None:
        if not isinstance(daily_plan, dict):
            raise ValueError("daily_plan must be a dictionary.")
        if "tasks" in daily_plan and not isinstance(daily_plan["tasks"], list):
            raise ValueError("daily_plan tasks must be a list.")
        self._validate_numeric_payload(daily_plan, field_name="daily_plan")

    def _validate_rl_schedule_result(self, rl_result: Any) -> None:
        if not isinstance(rl_result, dict):
            raise ValueError("RL scheduler must return a dictionary.")
        if "optimized_schedule" not in rl_result:
            raise ValueError("RL scheduler result missing optimized_schedule.")
        self._validate_task_list(rl_result["optimized_schedule"], "rl optimized_schedule")

    def _validate_optimization_result(self, optimization_result: Any) -> None:
        if not isinstance(optimization_result, dict):
            raise ValueError("OptimizationEngine must return a dictionary.")
        if "optimized_schedule" not in optimization_result:
            raise ValueError("OptimizationEngine result missing optimized_schedule.")
        self._validate_task_list(optimization_result["optimized_schedule"], "optimized_schedule")
        if "projected_productivity_gain" in optimization_result:
            self._finite_number(
                optimization_result["projected_productivity_gain"],
                field_name="projected_productivity_gain",
            )

    def _validate_learning_update(self, learning_update: Any) -> None:
        if not isinstance(learning_update, dict):
            raise ValueError("learning_update must be a dictionary.")
        for key in ("drift", "retraining", "rl_policy_update"):
            if key not in learning_update:
                raise ValueError(f"learning_update missing {key}.")
        self._validate_numeric_payload(learning_update, field_name="learning_update")

    def _validate_monitor_metrics(self, metrics: Any) -> None:
        if not isinstance(metrics, dict):
            raise ValueError("system_metrics must be a dictionary.")
        self._validate_numeric_payload(metrics, field_name="system_metrics")

    def _validate_graph_id(self, value: Any, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")

    def _resolve_preferred_hour(self, task: Dict[str, Any]) -> int:
        if task.get("hour_of_day") is not None:
            return self._resolve_hour(task["hour_of_day"], field_name="hour_of_day")
        focus_hours = getattr(self.behavior_engine, "user_patterns", {}).get("best_focus_hours", [10])
        if not isinstance(focus_hours, list) or not focus_hours:
            return 10
        return self._resolve_hour(focus_hours[0], field_name="best_focus_hours")

    def _resolve_hour(self, value: Any, *, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer hour from 0 to 23.")
        if isinstance(value, int):
            hour = value
        elif isinstance(value, str) and value.strip().isdigit():
            hour = int(value.strip())
        else:
            raise ValueError(f"{field_name} must be an integer hour from 0 to 23.")
        if not 0 <= hour <= 23:
            raise ValueError(f"{field_name} must be an integer hour from 0 to 23.")
        return hour

    def _positive_integer(self, value: Any, *, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a positive integer.") from None
        if not math.isfinite(number) or not number.is_integer() or number <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
        return int(number)

    def _positive_finite_number(self, value: Any, *, field_name: str) -> float:
        number = self._finite_number(value, field_name=field_name)
        if number <= 0:
            raise ValueError(f"{field_name} must be positive.")
        return number

    def _finite_number(self, value: Any, *, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return number

    def _duration_since(self, started_at: float) -> float:
        return self._finite_number(perf_counter() - started_at, field_name="engine_duration")

    def _validate_numeric_payload(self, payload: Any, *, field_name: str) -> None:
        if isinstance(payload, dict):
            for value in payload.values():
                self._validate_numeric_payload(value, field_name=field_name)
            return
        if isinstance(payload, list):
            for value in payload:
                self._validate_numeric_payload(value, field_name=field_name)
            return
        if isinstance(payload, bool) or payload is None or isinstance(payload, str):
            return
        if isinstance(payload, (int, float)):
            self._finite_number(payload, field_name=field_name)
