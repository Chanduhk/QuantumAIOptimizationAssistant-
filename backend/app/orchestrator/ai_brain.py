from __future__ import annotations

import logging
import math
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

from backend.app.domain.day_model import Day
from backend.app.domain.evaluation import DayEvaluator

if TYPE_CHECKING:
    from backend.app.context.context_builder import ContextBuilder, ContextState

logger = logging.getLogger(__name__)


class AIBrain:
    """Central orchestration layer for Day scheduling, evaluation, and forecasting."""

    def __init__(
        self,
        scheduler: Any,
        forecast_engine: Any,
        context_builder: "ContextBuilder",
        *,
        memory_manager: Optional[Any] = None,
        recommendation_engine: Optional[Any] = None,
    ) -> None:
        self.scheduler = scheduler
        self.forecast_engine = forecast_engine
        self.context_builder = context_builder
        self.memory_manager = memory_manager
        self.recommendation_engine = recommendation_engine
        self._last_context: Optional["ContextState"] = None
        self._last_schedule: Optional[Dict[str, Any]] = None
        self._last_evaluation: Optional[Dict[str, float]] = None
        self._last_forecast_score: Optional[float] = None

    def health_check(self) -> Dict[str, Any]:
        """Return readiness information for the orchestration dependencies."""
        scheduler_ready = any(
            callable(getattr(self.scheduler, method_name, None))
            for method_name in ("generate", "generate_schedule", "generate_from_order")
        )
        forecast_ready = self.forecast_engine is not None and (
            callable(getattr(self.forecast_engine, "simulate", None))
            or callable(self.forecast_engine)
        )
        context_ready = callable(getattr(self.context_builder, "build", None))
        healthy = scheduler_ready and forecast_ready and context_ready
        return {
            "healthy": healthy,
            "scheduler_ready": scheduler_ready,
            "forecast_ready": forecast_ready,
            "context_builder_ready": context_ready,
            "memory_manager_ready": self.memory_manager is not None,
            "recommendation_engine_ready": self.recommendation_engine is not None,
        }

    def build_context(self, day: Day) -> "ContextState":
        """Build and cache the current ContextState for a Day."""
        logger.info("AIBrain building context.")
        self._validate_day(day)
        context = self.context_builder.build(day)
        self._last_context = context
        return context

    def generate_schedule(self, day: Day) -> Dict[str, Any]:
        """Generate a schedule using the injected scheduler and existing interfaces."""
        logger.info("AIBrain generating schedule.")
        self._validate_day(day)
        self._bind_day_to_scheduler(day)

        generate = getattr(self.scheduler, "generate", None)
        if callable(generate):
            schedule = generate(day)
        elif callable(getattr(self.scheduler, "generate_schedule", None)):
            self._reset_scheduler_state()
            schedule = self.scheduler.generate_schedule()
        elif callable(getattr(self.scheduler, "generate_from_order", None)):
            schedule = self.scheduler.generate_from_order(list(day.tasks))
        else:
            raise TypeError("Scheduler must expose generate, generate_schedule, or generate_from_order.")

        if not isinstance(schedule, dict):
            raise ValueError("Scheduler must return a dictionary schedule.")
        self._last_schedule = schedule
        logger.info("Schedule generated with blocks=%s.", list(schedule.keys()))
        return schedule

    def run_forecast(self, day: Day) -> float:
        """Run the injected forecast engine through the existing simulate interface."""
        logger.info("AIBrain running forecast.")
        self._validate_day(day)
        forecast_engine = self._resolve_forecast_engine(day)
        simulate = getattr(forecast_engine, "simulate", None)
        if not callable(simulate):
            raise TypeError("Forecast engine must expose simulate().")
        forecast_score = self._finite_float(simulate(), "forecast_score")
        self._last_forecast_score = forecast_score
        logger.info("Forecast complete with score=%.3f.", forecast_score)
        return forecast_score

    def run_daily_cycle(self, day: Day) -> Dict[str, Any]:
        """Run context, scheduling, evaluation, and forecast for one Day."""
        logger.info("AIBrain starting daily cycle.")
        context = self.build_context(day)
        schedule = self.generate_schedule(day)
        evaluation = self._evaluate(day, schedule)
        forecast_score = self.run_forecast(day)

        result = {
            "context": context,
            "schedule": schedule,
            "evaluation": evaluation,
            "forecast_score": forecast_score,
        }
        self._record_cycle(result)
        logger.info("AIBrain daily cycle complete.")
        return result

    def generate_system_report(self) -> Dict[str, Any]:
        """Return a consolidated report of the most recent AI brain cycle."""
        logger.info("Generating AIBrain system report.")
        return {
            "health": self.health_check(),
            "context": self._serialize(self._last_context),
            "schedule": self._last_schedule,
            "evaluation": self._last_evaluation,
            "forecast_score": self._last_forecast_score,
        }

    def _evaluate(self, day: Day, schedule: Dict[str, Any]) -> Dict[str, float]:
        evaluator = DayEvaluator(day, schedule)
        evaluation = {
            "productivity_score": self._finite_float(evaluator.productivity_score(), "productivity_score"),
            "priority_score": self._finite_float(evaluator.priority_score(), "priority_score"),
            "energy_alignment": self._finite_float(evaluator.energy_alignment_score(), "energy_alignment"),
            "stress_penalty": self._finite_float(evaluator.stress_penalty(), "stress_penalty"),
            "total_score": self._finite_float(evaluator.total_score(), "total_score"),
        }
        self._last_evaluation = evaluation
        return evaluation

    def _resolve_forecast_engine(self, day: Day) -> Any:
        engine = self.forecast_engine
        if callable(getattr(engine, "simulate", None)):
            if hasattr(engine, "original_day"):
                setattr(engine, "original_day", day)
            if hasattr(engine, "scheduler"):
                setattr(engine, "scheduler", self.scheduler)
            return engine

        if callable(engine):
            try:
                return engine(day, self.scheduler)
            except TypeError:
                return engine(day=day, scheduler=self.scheduler)

        raise TypeError("Forecast engine must be an instance with simulate() or a callable factory.")

    def _bind_day_to_scheduler(self, day: Day) -> None:
        if hasattr(self.scheduler, "day"):
            setattr(self.scheduler, "day", day)

    def _reset_scheduler_state(self) -> None:
        if hasattr(self.scheduler, "schedule"):
            self.scheduler.schedule = {
                "morning": [],
                "afternoon": [],
                "evening": [],
            }
        if hasattr(self.scheduler, "block_hours"):
            self.scheduler.block_hours = {
                "morning": 3,
                "afternoon": 3,
                "evening": 2,
            }

    def _record_cycle(self, result: Dict[str, Any]) -> None:
        if self.memory_manager is not None and callable(getattr(self.memory_manager, "store_memory", None)):
            memory_result = self.memory_manager.store_memory("AIBrain daily cycle completed.", self._serialize(result))
            if memory_result is not None and not isinstance(memory_result, dict):
                raise ValueError("memory_manager.store_memory must return a dictionary or None.")
        if self.recommendation_engine is not None and callable(getattr(self.recommendation_engine, "record_cycle", None)):
            recommendation_result = self.recommendation_engine.record_cycle(result)
            if recommendation_result is not None and not isinstance(recommendation_result, (dict, list)):
                raise ValueError("recommendation_engine.record_cycle must return a dictionary, list, or None.")

    def _serialize(self, value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return {key: self._serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        return value

    def _validate_day(self, day: Day) -> None:
        if not isinstance(day, Day):
            raise TypeError("AIBrain requires an existing Day instance.")

    def _finite_float(self, value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return number
