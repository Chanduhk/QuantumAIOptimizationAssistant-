from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.ai_rl import RLScheduler
from backend.app.context import ContextEngine
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.engines.learning_engine import LearningEngine
from backend.app.engines.optimization_engine import OptimizationEngine
from backend.app.engines.planning_engine import PlanningEngine
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.engines.scheduling_engine import SchedulingEngine
from backend.app.memory import VectorMemorySystem
from backend.app.models.task import Task
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine


class QuantumLifeBrain:
    """Autonomous multi-engine AI assistant architecture for Quantum Life AI."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.behavior_engine = BehaviorIntelligenceEngine(session=session)
        self.planning_engine = PlanningEngine()
        self.scheduling_engine = SchedulingEngine()
        self.decision_engine = DecisionEngine()
        self.optimization_engine = OptimizationEngine()
        self.prediction_engine = PredictionEngine()
        self.learning_engine = LearningEngine()
        self.rl_scheduler = RLScheduler()
        self.memory_system = VectorMemorySystem()
        self.context_engine = ContextEngine(memory_system=self.memory_system)

    def load_user_context(self, user_id: int, days_back: int = 90) -> Dict[str, Any]:
        tasks = self.behavior_engine.collect_behavior_data(user_id=user_id, days_back=days_back)
        if tasks.empty:
            raise ValueError("No completed tasks found for the user.")

        self.behavior_engine.extract_features()
        patterns = self.behavior_engine.get_user_patterns()
        return patterns

    def get_active_tasks(self, user_id: int, task_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        query = self.session.query(Task).filter(Task.user_id == user_id)
        if task_ids:
            query = query.filter(Task.id.in_(task_ids))
        else:
            query = query.filter(Task.completed.is_(False))

        tasks = query.order_by(Task.priority.desc(), Task.id.asc()).all()
        return [self._serialize_task(task) for task in tasks]

    def generate_daily_plan(
        self,
        user_id: int,
        days_back: int = 90,
        task_ids: Optional[List[int]] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        pipeline_output = self.plan_day(
            user_id=user_id,
            days_back=days_back,
            task_ids=task_ids,
            query=query,
        )
        plan = self.planning_engine.generate_daily_plan(
            pipeline_output["rl_schedule"]["optimized_schedule"],
            pipeline_output["behavior_patterns"],
        )

        return {
            "context": pipeline_output["context"],
            "behavior_patterns": pipeline_output["behavior_patterns"],
            "predicted_tasks": pipeline_output["predicted_tasks"],
            "prioritized_tasks": pipeline_output["prioritized_tasks"],
            "optimized_schedule": pipeline_output["rl_schedule"]["optimized_schedule"],
            "projected_productivity_gain": pipeline_output["optimization"]["projected_productivity_gain"],
            "plan": plan,
        }

    def optimize_schedule(
        self,
        user_id: int,
        days_back: int = 90,
        task_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        pipeline_output = self.plan_day(user_id=user_id, days_back=days_back, task_ids=task_ids)

        return {
            "context": pipeline_output["context"],
            "behavior_patterns": pipeline_output["behavior_patterns"],
            "scheduled_tasks": pipeline_output["scheduled_tasks"],
            "optimized_schedule": pipeline_output["rl_schedule"]["optimized_schedule"],
            "projected_productivity_gain": pipeline_output["optimization"]["projected_productivity_gain"],
            "rl_policy_states": pipeline_output["rl_schedule"]["policy_states"],
        }

    def prioritize_tasks(
        self,
        user_id: int,
        days_back: int = 90,
        task_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        behavior_patterns = self.load_user_context(user_id=user_id, days_back=days_back)
        tasks = self.get_active_tasks(user_id=user_id, task_ids=task_ids)
        if not tasks:
            raise ValueError("No active tasks found for the user.")

        predicted_tasks = self.prediction_engine.predict_batch(
            self.behavior_engine,
            tasks,
            behavior_patterns,
        )
        prioritized_tasks = self.decision_engine.prioritize_tasks(
            tasks,
            predicted_tasks,
            behavior_patterns,
        )

        return {
            "behavior_patterns": behavior_patterns,
            "predicted_tasks": predicted_tasks,
            "prioritized_tasks": prioritized_tasks,
        }

    def predict_productivity(
        self,
        user_id: int,
        task_type: str,
        duration: float,
        hour_of_day: Optional[int] = None,
        days_back: int = 90,
    ) -> Dict[str, Any]:
        behavior_patterns = self.load_user_context(user_id=user_id, days_back=days_back)
        task_payload = {
            "task_type": task_type,
            "estimated_duration": duration,
            "hour_of_day": hour_of_day,
        }
        predicted_task = self.prediction_engine.predict_productivity(
            self.behavior_engine,
            task_payload,
            behavior_patterns,
        )
        return {
            "behavior_patterns": behavior_patterns,
            "prediction": predicted_task,
        }

    def update_learning_model(self, user_id: int, days_back: int = 90) -> Dict[str, Any]:
        return self.learning_engine.update_model(
            self.behavior_engine,
            self.rl_scheduler,
            user_id=user_id,
            days_back=days_back,
        )

    def train_rl_scheduler(
        self,
        user_id: int,
        days_back: int = 90,
        task_ids: Optional[List[int]] = None,
        episodes: int = 25,
    ) -> Dict[str, Any]:
        behavior_patterns = self.load_user_context(user_id=user_id, days_back=days_back)
        tasks = self.get_active_tasks(user_id=user_id, task_ids=task_ids)
        if not tasks:
            raise ValueError("No active tasks found for the user.")

        predicted_tasks = self.prediction_engine.predict_batch(
            self.behavior_engine,
            tasks,
            behavior_patterns,
        )
        return self.rl_scheduler.train_agent(predicted_tasks, behavior_patterns, episodes=episodes)

    def store_memory(self, task_description: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        return self.memory_system.store_memory(task_description, metadata)

    def search_memory(self, query: str, limit: int = 5, *, user_id: int | None = None) -> Dict[str, Any]:
        return {
            "query": query,
            "results": self.memory_system.search_similar_tasks(query, limit=limit, user_id=user_id),
        }

    def get_ai_context(
        self,
        user_id: int,
        days_back: int = 90,
        task_ids: Optional[List[int]] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        behavior_patterns = self.load_user_context(user_id=user_id, days_back=days_back)
        tasks = self.get_active_tasks(user_id=user_id, task_ids=task_ids)
        return self.context_engine.build_context(
            user_id=user_id,
            behavior_patterns=behavior_patterns,
            current_tasks=tasks,
            query=query,
        )

    def plan_day(
        self,
        user_id: int,
        days_back: int = 90,
        task_ids: Optional[List[int]] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        tasks = self.get_active_tasks(user_id=user_id, task_ids=task_ids)
        if not tasks:
            raise ValueError("No active tasks found for the user.")

        behavior_patterns = self.load_user_context(user_id=user_id, days_back=days_back)
        ai_context = self.context_engine.build_context(
            user_id=user_id,
            behavior_patterns=behavior_patterns,
            current_tasks=tasks,
            query=query,
        )
        predicted_tasks = self.prediction_engine.predict_batch(
            self.behavior_engine,
            tasks,
            behavior_patterns,
        )
        prioritized_tasks = self.decision_engine.prioritize_tasks(
            tasks,
            predicted_tasks,
            behavior_patterns,
        )
        scheduled_tasks = self.scheduling_engine.optimize_schedule(prioritized_tasks, behavior_patterns)
        optimization_result = self.optimization_engine.optimize_schedule(
            scheduled_tasks,
            behavior_patterns,
        )
        rl_schedule = self.rl_scheduler.optimize_schedule(
            optimization_result["optimized_schedule"],
            behavior_patterns,
            train_before_optimize=False,
        )

        return {
            "context": ai_context,
            "behavior_patterns": behavior_patterns,
            "predicted_tasks": predicted_tasks,
            "prioritized_tasks": prioritized_tasks,
            "scheduled_tasks": scheduled_tasks,
            "optimization": optimization_result,
            "rl_schedule": rl_schedule,
        }

    def run_example_integration_workflow(
        self,
        user_id: int,
        days_back: int = 90,
        task_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Example orchestration flow for the seven-engine AI brain."""
        prioritized_output = self.prioritize_tasks(user_id=user_id, days_back=days_back, task_ids=task_ids)
        schedule_output = self.optimize_schedule(user_id=user_id, days_back=days_back, task_ids=task_ids)
        plan_output = self.generate_daily_plan(user_id=user_id, days_back=days_back, task_ids=task_ids)

        return {
            "workflow": [
                "Context Engine fuses behavior patterns, vector memory, active tasks, and time of day.",
                "Behavior Intelligence Engine extracts patterns from completed task history.",
                "Prediction Engine estimates productivity for active tasks.",
                "Decision Intelligence Engine ranks tasks by outcome quality and urgency.",
                "Scheduling Intelligence Engine assigns work into productive time windows.",
                "Optimization Engine improves slot assignment for higher output.",
                "RL Scheduler learns and selects high-value execution slots over time.",
                "Planning Intelligence Engine produces an actionable daily plan.",
                "Learning Engine refreshes the model, detects drift, and updates RL policy.",
            ],
            "prioritization": prioritized_output,
            "scheduling": schedule_output,
            "planning": plan_output,
        }

    def _serialize_task(self, task: Task) -> Dict[str, Any]:
        return {
            "id": task.id,
            "user_id": task.user_id,
            "title": task.title,
            "task_type": task.task_type,
            "priority": task.priority,
            "estimated_duration": task.estimated_duration,
            "estimated_duration_unit": task.estimated_duration_unit,
            "estimated_duration_source": task.estimated_duration_source,
            "actual_duration": task.actual_duration,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "end_time": task.end_time.isoformat() if task.end_time else None,
            "completed": task.completed,
        }
