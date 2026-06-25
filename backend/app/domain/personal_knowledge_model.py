from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class KnowledgeNode:
    """In-memory node for the evolving personal knowledge graph."""

    node_id: str
    node_type: str
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.node_id = _required_text(self.node_id, "node_id")
        self.node_type = _required_text(self.node_type, "node_type").lower()
        self.name = _required_text(self.name, "name")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary.")
        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime.")
        if not isinstance(self.updated_at, datetime):
            raise ValueError("updated_at must be a datetime.")


@dataclass
class KnowledgeRelationship:
    """Directed relationship between two personal knowledge nodes."""

    relationship_id: str
    source_id: str
    target_id: str
    relationship_type: str
    strength: float = 1.0

    def __post_init__(self) -> None:
        self.relationship_id = _required_text(self.relationship_id, "relationship_id")
        self.source_id = _required_text(self.source_id, "source_id")
        self.target_id = _required_text(self.target_id, "target_id")
        self.relationship_type = _required_text(self.relationship_type, "relationship_type").lower()
        if self.source_id == self.target_id:
            raise ValueError("source_id and target_id must differ.")
        self.strength = _bounded_float(self.strength, "strength", 0.0, 1.0)


@dataclass
class KnowledgeInsight:
    """Deterministic insight derived from recurring personal knowledge patterns."""

    insight_id: str
    category: str
    description: str
    confidence: float
    related_nodes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.insight_id = _required_text(self.insight_id, "insight_id")
        self.category = _required_text(self.category, "category").lower()
        self.description = _required_text(self.description, "description")
        self.confidence = _bounded_float(self.confidence, "confidence", 0.0, 1.0)
        self.related_nodes = _string_list(self.related_nodes, "related_nodes")


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
