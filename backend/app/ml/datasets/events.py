from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.ml.datasets.models import DataQualityIssue, _datetime, _finite, _freeze_mapping, _safe_text


class EventType(str, Enum):
    """Task events required for leakage-safe duration-ratio datasets."""

    TASK_CREATED = "task_created"
    TASK_SCHEDULED = "task_scheduled"
    TASK_STARTED = "task_started"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    TASK_RESCHEDULED = "task_rescheduled"
    CONTEXT_RECORDED = "context_recorded"


TERMINAL_EVENTS = frozenset({EventType.TASK_COMPLETED, EventType.TASK_FAILED, EventType.TASK_CANCELLED})


@dataclass(frozen=True)
class RawTaskEvent:
    """Immutable raw task event used as F.3 dataset input."""

    event_id: str
    task_id: str
    user_id: str
    event_type: EventType | str
    timestamp: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "task_event_v0.1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _safe_text(self.event_id, "event_id"))
        object.__setattr__(self, "task_id", _safe_text(self.task_id, "task_id"))
        object.__setattr__(self, "user_id", _safe_text(self.user_id, "user_id"))
        try:
            event_type = self.event_type if isinstance(self.event_type, EventType) else EventType(str(self.event_type))
        except ValueError as exc:
            raise ValueError("event_type is not supported.") from exc
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "timestamp", _datetime(self.timestamp, "timestamp"))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))
        object.__setattr__(self, "schema_version", _safe_text(self.schema_version, "schema_version"))
        self._validate_payload()

    def _validate_payload(self) -> None:
        if self.event_type in {EventType.TASK_CREATED, EventType.TASK_SCHEDULED, EventType.TASK_RESCHEDULED}:
            if "estimated_duration_minutes" in self.payload:
                estimated = _finite(self.payload["estimated_duration_minutes"], "estimated_duration_minutes")
                if estimated <= 0:
                    raise ValueError("estimated_duration_minutes must be positive.")
            if "priority" in self.payload:
                priority = int(self.payload["priority"])
                if priority < 1 or priority > 5:
                    raise ValueError("priority must be between 1 and 5.")
        if self.event_type is EventType.TASK_COMPLETED and "actual_duration_minutes" in self.payload:
            actual = _finite(self.payload["actual_duration_minutes"], "actual_duration_minutes")
            if actual < 0:
                raise ValueError("actual_duration_minutes cannot be negative.")


@dataclass(frozen=True)
class CanonicalEventHistory:
    """Immutable task event history after deterministic normalization."""

    task_id: str
    user_id: str
    events: tuple[RawTaskEvent, ...]
    issues: tuple[DataQualityIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _safe_text(self.task_id, "task_id"))
        object.__setattr__(self, "user_id", _safe_text(self.user_id, "user_id"))
        if not isinstance(self.events, tuple) or not self.events:
            raise ValueError("events must be a non-empty tuple.")
        if any(not isinstance(event, RawTaskEvent) for event in self.events):
            raise ValueError("events must contain RawTaskEvent instances.")
        ordered = tuple(sorted(self.events, key=lambda event: (event.timestamp, event.event_id)))
        if any(event.task_id != self.task_id for event in ordered):
            raise ValueError("all events must share task_id.")
        if any(event.user_id != self.user_id for event in ordered):
            raise ValueError("all events must share user_id.")
        object.__setattr__(self, "events", ordered)
        if not isinstance(self.issues, tuple):
            raise ValueError("issues must be a tuple.")


class EventHistoryBuilder:
    """Build canonical histories while rejecting duplicate IDs and invalid ordering."""

    def build(self, events: tuple[RawTaskEvent, ...]) -> tuple[CanonicalEventHistory, ...]:
        """Return deterministic canonical task histories."""

        if not isinstance(events, tuple):
            raise ValueError("events must be a tuple.")
        seen_ids: set[str] = set()
        grouped: dict[tuple[str, str], list[RawTaskEvent]] = {}
        for event in events:
            if not isinstance(event, RawTaskEvent):
                raise ValueError("events must contain RawTaskEvent instances.")
            if event.event_id in seen_ids:
                raise ValueError(f"duplicate event_id: {event.event_id}.")
            seen_ids.add(event.event_id)
            grouped.setdefault((event.user_id, event.task_id), []).append(event)
        histories = []
        for (user_id, task_id), task_events in sorted(grouped.items()):
            ordered = tuple(sorted(task_events, key=lambda event: (event.timestamp, event.event_id)))
            issues = self._validate_transitions(ordered)
            histories.append(CanonicalEventHistory(task_id=task_id, user_id=user_id, events=ordered, issues=issues))
        return tuple(histories)

    @staticmethod
    def _validate_transitions(events: tuple[RawTaskEvent, ...]) -> tuple[DataQualityIssue, ...]:
        issues: list[DataQualityIssue] = []
        terminal_seen: RawTaskEvent | None = None
        started = False
        paused = False
        for event in events:
            if terminal_seen is not None and event.timestamp > terminal_seen.timestamp:
                issues.append(DataQualityIssue("ERROR", "EVENT_AFTER_TERMINAL", "event occurs after terminal outcome", event.task_id, event.event_id))
            if event.event_type is EventType.TASK_STARTED:
                started = True
                paused = False
            if event.event_type is EventType.TASK_PAUSED:
                if not started or paused:
                    issues.append(DataQualityIssue("ERROR", "INVALID_PAUSE", "pause requires an active started task", event.task_id, event.event_id))
                paused = True
            if event.event_type is EventType.TASK_RESUMED:
                if not paused:
                    issues.append(DataQualityIssue("ERROR", "INVALID_RESUME", "resume requires a paused task", event.task_id, event.event_id))
                paused = False
            if event.event_type in TERMINAL_EVENTS:
                if terminal_seen is not None:
                    issues.append(DataQualityIssue("ERROR", "DUPLICATE_TERMINAL", "multiple terminal outcomes found", event.task_id, event.event_id))
                terminal_seen = event
        return tuple(issues)


def thaw_payload(event: RawTaskEvent) -> dict[str, Any]:
    """Return a mutable copy of event payload for internal calculations."""

    return {key: event.payload[key] for key in event.payload}
