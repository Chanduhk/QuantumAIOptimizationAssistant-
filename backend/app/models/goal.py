from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, Integer, String

from .base import Base


class Goal(Base):
    """Persistent goal entity for long-term objectives and planning alignment."""

    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True, default="")
    category = Column(String(100), nullable=True, default="general")
    priority = Column(Integer, nullable=False, default=1)
    target_date = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default="active")  # active, completed, paused, archived
    progress = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=True, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, nullable=True)
