from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from time import perf_counter
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.memory import VectorMemorySystem
from backend.app.monitoring import AIMonitor
from backend.app.orchestrator.ai_brain_controller import AIBrainController

_INTENT_USAGE = defaultdict(int)


class AIInteractionLayer:
    """Natural-language interface for routing user commands into AI workflows."""

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
        self.engine_registry = engine_registry
        self.monitor = monitor or AIMonitor()
        self.memory_system = memory_system or VectorMemorySystem()
        self.brain_controller: Optional[AIBrainController] = None
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    async def initialize_engine(self) -> None:
        """Initialize shared engine references for command routing."""
        if self._initialized:
            return

        from backend.app.core.engine_registry import EngineRegistry
        self.engine_registry = self.engine_registry or EngineRegistry(self.session)
        self.brain_controller = AIBrainController(
            session=self.session,
            days_back=self.days_back,
            engine_registry=self.engine_registry,
            monitor=self.monitor,
            memory_system=self.memory_system,
        )
        self._initialized = True

    def detect_intent(self, command: str) -> str:
        """Classify a natural-language command into a supported intent."""
        normalized = command.strip().lower()
        if not normalized:
            raise ValueError("command is required.")

        if any(keyword in normalized for keyword in ("learn", "retrain", "update model", "improve model")):
            return "run_learning_cycle"
        if any(keyword in normalized for keyword in ("recommend", "suggest", "insight")):
            return "get_recommendations"
        if any(keyword in normalized for keyword in ("productivity", "focus report", "performance", "analyze my work")):
            return "analyze_productivity"
        if any(keyword in normalized for keyword in ("optimize", "reschedule", "rearrange", "schedule")):
            return "optimize_schedule"
        if any(keyword in normalized for keyword in ("plan", "plan my day", "organize my day")):
            return "plan_day"
        # Do not silently treat open-ended conversation as a planning request.
        # The controller rejects this intent until a general chat provider exists.
        return "general_question"

    def parse_command(self, command: str) -> Dict[str, Any]:
        """Extract goal, task types, and time references from a command."""
        normalized = command.strip()
        intent = self.detect_intent(normalized)
        lowered = normalized.lower()

        task_type_matches = re.findall(
            r"\b(coding|research|writing|analysis|meeting|planning|review|learning|study|admin)\b",
            lowered,
        )
        date_match = re.search(
            r"\b(today|tomorrow|tonight|this week|next week|morning|afternoon|evening)\b",
            lowered,
        )

        parameters = {
            "intent": intent,
            "goal": normalized,
            "task_type": task_type_matches[0] if task_type_matches else None,
            "task_types": task_type_matches,
            "date": date_match.group(1) if date_match else None,
            "command": normalized,
        }
        return parameters

    async def execute_intent(self, request: "BrainRequest") -> "BrainResponse":
        """Route a formally typed BrainRequest to the appropriate AI subsystem."""
        await self.initialize_engine()
        if not self.brain_controller:
            raise RuntimeError("Brain Controller not initialized.")
        return await self.brain_controller.process_intent(request)

    async def process_command(self, user_id: int, command: str) -> Dict[str, Any]:
        """Detect intent, parse parameters, execute the action, and log usage."""
        await self.initialize_engine()
        started = perf_counter()

        try:
            intent = self.detect_intent(command)
            parameters = self.parse_command(command)
            
            from backend.app.orchestrator.brain_models import BrainRequest
            import uuid
            
            brain_request = BrainRequest(
                request_id=str(uuid.uuid4()),
                user_id=user_id,
                intent=intent,
                command=command,
                parameters=parameters,
                days_back=self.days_back
            )

            brain_response = await self.execute_intent(brain_request)

            result = brain_response.raw_result
            if "schedule" not in result and brain_response.schedule:
                result["schedule"] = brain_response.schedule
            if "executive_summary" not in result:
                result["executive_summary"] = brain_response.executive_summary
            if "quantum_status" not in result:
                result["quantum_status"] = brain_response.quantum_status
            if "trace" not in result:
                result["trace"] = brain_response.trace.model_dump()
            if "success" not in result:
                result["success"] = brain_response.success
            if "errors" not in result:
                result["errors"] = brain_response.errors

            self._store_command_memory(user_id=user_id, command=command, intent=intent, result=result)
            self._record_usage(intent=intent, duration=perf_counter() - started)

            return {
                "intent": intent,
                "result": result,
            }
        except Exception as exc:
            self.logger.exception("Command processing failed for user %s", user_id)
            raise ValueError(f"Command processing failed: {exc}") from exc

    def _latest_schedule_from_memory(self, user_id: int) -> List[Dict[str, Any]]:
        memory_context = self.memory_system.retrieve_context(user_id=user_id)
        for record in reversed(memory_context.get("recent_memories", [])):
            metadata = record.get("metadata", {})
            for key in ("schedule", "optimized_schedule_snapshot", "payload"):
                schedule = metadata.get(key)
                if isinstance(schedule, list) and schedule:
                    return schedule
        return []

    def _store_command_memory(
        self,
        *,
        user_id: int,
        command: str,
        intent: str,
        result: Dict[str, Any],
    ) -> None:
        self.memory_system.store_memory(
            command,
            {
                "user_id": user_id,
                "event_type": "ai_command",
                "intent": intent,
                "timestamp": datetime.utcnow().isoformat(),
                "result": result,
            },
        )

    def _record_usage(self, *, intent: str, duration: float) -> None:
        _INTENT_USAGE[intent] += 1
        self.monitor.log_engine_execution("AIInteractionLayer", duration)
        self.monitor.log_event(f"COMMAND_{intent.upper()}")
        self.monitor.log_training_metrics(
            "AIInteractionLayer",
            {
                "intent": intent,
                "intent_frequency": dict(_INTENT_USAGE),
                "command_processing_time_seconds": round(duration, 4),
                "system_usage_patterns": self.monitor.report_system_metrics(),
            },
        )
