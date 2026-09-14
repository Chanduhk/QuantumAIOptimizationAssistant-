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

export interface TaskListResponse {
  tasks: Record<string, unknown>[];
}

export interface TaskResponse {
  task: Record<string, unknown>;
}

export interface OrchestratorTaskInput {
  title: string;
  type: string;
  priority: number;
  duration: number;
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

export interface CommandRequest {
  user_id: number;
  command: string;
  days_back?: number;
}

export interface CommandResponse {
  intent: string;
  result: Record<string, unknown>;
}

export const api = {
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
    get: (taskId: string, userId?: number) => 
      apiClient.get<TaskResponse>(`/api/v1/tasks/${taskId}`, { params: { user_id: userId } }).then(res => res.data),
  },
  ai: {
    createExecutivePlan: (data: ExecutivePlanRequest) =>
      apiClient.post<MultiEngineResponse>("/api/v1/ai/executive-plan", data).then(res => res.data),
    command: (data: CommandRequest) =>
      apiClient.post<CommandResponse>("/api/v1/ai/command", data).then(res => res.data),
    context: (userId: number, daysBack?: number, query?: string) =>
      apiClient.get<MultiEngineResponse>("/api/v1/ai/context", { params: { user_id: userId, days_back: daysBack, query } }).then(res => res.data),
  }
};
