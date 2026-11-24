from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class Task(Base):
    """Task history captured by the assistant for behavior analysis."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    task_type = Column(String(100), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=3)
    deadline = Column(DateTime, nullable=True, index=True)
    dependencies = Column(String(500), nullable=True)
    goal_id = Column(Integer, nullable=True, index=True)
    context_info = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=True, index=True)
    lifecycle_state = Column(String(32), nullable=True, index=True)
    estimated_duration = Column(Float, nullable=True)
    estimated_duration_unit = Column(String(16), nullable=True)
    estimated_duration_source = Column(String(64), nullable=True)
    actual_duration = Column(Float, nullable=True)
    start_time = Column(DateTime, nullable=True, index=True)
    end_time = Column(DateTime, nullable=True)
    scheduled_start_time = Column(DateTime, nullable=True, index=True)
    scheduled_end_time = Column(DateTime, nullable=True)
    reschedule_count = Column(Integer, nullable=False, default=0)
    completed = Column(Boolean, nullable=False, default=False, index=True)
    outcome_valid = Column(Boolean, nullable=True)
    focus_rating = Column(Float, nullable=True)
    energy_rating = Column(Float, nullable=True)
    productivity_rating = Column(Float, nullable=True)
    feedback_notes = Column(String(1000), nullable=True)
    feedback_submitted_at = Column(DateTime, nullable=True)

    behavior_records = relationship(
        "BehaviorData",
        back_populates="task",
        cascade="all, delete-orphan",
    )
