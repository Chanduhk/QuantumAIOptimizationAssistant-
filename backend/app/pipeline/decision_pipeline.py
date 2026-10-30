from __future__ import annotations

import logging
from datetime import datetime
from statistics import mean
from time import perf_counter
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.engine_registry import EngineRegistry
from backend.app.core.events import EventBus
from backend.app.domain.optimization_input_contract import normalize_duration
from backend.app.monitoring import AIMonitor


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
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.engine_registry = engine_registry
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
        """Initialize all engine references from the registry."""
        if self._initialized:
            return

        self.engine_registry = self.engine_registry or EngineRegistry(self.session)

        self.behavior_engine = self.engine_registry.get_behavior_engine()
        self.decision_engine = self.engine_registry.get_decision_engine()
        self.prediction_engine = self.engine_registry.get_prediction_engine()
        self.planning_engine = self.engine_registry.get_planning_engine()
        self.optimization_engine = self.engine_registry.get_optimization_engine()

        self.cognitive_engine = self.engine_registry.get_cognitive_engine()
        self.context_engine = self.engine_registry.get_context_engine()
        self.rl_scheduler = self.engine_registry.get_rl_scheduler()
        self.memory_system = self.engine_registry.get_memory_system()
        self.feature_store = self.engine_registry.get_feature_store()
        self.knowledge_graph = self.engine_registry.get_knowledge_graph()
        self.ai_monitor = self.engine_registry.get_ai_monitor()

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
            duration_hours = normalize_duration(
                task.get("estimated_duration"),
                task.get("estimated_duration_unit", "unknown"),
                task.get("estimated_duration_source"),
            ).normalized_hours
            prediction_task = {**task, "estimated_duration": duration_hours}
            try:
                prediction = self.prediction_engine.predict_productivity(
                    self.behavior_engine,
                    prediction_task,
                    behavior_patterns,
                )
            except Exception:
                self.logger.exception("Prediction fallback activated for task '%s'", task.get("title"))
                prediction = self._fallback_prediction(prediction_task, behavior_patterns)

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
            dur = task.get("estimated_duration")
            unit = task.get("estimated_duration_unit") or "minutes"
            src = task.get("estimated_duration_source") or "task_api"
            merged_tasks.append(
                {
                    **prediction,
                    **task,
                    "completion_probability": prediction.get("completion_probability", 0.0),
                    "estimated_duration": dur,
                    "estimated_duration_unit": unit,
                    "estimated_duration_source": src,
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
        task_map = {str(item.get("id")): item for item in tasks}
        for plan_task in plan.get("tasks", []):
            orig = task_map.get(str(plan_task.get("task_id") or plan_task.get("id")), {})
            plan_task["estimated_duration"] = orig.get("estimated_duration", plan_task.get("estimated_duration"))
            plan_task["estimated_duration_unit"] = orig.get("estimated_duration_unit") or "hours"
            plan_task["estimated_duration_source"] = orig.get("estimated_duration_source") or "decision_pipeline"
            plan_task["origin"] = orig.get("origin", "existing" if str(orig.get("id", "")).isdigit() else "proposed")
            plan_task["deadline"] = orig.get("deadline")
            plan_task["deadline_expression"] = orig.get("deadline_expression")
            plan_task["deadline_dt"] = orig.get("deadline_dt")
            plan_task["deadline_precision"] = orig.get("deadline_precision")
            plan_task["dependencies"] = orig.get("dependencies") or []
            plan_task["min_start_hour"] = orig.get("min_start_hour")
            plan_task["scheduling_preference"] = orig.get("scheduling_preference")
            if "priority" not in plan_task or plan_task.get("priority") is None:
                plan_task["priority"] = orig.get("priority", 3)
        self._latest_plan = plan
        self._monitor().log_engine_execution("PlanningEngine", perf_counter() - started)
        return plan

    async def optimize_schedule(
        self,
        plan: Dict[str, Any],
        available_hours: Optional[float] = None,
        day_start: int = 9,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run RL scheduling followed by deterministic, constraint-aware schedule optimization."""
        await self.initialize_pipeline()
        behavior_patterns = dict(self._latest_context.get("behavior_patterns", {}))
        constraints = constraints or {}

        rl_input = [
            {
                "id": item.get("task_id") or item.get("id"),
                "title": item.get("title"),
                "task_type": item.get("task_type"),
                "priority": item.get("priority", 3),
                "estimated_duration": item.get("estimated_duration"),
                "estimated_duration_unit": item.get("estimated_duration_unit") or "hours",
                "estimated_duration_source": item.get("estimated_duration_source") or "decision_pipeline",
                "predicted_productivity": item.get("predicted_productivity"),
                "scheduled_hour": item.get("recommended_hour"),
                "origin": item.get("origin"),
                "deadline": item.get("deadline"),
                "deadline_expression": item.get("deadline_expression"),
                "deadline_dt": item.get("deadline_dt"),
                "deadline_precision": item.get("deadline_precision"),
                "dependencies": item.get("dependencies") or [],
                "min_start_hour": item.get("min_start_hour"),
                "scheduling_preference": item.get("scheduling_preference"),
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
                "scheduled_hour": int(task.get("rl_scheduled_hour", task.get("scheduled_hour", day_start))),
                "schedule_score": float(task.get("rl_reward_estimate", 0.0)),
                "estimated_duration_unit": task.get("estimated_duration_unit") or "hours",
                "estimated_duration_source": task.get("estimated_duration_source") or "decision_pipeline",
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
        effective_horizon_end = (day_start + available_hours) if available_hours is not None else 18.0

        task_map: Dict[str, Dict[str, Any]] = {}
        for item in plan.get("tasks", []):
            if item.get("id"):
                task_map[str(item.get("id"))] = item
            if item.get("task_id"):
                task_map[str(item.get("task_id"))] = item
            if item.get("title"):
                task_map[str(item.get("title")).strip().lower()] = item

        tasks_pool = list(optimized_result["optimized_schedule"])

        # Determine task ordering with constraints & Multi-Criteria Decision Policy
        order_overrides = constraints.get("order_overrides") or []
        buffer_minutes = float(constraints.get("buffer_minutes") or 0.0)
        strategy = constraints.get("strategy", "deadline_first")

        # Precompute dependency counts: tasks that other tasks depend on should come first
        dependents_count: Dict[str, int] = {}
        for other_t in tasks_pool:
            o_id = str(other_t.get("id") or other_t.get("task_id") or "")
            o_orig = task_map.get(o_id) or task_map.get(str(other_t.get("title", "")).strip().lower()) or {}
            for dep in (o_orig.get("dependencies") or []):
                dep_key = str(dep).lower()
                dependents_count[dep_key] = dependents_count.get(dep_key, 0) + 1

        def get_sort_key(t: Dict[str, Any]) -> Tuple[int, int, float, float]:
            t_id = str(t.get("id") or t.get("task_id") or "")
            t_title = str(t.get("title", "")).strip().lower()
            orig = task_map.get(t_id) or task_map.get(t_title) or {}

            # 1. Explicit order overrides
            override_weight = 0
            for idx, (first_pat, second_pat) in enumerate(order_overrides):
                first_lower = str(first_pat).lower()
                second_lower = str(second_pat).lower()
                if first_lower in t_title or first_lower == t_id:
                    override_weight -= (1000 - idx * 50)
                elif second_lower in t_title or second_lower == t_id:
                    override_weight += (1000 - idx * 50)

            # 2. Dependency precedence: if other tasks depend on this task, schedule it earlier
            dep_boost = 0
            for dep_k, count in dependents_count.items():
                if dep_k in t_title or dep_k == t_id:
                    dep_boost -= (100 * count)

            # 3. Deadline for Earliest Deadline First (EDF)
            d_dt = orig.get("deadline_dt") or t.get("deadline_dt")
            if isinstance(d_dt, datetime):
                deadline_val = d_dt.timestamp()
            elif isinstance(d_dt, str) and d_dt:
                try:
                    deadline_val = datetime.fromisoformat(d_dt).timestamp()
                except Exception:
                    deadline_val = 9e11
            else:
                # Tasks without explicit deadlines sort after deadline-driven tasks
                deadline_val = 9e11

            # 4. Strategy tie-breaker (priority or shortest duration first)
            dur = float(orig.get("estimated_duration") or t.get("estimated_duration") or 1.0)
            prio = float(orig.get("priority") or t.get("priority") or 3.0)
            if strategy == "shortest_first":
                tie_val = dur - (prio * 0.1)
            else:
                tie_val = -prio

            return (override_weight, dep_boost, deadline_val, tie_val)

        sorted_tasks = sorted(tasks_pool, key=get_sort_key)

        current_time = float(day_start)
        optimized_schedule = []
        scheduled_tasks_by_ref: Dict[str, Dict[str, Any]] = {}

        for task in sorted_tasks:
            t_id = str(task.get("id") or task.get("task_id") or "")
            orig = task_map.get(t_id) or task_map.get(str(task.get("title", "")).strip().lower()) or {}
            prediction = prediction_by_id.get(t_id, {})

            duration_val = normalize_duration(
                task.get("estimated_duration") or orig.get("estimated_duration"),
                task.get("estimated_duration_unit") or orig.get("estimated_duration_unit", "hours"),
                task.get("estimated_duration_source") or orig.get("estimated_duration_source", "decision_pipeline"),
            ).normalized_hours

            # Calculate candidate start time
            scheduled_start = current_time

            # 1. Minimum start hour constraint (e.g. after lunch = 13.0)
            min_hour = orig.get("min_start_hour")
            if "min_start_hours" in constraints:
                for k, v in constraints["min_start_hours"].items():
                    if k.lower() in str(task.get("title", "")).lower() or k == t_id:
                        min_hour = max(min_hour or 0.0, float(v))
            if min_hour is not None:
                scheduled_start = max(scheduled_start, float(min_hour))

            # 2. Dependency constraints
            deps = orig.get("dependencies") or []
            for dep_item in deps:
                dep_lower = str(dep_item).lower()
                for prev_id, prev_task in scheduled_tasks_by_ref.items():
                    if dep_lower in prev_task.get("title", "").lower() or dep_lower == prev_id:
                        scheduled_start = max(scheduled_start, float(prev_task["scheduled_end_hour"]))

            # 3. Schedule end time
            scheduled_end = round(scheduled_start + duration_val, 2)
            fits_horizon = scheduled_end <= effective_horizon_end

            # 4. Deadline feasibility check
            deadline_feasible = True
            deadline_warning = None
            d_dt = orig.get("deadline_dt")
            if isinstance(d_dt, str) and d_dt:
                try:
                    d_dt_parsed = datetime.fromisoformat(d_dt)
                except Exception:
                    d_dt_parsed = None
            elif isinstance(d_dt, datetime):
                d_dt_parsed = d_dt
            else:
                d_dt_parsed = None

            if d_dt_parsed is not None:
                ref_today = datetime.utcnow().date()
                if d_dt_parsed.date() < ref_today:
                    deadline_feasible = False
                    deadline_warning = f"Deadline has already passed ({orig.get('deadline_expression')})."
                elif d_dt_parsed.date() == ref_today:
                    deadline_hour = d_dt_parsed.hour + (d_dt_parsed.minute / 60.0)
                    if scheduled_end > deadline_hour:
                        deadline_feasible = False
                        deadline_warning = f"Estimated finish at {scheduled_end:.2f} is past today's deadline at {deadline_hour:.2f} ({orig.get('deadline_expression')})."

            # 5. Explainable reasons for prioritization
            reasons = []
            if orig.get("deadline_expression"):
                reasons.append(f"Prioritized by Earliest Deadline First (EDF) due to deadline: {orig.get('deadline_expression')}.")
            if deps:
                reasons.append(f"Sequenced following prerequisite dependency: {', '.join(deps)}.")
            if int(orig.get("priority") or task.get("priority", 3)) >= 4:
                reasons.append(f"High priority ({orig.get('priority') or task.get('priority')}/5) protected in schedule.")
            if min_hour and min_hour >= 13.0:
                reasons.append("Scheduled in afternoon slot per user preference (after lunch).")
            if not reasons:
                reasons.append("Sequenced to optimize focus and preserve non-overlapping execution intervals.")

            item_data = {
                "id": str(task.get("id") or ""),
                "task_id": task.get("id"),
                "title": task.get("title"),
                "task_type": task.get("task_type"),
                "priority": orig.get("priority") or task.get("priority", 3),
                "origin": orig.get("origin", "existing" if str(task.get("id", "")).isdigit() else "proposed"),
                "scheduled_hour": scheduled_start,
                "scheduled_end_hour": scheduled_end,
                "estimated_duration": duration_val,
                "estimated_duration_unit": "hours",
                "estimated_duration_source": orig.get("estimated_duration_source") or task.get("estimated_duration_source", "decision_pipeline"),
                "duration_source": orig.get("estimated_duration_source") or task.get("estimated_duration_source", "decision_pipeline"),
                "deadline": orig.get("deadline"),
                "deadline_expression": orig.get("deadline_expression"),
                "deadline_dt": d_dt_parsed.isoformat() if d_dt_parsed else (orig.get("deadline_dt") if isinstance(orig.get("deadline_dt"), str) else None),
                "deadline_precision": orig.get("deadline_precision"),
                "deadline_feasible": deadline_feasible,
                "deadline_warning": deadline_warning,
                "dependencies": deps,
                "min_start_hour": min_hour,
                "scheduling_preference": orig.get("scheduling_preference"),
                "reason_for_order": reasons[0] if reasons else "Scheduled sequentially",
                "predicted_productivity": prediction.get(
                    "predicted_productivity",
                    task.get("predicted_productivity"),
                ),
                "completion_probability": prediction.get("completion_probability", 0.0),
                "decision_score": task.get("decision_score"),
                "rl_reward_estimate": task.get("rl_reward_estimate"),
                "hour_productivity_score": task.get("hour_productivity_score"),
                "fits_in_horizon": fits_horizon,
                "capacity_warning": None if fits_horizon else f"Task extends to hour {scheduled_end:.2f}, exceeding available horizon ending at hour {effective_horizon_end:.2f}.",
                "reasons_for_prioritization": reasons,
            }

            optimized_schedule.append(item_data)
            scheduled_tasks_by_ref[t_id] = item_data
            scheduled_tasks_by_ref[str(task.get("title", "")).lower()] = item_data

            # Advance time pointer
            current_time = scheduled_end
            if buffer_minutes > 0:
                current_time = round(current_time + (buffer_minutes / 60.0), 2)

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

    async def run_pipeline(
        self,
        goal_text: str,
        user_id: int,
        tasks: Optional[List[Dict[str, Any]]] = None,
        available_hours: Optional[float] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            if tasks is not None:
                structured_tasks = [
                    self._normalize_goal_task(task, index=index, user_id=user_id, goal_metadata={"goal": goal_text})
                    for index, task in enumerate(tasks, start=1)
                ]
                self._latest_goal_text = goal_text
                self._latest_tasks = structured_tasks
            else:
                structured_tasks = await self.process_goal(goal_text, user_id)

            duration_errors = self._goal_task_duration_errors(structured_tasks)
            if duration_errors:
                raise ValueError(
                    "A reliable plan cannot be generated because goal-derived tasks lack "
                    "an explicit positive estimated duration, supported unit (minutes or hours), "
                    "and duration source. Add estimates to the tasks before planning. "
                    f"Affected tasks: {', '.join(duration_errors)}."
                )
            current_tasks = structured_tasks

            context = await self.build_context(user_id)
            await self._emit_event(
                CONTEXT_READY,
                {
                    "user_id": user_id,
                    "task_count": len(current_tasks),
                    "has_behavior_patterns": bool(context.get("behavior_patterns")),
                },
            )

            predictions = await self.predict_task_performance(current_tasks, context)
            await self._emit_event(
                PREDICTIONS_READY,
                {
                    "user_id": user_id,
                    "prediction_count": len(predictions),
                },
            )

            prioritized_tasks = await self.prioritize_tasks(current_tasks, predictions)
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

            optimized_schedule = await self.optimize_schedule(
                plan,
                available_hours=available_hours,
                constraints=constraints,
            )
            await self._emit_event(
                SCHEDULE_OPTIMIZED,
                {
                    "user_id": user_id,
                    "scheduled_tasks": len(optimized_schedule),
                },
            )

            await self.store_results(user_id, optimized_schedule)

            total_duration = sum(
                float(item.get("estimated_duration") or 0.0)
                for item in optimized_schedule
            )
            avail_limit = float(available_hours) if available_hours is not None else 8.0
            infeasible = [item for item in optimized_schedule if not item.get("fits_in_horizon", True)]
            if total_duration > avail_limit:
                accumulated = 0.0
                for item in optimized_schedule:
                    accumulated += float(item.get("estimated_duration") or 0.0)
                    if accumulated > avail_limit and item.get("fits_in_horizon", True):
                        item["fits_in_horizon"] = False
                        item["capacity_warning"] = f"Total workload {accumulated:.1f}h exceeds available limit of {avail_limit:.1f}h."
                        if item not in infeasible:
                            infeasible.append(item)

            deadline_risks = [item for item in optimized_schedule if item.get("deadline_feasible") is False]

            if infeasible or total_duration > avail_limit:
                feasibility_status = "INFEASIBLE_OVERLOAD"
            elif deadline_risks:
                feasibility_status = "DEADLINE_RISK"
            else:
                feasibility_status = "FEASIBLE"

            # Explainable recommendations & trade-offs
            reasons_summary = []
            for item in optimized_schedule:
                if item.get("reasons_for_prioritization"):
                    reasons_summary.extend(item["reasons_for_prioritization"])
            reasons_summary = list(dict.fromkeys(reasons_summary))  # deduplicate preserving order

            trade_offs = []
            if infeasible:
                fitted_count = len(optimized_schedule) - len(infeasible)
                trade_offs.append(
                    f"Prioritized the first {fitted_count} tasks within the {avail_limit:.1f}h window; "
                    f"{len(infeasible)} remaining task(s) exceed available capacity today."
                )
            if constraints and constraints.get("order_overrides"):
                trade_offs.append(
                    f"Applied manual order constraint overrides: {constraints['order_overrides']}."
                )
            if not trade_offs:
                trade_offs.append(
                    "Prioritized tasks with earliest deadlines first, trading off flexible tasks to minimize deadline slippage risk."
                )

            alternative_actions = []
            if infeasible:
                alternative_actions.append(
                    f"Option A (Capacity Expansion): Increase available horizon from {avail_limit:.1f}h to {total_duration:.1f}h to execute all planned tasks today."
                )
                alternative_actions.append(
                    "Option B (Task Deferral): Accept currently fitted tasks today and defer remaining work to tomorrow's window."
                )
                alternative_actions.append(
                    "Option C (Scope Reduction): Reduce duration of lower-priority tasks to compress workload within the declared horizon."
                )
            if deadline_risks:
                alternative_actions.append(
                    "Option D (Deadline Resolution): Reschedule or reorder at-risk tasks ahead of non-urgent activities."
                )

            pipeline_latency = perf_counter() - pipeline_started
            self._monitor().log_engine_execution("DecisionPipeline", pipeline_latency)
            self._monitor().log_training_metrics(
                "DecisionPipeline",
                {
                    "pipeline_latency_seconds": round(pipeline_latency, 4),
                    "task_count": len(prioritized_tasks),
                    "scheduled_task_count": len(optimized_schedule),
                    "feasibility_status": feasibility_status,
                },
            )

            return {
                "tasks": prioritized_tasks,
                "schedule": optimized_schedule,
                "predictions": predictions,
                "feasibility_status": feasibility_status,
                "total_demanded_hours": round(total_duration, 2),
                "available_hours": available_hours or 8.0,
                "infeasible_tasks": infeasible,
                "unscheduled_tasks": infeasible,
                "deadline_risk_tasks": deadline_risks,
                "reasons_for_prioritization": reasons_summary,
                "trade_offs": trade_offs,
                "alternative_actions": alternative_actions,
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
        estimated_duration = task.get("estimated_duration")

        return {
            "id": str(task.get("id") or f"goal-task-{user_id}-{index}"),
            "user_id": user_id,
            "title": str(task.get("title") or f"Task {index}").strip(),
            "task_type": task_type,
            "type": task_type,
            "priority": int(task.get("priority") if task.get("priority") is not None else 3),
            "estimated_duration": estimated_duration,
            "estimated_duration_unit": task.get("estimated_duration_unit") or "hours",
            "estimated_duration_source": task.get("estimated_duration_source") or "conversational_input",
            "origin": task.get("origin", "existing" if str(task.get("id", "")).isdigit() else "proposed"),
            "deadline": task.get("deadline"),
            "deadline_expression": task.get("deadline_expression"),
            "deadline_dt": (
                task.get("deadline_dt").isoformat() 
                if isinstance(task.get("deadline_dt"), datetime) 
                else (str(task.get("deadline_dt")) if task.get("deadline_dt") else None)
            ),
            "deadline_precision": task.get("deadline_precision"),
            "dependencies": task.get("dependencies") or [],
            "min_start_hour": task.get("min_start_hour"),
            "scheduling_preference": task.get("scheduling_preference"),
            "duration_provenance_status": (
                "KNOWN_UNIT"
                if task.get("estimated_duration") is not None
                and task.get("estimated_duration_unit") in {"minutes", "hours"}
                and task.get("estimated_duration_source")
                else "UNKNOWN_UNIT"
            ),
            "goal": goal_metadata.get("goal"),
            "goal_type": goal_metadata.get("goal_type"),
            "time_horizon": goal_metadata.get("time_horizon"),
            "completed": bool(task.get("completed", False)),
            "source": task.get("source") or "decision_pipeline",
        }

    def _goal_task_duration_errors(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """Reject heuristic goal tasks until they carry a real sourced estimate."""
        errors: List[str] = []
        for index, task in enumerate(tasks, start=1):
            title = str(task.get("title") or f"Task {index}")
            try:
                normalize_duration(
                    task.get("estimated_duration"),
                    task.get("estimated_duration_unit", "unknown"),
                    task.get("estimated_duration_source"),
                )
            except (TypeError, ValueError):
                errors.append(title)
        return errors

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
