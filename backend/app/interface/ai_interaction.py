from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.memory import VectorMemorySystem
from backend.app.monitoring import AIMonitor

if TYPE_CHECKING:
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
        clock: Optional[Callable[[], datetime]] = None,
        parser: Optional[Any] = None,
    ) -> None:
        self.session = session
        self.days_back = days_back
        self.engine_registry = engine_registry
        self.monitor = monitor or AIMonitor()
        self.memory_system = memory_system or VectorMemorySystem()
        self.clock = clock
        self.parser = parser
        self.brain_controller: Optional[AIBrainController] = None
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    async def initialize_engine(self) -> None:
        """Initialize shared engine references for command routing."""
        if self._initialized:
            return

        from backend.app.core.engine_registry import EngineRegistry
        from backend.app.orchestrator.ai_brain_controller import AIBrainController
        self.engine_registry = self.engine_registry or EngineRegistry(self.session)
        self.brain_controller = AIBrainController(
            session=self.session,
            days_back=self.days_back,
            engine_registry=self.engine_registry,
            monitor=self.monitor,
            memory_system=self.memory_system,
            clock=self.clock,
        )
        self._initialized = True

    def detect_intent(self, command: str) -> str:
        """Classify a natural-language command into a supported intent."""
        normalized = command.strip().lower()
        if not normalized:
            raise ValueError("command is required.")

        # Action-capable task management intents
        if re.search(r"\b(create|add|new)\s+task\b", normalized):
            return "create_task"
        if re.search(r"\b(list|show|view|what are)\s+(?:my\s+)?(?:pending\s+|active\s+)?tasks\b", normalized) or normalized in ("pending tasks", "my tasks", "tasks"):
            return "list_tasks"
        if any(keyword in normalized for keyword in (
            "which tasks should i complete first",
            "which task first",
            "what to do first",
            "prioritize",
            "rank my tasks",
            "order my tasks",
            "priority list",
        )):
            return "prioritize_tasks"

        # Plan acceptance & rejection
        if any(keyword in normalized for keyword in (
            "accept plan",
            "accept this plan",
            "accept proposal",
            "accept schedule",
            "confirm schedule",
            "confirm plan",
            "apply plan",
            "save plan",
        )):
            return "accept_plan"

        if any(keyword in normalized for keyword in (
            "reject plan",
            "reject this plan",
            "reject proposal",
            "cancel plan",
            "cancel proposal",
            "discard plan",
            "discard proposal",
            "decline plan",
            "decline proposal",
        )):
            return "reject_plan"

        # Plan refinement
        if re.search(r"\b(?:move|put|place|keep)\s+.+?\s+(?:ahead of|before|earlier than|later than|after|first)\b", normalized) or \
           re.search(r"\b(?:move|put)\s+.+?\s+first\b", normalized) or \
           re.search(r"\b(?:leave|keep|allow|add)\s+\d+\s*(?:minutes?|mins?)\b", normalized) or \
           re.search(r"\b(?:start|move|schedule)\s+.+?\s+after\s+lunch\b", normalized) or \
           re.search(r"\bafter\s+lunch\b", normalized) or \
           re.search(r"\b(?:show(?:\s+me)?\s+another\s+schedule|prioritizes?\s+the\s+|reduce\s+the\s+.+?\s+time|reduce\s+.+?\s+duration)\b", normalized) or \
           re.search(r"\b(?:i\s+)?(?:only\s+have|have\s+only)\s+\d+(?:\.\d+)?\s+hours?\b", normalized) or \
           re.search(r"\bonly\s+\d+(?:\.\d+)?\s+hours?\s+(?:available|now|left)?\b", normalized) or \
           re.search(r"\badjust(?:\s+the)?\s+plan\b", normalized):
            return "refine_plan"

        # Intelligent Deadline & Time Management intents
        if any(keyword in normalized for keyword in (
            "which task should i complete next",
            "what should i complete next",
            "what task next",
            "what to do next",
            "which task next",
            "what should i do next",
            "which task to do next",
            "next task",
        )):
            return "next_task"

        if any(keyword in normalized for keyword in (
            "which tasks are at risk of missing deadlines",
            "which tasks are at risk",
            "tasks at risk of missing deadlines",
            "tasks at risk",
            "deadline risk",
            "risk of missing deadlines",
            "miss any deadline",
            "which tasks might be late",
            "at risk of missing",
        )):
            return "deadline_risks"

        if any(keyword in normalized for keyword in (
            "how much work do i have today",
            "what is my workload today",
            "how much work today",
            "today's workload",
            "todays workload",
            "my workload today",
            "how much work do i have",
        )):
            return "workload_query"

        if any(keyword in normalized for keyword in (
            "can i finish all my tasks before their deadlines",
            "can i finish on time",
            "will i meet my deadlines",
            "is my schedule feasible",
            "can i finish all my tasks",
            "can i finish before deadline",
            "can i finish before their deadlines",
        )):
            return "feasibility_query"

        if any(keyword in normalized for keyword in (
            "which tasks are blocking other tasks",
            "what tasks are blocking",
            "blocking tasks",
            "which tasks are blocking",
            "tasks blocking other tasks",
            "which task is blocking",
        )):
            return "blocking_tasks"

        if any(keyword in normalized for keyword in (
            "reschedule my remaining tasks",
            "reschedule remaining tasks",
            "reschedule my tasks",
            "reschedule pending tasks",
        )):
            return "reschedule_tasks"

        if any(keyword in normalized for keyword in ("learn", "retrain", "update model", "improve model")):
            return "run_learning_cycle"
        if any(keyword in normalized for keyword in ("recommend", "suggest", "insight")):
            return "get_recommendations"
        if any(keyword in normalized for keyword in ("productivity", "focus report", "performance", "analyze my work")):
            return "analyze_productivity"
        if any(keyword in normalized for keyword in ("optimize", "reschedule", "rearrange", "move task", "move the")):
            return "optimize_schedule"
        if any(keyword in normalized for keyword in (
            "plan", "plan my day", "organize my day", "plan my afternoon",
            "arrange my pending work", "realistically complete today",
            "balance my deadlines", "plan today", "plan my schedule",
            "schedule my tasks", "plan schedule"
        )) or re.search(r"\bplan\s+(?:my\s+day\s+)?around\b", normalized) or \
           re.search(r"\buse\s+(?:my\s+)?existing\s+(?:tasks?|goals?)\b", normalized) or \
           re.search(r"\bdue\s+(?:tomorrow|next week|today|in\s+\w+\s+days?|\d{4}-\d{2}-\d{2})\b", normalized) or \
           re.search(r"\b(?:available|free)\s+(?:for\s+)?\d+(?:\.\d+)?\s+hours?\b", normalized) or \
           re.search(r"\b\d+(?:\.\d+)?\s+hours?\s+available\b", normalized) or \
           (re.search(r"\b(?:assignment|exam|project|thesis|paper|task)\b", normalized) and ("available" in normalized or "hours" in normalized)):
            return "plan_day"
        # Do not silently treat open-ended conversation as a planning request.
        # The controller rejects this intent until a general chat provider exists.
        return "general_question"

    def parse_command(self, command: str) -> Dict[str, Any]:
        """Extract goal, task types, numbers, duration, and time references from a command."""
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

        # Available hours extraction (e.g. "I have 4 hours available today", "available for 6 hours")
        avail_match = re.search(
            r"(?:i have|with|for)\s+(\d+(?:\.\d+)?)\s+hours?\s+available|"
            r"(\d+(?:\.\d+)?)\s+hours?\s+available|"
            r"available\s+(?:for\s+)?(\d+(?:\.\d+)?)\s+hours?",
            lowered,
        )
        available_hours: Optional[float] = None
        if avail_match:
            val = next((m for m in avail_match.groups() if m is not None), None)
            if val:
                available_hours = float(val)

        # Task count extraction (e.g. "three most important tasks")
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        count_match = re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:most\s+)?(?:important\s+)?tasks?\b",
            lowered,
        )
        task_count: Optional[int] = None
        if count_match:
            raw_count = count_match.group(1)
            task_count = word_to_num.get(raw_count, int(raw_count) if raw_count.isdigit() else None)

        # Task creation parameters
        title: Optional[str] = None
        priority: int = 3
        estimated_duration_minutes: float = 60.0

        if intent == "create_task":
            title_match = re.search(
                r"(?:create|add|new)\s+task\s+[:\-]?\s*(.+?)(?:\s+(?:with|priority|duration|due)|$)",
                normalized,
                re.IGNORECASE,
            )
            if title_match:
                title = title_match.group(1).strip()
            if not title:
                title = normalized

            prio_match = re.search(r"\bpriority\s+(\d)\b", lowered)
            if prio_match:
                prio_val = int(prio_match.group(1))
                if 1 <= prio_val <= 5:
                    priority = prio_val
            elif "urgent" in lowered or "critical" in lowered:
                priority = 5
            elif "high priority" in lowered:
                priority = 4
            elif "low priority" in lowered:
                priority = 2

            dur_match = re.search(
                r"(?:duration|for)\s+(\d+(?:\.\d+)?)\s*(minutes?|hours?|mins?|hrs?)\b|"
                r"(\d+(?:\.\d+)?)\s*(minutes?|hours?|mins?|hrs?)\s+duration\b",
                lowered,
            )
            if dur_match:
                groups = [g for g in dur_match.groups() if g is not None]
                if len(groups) >= 2:
                    val = float(groups[0])
                    unit = groups[1].lower()
                    if "hour" in unit or "hr" in unit:
                        estimated_duration_minutes = val * 60.0
                    else:
                        estimated_duration_minutes = val

        parser = self.parser
        if parser is None:
            from backend.app.interface.llm_provider import HybridPlanningParser
            parser = HybridPlanningParser(clock=self.clock)
        planning_context = parser.parse(normalized)

        extracted_task_dicts = [
            {
                "title": t.title,
                "task_type": t.task_type,
                "deadline_expression": t.deadline_expression,
                "deadline": t.deadline_dt.isoformat() if t.deadline_dt else None,
                "deadline_dt": t.deadline_dt,
                "deadline_precision": t.deadline_precision,
                "estimated_duration": t.estimated_duration,
                "estimated_duration_unit": t.estimated_duration_unit,
                "estimated_duration_source": t.estimated_duration_source,
                "priority": t.priority,
                "dependencies": t.dependencies,
                "scheduling_preference": t.scheduling_preference,
                "min_start_hour": t.min_start_hour,
                "raw_clause": t.raw_clause,
                "origin": t.origin,
            }
            for t in planning_context.extracted_tasks
        ]

        refinement_data = None
        if intent == "refine_plan":
            refinement_data = parser.parse_refinement(normalized)

        if planning_context.available_hours is not None:
            available_hours = planning_context.available_hours

        effective_task_count = task_count or planning_context.task_count

        parameters = {
            "intent": intent,
            "goal": normalized,
            "task_type": task_type_matches[0] if task_type_matches else "general",
            "task_types": task_type_matches,
            "date": date_match.group(1) if date_match else None,
            "available_hours": available_hours,
            "task_count": effective_task_count,
            "use_existing_tasks": planning_context.use_existing_tasks,
            "parser_provenance": planning_context.parser_provenance,
            "title": title,
            "priority": priority,
            "estimated_duration": estimated_duration_minutes,
            "estimated_duration_unit": "minutes",
            "extracted_tasks": extracted_task_dicts,
            "buffer_minutes": planning_context.buffer_minutes,
            "buffer_label": planning_context.buffer_label,
            "clarification_needed": planning_context.clarification_needed,
            "clarification_question": planning_context.clarification_question,
            "refinement": refinement_data,
            "command": normalized,
        }
        return parameters

    def extract_parameters(self, command: str) -> Tuple[str, Dict[str, Any]]:
        """Extract intent and parsed parameters from command."""
        intent = self.detect_intent(command)
        params = self.parse_command(command)
        return intent, params

    async def execute_intent(self, request: "BrainRequest") -> "BrainResponse":
        """Route a formally typed BrainRequest to the appropriate AI subsystem."""
        await self.initialize_engine()
        if not self.brain_controller:
            raise RuntimeError("Brain Controller not initialized.")
        return await self.brain_controller.process_intent(request)

    async def process_command(
        self,
        user_id: int,
        command: str,
        conversation_turns: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Detect intent, parse parameters, execute the action, and log usage."""
        await self.initialize_engine()
        started = perf_counter()

        try:
            intent = self.detect_intent(command)
            parameters = self.parse_command(command)
            if conversation_turns:
                parameters["conversation_turns"] = conversation_turns
            
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
        import json
        try:
            clean_result = json.loads(json.dumps(result, default=str))
        except Exception:
            clean_result = {"action": intent}

        self.memory_system.store_memory(
            command,
            {
                "user_id": user_id,
                "event_type": "ai_command",
                "intent": intent,
                "timestamp": datetime.utcnow().isoformat(),
                "result": clean_result,
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
