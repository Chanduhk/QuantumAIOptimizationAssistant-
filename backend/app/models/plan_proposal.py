from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from .base import Base


class PlanProposal(Base):
    """
    Authoritative database-backed plan proposal.
    Survives backend restarts and multi-worker execution.
    Maintains explicit UUID identity, versioning, ownership, lifecycle status,
    full schedule payload, and provenance metadata.
    """

    __tablename__ = "plan_proposals"

    id = Column(String(36), primary_key=True, index=True)  # UUID v4
    user_id = Column(Integer, nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="PROPOSED", index=True)  # PROPOSED, ACCEPTED, REJECTED, EXPIRED
    goal_text = Column(Text, nullable=True)
    available_hours = Column(Float, nullable=True, default=8.0)
    
    # Serialized JSON text for cross-database compatibility (SQLite, Postgres)
    schedule_data = Column(Text, nullable=False, default="[]")
    tasks_data = Column(Text, nullable=False, default="[]")
    constraints_data = Column(Text, nullable=True, default="{}")
    provenance_data = Column(Text, nullable=True, default="{}")
    raw_result_data = Column(Text, nullable=True, default="{}")
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    expires_at = Column(DateTime, nullable=False, index=True)

    @property
    def schedule(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.schedule_data) if self.schedule_data else []
        except Exception:
            return []

    @schedule.setter
    def schedule(self, value: List[Dict[str, Any]]) -> None:
        self.schedule_data = json.dumps(value or [], default=str)

    @property
    def tasks(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.tasks_data) if self.tasks_data else []
        except Exception:
            return []

    @tasks.setter
    def tasks(self, value: List[Dict[str, Any]]) -> None:
        self.tasks_data = json.dumps(value or [], default=str)

    @property
    def constraints(self) -> Dict[str, Any]:
        try:
            return json.loads(self.constraints_data) if self.constraints_data else {}
        except Exception:
            return {}

    @constraints.setter
    def constraints(self, value: Dict[str, Any]) -> None:
        self.constraints_data = json.dumps(value or {}, default=str)

    @property
    def provenance(self) -> Dict[str, Any]:
        try:
            return json.loads(self.provenance_data) if self.provenance_data else {}
        except Exception:
            return {}

    @provenance.setter
    def provenance(self, value: Dict[str, Any]) -> None:
        self.provenance_data = json.dumps(value or {}, default=str)

    @property
    def raw_result(self) -> Dict[str, Any]:
        try:
            return json.loads(self.raw_result_data) if self.raw_result_data else {}
        except Exception:
            return {}

    @raw_result.setter
    def raw_result(self, value: Dict[str, Any]) -> None:
        self.raw_result_data = json.dumps(value or {}, default=str)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "version": self.version,
            "status": self.status,
            "goal_text": self.goal_text,
            "available_hours": self.available_hours,
            "schedule": self.schedule,
            "tasks": self.tasks,
            "constraints": self.constraints,
            "provenance": self.provenance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
