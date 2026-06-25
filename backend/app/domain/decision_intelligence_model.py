from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class DecisionOption:
    """A candidate decision option to evaluate."""

    option_id: str
    title: str
    description: str = ""
    expected_benefit: float = 50.0
    estimated_cost: float = 0.0
    estimated_effort: float = 0.0
    goal_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.option_id = _required_text(self.option_id, "option_id")
        self.title = _required_text(self.title, "title")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")
        self.expected_benefit = _bounded_float(self.expected_benefit, "expected_benefit", 0.0, 100.0)
        self.estimated_cost = _bounded_float(self.estimated_cost, "estimated_cost", 0.0, 100.0)
        self.estimated_effort = _bounded_float(self.estimated_effort, "estimated_effort", 0.0, 100.0)
        self.goal_ids = _string_list(self.goal_ids, "goal_ids")
        self.metadata = _dict(self.metadata, "metadata")


@dataclass
class DecisionEvaluation:
    """Bounded score set for one decision option."""

    option_id: str
    utility_score: float
    risk_score: float
    confidence_score: float
    alignment_score: float
    overall_score: float
    evidence: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.option_id = _required_text(self.option_id, "option_id")
        self.utility_score = _bounded_float(self.utility_score, "utility_score", 0.0, 100.0)
        self.risk_score = _bounded_float(self.risk_score, "risk_score", 0.0, 100.0)
        self.confidence_score = _bounded_float(self.confidence_score, "confidence_score", 0.0, 100.0)
        self.alignment_score = _bounded_float(self.alignment_score, "alignment_score", 0.0, 100.0)
        self.overall_score = _bounded_float(self.overall_score, "overall_score", 0.0, 100.0)
        self.evidence = _string_list(self.evidence, "evidence")


@dataclass
class DecisionTradeoff:
    """Benefit-cost-risk-effort tradeoff for one option."""

    tradeoff_id: str
    option_id: str
    benefit: float
    cost: float
    risk: float
    effort: float
    alignment: float
    confidence: float

    def __post_init__(self) -> None:
        self.tradeoff_id = _required_text(self.tradeoff_id, "tradeoff_id")
        self.option_id = _required_text(self.option_id, "option_id")
        self.benefit = _bounded_float(self.benefit, "benefit", 0.0, 100.0)
        self.cost = _bounded_float(self.cost, "cost", 0.0, 100.0)
        self.risk = _bounded_float(self.risk, "risk", 0.0, 100.0)
        self.effort = _bounded_float(self.effort, "effort", 0.0, 100.0)
        self.alignment = _bounded_float(self.alignment, "alignment", 0.0, 100.0)
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)


@dataclass
class DecisionRecommendation:
    """Recommendation produced from evaluated options."""

    recommendation_id: str
    recommendation_type: str
    option_id: str
    title: str
    reasoning: str
    confidence: float
    priority: int

    def __post_init__(self) -> None:
        self.recommendation_id = _required_text(self.recommendation_id, "recommendation_id")
        self.recommendation_type = _required_text(self.recommendation_type, "recommendation_type").lower()
        self.option_id = _required_text(self.option_id, "option_id")
        self.title = _required_text(self.title, "title")
        self.reasoning = _required_text(self.reasoning, "reasoning")
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority <= 0:
            raise ValueError("priority must be a positive integer.")


@dataclass
class DecisionAnalysis:
    """Complete deterministic decision analysis result."""

    analysis_id: str
    options: List[DecisionOption | Dict[str, Any]]
    evaluations: List[DecisionEvaluation | Dict[str, Any]]
    tradeoffs: List[DecisionTradeoff | Dict[str, Any]]
    recommendations: List[DecisionRecommendation | Dict[str, Any]]
    ranking: List[str]
    executive_summary: str
    confidence: float
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.analysis_id = _required_text(self.analysis_id, "analysis_id")
        self.options = [item if isinstance(item, DecisionOption) else DecisionOption(**item) for item in self.options]
        self.evaluations = [
            item if isinstance(item, DecisionEvaluation) else DecisionEvaluation(**item)
            for item in self.evaluations
        ]
        self.tradeoffs = [item if isinstance(item, DecisionTradeoff) else DecisionTradeoff(**item) for item in self.tradeoffs]
        self.recommendations = [
            item if isinstance(item, DecisionRecommendation) else DecisionRecommendation(**item)
            for item in self.recommendations
        ]
        self.ranking = _ordered_string_list(self.ranking, "ranking")
        self.executive_summary = _required_text(self.executive_summary, "executive_summary")
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
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


def _string_list(value: object, field_name: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    return sorted(dict.fromkeys(item.strip() for item in value if item.strip()))


def _ordered_string_list(value: object, field_name: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings.")
    ordered: List[str] = []
    seen = set()
    for item in value:
        normalized = item.strip()
        if normalized and normalized not in seen:
            ordered.append(normalized)
            seen.add(normalized)
    return ordered


def _dict(value: object, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")
    return dict(value)
