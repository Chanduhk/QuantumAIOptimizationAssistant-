from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.adaptive import AdaptiveScheduler
from backend.app.database.db import create_tables, get_db
from backend.app.engines import QuantumLifeBrain
from backend.app.interface import AIInteractionLayer
from backend.app.learning import AutonomousLearningLoop
from backend.app.orchestrator import AIOrchestrator
from backend.app.pipeline import DecisionPipeline
from backend.app.recommendation import RecommendationEngine
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine


app = FastAPI(
    title="Quantum Life AI Behavior Intelligence API",
    version="1.0.0",
    description="Behavior learning backend for the Quantum Life AI personal assistant.",
)


class TrainRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    days_back: int = Field(default=90, ge=1, le=3650)


class PredictRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    days_back: int = Field(default=90, ge=1, le=3650)
    hour_of_day: int = Field(..., ge=0, le=23)
    task_type: str = Field(..., min_length=1)
    duration: float = Field(..., gt=0)


class BrainTaskRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    days_back: int = Field(default=90, ge=1, le=3650)
    task_ids: Optional[List[int]] = None
    query: Optional[str] = None


class LearnRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    days_back: int = Field(default=90, ge=1, le=3650)


class AIPlanRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    days_back: int = Field(default=90, ge=1, le=3650)
    task_ids: Optional[List[int]] = None
    query: Optional[str] = None


class RLTrainRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    days_back: int = Field(default=90, ge=1, le=3650)
    task_ids: Optional[List[int]] = None
    episodes: int = Field(default=25, ge=1, le=1000)


class MemoryStoreRequest(BaseModel):
    task_description: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class OrchestratorTaskInput(BaseModel):
    title: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1)
    duration: float = Field(..., gt=0)


class OrchestratorRunRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    tasks: List[OrchestratorTaskInput] = Field(..., min_length=1)
    query: Optional[str] = None
    update_learning: bool = False
    days_back: int = Field(default=90, ge=1, le=3650)


class DecisionPipelineRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    goal: str = Field(..., min_length=1)
    days_back: int = Field(default=90, ge=1, le=3650)


class AdaptiveScheduleRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    schedule: List[Dict[str, Any]] = Field(..., min_length=1)
    days_back: int = Field(default=90, ge=1, le=3650)


class LearningCycleRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    days_back: int = Field(default=90, ge=1, le=3650)


class CommandRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    command: str = Field(..., min_length=1)
    days_back: int = Field(default=90, ge=1, le=3650)


class TrainResponse(BaseModel):
    metrics: Dict[str, float]


class PatternsResponse(BaseModel):
    patterns: Dict[str, Any]


class PredictResponse(BaseModel):
    predicted_productivity: float


class ReportResponse(BaseModel):
    report: str


class MultiEngineResponse(BaseModel):
    result: Dict[str, Any]


class DecisionPipelineResponse(BaseModel):
    tasks: List[Dict[str, Any]]
    schedule: List[Dict[str, Any]]
    predictions: List[Dict[str, Any]]


class AdaptiveScheduleResponse(BaseModel):
    updated_schedule: List[Dict[str, Any]]
    reason: str


class LearningCycleResponse(BaseModel):
    status: str
    new_model_version: str
    accuracy_improvement: float


class RecommendationResponse(BaseModel):
    focus_hours: List[str]
    task_ordering: List[str]
    schedule_improvements: List[str]
    goal_progress_alerts: List[str]
    behavioral_insights: List[str]


class CommandResponse(BaseModel):
    intent: str
    result: Dict[str, Any]


@app.on_event("startup")
def startup() -> None:
    """Create database tables before the API starts serving requests."""
    create_tables()


def _build_behavior_engine(session: Session) -> BehaviorIntelligenceEngine:
    return BehaviorIntelligenceEngine(session=session)


def _build_brain(session: Session) -> QuantumLifeBrain:
    return QuantumLifeBrain(session=session)


def _build_orchestrator(session: Session, days_back: int = 90) -> AIOrchestrator:
    return AIOrchestrator(session=session, days_back=days_back)


def _build_decision_pipeline(session: Session, days_back: int = 90) -> DecisionPipeline:
    return DecisionPipeline(session=session, days_back=days_back)


def _build_adaptive_scheduler(session: Session, days_back: int = 90) -> AdaptiveScheduler:
    return AdaptiveScheduler(session=session, days_back=days_back)


def _build_learning_loop(session: Session, days_back: int = 90) -> AutonomousLearningLoop:
    return AutonomousLearningLoop(session=session, days_back=days_back)


def _build_recommendation_engine(session: Session, days_back: int = 90) -> RecommendationEngine:
    return RecommendationEngine(session=session, days_back=days_back)


def _build_interaction_layer(session: Session, days_back: int = 90) -> AIInteractionLayer:
    return AIInteractionLayer(session=session, days_back=days_back)


def _prepare_engine(engine: BehaviorIntelligenceEngine, user_id: int, days_back: int) -> None:
    tasks = engine.collect_behavior_data(user_id=user_id, days_back=days_back)
    if tasks.empty:
        raise HTTPException(status_code=404, detail="No completed tasks found for the user.")

    engine.extract_features()


@app.post("/api/v1/behavior/train", response_model=TrainResponse)
def train_behavior_model(
    request: TrainRequest,
    db: Session = Depends(get_db),
) -> TrainResponse:
    engine = _build_behavior_engine(db)
    _prepare_engine(engine, request.user_id, request.days_back)

    try:
        metrics = engine.train_productivity_model()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TrainResponse(metrics=metrics)


@app.get("/api/v1/behavior/patterns/{user_id}", response_model=PatternsResponse)
def get_behavior_patterns(
    user_id: int,
    days_back: int = Query(default=90, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> PatternsResponse:
    engine = _build_behavior_engine(db)
    _prepare_engine(engine, user_id, days_back)
    return PatternsResponse(patterns=engine.get_user_patterns())


@app.post("/api/v1/behavior/predict", response_model=PredictResponse)
def predict_behavior(
    request: PredictRequest,
    db: Session = Depends(get_db),
) -> PredictResponse:
    engine = _build_behavior_engine(db)
    _prepare_engine(engine, request.user_id, request.days_back)

    try:
        prediction = engine.predict_task_productivity(
            hour_of_day=request.hour_of_day,
            task_type=request.task_type,
            duration=request.duration,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PredictResponse(predicted_productivity=prediction)


@app.get("/api/v1/behavior/report/{user_id}", response_model=ReportResponse)
def get_behavior_report(
    user_id: int,
    days_back: int = Query(default=90, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> ReportResponse:
    engine = _build_behavior_engine(db)
    _prepare_engine(engine, user_id, days_back)
    return ReportResponse(report=engine.generate_report())


@app.post("/api/v1/plan/generate", response_model=MultiEngineResponse)
def generate_plan(
    request: BrainTaskRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.generate_daily_plan(
            user_id=request.user_id,
            days_back=request.days_back,
            task_ids=request.task_ids,
            query=request.query,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/ai/run-orchestrator", response_model=MultiEngineResponse)
def run_ai_orchestrator(
    request: OrchestratorRunRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    orchestrator = _build_orchestrator(db, days_back=request.days_back)
    try:
        result = orchestrator.process_tasks(
            tasks=[task.model_dump() for task in request.tasks],
            user_id=request.user_id,
            query=request.query,
            update_learning=request.update_learning,
            days_back=request.days_back,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post(
    "/api/v1/ai/run-decision-pipeline",
    response_model=DecisionPipelineResponse,
)
async def run_decision_pipeline(
    request: DecisionPipelineRequest,
    db: Session = Depends(get_db),
) -> DecisionPipelineResponse:
    pipeline = _build_decision_pipeline(db, days_back=request.days_back)
    try:
        result = await pipeline.run_pipeline(
            goal_text=request.goal,
            user_id=request.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DecisionPipelineResponse(**result)


@app.post(
    "/api/v1/ai/adaptive-schedule",
    response_model=AdaptiveScheduleResponse,
)
async def adaptive_schedule(
    request: AdaptiveScheduleRequest,
    db: Session = Depends(get_db),
) -> AdaptiveScheduleResponse:
    adaptive_engine = _build_adaptive_scheduler(db, days_back=request.days_back)
    try:
        result = await adaptive_engine.adapt_schedule(
            schedule=request.schedule,
            user_id=request.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AdaptiveScheduleResponse(**result)


@app.post(
    "/api/v1/ai/run-learning-cycle",
    response_model=LearningCycleResponse,
)
async def run_learning_cycle(
    request: LearningCycleRequest,
    db: Session = Depends(get_db),
) -> LearningCycleResponse:
    learning_loop = _build_learning_loop(db, days_back=request.days_back)
    try:
        result = await learning_loop.run_learning_cycle(request.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LearningCycleResponse(
        status=result["status"],
        new_model_version=result["new_model_version"],
        accuracy_improvement=result["accuracy_improvement"],
    )


@app.get(
    "/api/v1/ai/recommendations/{user_id}",
    response_model=RecommendationResponse,
)
async def get_recommendations(
    user_id: int,
    days_back: int = Query(default=90, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    recommendation_engine = _build_recommendation_engine(db, days_back=days_back)
    try:
        result = await recommendation_engine.generate_recommendations(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RecommendationResponse(**result)


@app.post(
    "/api/v1/ai/command",
    response_model=CommandResponse,
)
async def process_ai_command(
    request: CommandRequest,
    db: Session = Depends(get_db),
) -> CommandResponse:
    interaction_layer = _build_interaction_layer(db, days_back=request.days_back)
    try:
        result = await interaction_layer.process_command(
            user_id=request.user_id,
            command=request.command,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CommandResponse(**result)


@app.post("/api/v1/schedule/optimize", response_model=MultiEngineResponse)
def optimize_schedule(
    request: BrainTaskRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.optimize_schedule(
            user_id=request.user_id,
            days_back=request.days_back,
            task_ids=request.task_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/decision/prioritize", response_model=MultiEngineResponse)
def prioritize_tasks(
    request: BrainTaskRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.prioritize_tasks(
            user_id=request.user_id,
            days_back=request.days_back,
            task_ids=request.task_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.get("/api/v1/predict/productivity", response_model=MultiEngineResponse)
def predict_productivity(
    user_id: int = Query(..., ge=1),
    task_type: str = Query(..., min_length=1),
    duration: float = Query(..., gt=0),
    hour_of_day: Optional[int] = Query(default=None, ge=0, le=23),
    days_back: int = Query(default=90, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.predict_productivity(
            user_id=user_id,
            task_type=task_type,
            duration=duration,
            hour_of_day=hour_of_day,
            days_back=days_back,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/learn/update-model", response_model=MultiEngineResponse)
def update_learning_model(
    request: LearnRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.update_learning_model(
            user_id=request.user_id,
            days_back=request.days_back,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/ai/plan-day", response_model=MultiEngineResponse)
def ai_plan_day(
    request: AIPlanRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.generate_daily_plan(
            user_id=request.user_id,
            days_back=request.days_back,
            task_ids=request.task_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/ai/optimize-schedule", response_model=MultiEngineResponse)
def ai_optimize_schedule(
    request: AIPlanRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.plan_day(
            user_id=request.user_id,
            days_back=request.days_back,
            task_ids=request.task_ids,
            query=request.query,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/ai/train-rl", response_model=MultiEngineResponse)
def ai_train_rl(
    request: RLTrainRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.train_rl_scheduler(
            user_id=request.user_id,
            days_back=request.days_back,
            task_ids=request.task_ids,
            episodes=request.episodes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/ai/memory/store", response_model=MultiEngineResponse)
def ai_store_memory(
    request: MemoryStoreRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.store_memory(
            task_description=request.task_description,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/ai/memory/search", response_model=MultiEngineResponse)
def ai_search_memory(
    request: MemorySearchRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    result = brain.search_memory(query=request.query, limit=request.limit)
    return MultiEngineResponse(result=result)


@app.get("/api/v1/ai/context", response_model=MultiEngineResponse)
def ai_get_context(
    user_id: int = Query(..., ge=1),
    days_back: int = Query(default=90, ge=1, le=3650),
    query: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        result = brain.get_ai_context(
            user_id=user_id,
            days_back=days_back,
            query=query,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)
