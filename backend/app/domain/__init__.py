"""Domain models for AI scheduling and behavior analysis.

Contains core data structures and evaluation logic for daily planning:

Classes:
    Day: Represents a single day with available hours and tasks
    DayEvaluator: Evaluates day schedules against multiple metrics
    
Functions:
    compute_overload_index: Calculate task load vs capacity
    compute_strategic_weight: Calculate task importance score
    apply_strategic_compression: Apply soft-freeze penalties during overload

Import directly from submodules:
    from backend.app.domain.day_model import Day
    from backend.app.domain.evaluation import DayEvaluator
    from backend.app.domain.strategic_compression import compute_overload_index
"""

from backend.app.domain.dependency_model import TaskDependency  # noqa: F401
from backend.app.domain.goal_model import Goal, Milestone  # noqa: F401
from backend.app.domain.multi_objective_model import OptimizationObjective, OptimizationResult  # noqa: F401
from backend.app.domain.simulation_model import SimulationResult, SimulationScenario  # noqa: F401
from backend.app.domain.strategic_plan_model import RoadmapItem, StrategicPlan  # noqa: F401

__all__ = [
    "Goal",
    "Milestone",
    "TaskDependency",
    "RoadmapItem",
    "StrategicPlan",
    "SimulationScenario",
    "SimulationResult",
    "OptimizationObjective",
    "OptimizationResult",
]
