from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class PlanObjective:
    """Top-level objective the autonomous planning agent can decompose."""

    objective_id: str
    title: str
    priority: int = 1
    goal_id: str | None = None
    success_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.objective_id = _required_text(self.objective_id, "objective_id")
        self.title = _required_text(self.title, "title")
        self.priority = _positive_int(self.priority, "priority")
        if self.goal_id is not None:
            self.goal_id = _required_text(self.goal_id, "goal_id")
        self.success_criteria = _string_list(self.success_criteria, "success_criteria")
        self.metadata = _dict(self.metadata, "metadata")


@dataclass
class PlanMilestone:
    """Milestone generated beneath a plan objective."""

    milestone_id: str
    objective_id: str
    title: str
    sequence: int
    progress: float = 0.0
    status: str = "planned"

    def __post_init__(self) -> None:
        self.milestone_id = _required_text(self.milestone_id, "milestone_id")
        self.objective_id = _required_text(self.objective_id, "objective_id")
        self.title = _required_text(self.title, "title")
        self.sequence = _positive_int(self.sequence, "sequence")
        self.progress = _bounded_float(self.progress, "progress", 0.0, 100.0)
        self.status = _required_text(self.status, "status").lower()


@dataclass
class PlanTask:
    """Executable recommended task generated beneath a milestone."""

    task_id: str
    milestone_id: str
    title: str
    sequence: int
    estimated_duration: float = 1.0
    priority: int = 1
    blocked: bool = False
    reasoning: str = ""

    def __post_init__(self) -> None:
        self.task_id = _required_text(self.task_id, "task_id")
        self.milestone_id = _required_text(self.milestone_id, "milestone_id")
        self.title = _required_text(self.title, "title")
        self.sequence = _positive_int(self.sequence, "sequence")
        self.estimated_duration = _bounded_float(self.estimated_duration, "estimated_duration", 0.1, 24.0)
        self.priority = _positive_int(self.priority, "priority")
        if not isinstance(self.blocked, bool):
            raise ValueError("blocked must be a boolean.")
        if not isinstance(self.reasoning, str):
            raise ValueError("reasoning must be a string.")


@dataclass
class RecoveryPlan:
    """Recommended recovery plan for at-risk or blocked progress."""

    recovery_plan_id: str
    trigger: str
    actions: List[str]
    priority: int
    expected_impact: float
    reasoning: str

    def __post_init__(self) -> None:
        self.recovery_plan_id = _required_text(self.recovery_plan_id, "recovery_plan_id")
        self.trigger = _required_text(self.trigger, "trigger")
        self.actions = _string_list(self.actions, "actions")
        if not self.actions:
            raise ValueError("actions must not be empty.")
        self.priority = _positive_int(self.priority, "priority")
        self.expected_impact = _bounded_float(self.expected_impact, "expected_impact", 0.0, 100.0)
        self.reasoning = _required_text(self.reasoning, "reasoning")


@dataclass
class ContingencyPlan:
    """Alternative non-executing plan for plausible future conditions."""

    contingency_plan_id: str
    scenario: str
    actions: List[str]
    risk_score: float
    confidence_score: float

    def __post_init__(self) -> None:
        self.contingency_plan_id = _required_text(self.contingency_plan_id, "contingency_plan_id")
        self.scenario = _required_text(self.scenario, "scenario")
        self.actions = _string_list(self.actions, "actions")
        if not self.actions:
            raise ValueError("actions must not be empty.")
        self.risk_score = _bounded_float(self.risk_score, "risk_score", 0.0, 100.0)
        self.confidence_score = _bounded_float(self.confidence_score, "confidence_score", 0.0, 100.0)


@dataclass
class AutonomousPlan:
    """Complete recommended plan hierarchy with quality scores and explanation."""

    plan_id: str
    objective: PlanObjective | Dict[str, Any]
    milestones: List[PlanMilestone | Dict[str, Any]]
    tasks: List[PlanTask | Dict[str, Any]]
    feasibility_score: float
    dependency_score: float
    risk_score: float
    goal_alignment_score: float
    overall_plan_score: float
    reasoning: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.plan_id = _required_text(self.plan_id, "plan_id")
        self.objective = self.objective if isinstance(self.objective, PlanObjective) else PlanObjective(**self.objective)
        self.milestones = [
            milestone if isinstance(milestone, PlanMilestone) else PlanMilestone(**milestone)
            for milestone in self.milestones
        ]
        self.tasks = [
            task if isinstance(task, PlanTask) else PlanTask(**task)
            for task in self.tasks
        ]
        self.feasibility_score = _bounded_float(self.feasibility_score, "feasibility_score", 0.0, 100.0)
        self.dependency_score = _bounded_float(self.dependency_score, "dependency_score", 0.0, 100.0)
        self.risk_score = _bounded_float(self.risk_score, "risk_score", 0.0, 100.0)
        self.goal_alignment_score = _bounded_float(self.goal_alignment_score, "goal_alignment_score", 0.0, 100.0)
        self.overall_plan_score = _bounded_float(self.overall_plan_score, "overall_plan_score", 0.0, 100.0)
        self.reasoning = _required_text(self.reasoning, "reasoning")
        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime.")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive integer.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a positive integer.") from None
    if not math.isfinite(number) or not number.is_integer() or number <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return int(number)


def _bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return max(minimum, min(maximum, number))


def _string_list(value: object, field_name: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    return sorted(dict.fromkeys(item.strip() for item in value if item.strip()))


def _dict(value: object, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")
    return dict(value)
