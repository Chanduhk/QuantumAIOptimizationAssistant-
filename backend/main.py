import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal, Union

from dotenv import load_dotenv

# Ensure environment variables are loaded reliably regardless of execution working directory
_backend_env = Path(__file__).resolve().parent / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env)
_root_env = Path(__file__).resolve().parents[1] / ".env"
if _root_env.exists():
    load_dotenv(_root_env)
load_dotenv()

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.adaptive import AdaptiveScheduler
from backend.app.database.db import create_tables, get_db
from backend.app.engines import QuantumLifeBrain
from backend.app.interface import AIInteractionLayer
from backend.app.memory import VectorMemorySystem
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
    id: Optional[Union[str, int]] = None
    title: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1)
    duration: float = Field(..., gt=0)
    estimated_duration_unit: Optional[Literal["minutes", "hours"]] = None
    estimated_duration_source: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    dependencies: Optional[List[Any]] = None
    depends_on_task_ids: List[str] = Field(default_factory=list)
    goal_id: Optional[int] = None
    context_info: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_dependencies_and_id(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        raw_id = data.get("id")
        if raw_id is not None:
            if isinstance(raw_id, bool):
                raise ValueError("Task ID must be a valid non-empty string.")
            s_id = str(raw_id).strip()
            if not s_id:
                raise ValueError("Task ID must be a valid non-empty string.")
            data["id"] = s_id

        raw_deps = data.get("depends_on_task_ids")
        if raw_deps is None and "dependencies" in data:
            raw_deps = data.get("dependencies")

        if raw_deps in (None, ""):
            data["depends_on_task_ids"] = []
            data["dependencies"] = []
            return data

        if isinstance(raw_deps, (str, int)) and not isinstance(raw_deps, bool):
            raw_deps = [raw_deps]
        elif not isinstance(raw_deps, (list, tuple, set)):
            raise ValueError("depends_on_task_ids must be a list of task ids.")

        cleaned_deps: List[str] = []
        for item in raw_deps:
            if item is None or isinstance(item, bool):
                raise ValueError("depends_on_task_ids must contain non-empty strings.")
            if isinstance(item, (str, int)):
                s_item = str(item).strip()
                if not s_item:
                    raise ValueError("depends_on_task_ids must contain non-empty strings.")
                cleaned_deps.append(s_item)
            else:
                raise ValueError("depends_on_task_ids must contain non-empty strings.")

        seen = set()
        deduped = []
        for d in cleaned_deps:
            if d not in seen:
                seen.add(d)
                deduped.append(d)

        data["depends_on_task_ids"] = deduped
        data["dependencies"] = deduped
        return data


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
    conversation_id: Optional[str] = None


class AcceptPlanRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    schedule: Optional[List[Dict[str, Any]]] = None
    proposal_id: Optional[str] = None
    version: Optional[int] = None


class RejectPlanRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    proposal_id: Optional[str] = None


class TaskCreateRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    task_type: str = Field(..., min_length=1, max_length=100)
    priority: int = Field(default=3, ge=1, le=5)
    estimated_duration: float = Field(..., gt=0)
    estimated_duration_unit: Literal["minutes", "hours"] = "minutes"
    created_at: Optional[datetime] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    dependencies: Optional[List[int]] = None
    goal_id: Optional[int] = None
    context_info: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    task_type: Optional[str] = Field(default=None, min_length=1, max_length=100)
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    estimated_duration: Optional[float] = Field(default=None, gt=0)
    estimated_duration_unit: Optional[Literal["minutes", "hours"]] = None
    deadline: Optional[datetime] = None
    dependencies: Optional[List[int]] = None
    goal_id: Optional[int] = None
    context_info: Optional[str] = None
    clear_deadline: bool = False
    clear_goal: bool = False
    clear_dependencies: bool = False


class GoalCreateRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default="general", max_length=100)
    priority: int = Field(default=3, ge=1, le=5)
    target_date: Optional[datetime] = None
    status: Optional[str] = Field(default="active", max_length=50)
    progress: Optional[float] = Field(default=0.0, ge=0.0, le=1.0)


class GoalUpdateRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    target_date: Optional[datetime] = None
    status: Optional[str] = Field(default=None, max_length=50)
    progress: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    clear_target_date: bool = False


class GoalResponse(BaseModel):
    goal: Dict[str, Any]


class GoalListResponse(BaseModel):
    goals: List[Dict[str, Any]]


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
    focus_rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    energy_rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    productivity_rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    feedback_notes: Optional[str] = Field(default=None, max_length=1000)


class TaskFeedbackRequest(BaseModel):
    user_id: Optional[int] = Field(default=None, ge=1)
    focus_rating: float = Field(..., ge=1.0, le=5.0)
    energy_rating: float = Field(..., ge=1.0, le=5.0)
    productivity_rating: float = Field(..., ge=1.0, le=5.0)
    feedback_notes: Optional[str] = Field(default=None, max_length=1000)


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


def _normalize_numpy_response_values(value: Any) -> Any:
    """Convert NumPy values in untyped response payloads to JSON-native values.

    Orchestrator responses intentionally use ``Dict[str, Any]`` so FastAPI's
    response model cannot validate nested NumPy scalars or arrays. Convert
    those known types recursively at the HTTP boundary; leave all unrelated
    objects untouched for the normal response validation/serialization path.
    """
    if isinstance(value, np.generic):
        return _normalize_numpy_response_values(value.item())
    if isinstance(value, np.ndarray):
        return _normalize_numpy_response_values(value.tolist())
    if isinstance(value, Mapping):
        return {
            _normalize_numpy_response_values(key): _normalize_numpy_response_values(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_numpy_response_values(item) for item in value]
    return value


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
    conversation_id: Optional[str] = None


class ConversationSummaryResponse(BaseModel):
    id: str
    user_id: int
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0


class ConversationListResponse(BaseModel):
    conversations: List[ConversationSummaryResponse]


class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    user_id: int
    role: str
    content: str
    intent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class ConversationDetailResponse(BaseModel):
    conversation: ConversationSummaryResponse
    messages: List[ChatMessageResponse]


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)


class ProviderTestResponse(BaseModel):
    success: bool
    message: str
    status: str
    last_error: Optional[str] = None
    error_category: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: List[Dict[str, Any]]


class TaskResponse(BaseModel):
    task: Dict[str, Any]


class ExecutivePlanRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    tasks: List[OrchestratorTaskInput] = Field(..., min_length=1)
    query: Optional[str] = None
    days_back: int = Field(default=90, ge=1, le=3650)
    goals: Optional[List[Dict[str, Any]]] = None


class SystemHealthResponse(BaseModel):
    status: str
    database_connected: bool
    timestamp: str
    database_pool: Optional[Dict[str, Any]] = None


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
    production_model_approved: bool = False
    candidate_model_staging: bool = False
    heuristic_fallback_active: bool = True
    rl_policy_status: str = "UNINITIALIZED_ZERO_POLICY"
    demo_artifacts_locked: bool = True
    total_components_available: Optional[int] = None
    component_inventory: Optional[Dict[str, Any]] = None


class TrainingTriggerRequest(BaseModel):
    job_type: str = "public_benchmark"
    force: bool = False


class TrainingRetryRequest(BaseModel):
    job_id: Optional[str] = None


@app.on_event("startup")
def startup() -> None:
    """Create database tables and initialize component registry before serving."""
    create_tables()
    from backend.app.ml.system_inventory import SystemComponentRegistry

    SystemComponentRegistry.get_instance().initialize_all()

    from backend.app.learning.autonomous_learning import get_learning_coordinator
    from backend.app.database.db import SessionLocal

    get_learning_coordinator().initialize(db_session_factory=SessionLocal)


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
    # QuantumLifeBrain constructs VectorMemorySystem. Start its expensive local
    # embedding import before construction so every brain-backed API, not only
    # the JAM command route, can use the deterministic fallback during warm-up.
    VectorMemorySystem.preload_model_async()
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
            description=request.description,
            deadline=request.deadline,
            dependencies=request.dependencies,
            goal_id=request.goal_id,
            context_info=request.context_info,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiEngineResponse(result={"task": service.serialize_task(task)})


@app.put("/api/v1/tasks/{task_id}", response_model=MultiEngineResponse)
@app.patch("/api/v1/tasks/{task_id}", response_model=MultiEngineResponse)
def update_task(
    task_id: int,
    request: TaskUpdateRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    service = _build_task_lifecycle_service(db)
    try:
        task = service.update_task(
            task_id=task_id,
            user_id=request.user_id,
            title=request.title,
            description=request.description,
            task_type=request.task_type,
            priority=request.priority,
            estimated_duration=request.estimated_duration,
            estimated_duration_unit=request.estimated_duration_unit,
            deadline=request.deadline,
            dependencies=request.dependencies,
            goal_id=request.goal_id,
            context_info=request.context_info,
            clear_deadline=request.clear_deadline,
            clear_goal=request.clear_goal,
            clear_dependencies=request.clear_dependencies,
        )
        return MultiEngineResponse(result={"task": service.serialize_task(task)})
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg or "unauthorized" in msg:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/v1/tasks/{task_id}", response_model=MultiEngineResponse)
def delete_task(
    task_id: int,
    user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    service = _build_task_lifecycle_service(db)
    try:
        service.delete_task(task_id=task_id, user_id=user_id)
        return MultiEngineResponse(result={"deleted": True, "task_id": task_id})
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg or "unauthorized" in msg:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
        msg = str(exc)
        if msg == "task not found.":
            raise HTTPException(status_code=404, detail="Task not found") from exc
        if msg == "task has already been started.":
            raise HTTPException(status_code=409, detail="task has already been started.") from exc
        if msg == "completed task cannot be started.":
            raise HTTPException(status_code=409, detail="completed task cannot be started.") from exc
        raise HTTPException(status_code=400, detail=msg) from exc
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
            focus_rating=request.focus_rating,
            energy_rating=request.energy_rating,
            productivity_rating=request.productivity_rating,
            feedback_notes=request.feedback_notes,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "task not found.":
            raise HTTPException(status_code=404, detail="Task not found") from exc
        if msg == "task has already been completed.":
            raise HTTPException(status_code=409, detail="Task has already been completed") from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    return MultiEngineResponse(result={"task": service.serialize_task(task)})


@app.post("/api/v1/tasks/{task_id}/feedback", response_model=MultiEngineResponse)
def submit_task_feedback(
    task_id: int,
    request: TaskFeedbackRequest,
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    service = _build_task_lifecycle_service(db)
    try:
        task = service.record_feedback(
            task_id=task_id,
            user_id=request.user_id,
            focus_rating=request.focus_rating,
            energy_rating=request.energy_rating,
            productivity_rating=request.productivity_rating,
            feedback_notes=request.feedback_notes,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "task not found.":
            raise HTTPException(status_code=404, detail="Task not found") from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    return MultiEngineResponse(result={"task": service.serialize_task(task)})


@app.get("/api/v1/ml/readiness", response_model=MultiEngineResponse)
def get_ml_system_readiness(
    user_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    from backend.app.ml.readiness import assess_full_ml_system_readiness

    report = assess_full_ml_system_readiness(db, user_id=user_id)
    return MultiEngineResponse(result=report.to_dict())


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommandResponse:
    if current_user.id != request.user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User isolation violation.")

    from backend.app.services.chat_service import ChatService
    chat_service = ChatService(db)
    conv = chat_service.get_or_create_active_conversation(
        user_id=current_user.id,
        conversation_id=request.conversation_id,
        title_hint=request.command,
    )
    chat_service.add_user_message(
        user_id=current_user.id,
        conversation_id=conv.id,
        content=request.command,
    )
    turns = chat_service.get_conversation_turns(current_user.id, conv.id, max_turns=6)

    # Local transformer import/model loading is expensive on cold processes.
    # Start it once outside this request; VectorMemorySystem uses its deterministic
    # fallback while the local-only model is initializing.
    VectorMemorySystem.preload_model_async()
    interaction_layer = _build_interaction_layer(db, days_back=request.days_back)
    try:
        result = await interaction_layer.process_command(
            user_id=current_user.id,
            command=request.command,
            conversation_turns=turns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw_res = result.get("result", {})
    summary = (
        raw_res.get("executive_summary")
        or raw_res.get("answer")
        or f"Processed {result.get('intent', 'command')}."
    )
    chat_service.add_assistant_message(
        user_id=current_user.id,
        conversation_id=conv.id,
        content=str(summary),
        intent=result.get("intent"),
        metadata=raw_res,
    )

    return CommandResponse(
        intent=result["intent"],
        result=result["result"],
        conversation_id=conv.id,
    )


@app.post(
    "/api/v1/ai/accept-plan",
    response_model=MultiEngineResponse,
)
@app.post(
    "/api/v1/ai/plan/accept",
    response_model=MultiEngineResponse,
)
async def accept_plan(
    request: AcceptPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    if current_user.id != request.user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User isolation violation.")
    interaction_layer = _build_interaction_layer(db)
    await interaction_layer.initialize_engine()
    from backend.app.orchestrator.brain_models import BrainRequest
    import uuid
    brain_request = BrainRequest(
        request_id=str(uuid.uuid4()),
        user_id=current_user.id,
        intent="accept_plan",
        command="Accept plan proposal",
        parameters={
            "intent": "accept_plan",
            "schedule": request.schedule,
            "proposal_id": request.proposal_id,
            "version": request.version,
        },
    )
    response = await interaction_layer.execute_intent(brain_request)
    if not response.success:
        raise HTTPException(status_code=400, detail=response.executive_summary)
    return MultiEngineResponse(result=response.raw_result)


@app.post(
    "/api/v1/ai/reject-plan",
    response_model=MultiEngineResponse,
)
@app.post(
    "/api/v1/ai/plan/reject",
    response_model=MultiEngineResponse,
)
async def reject_plan(
    request: RejectPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    if current_user.id != request.user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User isolation violation.")
    interaction_layer = _build_interaction_layer(db)
    await interaction_layer.initialize_engine()
    from backend.app.orchestrator.brain_models import BrainRequest
    import uuid
    brain_request = BrainRequest(
        request_id=str(uuid.uuid4()),
        user_id=current_user.id,
        intent="reject_plan",
        command="Reject plan proposal",
        parameters={
            "intent": "reject_plan",
            "proposal_id": request.proposal_id,
        },
    )
    response = await interaction_layer.execute_intent(brain_request)
    return MultiEngineResponse(result=response.raw_result)


@app.get(
    "/api/v1/ai/plan/active",
    response_model=MultiEngineResponse,
)
def get_active_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    from backend.app.services.plan_proposal_service import PlanProposalService
    service = PlanProposalService(db)
    active = service.get_active_proposal(current_user.id)
    return MultiEngineResponse(result={"active_proposal": active.to_dict() if active else None})


FRIENDLY_MODEL_NAMES: Dict[str, str] = {
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.0-flash": "Gemini 2.0 Flash",
    "gemini-1.5-flash": "Gemini 1.5 Flash",
    "gemini-1.5-pro": "Gemini 1.5 Pro",
    "gpt-4o-mini": "GPT-4o mini",
    "gpt-4o": "GPT-4o",
}


def get_friendly_model_name(raw_model: str) -> str:
    if raw_model in FRIENDLY_MODEL_NAMES:
        return FRIENDLY_MODEL_NAMES[raw_model]
    if raw_model and raw_model.lower().startswith("gemini"):
        parts = raw_model.split("-")
        return " ".join(p.capitalize() for p in parts)
    return raw_model or "Gemini 3.8 Flash"


class ProviderStatusResponse(BaseModel):
    provider: str
    model: str
    display_model: str
    is_configured: bool
    status: str
    status_label: str
    fallback_active: bool


@app.get(
    "/api/v1/ai/provider-status",
    response_model=ProviderStatusResponse,
)
def get_ai_provider_status() -> ProviderStatusResponse:
    from backend.app.interface.llm_provider import get_default_llm_provider
    provider = get_default_llm_provider()
    raw_status = provider.get_status()
    raw_model = str(raw_status.get("model") or "gemini-3.8-flash")
    return ProviderStatusResponse(
        provider=str(raw_status.get("provider") or "gemini"),
        model=raw_model,
        display_model=get_friendly_model_name(raw_model),
        is_configured=bool(raw_status.get("is_configured", False)),
        status=str(raw_status.get("status") or "gemini_unconfigured"),
        status_label=str(raw_status.get("status_label") or "Configured"),
        fallback_active=bool(raw_status.get("fallback_active", False)),
    )


@app.post(
    "/api/v1/ai/provider-test",
    response_model=ProviderTestResponse,
)
def test_ai_provider_connection() -> ProviderTestResponse:
    from backend.app.interface.llm_provider import get_default_llm_provider
    provider = get_default_llm_provider()
    if hasattr(provider, "test_connection"):
        success, raw_message = provider.test_connection()
    else:
        success = provider.is_configured()
        raw_message = f"Provider {provider.provider_name} does not implement active test connection."
    status_dict = provider.get_status()
    raw_model = str(status_dict.get("model") or "gemini-3.8-flash")
    friendly = get_friendly_model_name(raw_model)

    if success:
        clean_message = f"Connection to {friendly} succeeded."
    elif not provider.is_configured():
        clean_message = f"{friendly} is not configured."
    else:
        clean_message = raw_message
        for sensitive_term in ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY"]:
            clean_message = clean_message.replace(f"({sensitive_term} missing)", "credentials missing")
            clean_message = clean_message.replace(f"Please check your {sensitive_term}.", "Please check your credentials.")
        clean_message = clean_message.replace(raw_model, friendly)

    return ProviderTestResponse(
        success=success,
        message=clean_message,
        status=str(status_dict.get("status") or ("gemini_configured" if success else "gemini_unconfigured")),
    )


@app.get(
    "/api/v1/jam/conversations",
    response_model=ConversationListResponse,
)
def list_jam_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    from backend.app.services.chat_service import ChatService
    service = ChatService(db)
    items = service.list_conversations(current_user.id)
    return ConversationListResponse(conversations=[ConversationSummaryResponse(**item) for item in items])


@app.post(
    "/api/v1/jam/conversations",
    response_model=ConversationSummaryResponse,
    status_code=201,
)
def create_jam_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationSummaryResponse:
    from backend.app.services.chat_service import ChatService
    service = ChatService(db)
    conv = service.create_conversation(current_user.id, title=request.title)
    return ConversationSummaryResponse(**conv.to_dict())


@app.get(
    "/api/v1/jam/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def get_jam_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    from backend.app.services.chat_service import ChatService
    service = ChatService(db)
    conv = service.get_conversation(current_user.id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
    messages = service.get_messages(current_user.id, conversation_id)
    return ConversationDetailResponse(
        conversation=ConversationSummaryResponse(**conv.to_dict()),
        messages=[ChatMessageResponse(**m) for m in messages],
    )


@app.delete(
    "/api/v1/jam/conversations/{conversation_id}",
)
def delete_jam_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    from backend.app.services.chat_service import ChatService
    service = ChatService(db)
    deleted = service.delete_conversation(current_user.id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
    return {"success": True, "deleted_conversation_id": conversation_id}


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
    return MultiEngineResponse(result=_normalize_numpy_response_values(result))


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


def _build_goal_service(session: Session):
    from backend.app.services.goal_service import GoalService
    return GoalService(session)


@app.post("/api/v1/goals", response_model=GoalResponse)
def create_goal(
    request: GoalCreateRequest,
    db: Session = Depends(get_db),
) -> GoalResponse:
    service = _build_goal_service(db)
    try:
        goal = service.create_goal(
            user_id=request.user_id,
            title=request.title,
            description=request.description,
            category=request.category,
            priority=request.priority,
            target_date=request.target_date,
            status=request.status or "active",
            progress=request.progress or 0.0,
        )
        return GoalResponse(goal=service.serialize_goal(goal))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/goals", response_model=GoalListResponse)
def list_goals(
    user_id: int = Query(..., ge=1),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> GoalListResponse:
    service = _build_goal_service(db)
    goals = service.list_goals(user_id=user_id, status=status)
    return GoalListResponse(goals=[service.serialize_goal(g) for g in goals])


@app.get("/api/v1/goals/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: int,
    user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> GoalResponse:
    service = _build_goal_service(db)
    try:
        goal = service.get_goal(goal_id=goal_id, user_id=user_id)
        return GoalResponse(goal=service.serialize_goal(goal))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/v1/goals/{goal_id}", response_model=GoalResponse)
@app.patch("/api/v1/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    request: GoalUpdateRequest,
    db: Session = Depends(get_db),
) -> GoalResponse:
    service = _build_goal_service(db)
    try:
        goal = service.update_goal(
            goal_id=goal_id,
            user_id=request.user_id,
            title=request.title,
            description=request.description,
            category=request.category,
            priority=request.priority,
            target_date=request.target_date,
            status=request.status,
            progress=request.progress,
            clear_target_date=request.clear_target_date,
        )
        return GoalResponse(goal=service.serialize_goal(goal))
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg or "unauthorized" in msg:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/v1/goals/{goal_id}", response_model=MultiEngineResponse)
def delete_goal(
    goal_id: int,
    user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    service = _build_goal_service(db)
    try:
        service.delete_goal(goal_id=goal_id, user_id=user_id)
        return MultiEngineResponse(result={"deleted": True, "goal_id": goal_id})
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg or "unauthorized" in msg:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _build_goal_service(session: Session):
    from backend.app.services.goal_service import GoalService
    return GoalService(session)


@app.post("/api/v1/goals", response_model=GoalResponse)
def create_goal(
    request: GoalCreateRequest,
    db: Session = Depends(get_db),
) -> GoalResponse:
    service = _build_goal_service(db)
    try:
        goal = service.create_goal(
            user_id=request.user_id,
            title=request.title,
            description=request.description,
            category=request.category,
            priority=request.priority,
            target_date=request.target_date,
            status=request.status or "active",
            progress=request.progress or 0.0,
        )
        return GoalResponse(goal=service.serialize_goal(goal))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/goals", response_model=GoalListResponse)
def list_goals(
    user_id: int = Query(..., ge=1),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> GoalListResponse:
    service = _build_goal_service(db)
    goals = service.list_goals(user_id=user_id, status=status)
    return GoalListResponse(goals=[service.serialize_goal(g) for g in goals])


@app.get("/api/v1/goals/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: int,
    user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> GoalResponse:
    service = _build_goal_service(db)
    try:
        goal = service.get_goal(goal_id=goal_id, user_id=user_id)
        return GoalResponse(goal=service.serialize_goal(goal))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/v1/goals/{goal_id}", response_model=GoalResponse)
@app.patch("/api/v1/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    request: GoalUpdateRequest,
    db: Session = Depends(get_db),
) -> GoalResponse:
    service = _build_goal_service(db)
    try:
        goal = service.update_goal(
            goal_id=goal_id,
            user_id=request.user_id,
            title=request.title,
            description=request.description,
            category=request.category,
            priority=request.priority,
            target_date=request.target_date,
            status=request.status,
            progress=request.progress,
            clear_target_date=request.clear_target_date,
        )
        return GoalResponse(goal=service.serialize_goal(goal))
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg or "unauthorized" in msg:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/v1/goals/{goal_id}", response_model=MultiEngineResponse)
def delete_goal(
    goal_id: int,
    user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    service = _build_goal_service(db)
    try:
        service.delete_goal(goal_id=goal_id, user_id=user_id)
        return MultiEngineResponse(result={"deleted": True, "goal_id": goal_id})
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg or "unauthorized" in msg:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    submitted_task_ids = {str(task.id).strip() for task in request.tasks if task.id}

    # 1. Detect self-dependencies (Case F)
    for task in request.tasks:
        tid = str(task.id).strip() if task.id else None
        if tid and tid in task.depends_on_task_ids:
            raise HTTPException(status_code=400, detail="A task cannot depend on itself.")

    # 2. Detect cycles among submitted tasks (Case G)
    from backend.app.knowledge.dependency_graph import DependencyGraph
    from backend.app.domain.dependency_model import TaskDependency
    cycle_graph = DependencyGraph()
    for task in request.tasks:
        tid = str(task.id).strip() if task.id else None
        if tid:
            cycle_graph.tasks.add(tid)
            for dep in task.depends_on_task_ids:
                if dep in submitted_task_ids:
                    cycle_graph.add_dependency(
                        TaskDependency(
                            dependency_id=f"chk:{tid}:{dep}",
                            task_id=tid,
                            depends_on_task_id=dep,
                        )
                    )
    cycles = cycle_graph.detect_cycles()
    if cycles:
        cycle_str = " -> ".join(cycles[0])
        raise HTTPException(
            status_code=400,
            detail=f"Circular dependency detected among tasks: {cycle_str}.",
        )

    # 3. Validate unselected / external dependency references (Case H / J)
    from backend.app.models.task import Task
    external_deps = set()
    for task in request.tasks:
        for dep in task.depends_on_task_ids:
            if dep not in submitted_task_ids:
                external_deps.add(dep)
    if external_deps:
        numeric_ids = []
        for dep in external_deps:
            try:
                numeric_ids.append(int(dep))
            except (ValueError, TypeError):
                pass
        db_tasks = db.query(Task).filter(Task.user_id == request.user_id, Task.id.in_(numeric_ids)).all() if numeric_ids else []
        found_ids = {str(dbt.id) for dbt in db_tasks}
        unauthorized_or_missing = external_deps - found_ids
        if unauthorized_or_missing:
            first_missing = sorted(unauthorized_or_missing)[0]
            raise HTTPException(
                status_code=400,
                detail=f"Prerequisite task '{first_missing}' not found or unauthorized.",
            )

    orchestrator = _build_orchestrator(db, days_back=request.days_back)
    try:
        result = orchestrator.execute_executive_planning(
            tasks=[task.model_dump() for task in request.tasks],
            user_id=request.user_id,
            query=request.query,
            goals=request.goals,
        )
        return MultiEngineResponse(result=_normalize_numpy_response_values(result))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/system/health", response_model=SystemHealthResponse)
def get_system_health(db: Session = Depends(get_db)) -> SystemHealthResponse:
    from backend.app.database.db import get_pool_status
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False
        
    return SystemHealthResponse(
        status="operational" if db_connected else "degraded",
        database_connected=db_connected,
        timestamp=datetime.utcnow().isoformat(),
        database_pool=get_pool_status(),
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
    from backend.app.ml.model_registry import ModelStatus, get_model_registry
    from backend.app.ai_rl.rl_scheduler import RLScheduler
    from backend.app.ml.system_inventory import SystemComponentRegistry

    registry = get_model_registry()
    rl_scheduler = RLScheduler()
    component_reg = SystemComponentRegistry.get_instance()
    summary = component_reg.get_inventory_summary()

    prod_model = (
        registry.get_latest_model("DurationRatioModel")
        or registry.get_latest_model("behavior_model")
        or registry.get_latest_model("ProductivityModel")
    )
    staging_models = [
        m
        for m_name in ("DurationRatioModel", "behavior_model", "ProductivityModel")
        for m in registry.list_models(m_name)
        if m.status == ModelStatus.STAGING
    ]

    rl_status = "UNINITIALIZED_ZERO_POLICY" if len(rl_scheduler.q_table) == 0 else "TRAINED"
    total_registered = sum(
        len(registry.list_models(m_name))
        for m_name in ("DurationRatioModel", "behavior_model", "ProductivityModel")
    )

    return ModelStatusResponse(
        status="production" if prod_model else "uninitialized",
        in_memory_only=True,
        models_registered=total_registered,
        production_model_approved=prod_model is not None,
        candidate_model_staging=len(staging_models) > 0,
        heuristic_fallback_active=prod_model is None,
        rl_policy_status=rl_status,
        demo_artifacts_locked=True,
        total_components_available=summary.get("available_for_execution", 0),
        component_inventory=summary.get("components"),
    )


@app.get("/api/v1/system/component-inventory", response_model=MultiEngineResponse)
def get_system_component_inventory() -> MultiEngineResponse:
    from backend.app.ml.system_inventory import SystemComponentRegistry

    registry = SystemComponentRegistry.get_instance()
    return MultiEngineResponse(result=registry.get_inventory_summary())


@app.get("/api/v1/ml/training/status", response_model=MultiEngineResponse)
def get_ml_training_status(
    authenticated_user: Optional[User] = Depends(enforce_authenticated_request),
) -> MultiEngineResponse:
    from backend.app.ml.training_controller import get_training_controller
    from backend.app.learning.autonomous_learning import get_learning_coordinator

    controller = get_training_controller()
    coord = get_learning_coordinator()
    status_data = controller.get_status()
    uid = authenticated_user.id if authenticated_user else None
    status_data["automatic_learning"] = coord.get_learning_status(user_id=uid)
    return MultiEngineResponse(result=status_data)


@app.post("/api/v1/ml/training/trigger", response_model=MultiEngineResponse, status_code=202)
def trigger_ml_training(
    request: TrainingTriggerRequest = TrainingTriggerRequest(),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    from backend.app.ml.training_controller import get_training_controller
    from backend.app.database.db import SessionLocal

    controller = get_training_controller()
    try:
        job = controller.trigger_training(
            job_type=request.job_type,
            force=request.force,
            triggered_by=f"user_{current_user.id}" if current_user else "api",
            user_id=current_user.id if current_user else None,
            db_session_factory=SessionLocal,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiEngineResponse(result=job.to_dict())


@app.post("/api/v1/ml/training/retry", response_model=MultiEngineResponse, status_code=202)
def retry_ml_training(
    request: TrainingRetryRequest = TrainingRetryRequest(),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MultiEngineResponse:
    from backend.app.ml.training_controller import get_training_controller
    from backend.app.database.db import SessionLocal

    controller = get_training_controller()
    try:
        job = controller.retry_training(
            job_id=request.job_id,
            user_id=current_user.id if current_user else None,
            db_session_factory=SessionLocal,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MultiEngineResponse(result=job.to_dict())


@app.post("/api/v1/ml/datasets/bootstrap-public", response_model=MultiEngineResponse)
def bootstrap_public_dataset(
    force: bool = Query(default=False),
) -> MultiEngineResponse:
    from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager

    mgr = PublicDatasetManager()
    try:
        meta = mgr.bootstrap_uci_garment(force=force)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to bootstrap public dataset: {exc}") from exc
    return MultiEngineResponse(result=meta.to_dict())


@app.get("/api/v1/benchmarks/datasets", response_model=MultiEngineResponse)
def get_benchmark_datasets() -> MultiEngineResponse:
    from backend.app.ml.datasets.public_dataset_manager import PublicDatasetManager

    mgr = PublicDatasetManager()
    return MultiEngineResponse(
        result={
            "catalog": mgr.get_dataset_catalog(),
            "compatibility_matrix": mgr.get_compatibility_matrix(),
            "scheduling_scenarios": mgr.get_scheduling_benchmark_scenarios(),
        }
    )


@app.get("/api/v1/benchmarks/quantum", response_model=MultiEngineResponse)
def get_quantum_benchmarks() -> MultiEngineResponse:
    import json
    from pathlib import Path
    from backend.app.quantum.benchmarking.quantum_benchmark_runner import QuantumBenchmarkRunner

    results_path = Path("scratch/quantum_optimization_benchmark_results.json")
    if results_path.exists():
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return MultiEngineResponse(result=data)
        except Exception:
            pass

    runner = QuantumBenchmarkRunner()
    summary = runner.run_all_benchmarks()
    return MultiEngineResponse(result=summary.to_dict())


@app.get("/api/v1/benchmarks/rl", response_model=MultiEngineResponse)
def get_rl_benchmarks() -> MultiEngineResponse:
    import json
    from pathlib import Path

    results_path = Path("scratch/rl_benchmark_results.json")
    if results_path.exists():
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return MultiEngineResponse(result=data)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return MultiEngineResponse(result={"status": "not_executed", "notes": "Run RL benchmark suite to populate."})


@app.get("/api/v1/benchmarks/vector-memory", response_model=MultiEngineResponse)
def get_vector_memory_benchmarks() -> MultiEngineResponse:
    import json
    from pathlib import Path

    results_path = Path("scratch/vector_memory_benchmark_results.json")
    if results_path.exists():
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return MultiEngineResponse(result=data)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return MultiEngineResponse(result={"status": "not_executed", "notes": "Run vector memory benchmark to populate."})

