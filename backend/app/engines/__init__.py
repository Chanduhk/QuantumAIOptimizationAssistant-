"""Engines package - AI decision-making and optimization engines.

Import directly from submodules:
    from backend.app.engines.brain_workflow import QuantumLifeBrain
    from backend.app.engines.decision_engine import DecisionEngine
    from backend.app.engines.learning_engine import LearningEngine
    from backend.app.engines.optimization_engine import OptimizationEngine
    from backend.app.engines.planning_engine import PlanningEngine
    from backend.app.engines.prediction_engine import PredictionEngine
    from backend.app.engines.scheduling_engine import SchedulingEngine
"""

from backend.app.engines.adaptive_life_operating_system import AdaptiveLifeOperatingSystem  # noqa: F401
from backend.app.engines.conversational_intelligence_engine import ConversationalIntelligenceEngine  # noqa: F401
from backend.app.engines.dependency_intelligence_engine import DependencyIntelligenceEngine  # noqa: F401
from backend.app.engines.future_simulation_engine import FutureSimulationEngine  # noqa: F401
from backend.app.engines.goal_intelligence_engine import GoalIntelligenceEngine  # noqa: F401
from backend.app.engines.meta_cognitive_engine import MetaCognitiveEngine  # noqa: F401
from backend.app.engines.multi_objective_optimization_engine import MultiObjectiveOptimizationEngine  # noqa: F401
from backend.app.engines.strategic_planning_engine import StrategicPlanningEngine  # noqa: F401

__all__ = [
    "AdaptiveLifeOperatingSystem",
    "ConversationalIntelligenceEngine",
    "DependencyIntelligenceEngine",
    "FutureSimulationEngine",
    "GoalIntelligenceEngine",
    "MetaCognitiveEngine",
    "MultiObjectiveOptimizationEngine",
    "StrategicPlanningEngine",
]
