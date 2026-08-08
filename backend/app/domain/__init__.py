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

from backend.app.domain.adaptive_life_model import (  # noqa: F401
    AdaptiveRecommendation,
    LifeSignal,
    Opportunity,
    RiskAlert,
)
from backend.app.domain.autonomous_planning_model import (  # noqa: F401
    AutonomousPlan,
    ContingencyPlan,
    PlanMilestone,
    PlanObjective,
    PlanTask,
    RecoveryPlan,
)
from backend.app.domain.behavior_learning_model import (  # noqa: F401
    BehaviorInsight,
    BehaviorObservation,
    BehaviorPattern,
    BehaviorTrend,
    LearningSnapshot,
)
from backend.app.domain.conversation_model import (  # noqa: F401
    ClarificationQuestion,
    ConversationContext,
    ConversationTurn,
    ExplanationResult,
)
from backend.app.domain.context_awareness_model import (  # noqa: F401
    ContextConflict,
    ContextInsight,
    ContextShift,
    ContextSignal,
    ContextSnapshot,
)
from backend.app.domain.day_model import Day  # noqa: F401
from backend.app.domain.decision_intelligence_model import (  # noqa: F401
    DecisionAnalysis,
    DecisionEvaluation,
    DecisionOption,
    DecisionRecommendation,
    DecisionTradeoff,
)
from backend.app.domain.dependency_model import TaskDependency  # noqa: F401
from backend.app.domain.evaluation import DayEvaluator  # noqa: F401
from backend.app.domain.executive_experience_model import (  # noqa: F401
    ExecutiveDecisionRecord,
    ExecutiveLearningSnapshot,
    ExecutivePattern,
    ExecutiveStrategyProfile,
)
from backend.app.domain.executive_execution_model import (  # noqa: F401
    ExecutionCheckpoint,
    ExecutionDeviation,
    ExecutionTimeline,
    ExecutiveAlert,
    PlanExecutionState,
    RecoveryRecommendation,
)
from backend.app.domain.executive_governance_model import (  # noqa: F401
    ExecutiveGovernanceSummary,
    ExecutivePolicy,
    GovernanceAudit,
    GovernanceDecision,
    GovernanceRecommendation,
    GovernanceRule,
    GovernanceViolation,
)
from backend.app.domain.executive_reasoning_model import (  # noqa: F401
    Evidence,
    EvidenceConflict,
    ExecutiveRecommendation,
    ExecutiveReasoningTrace,
)
from backend.app.domain.executive_resource_model import (  # noqa: F401
    AttentionAllocation,
    CapacityForecast,
    EnergyProfile,
    ExecutiveResourceSummary,
    ResourceAllocation,
    ResourceConflict,
    ResourceRecommendation,
    ResourceState,
)
from backend.app.domain.goal_model import Goal, Milestone  # noqa: F401
from backend.app.domain.meta_cognitive_model import (  # noqa: F401
    PerformanceSummary,
    ReflectionRecord,
    StrategyRecommendation,
)
from backend.app.domain.multi_objective_model import OptimizationObjective, OptimizationResult  # noqa: F401
from backend.app.domain.personal_knowledge_model import (  # noqa: F401
    KnowledgeInsight,
    KnowledgeNode,
    KnowledgeRelationship,
)
from backend.app.domain.simulation_model import SimulationResult, SimulationScenario  # noqa: F401
from backend.app.domain.strategic_compression import (  # noqa: F401
    apply_strategic_compression,
    compute_overload_index,
    compute_strategic_weight,
)
from backend.app.domain.strategic_plan_model import RoadmapItem, StrategicPlan  # noqa: F401

__all__ = [
    "Day",
    "DayEvaluator",
    "compute_overload_index",
    "compute_strategic_weight",
    "apply_strategic_compression",
    "Goal",
    "Milestone",
    "TaskDependency",
    "RoadmapItem",
    "StrategicPlan",
    "SimulationScenario",
    "SimulationResult",
    "OptimizationObjective",
    "OptimizationResult",
    "ReflectionRecord",
    "StrategyRecommendation",
    "PerformanceSummary",
    "LifeSignal",
    "Opportunity",
    "RiskAlert",
    "AdaptiveRecommendation",
    "ConversationTurn",
    "ConversationContext",
    "ExplanationResult",
    "ClarificationQuestion",
    "KnowledgeNode",
    "KnowledgeRelationship",
    "KnowledgeInsight",
    "PlanObjective",
    "PlanMilestone",
    "PlanTask",
    "RecoveryPlan",
    "ContingencyPlan",
    "AutonomousPlan",
    "BehaviorObservation",
    "BehaviorPattern",
    "BehaviorTrend",
    "BehaviorInsight",
    "LearningSnapshot",
    "ContextSignal",
    "ContextSnapshot",
    "ContextShift",
    "ContextConflict",
    "ContextInsight",
    "DecisionOption",
    "DecisionEvaluation",
    "DecisionTradeoff",
    "DecisionRecommendation",
    "DecisionAnalysis",
    "Evidence",
    "EvidenceConflict",
    "ExecutiveReasoningTrace",
    "ExecutiveRecommendation",
    "ExecutiveDecisionRecord",
    "ExecutivePattern",
    "ExecutiveLearningSnapshot",
    "ExecutiveStrategyProfile",
    "ExecutionCheckpoint",
    "PlanExecutionState",
    "ExecutionDeviation",
    "ExecutiveAlert",
    "RecoveryRecommendation",
    "ExecutionTimeline",
    "ExecutivePolicy",
    "GovernanceRule",
    "GovernanceViolation",
    "GovernanceDecision",
    "GovernanceRecommendation",
    "GovernanceAudit",
    "ExecutiveGovernanceSummary",
    "ResourceState",
    "ResourceAllocation",
    "ResourceConflict",
    "AttentionAllocation",
    "EnergyProfile",
    "CapacityForecast",
    "ResourceRecommendation",
    "ExecutiveResourceSummary",
]
