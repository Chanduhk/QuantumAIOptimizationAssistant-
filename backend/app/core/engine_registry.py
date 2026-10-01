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

        # F7.2 Added Dependencies
        self._memory_system = None
        self._context_engine = None
        self._rl_scheduler = None
        self._feature_store = None
        self._ai_monitor = None
        self._knowledge_graph = None
        self._cognitive_engine = None

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

    def get_memory_system(self):
        if self._memory_system is None:
            from backend.app.memory import VectorMemorySystem
            self._memory_system = VectorMemorySystem()
        return self._memory_system

    def get_context_engine(self):
        if self._context_engine is None:
            from backend.app.context import ContextEngine
            self._context_engine = ContextEngine(memory_system=self.get_memory_system())
        return self._context_engine

    def get_rl_scheduler(self):
        if self._rl_scheduler is None:
            from backend.app.ai_rl import RLScheduler
            self._rl_scheduler = RLScheduler()
        return self._rl_scheduler

    def get_feature_store(self):
        if self._feature_store is None:
            from backend.app.ml import FeatureStore
            self._feature_store = FeatureStore()
        return self._feature_store

    def get_ai_monitor(self):
        if self._ai_monitor is None:
            from backend.app.monitoring import AIMonitor
            self._ai_monitor = AIMonitor()
        return self._ai_monitor

    def get_knowledge_graph(self):
        if self._knowledge_graph is None:
            from backend.app.knowledge import AIKnowledgeGraph
            self._knowledge_graph = AIKnowledgeGraph()
        return self._knowledge_graph

    def get_goal_intelligence_engine(self):
        if not hasattr(self, "_goal_intelligence_engine"):
            from backend.app.engines.goal_intelligence_engine import GoalIntelligenceEngine
            self._goal_intelligence_engine = GoalIntelligenceEngine()
        return self._goal_intelligence_engine

    def get_dependency_intelligence_engine(self):
        if not hasattr(self, "_dependency_intelligence_engine"):
            from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine
            self._dependency_intelligence_engine = DependencyIntelligenceEngine()
        return self._dependency_intelligence_engine

    def get_future_simulation_engine(self):
        if not hasattr(self, "_future_simulation_engine"):
            from backend.app.engines.future_simulation_engine import FutureSimulationEngine
            self._future_simulation_engine = FutureSimulationEngine()
        return self._future_simulation_engine

    def get_strategic_planning_engine(self):
        if not hasattr(self, "_strategic_planning_engine"):
            from backend.app.engines.strategic_planning_engine import StrategicPlanningEngine
            self._strategic_planning_engine = StrategicPlanningEngine()
        return self._strategic_planning_engine

    def get_cognitive_engine(self):
        if self._cognitive_engine is None:
            from backend.app.cognitive import CognitiveEngine
            self._cognitive_engine = CognitiveEngine(
                behavior_engine=self.get_behavior_engine(),
                knowledge_graph=self.get_knowledge_graph()
            )
        return self._cognitive_engine

def get_engine_registry(db: Session = Depends(get_db)) -> EngineRegistry:
    """FastAPI dependency that provides a per-request engine registry."""
    return EngineRegistry(session=db)
