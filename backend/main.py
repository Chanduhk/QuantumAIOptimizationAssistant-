import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
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
from backend.app.services.task_lifecycle_service import TaskLifecycleService
from backend.app.ml.datasets import DatasetQualityAuditor, TaskCollectionReporter, TaskDataExtractor
from backend.app.models.auth import User
from backend.app.services.auth_service import (
    clear_session_cookies,
    enforce_authenticated_request,
    get_current_user,
    register_user,
    authenticate_user,
    revoke_session,
    set_session_cookies,
)
app = FastAPI(
    title="Quantum Life AI Behavior Intelligence API",
    version="1.0.0",
    description="Behavior learning backend for the Quantum Life AI personal assistant.",
    dependencies=[Depends(enforce_authenticated_request)],
)

origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    id: Optional[int] = Field(default=None, ge=1)
    title: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1)
    duration: float = Field(..., gt=0)
    estimated_duration_unit: Optional[Literal["minutes"]] = None
    estimated_duration_source: Optional[str] = Field(default=None, min_length=1, max_length=100)


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


class TaskCreateRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    task_type: str = Field(..., min_length=1, max_length=100)
    priority: int = Field(default=3, ge=1, le=5)
    estimated_duration: float = Field(..., gt=0)
    estimated_duration_unit: Literal["minutes"] = "minutes"
    created_at: Optional[datetime] = None


class AuthenticationRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=12, max_length=1024)


class AuthenticatedUserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime


class AuthSessionResponse(BaseModel):
    user: AuthenticatedUserResponse
    expires_at: datetime


class LogoutResponse(BaseModel):
    logged_out: bool


class TaskStartRequest(BaseModel):
    user_id: Optional[int] = Field(default=None, ge=1)
    started_at: Optional[datetime] = None


class TaskCompleteRequest(BaseModel):
    user_id: Optional[int] = Field(default=None, ge=1)
    completed_at: Optional[datetime] = None
    actual_duration: Optional[float] = Field(default=None, gt=0)


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


class TaskListResponse(BaseModel):
    tasks: List[Dict[str, Any]]


class TaskResponse(BaseModel):
    task: Dict[str, Any]


class ExecutivePlanRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    tasks: List[OrchestratorTaskInput] = Field(..., min_length=1)
    query: Optional[str] = None
    days_back: int = Field(default=90, ge=1, le=3650)


class SystemHealthResponse(BaseModel):
    status: str
    database_connected: bool
    timestamp: str


class SystemStatusResponse(BaseModel):
    status: str
    ai_metrics: Dict[str, Any]


class QuantumStatusResponse(BaseModel):
    available: bool
    config: Dict[str, Any]
    qaoa_config: Dict[str, Any]
    direct_execution_exposed: bool


class ModelStatusResponse(BaseModel):
    status: str
    in_memory_only: bool
    models_registered: int


@app.on_event("startup")
def startup() -> None:
    """Create database tables before the API starts serving requests."""
    create_tables()


def _auth_user_payload(user: User) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse(id=user.id, email=user.email, created_at=user.created_at)


@app.post("/api/v1/auth/register", response_model=AuthSessionResponse, status_code=201)
def register_account(
    request: AuthenticationRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    credentials = register_user(db, request.email, request.password)
    set_session_cookies(response, credentials)
    return AuthSessionResponse(
        user=_auth_user_payload(credentials.user),
        expires_at=credentials.expires_at,
    )


@app.post("/api/v1/auth/login", response_model=AuthSessionResponse)
def login_account(
    request: AuthenticationRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    credentials = authenticate_user(db, request.email, request.password)
    set_session_cookies(response, credentials)
    return AuthSessionResponse(
        user=_auth_user_payload(credentials.user),
        expires_at=credentials.expires_at,
    )


@app.get("/api/v1/auth/me", response_model=AuthenticatedUserResponse)
def current_account(user: User = Depends(get_current_user)) -> AuthenticatedUserResponse:
    return _auth_user_payload(user)


@app.post("/api/v1/auth/logout", response_model=LogoutResponse)
def logout_account(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    del user  # Authentication dependency enforces the active session.
    revoke_session(request, db)
    clear_session_cookies(response)
    return LogoutResponse(logged_out=True)


def _build_behavior_engine(session: Session) -> BehaviorIntelligenceEngine:
    return BehaviorIntelligenceEngine(session=session)


def _build_task_lifecycle_service(session: Session) -> TaskLifecycleService:
    return TaskLifecycleService(session=session)


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


@app.post("/api/v1/tasks", response_model=MultiEngineResponse)
def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    service = _build_task_lifecycle_service(db)
    try:
        task = service.create_task(
            user_id=request.user_id,
            title=request.title,
            task_type=request.task_type,
            priority=request.priority,
            estimated_duration=request.estimated_duration,
            estimated_duration_unit=request.estimated_duration_unit,
            estimated_duration_source="task_api",
            created_at=request.created_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiEngineResponse(result={"task": service.serialize_task(task)})


@app.post("/api/v1/tasks/{task_id}/start", response_model=MultiEngineResponse)
def start_task(
    task_id: int,
    request: TaskStartRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    service = _build_task_lifecycle_service(db)
    try:
        task = service.start_task(
            task_id=task_id,
            user_id=request.user_id,
            started_at=request.started_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiEngineResponse(result={"task": service.serialize_task(task)})


@app.post("/api/v1/tasks/{task_id}/complete", response_model=MultiEngineResponse)
def complete_task(
    task_id: int,
    request: TaskCompleteRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    service = _build_task_lifecycle_service(db)
    try:
        task = service.complete_task(
            task_id=task_id,
            user_id=request.user_id,
            completed_at=request.completed_at,
            actual_duration=request.actual_duration,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiEngineResponse(result={"task": service.serialize_task(task)})


@app.get("/api/v1/tasks/ml-dataset/readiness", response_model=MultiEngineResponse)
def get_task_dataset_readiness(
    user_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    try:
        extraction = TaskDataExtractor(db).extract(user_id=user_id)
        collection_report = TaskCollectionReporter(db).report(user_id=user_id)
        quality_audit = DatasetQualityAuditor().audit_extraction(
            extraction,
            collection_report=collection_report,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiEngineResponse(
        result={
            "adapter_report": extraction.report.to_dict(),
            "collection_report": collection_report.to_dict(),
            "quality_audit": quality_audit.to_dict(),
        }
    )


@app.get("/api/v1/tasks/data-collection/status", response_model=MultiEngineResponse)
def get_task_data_collection_status(
    user_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    try:
        report = TaskCollectionReporter(db).report(user_id=user_id)
        quality_audit = DatasetQualityAuditor().audit_session(db, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiEngineResponse(
        result={
            "collection_report": report.to_dict(),
            "quality_audit": quality_audit.to_dict(),
        }
    )


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
    user: User = Depends(get_current_user),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    try:
        metadata = dict(request.metadata)
        metadata["user_id"] = user.id
        result = brain.store_memory(
            task_description=request.task_description,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultiEngineResponse(result=result)


@app.post("/api/v1/ai/memory/search", response_model=MultiEngineResponse)
def ai_search_memory(
    request: MemorySearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MultiEngineResponse:
    brain = _build_brain(db)
    result = brain.search_memory(query=request.query, limit=request.limit, user_id=user.id)
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


@app.get("/api/v1/tasks", response_model=TaskListResponse)
def list_tasks(
    user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    from backend.app.services.task_lifecycle_service import TaskLifecycleService

    svc = TaskLifecycleService(session=db)
    all_tasks = svc.get_all_tasks(user_id=user_id)
    serialized = [svc.serialize_task(t) for t in all_tasks]
    return TaskListResponse(tasks=serialized)


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    user_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> TaskResponse:
    service = _build_task_lifecycle_service(db)
    try:
        task = service.get_task(task_id=task_id, user_id=user_id)
        return TaskResponse(task=service.serialize_task(task))
    except ValueError as exc:
        if str(exc) == "task not found.":
            raise HTTPException(status_code=404, detail="Task not found") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/ai/executive-plan", response_model=MultiEngineResponse)
def generate_executive_plan(
    request: ExecutivePlanRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    orchestrator = _build_orchestrator(db, days_back=request.days_back)
    try:
        result = orchestrator.execute_executive_planning(
            tasks=[task.model_dump() for task in request.tasks],
            user_id=request.user_id,
            query=request.query,
        )
        return MultiEngineResponse(result=result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/system/health", response_model=SystemHealthResponse)
def get_system_health(db: Session = Depends(get_db)) -> SystemHealthResponse:
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False
        
    return SystemHealthResponse(
        status="operational" if db_connected else "degraded",
        database_connected=db_connected,
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/api/v1/system/status", response_model=SystemStatusResponse)
def get_system_status() -> SystemStatusResponse:
    from backend.app.monitoring import AIMonitor
    monitor = AIMonitor()
    return SystemStatusResponse(
        status="operational",
        ai_metrics=monitor.report_system_metrics()
    )


@app.get("/api/v1/quantum/status", response_model=QuantumStatusResponse)
def get_quantum_status() -> QuantumStatusResponse:
    try:
        from backend.app.quantum.integration.models import AIQuantumIntegrationConfig
        from backend.app.quantum.optimization import QAOAConfig
        config = AIQuantumIntegrationConfig()
        qaoa_config = QAOAConfig(shots=config.qaoa_shots, seed=config.qaoa_seed)
        return QuantumStatusResponse(
            available=True,
            config={
                "allow_quantum": config.allow_quantum,
                "allow_classical_fallback": config.allow_classical_fallback,
                "max_variables_for_quantum": config.max_variables_for_quantum,
                "max_states_for_suitability": config.max_states_for_suitability,
            },
            qaoa_config={
                "shots": qaoa_config.shots,
                "seed": qaoa_config.seed,
                "max_qubits": qaoa_config.max_qubits,
                "max_shots": qaoa_config.max_shots,
            },
            direct_execution_exposed=False
        )
    except ImportError:
        return QuantumStatusResponse(
            available=False,
            config={},
            qaoa_config={},
            direct_execution_exposed=False
        )


@app.get("/api/v1/ml/model-status", response_model=ModelStatusResponse)
def get_model_status() -> ModelStatusResponse:
    from backend.app.ml.model_registry import ModelRegistry
    registry = ModelRegistry()
    return ModelStatusResponse(
        status="uninitialized",
        in_memory_only=True,
        models_registered=len(registry.store.list("behavior_model")) if hasattr(registry, "store") else 0
    )
