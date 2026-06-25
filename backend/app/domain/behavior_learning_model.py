from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class BehaviorObservation:
    """Single behavioral observation recorded by the continuous learning system."""

    observation_id: str
    observation_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    productivity_score: float = 0.0
    hour_of_day: int | None = None
    task_type: str = "general"
    goal_id: str | None = None
    completed: bool = False
    deferred: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.observation_id = _required_text(self.observation_id, "observation_id")
        self.observation_type = _required_text(self.observation_type, "observation_type").lower()
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")
        self.productivity_score = _bounded_float(self.productivity_score, "productivity_score", 0.0, 100.0)
        if self.hour_of_day is not None:
            self.hour_of_day = _hour(self.hour_of_day, "hour_of_day")
        self.task_type = _required_text(self.task_type, "task_type").lower()
        if self.goal_id is not None:
            self.goal_id = _required_text(self.goal_id, "goal_id")
        if not isinstance(self.completed, bool):
            raise ValueError("completed must be a boolean.")
        if not isinstance(self.deferred, bool):
            raise ValueError("deferred must be a boolean.")
        self.metadata = _dict(self.metadata, "metadata")


@dataclass
class BehaviorPattern:
    """Learned recurring behavior pattern."""

    pattern_id: str
    pattern_type: str
    description: str
    confidence: float
    evidence_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.pattern_id = _required_text(self.pattern_id, "pattern_id")
        self.pattern_type = _required_text(self.pattern_type, "pattern_type").lower()
        self.description = _required_text(self.description, "description")
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        if not isinstance(self.evidence_count, int) or isinstance(self.evidence_count, bool) or self.evidence_count < 0:
            raise ValueError("evidence_count must be a non-negative integer.")
        self.metadata = _dict(self.metadata, "metadata")


@dataclass
class BehaviorTrend:
    """Directional trend inferred from behavioral history."""

    trend_id: str
    trend_type: str
    direction: str
    strength: float
    evidence: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.trend_id = _required_text(self.trend_id, "trend_id")
        self.trend_type = _required_text(self.trend_type, "trend_type").lower()
        self.direction = _choice(self.direction, "direction", {"improving", "declining", "stable", "insufficient_data"})
        self.strength = _bounded_float(self.strength, "strength", 0.0, 1.0)
        self.evidence = _string_list(self.evidence, "evidence")


@dataclass
class BehaviorInsight:
    """Actionable learned insight derived from observations, patterns, and trends."""

    insight_id: str
    title: str
    confidence: float
    evidence: List[str]
    recommendation: str

    def __post_init__(self) -> None:
        self.insight_id = _required_text(self.insight_id, "insight_id")
        self.title = _required_text(self.title, "title")
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        self.evidence = _string_list(self.evidence, "evidence")
        self.recommendation = _required_text(self.recommendation, "recommendation")


@dataclass
class LearningSnapshot:
    """Summary snapshot of learned behavioral state."""

    snapshot_id: str
    period: str
    observation_count: int
    patterns: List[BehaviorPattern | Dict[str, Any]]
    trends: List[BehaviorTrend | Dict[str, Any]]
    insights: List[BehaviorInsight | Dict[str, Any]]
    consistency_score: float
    habit_strength: float
    behavior_volatility: float
    learning_confidence: float
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.snapshot_id = _required_text(self.snapshot_id, "snapshot_id")
        self.period = _choice(self.period, "period", {"weekly", "monthly"})
        if not isinstance(self.observation_count, int) or isinstance(self.observation_count, bool) or self.observation_count < 0:
            raise ValueError("observation_count must be a non-negative integer.")
        self.patterns = [item if isinstance(item, BehaviorPattern) else BehaviorPattern(**item) for item in self.patterns]
        self.trends = [item if isinstance(item, BehaviorTrend) else BehaviorTrend(**item) for item in self.trends]
        self.insights = [item if isinstance(item, BehaviorInsight) else BehaviorInsight(**item) for item in self.insights]
        self.consistency_score = _bounded_float(self.consistency_score, "consistency_score", 0.0, 100.0)
        self.habit_strength = _bounded_float(self.habit_strength, "habit_strength", 0.0, 100.0)
        self.behavior_volatility = _bounded_float(self.behavior_volatility, "behavior_volatility", 0.0, 100.0)
        self.learning_confidence = _bounded_float(self.learning_confidence, "learning_confidence", 0.0, 1.0)
        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime.")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return max(minimum, min(maximum, number))


def _hour(value: object, field_name: str) -> int:
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


def _choice(value: object, field_name: str, choices: set[str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be one of {', '.join(sorted(choices))}.")
    normalized = value.strip().lower()
    if normalized not in choices:
        raise ValueError(f"{field_name} must be one of {', '.join(sorted(choices))}.")
    return normalized


def _string_list(value: object, field_name: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    return sorted(dict.fromkeys(item.strip() for item in value if item.strip()))


def _dict(value: object, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")
    return dict(value)
