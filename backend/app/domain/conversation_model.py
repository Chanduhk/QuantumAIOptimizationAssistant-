from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


VALID_ROLES = {"user", "assistant", "system"}


@dataclass
class ConversationTurn:
    """Single in-memory conversation turn."""

    turn_id: str
    role: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    intent: str = "general_question"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.turn_id = _required_text(self.turn_id, "turn_id")
        self.role = _role(self.role)
        self.message = _required_text(self.message, "message")
        self.intent = _required_text(self.intent, "intent")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary.")


@dataclass
class ConversationContext:
    """Bounded in-memory context for one conversation."""

    conversation_id: str
    active_goal_ids: List[str] = field(default_factory=list)
    active_topics: List[str] = field(default_factory=list)
    recent_intents: List[str] = field(default_factory=list)
    memory_references: List[str] = field(default_factory=list)
    conversation_summary: str = ""

    def __post_init__(self) -> None:
        self.conversation_id = _required_text(self.conversation_id, "conversation_id")
        self.active_goal_ids = _string_list(self.active_goal_ids, "active_goal_ids")
        self.active_topics = _string_list(self.active_topics, "active_topics")
        self.recent_intents = _string_list(self.recent_intents, "recent_intents")
        self.memory_references = _string_list(self.memory_references, "memory_references")
        if not isinstance(self.conversation_summary, str):
            raise ValueError("conversation_summary must be a string.")


@dataclass
class ExplanationResult:
    """Human-readable explanation generated from structured intelligence outputs."""

    explanation_type: str
    title: str
    summary: str
    key_factors: List[str]
    recommendations: List[str]
    confidence: float

    def __post_init__(self) -> None:
        self.explanation_type = _required_text(self.explanation_type, "explanation_type")
        self.title = _required_text(self.title, "title")
        self.summary = _required_text(self.summary, "summary")
        self.key_factors = _string_list(self.key_factors, "key_factors")
        self.recommendations = _string_list(self.recommendations, "recommendations")
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)


@dataclass
class ClarificationQuestion:
    """Question used when deterministic context is insufficient."""

    question: str
    reason: str
    priority: int

    def __post_init__(self) -> None:
        self.question = _required_text(self.question, "question")
        self.reason = _required_text(self.reason, "reason")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority <= 0:
            raise ValueError("priority must be a positive integer.")


def _role(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("role must be user, assistant, or system.")
    normalized = value.strip().lower()
    if normalized not in VALID_ROLES:
        raise ValueError("role must be user, assistant, or system.")
    return normalized


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _string_list(value: object, field_name: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    return sorted(dict.fromkeys(item.strip() for item in value if item.strip()))


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return max(minimum, min(maximum, number))
