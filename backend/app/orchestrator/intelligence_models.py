from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class MemoryState(BaseModel):
    available: bool = False
    context_keys: List[str] = Field(default_factory=list)
    recent_memories: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None

class BehavioralInsights(BaseModel):
    available: bool = False
    patterns_identified: int = 0
    insights: List[str] = Field(default_factory=list)
    error: Optional[str] = None

class PredictiveForecast(BaseModel):
    available: bool = False
    forecast_window_days: int = 0
    predictions: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None

class GoalAlignment(BaseModel):
    available: bool = False
    active_goals: int = 0
    alignment_score: float = 0.0
    error: Optional[str] = None

class DependencyGraph(BaseModel):
    available: bool = False
    nodes: int = 0
    edges: int = 0
    critical_path: List[str] = Field(default_factory=list)
    error: Optional[str] = None

class SimulationResults(BaseModel):
    available: bool = False
    scenarios_run: int = 0
    best_outcome: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class StrategicHorizon(BaseModel):
    available: bool = False
    horizon_days: int = 0
    strategy_recommendation: Optional[str] = None
    error: Optional[str] = None

class IntelligenceContext(BaseModel):
    """
    Honest container of what is actively known by the AI Brain.
    If an engine is offline or missing, its corresponding state is marked available=False.
    """
    memory_state: MemoryState = Field(default_factory=MemoryState)
    behavioral_insights: BehavioralInsights = Field(default_factory=BehavioralInsights)
    predictive_forecast: PredictiveForecast = Field(default_factory=PredictiveForecast)
    goal_alignment: GoalAlignment = Field(default_factory=GoalAlignment)
    dependency_graph: DependencyGraph = Field(default_factory=DependencyGraph)
    simulation_results: SimulationResults = Field(default_factory=SimulationResults)
    strategic_horizon: StrategicHorizon = Field(default_factory=StrategicHorizon)
    
    def to_executive_format(self) -> Dict[str, Any]:
        """Format the intelligence context for the Executive Cognitive Brain."""
        return {
            "memory": self.memory_state.model_dump() if self.memory_state.available else None,
            "behavior": self.behavioral_insights.model_dump() if self.behavioral_insights.available else None,
            "prediction": self.predictive_forecast.model_dump() if self.predictive_forecast.available else None,
            "goals": self.goal_alignment.model_dump() if self.goal_alignment.available else None,
            "dependencies": self.dependency_graph.model_dump() if self.dependency_graph.available else None,
            "simulation": self.simulation_results.model_dump() if self.simulation_results.available else None,
            "strategy": self.strategic_horizon.model_dump() if self.strategic_horizon.available else None,
        }
