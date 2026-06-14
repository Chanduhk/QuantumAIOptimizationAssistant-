from __future__ import annotations

from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.engines.learning_engine import LearningEngine
from backend.app.engines.optimization_engine import OptimizationEngine
from backend.app.engines.planning_engine import PlanningEngine
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.engines.scheduling_engine import SchedulingEngine
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine


class EngineRegistry:
    """Lazy engine registry for the Quantum Life AI backend.

    The registry holds one SQLAlchemy session for the current request and
    initializes engine instances only when a caller actually needs them.
    """

    def __init__(self, session: Session) -> None:
        # The session is shared with any engine that needs database access.
        self.session = session

        # Engines are created on demand to avoid unnecessary memory usage.
        self._behavior_engine: Optional[BehaviorIntelligenceEngine] = None
        self._planning_engine: Optional[PlanningEngine] = None
        self._scheduling_engine: Optional[SchedulingEngine] = None
        self._decision_engine: Optional[DecisionEngine] = None
        self._prediction_engine: Optional[PredictionEngine] = None
        self._optimization_engine: Optional[OptimizationEngine] = None
        self._learning_engine: Optional[LearningEngine] = None

    def get_behavior_engine(self) -> BehaviorIntelligenceEngine:
        """Return the shared behavior engine instance."""
        if self._behavior_engine is None:
            self._behavior_engine = BehaviorIntelligenceEngine(session=self.session)
        return self._behavior_engine

    def get_planning_engine(self) -> PlanningEngine:
        """Return the planning engine instance."""
        if self._planning_engine is None:
            self._planning_engine = PlanningEngine()
        return self._planning_engine

    def get_scheduling_engine(self) -> SchedulingEngine:
        """Return the scheduling engine instance."""
        if self._scheduling_engine is None:
            self._scheduling_engine = SchedulingEngine()
        return self._scheduling_engine

    def get_decision_engine(self) -> DecisionEngine:
        """Return the decision engine instance."""
        if self._decision_engine is None:
            self._decision_engine = DecisionEngine()
        return self._decision_engine

    def get_prediction_engine(self) -> PredictionEngine:
        """Return the prediction engine instance."""
        if self._prediction_engine is None:
            self._prediction_engine = PredictionEngine()
        return self._prediction_engine

    def get_optimization_engine(self) -> OptimizationEngine:
        """Return the optimization engine instance."""
        if self._optimization_engine is None:
            self._optimization_engine = OptimizationEngine()
        return self._optimization_engine

    def get_learning_engine(self) -> LearningEngine:
        """Return the learning engine instance."""
        if self._learning_engine is None:
            self._learning_engine = LearningEngine()
        return self._learning_engine


def get_engine_registry(db: Session = Depends(get_db)) -> EngineRegistry:
    """FastAPI dependency that provides a per-request engine registry."""
    return EngineRegistry(session=db)
