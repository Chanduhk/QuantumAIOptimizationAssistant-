import { apiClient } from "./client";

// Types corresponding to actual backend schemas

export interface SystemHealthResponse {
  status: string;
  database_connected: boolean;
  timestamp: string;
  database_pool?: {
    pool_size?: number;
    checked_in?: number;
    checked_out?: number;
    overflow?: number;
    overflow_limit?: number;
    timeout?: number;
    status?: string;
  };
}

export interface SystemStatusResponse {
  status: string;
  ai_metrics: Record<string, unknown>;
}

export interface QuantumStatusResponse {
  available: boolean;
  config: Record<string, unknown>;
  qaoa_config: Record<string, unknown>;
  direct_execution_exposed: boolean;
}

export interface ComponentInventoryItem {
  canonical_id: string;
  component_id: string;
  display_name: string;
  name: string;
  module_path: string;
  component_type: "ml_model" | "pretrained_model" | "heuristic" | "optimizer" | "simulated_quantum" | "conversational" | "data_provider" | "worker";
  operational_state: "AVAILABLE" | "PRETRAINED" | "TRAINED" | "READY_FOR_TRAINING" | "NOT_READY_INSUFFICIENT_DATA" | "UNINITIALIZED" | "UNREGISTERED" | "DEGRADED" | "API_UNAVAILABLE" | "FAILED";
  training_state?: string | null;
  requires_external_api: boolean;
  has_local_implementation: boolean;
  can_execute_now: boolean;
  is_registered: boolean;
  artifact_version?: string | null;
  artifact_path?: string | null;
  fallback_active: boolean;
  fallback_description?: string | null;
  provenance?: string | null;
  last_check_timestamp: string;
  recovery_action?: string | null;
  status_explanation?: string | null;
  notes?: string | null;
  description?: string | null;
}

export interface ComponentInventoryResponse {
  total_components: number;
  components: ComponentInventoryItem[];
}

export interface ModelStatusResponse {
  status: string;
  in_memory_only: boolean;
  models_registered: number;
  production_model_approved?: boolean;
  candidate_model_staging?: boolean;
  heuristic_fallback_active?: boolean;
  rl_policy_status?: string;
  demo_artifacts_locked?: boolean;
  total_components_available?: number;
  component_inventory?: Record<string, ComponentInventoryItem>;
}

export interface MLTrainingStepLog {
  timestamp_utc: string;
  step: string;
  status: string;
  message: string;
  progress_pct: number;
}

export interface MLTrainingJobRecord {
  job_id: string;
  job_type: string;
  status: string;
  triggered_by: string;
  started_at_utc?: string;
  completed_at_utc?: string;
  progress_pct: number;
  current_step: string;
  step_logs: MLTrainingStepLog[];
  candidate_models: Array<Record<string, unknown>>;
  result_summary: Record<string, unknown>;
  error_message?: string;
  data_fingerprint?: string;
}

export interface PublicDatasetProvenance {
  dataset_id: string;
  name: string;
  source_url: string;
  license: string;
  citation: string;
  domain: string;
  is_personalized: boolean;
  target_name: string;
  target_semantics: string;
  total_records: number;
  train_records: number;
  val_records: number;
  test_records: number;
  sha256_checksum: string;
  download_timestamp_utc: string;
  files?: string[];
}

export interface MLTrainingStatusResult {
  controller_status: "idle" | "queued" | "running" | "completed" | "gated" | "failed";
  active_job: MLTrainingJobRecord | null;
  last_job: MLTrainingJobRecord | null;
  candidate_models: Array<{
    model_name: string;
    version: number;
    status: string;
    accuracy_score: number;
    training_timestamp: string;
    metrics: Record<string, unknown>;
  }>;
  production_models: Array<{
    model_name: string;
    version: number;
    status: string;
    accuracy_score: number;
    training_timestamp: string;
    metrics: Record<string, unknown>;
  }>;
  public_dataset: PublicDatasetProvenance | null;
  total_jobs_executed: number;
}

export interface UserBehaviorPatterns {
  user_id?: number;
  tasks_analyzed?: number;
  average_productivity?: number;
  average_focus_score?: number;
  average_energy_level?: number;
  average_completion_time?: number;
  best_focus_hours?: number[];
  preferred_task_types?: string[];
  hourly_productivity?: Record<string, number>;
  productivity_by_task_type?: Record<string, number>;
  average_duration_by_task_type?: Record<string, number>;
}

export interface RecommendationResponse {
  focus_hours: string[];
  task_ordering: string[];
  schedule_improvements: string[];
  goal_progress_alerts: string[];
  behavioral_insights: string[];
}

export interface DataCollectionStatusResponse {
  result: {
    collection_report?: Record<string, unknown>;
    quality_audit?: Record<string, unknown>;
    adapter_report?: Record<string, unknown>;
  };
}

export interface AuthUser {
  id: number;
  email: string;
  created_at: string;
}

export interface AuthenticationRequest {
  email: string;
  password: string;
}

export interface AuthSessionResponse {
  user: AuthUser;
  expires_at: string;
}

export interface LogoutResponse {
  logged_out: boolean;
}

export interface Task {
  id: number;
  user_id: number;
  title: string;
  description?: string | null;
  task_type: string;
  priority: number;
  estimated_duration: number | null;
  estimated_duration_unit?: string | null;
  estimated_duration_source?: string | null;
  actual_duration: number | null;
  created_at: string | null;
  start_time: string | null;
  end_time: string | null;
  completed: boolean;
  lifecycle_state: string | null;
  outcome_valid: boolean | null;
  focus_rating?: number | null;
  energy_rating?: number | null;
  productivity_rating?: number | null;
  feedback_notes?: string | null;
  feedback_submitted_at?: string | null;
  deadline?: string | null;
  dependencies?: number[] | string[] | null;
  goal_id?: number | null;
  context_info?: string | null;
}

export interface TaskCreateRequest {
  user_id: number;
  title: string;
  description?: string;
  task_type: string;
  priority?: number; // Backend defaults to 3
  estimated_duration: number;
  estimated_duration_unit?: 'minutes' | 'hours';
  deadline?: string;
  dependencies?: number[];
  goal_id?: number;
  context_info?: string;
  created_at?: string;
}

export interface TaskUpdateRequest {
  user_id: number;
  title?: string;
  description?: string;
  task_type?: string;
  priority?: number;
  estimated_duration?: number;
  estimated_duration_unit?: 'minutes' | 'hours';
  deadline?: string;
  dependencies?: number[];
  goal_id?: number;
  context_info?: string;
  clear_deadline?: boolean;
  clear_goal?: boolean;
  clear_dependencies?: boolean;
}

export interface Goal {
  id: number;
  user_id: number;
  title: string;
  description?: string | null;
  category?: string | null;
  priority: number;
  target_date?: string | null;
  status: string;
  progress: number;
  created_at?: string | null;
  updated_at?: string | null;
  task_count?: number;
}

export interface GoalCreateRequest {
  user_id: number;
  title: string;
  description?: string;
  category?: string;
  priority?: number;
  target_date?: string;
  status?: string;
  progress?: number;
}

export interface GoalUpdateRequest {
  user_id: number;
  title?: string;
  description?: string;
  category?: string;
  priority?: number;
  target_date?: string;
  status?: string;
  progress?: number;
  clear_target_date?: boolean;
}

export interface GoalListResponse {
  goals: Goal[];
}

export interface GoalResponse {
  goal: Goal;
}

export interface TaskStartRequest {
  user_id?: number;
  started_at?: string;
}

export interface TaskCompleteRequest {
  user_id?: number;
  completed_at?: string;
  actual_duration?: number;
  focus_rating?: number;
  energy_rating?: number;
  productivity_rating?: number;
  feedback_notes?: string;
}

export interface TaskFeedbackRequest {
  user_id?: number;
  focus_rating: number;
  energy_rating: number;
  productivity_rating: number;
  feedback_notes?: string;
}

export interface MLReadinessComponent {
  component_name: string;
  model_type: string;
  status: string;
  eligible_samples: number;
  required_samples: number;
  ground_truth_label_source: string;
  blocking_reasons: string[];
  data_collection_actions: string[];
  details: Record<string, unknown>;
}

export interface MLReadinessReport {
  overall_status: string;
  audit_timestamp: string;
  database_task_count: number;
  eligible_dataset_rows: number;
  components: {
    DurationRatioModel?: MLReadinessComponent;
    ProductivityModel?: MLReadinessComponent;
    RLScheduler?: MLReadinessComponent;
    [key: string]: MLReadinessComponent | undefined;
  };
  summary: string;
  next_steps: string[];
}

export interface TaskListResponse {
  tasks: Task[];
}

export interface TaskResponse {
  task: Task;
}

export interface ProviderStatusResponse {
  provider: string;
  model: string;
  display_model?: string;
  is_configured: boolean;
  status: string;
  status_label: string;
  fallback_active: boolean;
  has_api_key?: boolean;
  masked_key?: string;
  endpoint?: string;
  timeout_seconds?: number;
  supported_models?: string[];
  last_error?: string | null;
  error_category?: string | null;
}

export interface ProviderTestResponse {
  success: boolean;
  message: string;
  status: string;
  last_error?: string | null;
  error_category?: string | null;
}

export interface ConversationSummary {
  id: string;
  user_id: number;
  title: string;
  created_at?: string | null;
  updated_at?: string | null;
  message_count: number;
}

export interface ChatMessageRecord {
  id: string;
  conversation_id: string;
  user_id: number;
  role: "user" | "assistant";
  content: string;
  intent?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface ConversationDetail {
  conversation: ConversationSummary;
  messages: ChatMessageRecord[];
}

export interface OrchestratorTaskInput {
  id?: number | string;
  title: string;
  description?: string;
  type: string;
  priority: number;
  duration: number;
  estimated_duration_unit?: 'minutes' | 'hours';
  estimated_duration_source?: string;
  deadline?: string;
  dependencies?: string[] | number[];
  depends_on_task_ids?: string[];
  goal_id?: number;
  context_info?: string;
}

export interface ExecutivePlanRequest {
  user_id: number;
  tasks: OrchestratorTaskInput[];
  query?: string;
  days_back?: number;
}

export interface MultiEngineResponse {
  result: Record<string, unknown>;
}

export interface ExecutivePlanResponse {
  result: Record<string, unknown> & {
    optimization_evidence?: {
      mode?: string;
      prediction_matrix_status?: string;
      nontriviality_status?: string;
      quantum_suitability?: Record<string, unknown>;
      quantum_candidate?: Record<string, unknown>;
      hybrid_comparison?: Record<string, unknown>;
      executive_decision_authority?: string;
    };
    recommended_plan?: Record<string, unknown>;
    executive_summary?: unknown;
  };
}

export interface ActiveProposal {
  id: string;
  user_id: number;
  version: number;
  status: string;
  goal_text?: string | null;
  available_hours?: number | null;
  schedule: Array<Record<string, unknown>>;
  created_at?: string | null;
  expires_at?: string | null;
  [key: string]: unknown;
}

export interface CommandRequest {
  user_id: number;
  command: string;
  days_back?: number;
  conversation_id?: string;
}

export interface CommandResponse {
  intent: string;
  result: Record<string, unknown>;
  conversation_id?: string;
}

export interface DecisionPipelineRequest {
  user_id: number;
  goal: string;
  days_back?: number;
}

export interface DecisionPipelineResponse {
  tasks: Record<string, unknown>[];
  schedule: Record<string, unknown>[];
  predictions: Record<string, unknown>[];
}

export const api = {
  auth: {
    register: (data: AuthenticationRequest) =>
      apiClient.post<AuthSessionResponse>("/api/v1/auth/register", data).then((res) => res.data),
    login: (data: AuthenticationRequest) =>
      apiClient.post<AuthSessionResponse>("/api/v1/auth/login", data).then((res) => res.data),
    currentUser: () => apiClient.get<AuthUser>("/api/v1/auth/me").then((res) => res.data),
    logout: () => apiClient.post<LogoutResponse>("/api/v1/auth/logout").then((res) => res.data),
  },
  system: {
    getHealth: () => apiClient.get<SystemHealthResponse>("/api/v1/system/health").then(res => res.data),
    getStatus: () => apiClient.get<SystemStatusResponse>("/api/v1/system/status").then(res => res.data),
    getComponentInventory: () =>
      apiClient.get<MultiEngineResponse>("/api/v1/system/component-inventory").then((res) => {
        const result = (res.data?.result || {}) as Record<string, unknown>;
        const rawComponents = result.components;
        let components: ComponentInventoryItem[] = [];
        if (Array.isArray(rawComponents)) {
          components = rawComponents.map((item: Record<string, unknown>) => ({
            ...item,
            canonical_id: (item.canonical_id as string) || (item.component_id as string) || "",
            component_id: (item.component_id as string) || (item.canonical_id as string) || "",
            name: (item.name as string) || (item.display_name as string) || "",
            display_name: (item.display_name as string) || (item.name as string) || "",
          })) as unknown as ComponentInventoryItem[];
        } else if (rawComponents && typeof rawComponents === "object") {
          components = Object.entries(rawComponents as Record<string, Record<string, unknown>>).map(([key, item]) => ({
            ...item,
            canonical_id: (item.canonical_id as string) || key,
            component_id: (item.component_id as string) || (item.canonical_id as string) || key,
            name: (item.name as string) || (item.display_name as string) || key,
            display_name: (item.display_name as string) || (item.name as string) || key,
          })) as unknown as ComponentInventoryItem[];
        }
        return {
          total_components: typeof result.total_components === "number" ? result.total_components : components.length,
          components,
        } as ComponentInventoryResponse;
      }),
  },
  quantum: {
    getStatus: () => apiClient.get<QuantumStatusResponse>("/api/v1/quantum/status").then(res => res.data),
  },
  ml: {
    getModelStatus: () => apiClient.get<ModelStatusResponse>("/api/v1/ml/model-status").then(res => res.data),
    getReadiness: (userId?: number) =>
      apiClient.get<MultiEngineResponse>("/api/v1/ml/readiness", { params: userId ? { user_id: userId } : undefined })
        .then(res => res.data.result as unknown as MLReadinessReport),
    getTrainingStatus: () =>
      apiClient.get<MultiEngineResponse>("/api/v1/ml/training/status")
        .then(res => res.data.result as unknown as MLTrainingStatusResult),
    triggerTraining: (jobType = "public_benchmark", force = false) =>
      apiClient.post<MultiEngineResponse>("/api/v1/ml/training/trigger", { job_type: jobType, force })
        .then(res => res.data.result as unknown as MLTrainingJobRecord),
    retryTraining: (jobId?: string) =>
      apiClient.post<MultiEngineResponse>("/api/v1/ml/training/retry", { job_id: jobId })
        .then(res => res.data.result as unknown as MLTrainingJobRecord),
    bootstrapPublicDataset: (force = false) =>
      apiClient.post<MultiEngineResponse>(`/api/v1/ml/datasets/bootstrap-public?force=${force}`)
        .then(res => res.data.result as unknown as PublicDatasetProvenance),
  },
  learning: {
    dataCollectionStatus: (userId: number) =>
      apiClient.get<DataCollectionStatusResponse>("/api/v1/tasks/data-collection/status", { params: { user_id: userId } }).then(res => res.data),
    datasetReadiness: (userId: number) =>
      apiClient.get<DataCollectionStatusResponse>("/api/v1/tasks/ml-dataset/readiness", { params: { user_id: userId } }).then(res => res.data),
  },
  behavior: {
    patterns: (userId: number, daysBack = 90) =>
      apiClient.get<{ patterns: UserBehaviorPatterns }>(`/api/v1/behavior/patterns/${userId}`, { params: { days_back: daysBack } }).then(res => res.data),
  },
  tasks: {
    list: (userId: number) => 
      apiClient.get<TaskListResponse>("/api/v1/tasks", { params: { user_id: userId } }).then(res => res.data),
    get: (taskId: string | number, userId?: number) =>
      apiClient.get<TaskResponse>(`/api/v1/tasks/${taskId}`, { params: { user_id: userId } }).then(res => res.data),
    create: (data: TaskCreateRequest) =>
      apiClient.post<MultiEngineResponse>("/api/v1/tasks", data).then(res => res.data),
    start: (taskId: number, data: TaskStartRequest) =>
      apiClient.post<MultiEngineResponse>(`/api/v1/tasks/${taskId}/start`, data).then(res => res.data),
    complete: (taskId: number, data: TaskCompleteRequest) =>
      apiClient.post<MultiEngineResponse>(`/api/v1/tasks/${taskId}/complete`, data).then(res => res.data),
    feedback: (taskId: number, data: TaskFeedbackRequest) =>
      apiClient.post<MultiEngineResponse>(`/api/v1/tasks/${taskId}/feedback`, data).then(res => res.data),
    update: (taskId: number, data: TaskUpdateRequest) =>
      apiClient.put<MultiEngineResponse>(`/api/v1/tasks/${taskId}`, data).then(res => res.data),
    delete: (taskId: number, userId: number) =>
      apiClient.delete<MultiEngineResponse>(`/api/v1/tasks/${taskId}`, { params: { user_id: userId } }).then(res => res.data),
  },
  goals: {
    list: (userId: number, status?: string) =>
      apiClient.get<GoalListResponse>("/api/v1/goals", { params: { user_id: userId, status } }).then(res => res.data),
    get: (goalId: number, userId: number) =>
      apiClient.get<GoalResponse>(`/api/v1/goals/${goalId}`, { params: { user_id: userId } }).then(res => res.data),
    create: (data: GoalCreateRequest) =>
      apiClient.post<GoalResponse>("/api/v1/goals", data).then(res => res.data),
    update: (goalId: number, data: GoalUpdateRequest) =>
      apiClient.put<GoalResponse>(`/api/v1/goals/${goalId}`, data).then(res => res.data),
    delete: (goalId: number, userId: number) =>
      apiClient.delete<MultiEngineResponse>(`/api/v1/goals/${goalId}`, { params: { user_id: userId } }).then(res => res.data),
  },
  ai: {
    recommendations: (userId: number, daysBack = 90) =>
      apiClient.get<RecommendationResponse>(`/api/v1/ai/recommendations/${userId}`, { params: { days_back: daysBack } }).then(res => res.data),
    createExecutivePlan: (data: ExecutivePlanRequest) =>
      apiClient.post<ExecutivePlanResponse>("/api/v1/ai/executive-plan", data).then(res => res.data),
    command: (data: CommandRequest) =>
      apiClient.post<CommandResponse>("/api/v1/ai/command", data, { timeout: 240_000 }).then(res => res.data),
    context: (userId: number, daysBack?: number, query?: string) =>
      apiClient.get<MultiEngineResponse>("/api/v1/ai/context", { params: { user_id: userId, days_back: daysBack, query } }).then(res => res.data),
    runDecisionPipeline: (data: DecisionPipelineRequest) =>
      apiClient.post<DecisionPipelineResponse>("/api/v1/ai/run-decision-pipeline", data).then(res => res.data),
    acceptPlan: (data: { user_id: number; schedule?: Array<Record<string, unknown>>; proposal_id?: string; version?: number }) =>
      apiClient.post<MultiEngineResponse>("/api/v1/ai/plan/accept", data).then(res => res.data),
    rejectPlan: (data: { user_id: number; proposal_id?: string }) =>
      apiClient.post<MultiEngineResponse>("/api/v1/ai/plan/reject", data).then(res => res.data),
    activePlan: () =>
      apiClient.get<{ result: { active_proposal: ActiveProposal | null } }>("/api/v1/ai/plan/active").then(res => res.data.result.active_proposal),
    providerStatus: () =>
      apiClient.get<ProviderStatusResponse>("/api/v1/ai/provider-status").then(res => res.data),
    testProvider: () =>
      apiClient.post<ProviderTestResponse>("/api/v1/ai/provider-test").then(res => res.data),
  },
  jam: {
    listConversations: () =>
      apiClient.get<{ conversations: ConversationSummary[] }>("/api/v1/jam/conversations").then(res => res.data.conversations),
    createConversation: (title?: string) =>
      apiClient.post<ConversationSummary>("/api/v1/jam/conversations", { title }).then(res => res.data),
    getConversation: (conversationId: string) =>
      apiClient.get<ConversationDetail>(`/api/v1/jam/conversations/${conversationId}`).then(res => res.data),
    deleteConversation: (conversationId: string) =>
      apiClient.delete<{ success: boolean; deleted_conversation_id: string }>(`/api/v1/jam/conversations/${conversationId}`).then(res => res.data),
  },
  benchmarks: {
    getDatasets: () =>
      apiClient.get<MultiEngineResponse>("/api/v1/benchmarks/datasets").then((res) => res.data.result as Record<string, unknown>),
    getQuantum: () =>
      apiClient.get<MultiEngineResponse>("/api/v1/benchmarks/quantum").then((res) => res.data.result as Record<string, unknown>),
    getRL: () =>
      apiClient.get<MultiEngineResponse>("/api/v1/benchmarks/rl").then((res) => res.data.result as Record<string, unknown>),
    getVectorMemory: () =>
      apiClient.get<MultiEngineResponse>("/api/v1/benchmarks/vector-memory").then((res) => res.data.result as Record<string, unknown>),
  },
};

