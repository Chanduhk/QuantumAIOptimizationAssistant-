import { apiClient } from "./client";

// Types corresponding to actual backend schemas

export interface SystemHealthResponse {
  status: string;
  database_connected: boolean;
  timestamp: string;
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

export interface ModelStatusResponse {
  status: string;
  in_memory_only: boolean;
  models_registered: number;
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
  task_type: string;
  priority: number;
  estimated_duration: number | null;
  // Existing database rows may contain null or an unrecognized legacy value.
  estimated_duration_unit?: string | null;
  estimated_duration_source?: string | null;
  actual_duration: number | null;
  created_at: string | null;
  start_time: string | null;
  end_time: string | null;
  completed: boolean;
  lifecycle_state: string | null;
  outcome_valid: boolean | null;
}

export interface TaskCreateRequest {
  user_id: number;
  title: string;
  task_type: string;
  priority?: number; // Backend defaults to 3
  estimated_duration: number;
  estimated_duration_unit?: 'minutes';
  created_at?: string;
}

export interface TaskStartRequest {
  user_id?: number;
  started_at?: string;
}

export interface TaskCompleteRequest {
  user_id?: number;
  completed_at?: string;
  actual_duration?: number;
}

export interface TaskListResponse {
  tasks: Task[];
}

export interface TaskResponse {
  task: Task;
}

export interface OrchestratorTaskInput {
  id?: number;
  title: string;
  type: string;
  priority: number;
  duration: number;
  estimated_duration_unit?: 'minutes';
  estimated_duration_source?: string;
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

export interface CommandRequest {
  user_id: number;
  command: string;
  days_back?: number;
}

export interface CommandResponse {
  intent: string;
  result: Record<string, unknown>;
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
  },
  quantum: {
    getStatus: () => apiClient.get<QuantumStatusResponse>("/api/v1/quantum/status").then(res => res.data),
  },
  ml: {
    getModelStatus: () => apiClient.get<ModelStatusResponse>("/api/v1/ml/model-status").then(res => res.data),
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
  },
  ai: {
    createExecutivePlan: (data: ExecutivePlanRequest) =>
      apiClient.post<ExecutivePlanResponse>("/api/v1/ai/executive-plan", data).then(res => res.data),
    command: (data: CommandRequest) =>
      apiClient.post<CommandResponse>("/api/v1/ai/command", data).then(res => res.data),
    context: (userId: number, daysBack?: number, query?: string) =>
      apiClient.get<MultiEngineResponse>("/api/v1/ai/context", { params: { user_id: userId, days_back: daysBack, query } }).then(res => res.data),
    runDecisionPipeline: (data: DecisionPipelineRequest) =>
      apiClient.post<DecisionPipelineResponse>("/api/v1/ai/run-decision-pipeline", data).then(res => res.data),
  }
};
