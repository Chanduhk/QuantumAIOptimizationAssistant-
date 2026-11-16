from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ExtractedTaskSpec:
    """Specification for a task extracted from natural language."""

    title: str
    task_type: str = "general"
    deadline_expression: Optional[str] = None
    deadline_dt: Optional[datetime] = None
    deadline_precision: Optional[str] = None
    estimated_duration: float = 1.0  # in hours
    estimated_duration_unit: str = "hours"
    estimated_duration_source: str = "deterministic_heuristic"
    priority: int = 3
    dependencies: List[str] = field(default_factory=list)
    scheduling_preference: Optional[str] = None
    min_start_hour: Optional[float] = None
    raw_clause: str = ""
    origin: str = "proposed"
    goal_title: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ExtractedPlanningContext:
    """Complete planning context extracted from a natural language request."""

    command: str
    available_hours: Optional[float] = None
    extracted_tasks: List[ExtractedTaskSpec] = field(default_factory=list)
    general_preferences: List[str] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    order_overrides: List[Tuple[str, str]] = field(default_factory=list)
    buffer_minutes: Optional[float] = None
    buffer_label: Optional[str] = None
    use_existing_tasks: bool = False
    task_count: Optional[int] = None
    parser_provenance: str = "deterministic_fallback"


class NaturalLanguageExtractor:
    """Extracts tasks, deadlines, durations, constraints, and horizons from natural language."""

    WORD_TO_NUM: Dict[str, int] = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "half": 0.5,
    }

    MONTH_MAP: Dict[str, int] = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9, "sept": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    TASK_TYPE_KEYWORDS: Dict[str, List[str]] = {
        "writing": ["assignment", "report", "paper", "write", "writing", "essay", "article", "thesis", "draft"],
        "study": ["exam", "study", "review", "revision", "read", "learn", "homework", "quiz", "test"],
        "coding": ["project", "code", "coding", "bug", "triage", "implementation", "feature", "pr", "develop", "refactor"],
        "meeting": ["meeting", "standup", "sync", "discussion", "call", "conference"],
        "planning": ["plan", "planning", "roadmap", "architecture", "design review"],
        "analysis": ["analysis", "analyze", "evaluation", "metrics", "data"],
    }

    def __init__(
        self,
        *,
        clock: Optional[Callable[[], datetime]] = None,
        default_timezone: str = "UTC",
    ) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc).replace(tzinfo=None))
        self.default_timezone = default_timezone

    def get_reference_time(self) -> datetime:
        """Return the current reference datetime from the injectable clock."""
        dt = self.clock()
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    def extract(
        self,
        command: str,
        user_tz: str = "UTC",
        reference_time: Optional[datetime] = None,
    ) -> ExtractedPlanningContext:
        """Alias for parse_planning_request supporting user_tz and reference_time parameters."""
        return self.parse_planning_request(command, reference_time=reference_time)

    def extract_planning_context(
        self,
        command: str,
        user_tz: str = "UTC",
        reference_time: Optional[datetime] = None,
    ) -> ExtractedPlanningContext:
        """Alias for parse_planning_request supporting user_tz and reference_time parameters."""
        return self.parse_planning_request(command, reference_time=reference_time)

    def parse_planning_request(
        self,
        command: str,
        reference_time: Optional[datetime] = None,
    ) -> ExtractedPlanningContext:
        """Parse a full user request into planning constraints and multiple tasks."""
        normalized = command.strip()
        if not normalized:
            return ExtractedPlanningContext(
                command=command,
                clarification_needed=True,
                clarification_question="Please provide the tasks or goals you would like me to schedule.",
            )

        ref_dt = reference_time or self.get_reference_time()
        lowered = normalized.lower()

        # 0. Detect requests to use existing tasks or top priority tasks
        use_existing_tasks = False
        task_count = None
        if re.search(r"\buse\s+(?:my\s+)?existing\s+(?:tasks?|goals?)\b", lowered) or \
           re.search(r"\bmy\s+existing\s+tasks\b", lowered):
            use_existing_tasks = True

        around_match = re.search(
            r"\baround\s+(?:my\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*(?:most\s+)?(?:important|priority)\s+tasks?\b",
            lowered,
        )
        if around_match:
            use_existing_tasks = True
            raw_c = around_match.group(1)
            if raw_c:
                task_count = int(self.WORD_TO_NUM.get(raw_c.lower(), int(raw_c) if raw_c.isdigit() else 3))
            else:
                task_count = 3

        # 1. Extract Available Horizon
        available_hours = self._extract_available_hours(lowered)

        # 2. Extract general buffers or preferences
        buffer_minutes, buffer_label = self._extract_buffer(lowered)

        # 3. Segment into task clauses
        task_clauses = self._segment_task_clauses(normalized)

        # 4. Extract individual tasks
        extracted_tasks: List[ExtractedTaskSpec] = []
        for clause in task_clauses:
            spec = self._extract_single_task(clause, ref_dt)
            if spec and spec.title:
                extracted_tasks.append(spec)

        # 5. Clarification detection
        clarification_needed = False
        clarification_question = None
        if not extracted_tasks and not use_existing_tasks:
            clarification_needed = True
            clarification_question = (
                "I could not detect any specific tasks or deadlines to schedule. "
                "Could you list the tasks you'd like to work on and their deadlines?"
            )

        return ExtractedPlanningContext(
            command=normalized,
            available_hours=available_hours,
            extracted_tasks=extracted_tasks,
            clarification_needed=clarification_needed,
            clarification_question=clarification_question,
            buffer_minutes=buffer_minutes,
            buffer_label=buffer_label,
            use_existing_tasks=use_existing_tasks,
            task_count=task_count,
            parser_provenance="deterministic_fallback",
        )

    def _extract_available_hours(self, text: str) -> Optional[float]:
        """Extract available planning horizon in hours."""
        # e.g. "I have four hours available today", "available for 6 hours", "3.5 hours available"
        word_pattern = "|".join(self.WORD_TO_NUM.keys())
        match = re.search(
            rf"(?:i have|with|for)?\s*(\d+(?:\.\d+)?|{word_pattern})\s+hours?\s+(?:available|free|left)",
            text,
            re.IGNORECASE,
        )
        if match:
            raw = match.group(1).lower()
            return float(self.WORD_TO_NUM.get(raw, float(raw) if raw.replace(".", "", 1).isdigit() else 8.0))

        # "Available 4 hours", "Available for 6 hours"
        match_avail = re.search(
            r"\bavailable\s+(?:for\s+)?(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s+hours?",
            text,
            re.IGNORECASE,
        )
        if match_avail:
            raw = match_avail.group(1).lower()
            return float(self.WORD_TO_NUM.get(raw, float(raw) if raw.replace(".", "", 1).isdigit() else 8.0))

        # "I have 4 hours today"
        match3 = re.search(
            r"have\s+(\d+(?:\.\d+)?)\s+hours?\s+(?:today|this afternoon|this morning)",
            text,
            re.IGNORECASE,
        )
        if match3:
            return float(match3.group(1))

        return None

    def _extract_buffer(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract requested buffer time, e.g. 'Leave 30 minutes for revision'."""
        match = re.search(
            r"(?:leave|keep|allow|add)\s+(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\s+(?:for\s+)?([a-zA-Z\s]+)",
            text,
            re.IGNORECASE,
        )
        if match:
            mins = float(match.group(1))
            label = match.group(2).strip().split(".")[0].strip()
            return mins, label
        return None, None

    def _segment_task_clauses(self, command: str) -> List[str]:
        """Split a compound sentence into separate task clauses."""
        text = command.strip()

        # Remove available horizon sentence/clause from task parsing
        text = re.sub(
            r"\b(?:i have|with|for)?\s*(?:\d+(?:\.\d+)?|[a-zA-Z]+)\s+hours?\s+(?:available|free|left)[^.,;]*[.,;]?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\bavailable\s+(?:for\s+)?(?:\d+(?:\.\d+)?|[a-zA-Z]+)\s+hours?[^.,;]*[.,;]?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\bplan\s+(?:my\s+)?(?:schedule|day|afternoon|work)[^.,;]*[.,;]?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b(?:please\s+)?(?:organize|arrange)\s+(?:my\s+)?(?:pending\s+)?(?:schedule|work|tasks?)[^.,;]*[.,;]?",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Check for numbered items (1. ..., 2. ...)
        numbered = re.split(r"\b\d+[\.\)]\s+", text)
        if len(numbered) > 1:
            return [part.strip(" ,;.") for part in numbered if part.strip(" ,;.")]

        # Normalize "I have an X, a Y, and a Z" pattern
        cleaned = re.sub(r"^(?:i have|i've got|there is|there are)\s+", "", text, flags=re.IGNORECASE).strip()

        # Split on coordinating conjunctions, semicolons, newlines, or sentence breaks (e.g. "with high priority. Then write...")
        # Negative lookahead on commas avoids splitting modifier phrases like ", estimate 3 hours, high priority"
        modifiers = (
            r"estimate|takes?|lasting|duration|\d+\s*(?:hours?|hrs?|mins?|minutes?)"
            r"|(?:high|low|medium|critical|urgent|top)\s+priority|priority\s*\d+|urgent|critical"
            r"|contributes\s+to|part\s+of|towards|due|by\s+\w+|after\s+\w+|depends\s+on"
        )
        parts = re.split(rf",(?!\s*(?:{modifiers})\b)\s*(?:and\s+)?|\s+and\s+|;\s*|\n+|\.\s+(?:then\s+|also\s+|next\s+|after\s+that\s+)?|\.\s+(?=[A-Z])", cleaned, flags=re.IGNORECASE)
        clauses = []
        for part in parts:
            p = part.strip(" ,;.")
            if p and len(p) > 2:
                low_p = p.lower()
                if low_p in ("hello", "hi", "hey", "good morning", "can you help me plan something vague?", "can you help me plan something vague"):
                    continue
                if low_p in ("arrange my pending work", "my pending work", "pending work", "pending tasks", "arrange my tasks", "plan my day", "organize my day"):
                    continue
                if re.match(r"^(?:arrange|organize|schedule|plan)\s+(?:my\s+)?(?:pending\s+)?(?:work|tasks?)\b", low_p):
                    continue
                if re.match(r"^(?:hello|hi|hey|good\s+morning|can\s+you\s+help\s+me)\b", low_p) and not any(k in low_p for k in ("due", "exam", "assignment", "project", "task", "review", "hours", "mins", "minute")):
                    continue
                # Skip clauses that are purely available horizon statements
                if re.match(r"^(?:available|free)\s+(?:for\s+)?\d+(?:\.\d+)?\s+hours?\.?$", low_p) or re.match(r"^\d+(?:\.\d+)?\s+hours?\s+(?:available|free)\.?$", low_p):
                    continue
                clauses.append(p)
        return clauses

    def _extract_single_task(self, clause: str, ref_dt: datetime) -> Optional[ExtractedTaskSpec]:
        """Extract task attributes from an isolated clause."""
        raw_clause = clause.strip()
        if not raw_clause:
            return None

        # 1. Deadline extraction
        deadline_expr, deadline_dt, precision = self.parse_deadline(raw_clause, ref_dt)

        # 2. Duration extraction
        dur_hours, dur_source = self._extract_duration(raw_clause)

        # 3. Priority extraction
        priority = self._extract_priority(raw_clause)

        # 4. Scheduling preference (e.g. after lunch, morning)
        pref, min_hour = self._extract_scheduling_preference(raw_clause)

        # 5. Dependencies (e.g. after the assignment, depends on exam)
        dependencies = self._extract_dependencies(raw_clause)

        # 5b. Goal association (e.g. contributes to Graduation goal)
        goal_title = None
        goal_match = re.search(r"(?:contributes to|part of|towards|for)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)\s+goal\b", raw_clause, re.IGNORECASE)
        if goal_match:
            goal_title = goal_match.group(1).strip()

        # 6. Extract clean Title
        title = self._clean_title(raw_clause, deadline_expr)
        if not title:
            return None

        # 7. Infer Task Type
        task_type = self._infer_task_type(title)

        return ExtractedTaskSpec(
            title=title,
            task_type=task_type,
            deadline_expression=deadline_expr,
            deadline_dt=deadline_dt,
            deadline_precision=precision,
            estimated_duration=dur_hours,
            estimated_duration_unit="hours",
            estimated_duration_source=dur_source,
            priority=priority,
            dependencies=dependencies,
            scheduling_preference=pref,
            min_start_hour=min_hour,
            raw_clause=raw_clause,
            origin="proposed",
            goal_title=goal_title,
        )

    def parse_deadline(self, text: str, ref_dt: datetime) -> Tuple[Optional[str], Optional[datetime], Optional[str]]:
        """Parse relative or calendar date expressions relative to reference datetime."""
        lowered = text.lower()

        # "due tomorrow", "tomorrow morning", "tomorrow"
        if "tomorrow" in lowered:
            expr_match = re.search(r"\b(?:due\s+)?tomorrow(?:\s+(morning|afternoon|evening))?\b", lowered)
            expr = expr_match.group(0) if expr_match else "tomorrow"
            target = ref_dt + timedelta(days=1)
            hour = 17  # Default end of workday
            if "morning" in expr:
                hour = 12
            elif "afternoon" in expr:
                hour = 17
            elif "evening" in expr:
                hour = 20
            clean_expr = re.sub(r"^due\s+", "", expr).strip()
            return clean_expr, target.replace(hour=hour, minute=0, second=0, microsecond=0), "day"

        # "in N days" / "in three days"
        days_match = re.search(r"\bin\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\b", lowered)
        if days_match:
            raw_n = days_match.group(1)
            num_days = self.WORD_TO_NUM.get(raw_n, int(raw_n) if raw_n.isdigit() else 1)
            target = ref_dt + timedelta(days=num_days)
            return f"in {num_days} days", target.replace(hour=17, minute=0, second=0, microsecond=0), "relative_days"

        # "next week"
        if "next week" in lowered:
            expr_match = re.search(r"\b(?:due\s+)?next\s+week\b", lowered)
            expr = expr_match.group(0) if expr_match else "next week"
            target = ref_dt + timedelta(days=7)
            clean_expr = re.sub(r"^due\s+", "", expr).strip()
            return clean_expr, target.replace(hour=17, minute=0, second=0, microsecond=0), "week"

        # "today", "tonight", "this afternoon"
        today_match = re.search(r"\b(?:due\s+)?(?:today|tonight|this\s+afternoon|this\s+evening)\b", lowered)
        if today_match:
            expr = today_match.group(0)
            hour = 20 if "tonight" in expr or "evening" in expr else 17
            clean_expr = re.sub(r"^due\s+", "", expr).strip()
            return clean_expr, ref_dt.replace(hour=hour, minute=0, second=0, microsecond=0), "day"

        # Specific calendar date YYYY-MM-DD
        iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
        if iso_match:
            y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
            dt = datetime(y, m, d, 17, 0, 0)
            return iso_match.group(0), dt, "calendar_date"

        # Month Day, e.g. "October 20", "Oct 22", "20th Oct"
        month_words = "|".join(self.MONTH_MAP.keys())
        month_match = re.search(
            rf"\b({month_words})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b|\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_words})\b",
            lowered,
        )
        if month_match:
            if month_match.group(1):
                month_str, day_str = month_match.group(1), month_match.group(2)
            else:
                day_str, month_str = month_match.group(3), month_match.group(4)
            m = self.MONTH_MAP[month_str]
            d = int(day_str)
            y = ref_dt.year
            # If date has already passed this year, assume next year
            cand = datetime(y, m, d, 17, 0, 0)
            if cand < ref_dt.replace(hour=0, minute=0, second=0, microsecond=0):
                cand = datetime(y + 1, m, d, 17, 0, 0)
            return month_match.group(0), cand, "calendar_date"

        # Weekdays: e.g. "due Friday", "by Friday", "on Wednesday", "next Monday"
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        weekday_pattern = "|".join(weekdays.keys())
        w_match = re.search(
            rf"\b(?:due\s+|by\s+|on\s+)?(?:(next)\s+)?({weekday_pattern})(?:\s+(morning|afternoon|evening))?\b",
            lowered,
        )
        if w_match:
            is_next = bool(w_match.group(1))
            w_name = w_match.group(2)
            time_of_day = w_match.group(3)
            target_weekday = weekdays[w_name]
            current_weekday = ref_dt.weekday()
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0 or is_next:
                days_ahead += 7
            target = ref_dt + timedelta(days=days_ahead)
            hour = 17
            if time_of_day == "morning":
                hour = 12
            elif time_of_day == "afternoon":
                hour = 17
            elif time_of_day == "evening":
                hour = 20
            clean_expr = w_match.group(0).strip()
            return clean_expr, target.replace(hour=hour, minute=0, second=0, microsecond=0), "weekday"

        # Time of day: "by 5pm", "by 17:00", "by 5:00 pm"
        time_match = re.search(r"\bby\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
        if time_match:
            hr = int(time_match.group(1))
            mn = int(time_match.group(2) or 0)
            ampm = time_match.group(3)
            if ampm == "pm" and hr < 12:
                hr += 12
            elif ampm == "am" and hr == 12:
                hr = 0
            dt = ref_dt.replace(hour=hr, minute=mn, second=0, microsecond=0)
            return time_match.group(0), dt, "exact_time"

        return None, None, None

    def _extract_duration(self, text: str) -> Tuple[float, str]:
        """Extract duration in hours."""
        lowered = text.lower()
        match = re.search(
            r"(?:duration\s+of|for|lasting|takes?|estimate|approx(?:imately)?|around)?\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b|"
            r"\((\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\)",
            lowered,
        )
        if match:
            groups = [g for g in match.groups() if g is not None]
            if len(groups) >= 2:
                val = float(groups[0])
                unit = groups[1]
                if "min" in unit:
                    return round(val / 60.0, 2), "conversational_input"
                return round(val, 2), "conversational_input"

        # Check for "N-hour", "half hour", "30 mins"
        if "half an hour" in lowered or "half hour" in lowered:
            return 0.5, "conversational_input"

        # Default fallback
        return 1.0, "deterministic_heuristic"

    def _extract_priority(self, text: str) -> int:
        """Extract priority integer 1-5."""
        lowered = text.lower()
        prio_num = re.search(r"\bpriority\s+(\d)\b", lowered)
        if prio_num:
            val = int(prio_num.group(1))
            if 1 <= val <= 5:
                return val

        if any(w in lowered for w in ["critical", "urgent", "asap", "highest priority"]):
            return 5
        if "high priority" in lowered or "important" in lowered or "exam" in lowered:
            return 4
        if "low priority" in lowered or "minor" in lowered:
            return 2
        return 3

    def _extract_scheduling_preference(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """Extract time-of-day preferences (e.g. after lunch -> min_hour 13.0)."""
        lowered = text.lower()
        if "after lunch" in lowered or "in the afternoon" in lowered:
            return "after_lunch", 13.0
        if "in the morning" in lowered or "early morning" in lowered:
            return "morning", 9.0
        if "after 2pm" in lowered or "after 14:00" in lowered:
            return "after_14", 14.0
        if "first thing" in lowered or "start of day" in lowered:
            return "first", 9.0
        return None, None

    def _extract_dependencies(self, text: str) -> List[str]:
        """Extract explicit dependencies mentioned in text."""
        deps = []
        lowered = text.lower()
        match = re.search(r"(?:after|following|depends on)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+(?:due|by|for)|$|[.,;])", lowered)
        if match:
            dep_target = match.group(1).strip()
            if dep_target and len(dep_target) > 2 and dep_target not in ("lunch", "morning", "tomorrow", "today"):
                deps.append(dep_target)
        return deps

    def _clean_title(self, clause: str, deadline_expr: Optional[str]) -> str:
        """Clean clause text into a concise, professional task title."""
        title = clause.strip()

        # Remove leading articles, pronouns, transitions, and action verbs
        title = re.sub(r"^(?:an?\s+|the\s+|my\s+|to\s+|then\s+|also\s+|next\s+|finally\s+|after\s+that\s+|complete\s+(?:my\s+|the\s+)?|finish\s+(?:my\s+|the\s+)?|work\s+on\s+(?:my\s+|the\s+)?)", "", title, flags=re.IGNORECASE).strip()
        # Remove dependency suffix e.g. "after literature review"
        title = re.sub(r"\b(?:after|following|depends on)\s+(?:the\s+)?[a-zA-Z0-9_\-\s]+$", "", title, flags=re.IGNORECASE).strip()

        # Remove goal phrase e.g. "contributes to Graduation goal"
        title = re.sub(r"(?:contributes\s+to|part\s+of|towards|for)\s+(?:the\s+)?[a-zA-Z0-9_\-\s]+?\s+goal\b", "", title, flags=re.IGNORECASE).strip()

        # Remove deadline phrases and relative day remnants
        if deadline_expr:
            title = re.sub(re.escape(deadline_expr), "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\b(?:due|by)\b.*$", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\bin\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\b.*$", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\b(?:next week|tomorrow|today|tonight)\b.*$", "", title, flags=re.IGNORECASE).strip()

        # Remove duration phrases
        title = re.sub(r"(?:duration\s+of|for|lasting|takes?|estimate|approx(?:imately)?|around)?\s*\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?)\b", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\(\s*\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?)\s*\)", "", title, flags=re.IGNORECASE).strip()

        # Remove priority phrases
        title = re.sub(r"\b(?:priority\s+\d+|(?:high|low|medium|critical|urgent|top)\s+priority|urgent|critical|low priority)\b", "", title, flags=re.IGNORECASE).strip()

        # Remove preferences
        title = re.sub(r"\b(?:after lunch|in the morning|in the afternoon)\b", "", title, flags=re.IGNORECASE).strip()

        # Clean punctuation
        title = re.sub(r"^[,\s\-:]+|[,\s\-:]+$", "", title).strip()

        # Title capitalization
        if title:
            # If single word, capitalize
            parts = title.split()
            title = " ".join(p.capitalize() for p in parts)

        return title

    def _infer_task_type(self, title: str) -> str:
        """Infer task category based on keywords."""
        lowered = title.lower()
        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            if any(k in lowered for k in keywords):
                return task_type
        return "general"

    def parse_refinement(self, command: str, current_schedule: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Parse conversational follow-up instructions modifying the current proposal.
        Examples:
        - "Move the assignment ahead of the exam preparation."
        - "Leave 30 minutes for revision."
        - "Start the project work after lunch."
        - "Show me another schedule that prioritizes the exam."
        - "Keep the assignment first but reduce the project time today."
        """
        current_schedule = current_schedule or []
        lowered = command.strip().lower()

        # 0. Available hours adjustment: "I only have two hours available now. Adjust the plan." / "I only have 2 hours now"
        avail_refine_match = re.search(
            r"(?:i\s+)?(?:only\s+have|have\s+only)\s+(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s+hours?(?:\s+available)?(?:\s+now)?|"
            r"\bonly\s+(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s+hours?\s+(?:available|free|left|now)?",
            lowered,
        )
        if avail_refine_match:
            raw_h = next((g for g in avail_refine_match.groups() if g is not None), "2")
            h_val = float(self.WORD_TO_NUM.get(raw_h.lower(), float(raw_h) if raw_h.replace(".", "", 1).isdigit() else 2.0))
            return {
                "action": "reduce_available_hours",
                "new_available_hours": h_val,
                "description": f"Adjust planning horizon to {h_val:g} hour(s)",
            }

        # 1. Reordering: "Move X ahead of Y" / "Move X before Y" / "X ahead of Y"
        reorder_match = re.search(
            r"(?:move|put|place|keep)\s+(?:the\s+)?(.+?)\s+(?:ahead of|before)\s+(?:the\s+)?(.+?)(?:\.|$)",
            lowered,
        )
        if reorder_match:
            task_a = reorder_match.group(1).strip()
            task_b = reorder_match.group(2).strip()
            return {
                "action": "reorder",
                "first_task": task_a,
                "second_task": task_b,
                "description": f"Move '{task_a}' ahead of '{task_b}'",
            }

        # 1b. Move First: "Move the assignment first" / "Put assignment first"
        move_first_match = re.search(
            r"(?:move|put|place|do|keep)\s+(?:the\s+)?(.+?)\s+(?:first|at the top|ahead of everything)(?:\.|$)",
            lowered,
        )
        if move_first_match:
            task_a = move_first_match.group(1).strip()
            return {
                "action": "move_first",
                "task": task_a,
                "description": f"Move '{task_a}' first in schedule",
            }

        # 2. Add Buffer: "Leave 30 minutes for revision"
        buffer_mins, buffer_label = self._extract_buffer(lowered)
        if buffer_mins:
            return {
                "action": "add_buffer",
                "buffer_minutes": buffer_mins,
                "buffer_label": buffer_label or "break",
                "description": f"Add {int(buffer_mins)} min buffer for {buffer_label or 'break'}",
            }

        # 3. Time of day shift: "Start the project work after lunch"
        shift_match = re.search(
            r"(?:start|schedule|move)\s+(?:the\s+)?(.+?)\s+(?:work\s+)?(?:after lunch|at 1pm|at 13:00)",
            lowered,
        )
        if shift_match:
            target_task = shift_match.group(1).strip()
            return {
                "action": "set_start_hour",
                "task": target_task,
                "min_start_hour": 13.0,
                "description": f"Start '{target_task}' after lunch (13:00)",
            }

        # 3b. Alternative Schedule: "Show me another feasible option" / "Show me an alternative plan"
        alt_match = re.search(
            r"\b(?:show(?:\s+me)?\s+(?:another|an\s+alternative)\s+(?:feasible\s+)?(?:option|plan|schedule)|give\s+(?:me\s+)?another\s+(?:option|plan))\b",
            lowered,
        )
        if alt_match and "prioritiz" not in lowered:
            return {
                "action": "alternative_schedule",
                "description": "Generate an alternative feasible schedule",
            }

        # 3c. Accept or Reject Plan via Conversational Follow-up
        if re.search(r"\b(?:accept|approve|confirm)\s+(?:this\s+|the\s+)?plan\b", lowered):
            return {
                "action": "accept_plan",
                "description": "Accept and persist current plan proposal",
            }
        if re.search(r"\b(?:reject|discard|cancel)\s+(?:this\s+|the\s+)?plan\b", lowered):
            return {
                "action": "reject_plan",
                "description": "Reject and discard plan proposal without saving",
            }

        # 4. Reprioritize: "prioritizes the exam" / "prioritize exam" / "Show me another schedule that prioritizes the exam" / "prioritize the exam instead"
        prio_match = re.search(
            r"(?:show(?:\s+me)?\s+another\s+schedule\s+that\s+prioritizes?|prioritizes?|boost)\s+(?:the\s+)?(.+?)(?:\s+instead|\.|$)",
            lowered,
        )
        if prio_match:
            target_task = prio_match.group(1).strip()
            target_task = re.sub(r"\s+instead$", "", target_task).strip()
            return {
                "action": "reprioritize",
                "task": target_task,
                "new_priority": 5,
                "description": f"Boost priority of '{target_task}' to urgent (5)",
            }

        # 5. Reduce duration: "reduce the project time today" / "reduce X duration to 1 hour"
        reduce_match = re.search(
            r"reduce\s+(?:the\s+)?(.+?)\s+(?:time|duration)(?:\s+today)?(?:\s+to\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|minutes?|mins?))?",
            lowered,
        )
        if reduce_match:
            target_task = reduce_match.group(1).strip()
            explicit_dur = reduce_match.group(2)
            new_dur = float(explicit_dur) if explicit_dur else None
            return {
                "action": "reduce_duration",
                "task": target_task,
                "new_duration_hours": new_dur,
                "description": f"Reduce duration of '{target_task}'" + (f" to {new_dur}h" if new_dur else " by 50%"),
            }

        # 6. Ambiguous task adjustment detection
        if re.search(r"\b(?:move\s+the\s+task|adjust\s+the\s+plan|change\s+order|reschedule)\b", lowered) and not any(k in lowered for k in ("ahead of", "before", "first", "after", "hours", "mins", "minute")):
            return {
                "action": "clarification_needed",
                "clarification_question": "Which specific task would you like to move or adjust? Please specify.",
                "description": "Ambiguous adjustment request requiring clarification",
            }

        return {
            "action": "unrecognized",
            "description": "Could not extract specific refinement constraints.",
        }
