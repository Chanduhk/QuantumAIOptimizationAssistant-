from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class TraceStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"

class QuantumStatus(str, Enum):
    CLASSICAL_ONLY = "CLASSICAL_ONLY"
    QUANTUM_CONSIDERED_BUT_REJECTED = "QUANTUM_CONSIDERED_BUT_REJECTED"
    QUANTUM_EXECUTED = "QUANTUM_EXECUTED"
    HYBRID_EXECUTED = "HYBRID_EXECUTED"
    QUANTUM_FAILED_CLASSICAL_FALLBACK = "QUANTUM_FAILED_CLASSICAL_FALLBACK"
    SIMULATED_LOCAL = "SIMULATED_LOCAL"

class StageTrace(BaseModel):
    stage: str
    status: TraceStatus
    started_at: float
    completed_at: float
    duration_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

class BrainExecutionTrace(BaseModel):
    request_id: str
    started_at: float
    completed_at: float = 0.0
    total_duration_ms: float = 0.0
    stages: List[StageTrace] = Field(default_factory=list)

class BrainRequest(BaseModel):
    request_id: str
    user_id: int = Field(..., ge=1)
    intent: str
    command: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    execution_mode: str = "auto"
    optimization_preferences: Dict[str, Any] = Field(default_factory=dict)
    days_back: int = 90

class BrainResponse(BaseModel):
    success: bool
    request_id: str
    intent: str
    schedule: List[Dict[str, Any]] = Field(default_factory=list)
    recommendation: Optional[Dict[str, Any]] = None
    executive_summary: str
    quantum_status: QuantumStatus
    quantum_suitability_result: Optional[Dict[str, Any]] = None
    trace: BrainExecutionTrace
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    executive_trace: Optional[Dict[str, Any]] = None
    # Provide backward compatibility for existing un-schema'd consumers
    raw_result: Dict[str, Any] = Field(default_factory=dict)
