from __future__ import annotations

import logging
from datetime import datetime
from statistics import mean
from time import perf_counter
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.events import EventBus
from backend.app.pipeline import DecisionPipeline

TASK_STARTED = "TASK_STARTED"
TASK_DELAYED = "TASK_DELAYED"
PRODUCTIVITY_DROP = "PRODUCTIVITY_DROP"
SCHEDULE_UPDATED = "SCHEDULE_UPDATED"


class AdaptiveScheduler:
    """Real-time adaptive scheduling layer for dynamic plan adjustment."""

    def __init__(
        self,
        session: Session,
        *,
        days_back: int = 90,
        decision_pipeline: Optional[DecisionPipeline] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.event_bus = event_bus or EventBus()
        self.decision_pipeline = decision_pipeline
        self.logger = logging.getLogger(__name__)

        self._initialized = False
        self._active_user_id: Optional[int] = None
        self._active_schedule: List[Dict[str, Any]] = []

    async def initialize_scheduler(self) -> None:
        """Initialize shared engine references used by adaptive scheduling."""
        if self._initialized:
            return

        self.decision_pipeline = self.decision_pipeline or DecisionPipeline(
            session=self.session,
            days_back=self.days_back,
            event_bus=self.event_bus,
        )
        await self.decision_pipeline.initialize_pipeline()

        self.prediction_engine = self.decision_pipeline.prediction_engine
        self.behavior_engine = self.decision_pipeline.behavior_engine
        self.rl_scheduler = self.decision_pipeline.rl_scheduler
        self.optimization_engine = self.decision_pipeline.optimization_engine
        self.ai_monitor = self.decision_pipeline.ai_monitor
        self.memory_system = self.decision_pipeline.memory_system

        self._initialized = True

    async def monitor_execution(self, user_id: int) -> Dict[str, Any]:
        """Perform one execution-monitoring cycle for the active schedule."""
        await self.initialize_scheduler()
        started = perf_counter()

        if not self._active_schedule:
            raise ValueError("No active schedule loaded for monitoring.")

        current_dt = datetime.utcnow()
        current_time = self._to_decimal_hour(current_dt)
        current_task = self._find_current_task(self._active_schedule, current_time)
        interruptions = [
            task
            for task in self._active_schedule
            if self._has_interruption(task)
        ]

        monitor_payload = {
            "user_id": user_id,
            "current_time": current_time,
            "current_task": current_task,
            "elapsed_time": self._calculate_elapsed_time(current_task, current_dt),
            "task_completion_status": [
                {
                    "task_id": task.get("task_id"),
                    "title": task.get("title"),
                    "completed": bool(task.get("completed", False)),
                    "status": self._task_status(task, current_time),
                    "progress": float(task.get("progress", 0.0) or 0.0),
                }
                for task in self._active_schedule
            ],
            "interruptions": interruptions,
        }

        if current_task is not None:
            await self._emit_event(
                TASK_STARTED,
                {
                    "user_id": user_id,
                    "task_id": current_task.get("task_id"),
                    "title": current_task.get("title"),
                    "scheduled_hour": current_task.get("scheduled_hour"),
                },
            )

        self._monitor().log_engine_execution("AdaptiveScheduler:Monitor", perf_counter() - started)
        return monitor_payload

    async def detect_schedule_deviation(
        self,
        schedule: List[Dict[str, Any]],
        current_time: Any,
    ) -> Dict[str, Any]:
        """Detect delay, late start, productivity drop, and interruption deviations."""
        await self.initialize_scheduler()
        started = perf_counter()

        current_hour = self._coerce_decimal_hour(current_time)
        delayed_tasks: List[Dict[str, Any]] = []
        late_start_tasks: List[Dict[str, Any]] = []
        productivity_drop_tasks: List[Dict[str, Any]] = []
        interrupted_tasks: List[Dict[str, Any]] = []

        for task in schedule:
            if bool(task.get("completed", False)):
                continue

            scheduled_hour = float(task.get("scheduled_hour") or 0.0)
            expected_duration = float(task.get("estimated_duration") or 1.0)
            elapsed_time = self._calculate_elapsed_time(task)

            if self._is_task_running(task, current_hour) and elapsed_time > expected_duration + 0.25:
                delayed_tasks.append(task)

            if self._is_late_start(task, current_hour):
                late_start_tasks.append(task)

            if self._has_productivity_drop(task):
                productivity_drop_tasks.append(task)

            if self._has_interruption(task):
                interrupted_tasks.append(task)

        deviation_types: List[str] = []
        if delayed_tasks or late_start_tasks:
            deviation_types.append("delay")
        if productivity_drop_tasks:
            deviation_types.append("productivity_drop")
        if interrupted_tasks:
            deviation_types.append("interruption")

        reason = self._build_reason(
            delayed_tasks=delayed_tasks,
            late_start_tasks=late_start_tasks,
            productivity_drop_tasks=productivity_drop_tasks,
            interrupted_tasks=interrupted_tasks,
        )

        report = {
            "has_deviation": bool(deviation_types),
            "reason": reason,
            "deviation_types": deviation_types,
            "current_time": current_hour,
            "delayed_tasks": delayed_tasks,
            "late_start_tasks": late_start_tasks,
            "productivity_drop_tasks": productivity_drop_tasks,
            "interrupted_tasks": interrupted_tasks,
        }

        self._monitor().log_engine_execution(
            "AdaptiveScheduler:DeviationDetection",
            perf_counter() - started,
        )
        return report

    async def recalculate_schedule(
        self,
        schedule: List[Dict[str, Any]],
        deviation_report: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Recompute the unfinished portion of a schedule after deviations."""
        await self.initialize_scheduler()
        started = perf_counter()

        if not deviation_report.get("has_deviation"):
            return schedule

        user_id = self._active_user_id or self._infer_user_id(schedule)
        current_time = float(deviation_report.get("current_time") or self._to_decimal_hour(datetime.utcnow()))
        behavior_patterns = self._load_behavior_patterns(user_id)

        completed_tasks = [dict(task) for task in schedule if bool(task.get("completed", False))]
        remaining_tasks = self._remaining_tasks(schedule, current_time)
        if not remaining_tasks:
            return schedule

        prediction_started = perf_counter()
        refreshed_predictions = [
            self._predict_remaining_task(task, behavior_patterns, current_time)
            for task in remaining_tasks
        ]
        for prediction in refreshed_predictions:
            self._monitor().log_prediction(
                "AdaptiveScheduler",
                float(prediction.get("predicted_productivity", 0.0)),
            )
        self._monitor().log_engine_execution(
            "AdaptiveScheduler:PredictionRefresh",
            perf_counter() - prediction_started,
        )

        rl_started = perf_counter()
        rl_result = self.rl_scheduler.optimize_schedule(
            refreshed_predictions,
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

        resequenced_tasks = self._resequence_schedule(
            optimized_result["optimized_schedule"],
            current_time=current_time,
        )
        updated_schedule = sorted(
            completed_tasks + resequenced_tasks,
            key=lambda task: float(task.get("scheduled_hour") or 0.0),
        )

        productivity_values = [
            float(task.get("predicted_productivity", 0.0))
            for task in refreshed_predictions
        ]
        self._monitor().log_engine_execution(
            "AdaptiveScheduler:Recalculation",
            perf_counter() - started,
        )
        self._monitor().log_training_metrics(
            "AdaptiveScheduler",
            {
                "reason": deviation_report.get("reason"),
                "remaining_task_count": len(remaining_tasks),
                "updated_task_count": len(resequenced_tasks),
                "average_updated_prediction": round(mean(productivity_values), 2)
                if productivity_values
                else 0.0,
            },
        )

        return updated_schedule

    async def adapt_schedule(
        self,
        schedule: List[Dict[str, Any]],
        user_id: int,
    ) -> Dict[str, Any]:
        """Run one adaptive scheduling cycle and return the updated schedule."""
        await self.initialize_scheduler()
        if not schedule:
            raise ValueError("schedule is required.")

        self._active_user_id = user_id
        self._active_schedule = self._normalize_schedule(schedule, user_id=user_id)

        monitor_state = await self.monitor_execution(user_id)
        deviation_report = await self.detect_schedule_deviation(
            self._active_schedule,
            monitor_state["current_time"],
        )

        if not deviation_report["has_deviation"]:
            return {
                "updated_schedule": self._active_schedule,
                "reason": "no deviation detected",
            }

        if deviation_report["delayed_tasks"] or deviation_report["late_start_tasks"]:
            await self._emit_event(
                TASK_DELAYED,
                {
                    "user_id": user_id,
                    "task_ids": [
                        task.get("task_id")
                        for task in deviation_report["delayed_tasks"] + deviation_report["late_start_tasks"]
                    ],
                    "reason": deviation_report["reason"],
                },
            )
            await self._store_adaptive_event(
                user_id=user_id,
                event_type="delayed_tasks",
                summary="Adaptive scheduler detected delayed tasks.",
                payload=deviation_report["delayed_tasks"] + deviation_report["late_start_tasks"],
            )

        if deviation_report["productivity_drop_tasks"]:
            await self._emit_event(
                PRODUCTIVITY_DROP,
                {
                    "user_id": user_id,
                    "task_ids": [
                        task.get("task_id")
                        for task in deviation_report["productivity_drop_tasks"]
                    ],
                    "reason": deviation_report["reason"],
                },
            )
            await self._store_adaptive_event(
                user_id=user_id,
                event_type="productivity_drop",
                summary="Adaptive scheduler detected a productivity drop.",
                payload=deviation_report["productivity_drop_tasks"],
            )

        updated_schedule = await self.recalculate_schedule(self._active_schedule, deviation_report)
        self._active_schedule = updated_schedule

        await self._emit_event(
            SCHEDULE_UPDATED,
            {
                "user_id": user_id,
                "reason": deviation_report["reason"],
                "task_count": len(updated_schedule),
            },
        )
        await self._store_adaptive_event(
            user_id=user_id,
            event_type="schedule_updated",
            summary="Adaptive scheduler recalculated the live schedule.",
            payload=updated_schedule,
        )

        return {
            "updated_schedule": updated_schedule,
            "reason": deviation_report["reason"],
        }

    async def _emit_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        await self.event_bus.publish_event(event_name, payload)
        self._monitor().log_event(event_name)

    async def _store_adaptive_event(
        self,
        *,
        user_id: int,
        event_type: str,
        summary: str,
        payload: List[Dict[str, Any]],
    ) -> None:
        started = perf_counter()
        self.memory_system.store_memory(
            summary,
            {
                "user_id": user_id,
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": payload,
            },
        )
        self._monitor().log_engine_execution("VectorMemory", perf_counter() - started)

    def _normalize_schedule(
        self,
        schedule: List[Dict[str, Any]],
        *,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        normalized_schedule: List[Dict[str, Any]] = []
        for index, item in enumerate(schedule, start=1):
            task_id = item.get("task_id") or item.get("id") or f"adaptive-task-{user_id}-{index}"
            scheduled_hour = float(item.get("scheduled_hour") or item.get("optimized_hour") or index + 8)
            estimated_duration = float(
                item.get("estimated_duration")
                or item.get("completion_time_prediction")
                or max(0.5, float(item.get("scheduled_end_hour", scheduled_hour + 1.0)) - scheduled_hour)
            )
            normalized_schedule.append(
                {
                    **item,
                    "id": task_id,
                    "task_id": task_id,
                    "user_id": item.get("user_id", user_id),
                    "title": str(item.get("title") or f"Task {index}"),
                    "task_type": str(item.get("task_type") or item.get("type") or "general").lower(),
                    "priority": int(item.get("priority") or 3),
                    "estimated_duration": estimated_duration,
                    "scheduled_hour": scheduled_hour,
                    "scheduled_end_hour": float(item.get("scheduled_end_hour") or scheduled_hour + estimated_duration),
                    "predicted_productivity": float(item.get("predicted_productivity") or 0.0),
                    "completion_probability": float(
                        item.get("completion_probability")
                        or item.get("task_success_probability")
                        or 0.0
                    ),
                    "completed": bool(item.get("completed", False)),
                }
            )

        return sorted(normalized_schedule, key=lambda task: float(task["scheduled_hour"]))

    def _find_current_task(
        self,
        schedule: List[Dict[str, Any]],
        current_time: float,
    ) -> Optional[Dict[str, Any]]:
        for task in schedule:
            if bool(task.get("completed", False)):
                continue
            start = float(task.get("scheduled_hour") or 0.0)
            end = float(task.get("scheduled_end_hour") or start)
            if start <= current_time <= end:
                return task

        pending_tasks = [task for task in schedule if not bool(task.get("completed", False))]
        return pending_tasks[0] if pending_tasks else None

    def _remaining_tasks(
        self,
        schedule: List[Dict[str, Any]],
        current_time: float,
    ) -> List[Dict[str, Any]]:
        remaining: List[Dict[str, Any]] = []
        for task in schedule:
            if bool(task.get("completed", False)):
                continue
            task_copy = dict(task)
            task_copy["hour_of_day"] = max(
                current_time,
                float(task.get("scheduled_hour") or current_time),
            )
            remaining.append(task_copy)
        return remaining

    def _predict_remaining_task(
        self,
        task: Dict[str, Any],
        behavior_patterns: Dict[str, Any],
        current_time: float,
    ) -> Dict[str, Any]:
        task_payload = dict(task)
        task_payload["scheduled_hour"] = max(
            current_time,
            float(task.get("scheduled_hour") or current_time),
        )
        task_payload["hour_of_day"] = int(task_payload["scheduled_hour"])

        try:
            prediction = self.prediction_engine.predict_productivity(
                self.behavior_engine,
                task_payload,
                behavior_patterns,
            )
        except Exception:
            self.logger.exception(
                "Adaptive prediction fallback activated for task '%s'",
                task.get("title"),
            )
            prediction = self._fallback_prediction(task_payload, behavior_patterns)

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
        return prediction

    def _resequence_schedule(
        self,
        optimized_schedule: List[Dict[str, Any]],
        *,
        current_time: float,
    ) -> List[Dict[str, Any]]:
        running_hour = current_time
        resequenced: List[Dict[str, Any]] = []

        for task in sorted(
            optimized_schedule,
            key=lambda item: float(item.get("optimized_hour") or item.get("scheduled_hour") or 0.0),
        ):
            duration = float(task.get("estimated_duration") or 1.0)
            proposed_hour = float(task.get("optimized_hour") or task.get("scheduled_hour") or running_hour)
            selected_hour = max(running_hour, proposed_hour)
            running_hour = round(selected_hour + duration, 2)

            resequenced.append(
                {
                    **task,
                    "task_id": task.get("task_id") or task.get("id"),
                    "scheduled_hour": selected_hour,
                    "scheduled_end_hour": running_hour,
                    "rescheduled": True,
                }
            )

        return resequenced

    def _build_reason(
        self,
        *,
        delayed_tasks: List[Dict[str, Any]],
        late_start_tasks: List[Dict[str, Any]],
        productivity_drop_tasks: List[Dict[str, Any]],
        interrupted_tasks: List[Dict[str, Any]],
    ) -> str:
        if productivity_drop_tasks:
            return "productivity drop detected"
        if interrupted_tasks:
            return "unexpected interruption detected"
        if delayed_tasks:
            return "task duration exceeded expectation"
        if late_start_tasks:
            return "late start detected"
        return "no deviation detected"

    def _has_productivity_drop(self, task: Dict[str, Any]) -> bool:
        current_productivity = float(
            task.get("current_productivity")
            or task.get("actual_productivity")
            or task.get("live_productivity")
            or 0.0
        )
        predicted_productivity = float(task.get("predicted_productivity") or 0.0)
        energy_level = float(task.get("energy_level") or task.get("current_energy_level") or 100.0)

        if current_productivity and predicted_productivity:
            return current_productivity < (predicted_productivity * 0.75)
        return predicted_productivity > 0.0 and energy_level < 35.0

    def _has_interruption(self, task: Dict[str, Any]) -> bool:
        if bool(task.get("interrupted", False)):
            return True
        if str(task.get("status") or "").lower() == "interrupted":
            return True
        return int(task.get("interruption_count") or 0) > 0

    def _is_late_start(self, task: Dict[str, Any], current_time: float) -> bool:
        if bool(task.get("completed", False)):
            return False
        if task.get("started_at"):
            return False
        scheduled_hour = float(task.get("scheduled_hour") or 0.0)
        return current_time > scheduled_hour + 0.25

    def _is_task_running(self, task: Dict[str, Any], current_time: float) -> bool:
        if bool(task.get("completed", False)):
            return False
        if task.get("started_at"):
            return True
        start = float(task.get("scheduled_hour") or 0.0)
        end = float(task.get("scheduled_end_hour") or start)
        return start <= current_time <= end

    def _calculate_elapsed_time(
        self,
        task: Optional[Dict[str, Any]],
        current_dt: Optional[datetime] = None,
    ) -> float:
        if not task:
            return 0.0

        if task.get("elapsed_time") is not None:
            return float(task["elapsed_time"])
        if task.get("actual_elapsed_time") is not None:
            return float(task["actual_elapsed_time"])

        current_dt = current_dt or datetime.utcnow()
        started_at = task.get("started_at")
        if not started_at:
            scheduled_hour = float(task.get("scheduled_hour") or 0.0)
            return max(0.0, self._to_decimal_hour(current_dt) - scheduled_hour)

        try:
            started_dt = self._parse_datetime(started_at)
        except ValueError:
            return 0.0

        seconds = (current_dt - started_dt).total_seconds()
        return round(max(0.0, seconds / 3600.0), 2)

    def _task_status(self, task: Dict[str, Any], current_time: float) -> str:
        if bool(task.get("completed", False)):
            return "completed"
        if self._has_interruption(task):
            return "interrupted"
        if self._is_task_running(task, current_time):
            return "in_progress"
        if current_time < float(task.get("scheduled_hour") or 0.0):
            return "pending"
        return "delayed"

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
            self.logger.exception("Adaptive scheduler behavior fallback activated for user %s", user_id)
            return self._default_behavior_patterns(user_id)

    def _default_behavior_patterns(self, user_id: int) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "average_productivity": 60.0,
            "average_energy_level": 60.0,
            "average_completion_time": 1.0,
            "best_focus_hours": [9, 11, 14],
            "preferred_task_types": [],
            "hourly_productivity": {9: 58.0, 11: 67.0, 14: 72.0, 16: 63.0},
        }

    def _fallback_prediction(
        self,
        task: Dict[str, Any],
        behavior_patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        duration = float(task.get("estimated_duration") or 1.0)
        priority = float(task.get("priority") or 3.0)
        baseline = float(behavior_patterns.get("average_productivity", 60.0))
        predicted_productivity = max(35.0, min(95.0, baseline + (priority * 2.5) - (duration * 3.0)))
        completion_probability = max(
            0.1,
            min(0.98, (predicted_productivity / 100.0) * 0.75 + min(priority, 5.0) * 0.05),
        )
        completion_time_prediction = max(
            0.25,
            duration * float(behavior_patterns.get("average_completion_time", 1.0)),
        )
        return {
            **task,
            "predicted_productivity": round(predicted_productivity, 2),
            "task_success_probability": round(completion_probability, 4),
            "completion_time_prediction": round(completion_time_prediction, 2),
        }

    def _infer_user_id(self, schedule: List[Dict[str, Any]]) -> int:
        for task in schedule:
            if task.get("user_id") is not None:
                return int(task["user_id"])
        if self._active_user_id is None:
            raise ValueError("user_id is required to adapt a schedule.")
        return self._active_user_id

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            raise ValueError("Invalid datetime value.")
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)

    def _coerce_decimal_hour(self, value: Any) -> float:
        if isinstance(value, datetime):
            return self._to_decimal_hour(value)
        return float(value)

    def _to_decimal_hour(self, value: datetime) -> float:
        return round(value.hour + (value.minute / 60.0) + (value.second / 3600.0), 2)

    def _monitor(self) -> Any:
        if not self._initialized or self.ai_monitor is None:
            raise RuntimeError("Adaptive scheduler monitor is not initialized.")
        return self.ai_monitor
