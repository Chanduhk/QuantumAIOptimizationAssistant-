from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class BehaviorData(Base):
    """Derived features used for pattern analysis and model training."""

    __tablename__ = "behavior_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    hour_of_day = Column(Integer, nullable=False)
    task_type = Column(String(100), nullable=False)
    duration = Column(Float, nullable=False)
    focus_score = Column(Float, nullable=False)
    energy_level = Column(Float, nullable=False)
    completion_time = Column(Float, nullable=False)
    productivity_score = Column(Float, nullable=False)

    task = relationship("Task", back_populates="behavior_records")
