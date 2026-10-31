import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  api,
  ExecutivePlanRequest,
  CommandRequest,
  TaskCreateRequest,
  TaskStartRequest,
  TaskCompleteRequest,
  TaskFeedbackRequest,
  type AuthUser,
  type ExecutivePlanResponse,
  type Task,
  type TaskListResponse,
  type MultiEngineResponse,
} from "./endpoints";
import { ApiRequestError, getApiErrorMessage } from "./client";
import { useUserStore } from "@/stores/userStore";

export function isAlreadyStartedError(error: unknown): boolean {
  if (!error) return false;
  const message = (getApiErrorMessage(error) || "").toLowerCase();
  return (
    message.includes("already been started") ||
    message.includes("already started") ||
    (error instanceof ApiRequestError && error.status === 409 && message.includes("start"))
  );
}

export function isAlreadyCompletedError(error: unknown): boolean {
  if (!error) return false;
  const message = (getApiErrorMessage(error) || "").toLowerCase();
  return (
    message.includes("already been completed") ||
    message.includes("already completed") ||
    (error instanceof ApiRequestError && error.status === 409 && message.includes("complete"))
  );
}

export const CURRENT_USER_QUERY_KEY = ["auth", "current-user"] as const;

export function useCurrentUser() {
  return useQuery<AuthUser | null>({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: async () => {
      try {
        return await api.auth.currentUser();
      } catch (error) {
        if (error instanceof ApiRequestError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 30_000,
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ["system", "health"],
    queryFn: api.system.getHealth,
    refetchInterval: 30000, // Refetch every 30s
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system", "status"],
    queryFn: api.system.getStatus,
    refetchInterval: 15000,
  });
}

export function useQuantumStatus() {
  return useQuery({
    queryKey: ["quantum", "status"],
    queryFn: api.quantum.getStatus,
    refetchInterval: 15000,
  });
}

export function useComponentInventory() {
  return useQuery({
    queryKey: ["system", "component-inventory"],
    queryFn: api.system.getComponentInventory,
    refetchInterval: 30000,
  });
}

export function useMLModelStatus() {
  return useQuery({
    queryKey: ["ml", "status"],
    queryFn: api.ml.getModelStatus,
    refetchInterval: 30000,
  });
}

export function useMLTrainingStatus() {
  return useQuery({
    queryKey: ["ml", "training", "status"],
    queryFn: api.ml.getTrainingStatus,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.controller_status === "running" || data?.controller_status === "queued") {
        return 1500;
      }
      return 15000;
    },
  });
}

export function useTriggerTraining() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobType = "public_benchmark", force = false }: { jobType?: string; force?: boolean } = {}) =>
      api.ml.triggerTraining(jobType, force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml", "training", "status"] });
      queryClient.invalidateQueries({ queryKey: ["ml", "status"] });
    },
  });
}

export function useRetryTraining() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId?: string) => api.ml.retryTraining(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml", "training", "status"] });
      queryClient.invalidateQueries({ queryKey: ["ml", "status"] });
    },
  });
}

export function useBootstrapPublicDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (force?: boolean) => api.ml.bootstrapPublicDataset(force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml", "training", "status"] });
    },
  });
}

export function useMLReadiness() {
  const userId = useUserStore((state) => state.userId);
  return useQuery({
    queryKey: ["ml", "readiness", userId],
    queryFn: () => api.ml.getReadiness(userId ?? undefined),
    enabled: userId !== null,
    staleTime: 15_000,
  });
}

export function useDataCollectionStatus() {
  const userId = useUserStore((state) => state.userId);
  return useQuery({
    queryKey: ["learning", "collection", userId],
    queryFn: () => {
      if (userId === null) throw new Error("Authenticated user is required.");
      return api.learning.dataCollectionStatus(userId);
    },
    enabled: userId !== null,
    retry: false,
  });
}

export function useDatasetReadiness() {
  const userId = useUserStore((state) => state.userId);
  return useQuery({
    queryKey: ["learning", "readiness", userId],
    queryFn: () => {
      if (userId === null) throw new Error("Authenticated user is required.");
      return api.learning.datasetReadiness(userId);
    },
    enabled: userId !== null,
    retry: false,
  });
}

/** Endpoints that answer 404 until the user has completed tasks resolve to null. */
async function nullOn404<T>(request: () => Promise<T>): Promise<T | null> {
  try {
    return await request();
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) return null;
    throw error;
  }
}

export function useBehaviorPatterns(enabled = true) {
  const userId = useUserStore((state) => state.userId);
  return useQuery({
    queryKey: ["behavior", "patterns", userId],
    queryFn: () => {
      if (userId === null) throw new Error("Authenticated user is required.");
      return nullOn404(() => api.behavior.patterns(userId));
    },
    enabled: userId !== null && enabled,
    retry: false,
  });
}

export function useRecommendations(daysBack = 90, enabled = true) {
  const userId = useUserStore((state) => state.userId);
  return useQuery({
    queryKey: ["ai", "recommendations", userId, daysBack],
    queryFn: () => {
      if (userId === null) throw new Error("Authenticated user is required.");
      return nullOn404(() => api.ai.recommendations(userId, daysBack));
    },
    enabled: userId !== null && enabled,
    retry: false,
    staleTime: 60_000,
  });
}

export function useAIContext(enabled = true) {
  const userId = useUserStore((state) => state.userId);
  return useQuery({
    queryKey: ["ai", "context", userId],
    queryFn: () => {
      if (userId === null) throw new Error("Authenticated user is required.");
      return nullOn404(() => api.ai.context(userId, 90));
    },
    enabled: userId !== null && enabled,
    retry: false,
    staleTime: 60_000,
  });
}

export function useActivePlan() {
  const userId = useUserStore((state) => state.userId);
  return useQuery({
    queryKey: ["planning", userId, "active"],
    queryFn: api.ai.activePlan,
    enabled: userId !== null,
    staleTime: 10_000,
  });
}

export function useLatestExecutiveResult() {
  const userId = useUserStore((state) => state.userId);
  return useQuery<ExecutivePlanResponse | null>({
    queryKey: ["optimization", "latest", userId],
    queryFn: async () => null,
    enabled: false,
    initialData: null,
    staleTime: Infinity,
  });
}

export function useTasks() {
  const userId = useUserStore((state) => state.userId);
  
  return useQuery({
    queryKey: ["tasks", userId],
    queryFn: () => {
      if (userId === null) throw new Error("User ID is required to fetch tasks.");
      return api.tasks.list(userId);
    },
    enabled: userId !== null,
    // Prevent repeated page remounts from refetching the same user-scoped
    // task list; lifecycle/create mutations explicitly invalidate this query.
    staleTime: 15_000,
  });
}

export function useTask(taskId: string | number) {
  const userId = useUserStore((state) => state.userId);
  
  return useQuery({
    queryKey: ["tasks", taskId, userId],
    queryFn: () => {
      if (userId === null) throw new Error("User ID is required to fetch task.");
      return api.tasks.get(taskId, userId);
    },
    enabled: !!taskId && userId !== null,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  const userId = useUserStore((state) => state.userId);

  return useMutation({
    mutationFn: (data: Omit<TaskCreateRequest, "user_id">) => {
      if (userId === null) throw new Error("User ID is required to create a task.");
      return api.tasks.create({ ...data, user_id: userId });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["planning", userId] });
    },
  });
}

export function useStartTask() {
  const queryClient = useQueryClient();
  const userId = useUserStore((state) => state.userId);

  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: number; data: Omit<TaskStartRequest, "user_id"> }) => {
      if (userId === null) throw new Error("User ID is required to start a task.");
      return api.tasks.start(taskId, { ...data, user_id: userId });
    },
    onSuccess: (response, { taskId }) => {
      const task = (response as MultiEngineResponse)?.result?.task as Task | undefined;
      if (task) {
        queryClient.setQueriesData<TaskListResponse>({ queryKey: ["tasks"] }, (old) => {
          if (!old?.tasks) return old;
          return {
            ...old,
            tasks: old.tasks.map((t) => (t.id === taskId ? { ...t, ...task } : t)),
          };
        });
        if (userId !== null) {
          queryClient.setQueryData(["tasks", taskId, userId], { task });
        }
      }
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["tasks", taskId] });
      queryClient.invalidateQueries({ queryKey: ["planning", userId] });
    },
    onError: (error, { taskId }) => {
      if (isAlreadyStartedError(error)) {
        queryClient.invalidateQueries({ queryKey: ["tasks"] });
        queryClient.invalidateQueries({ queryKey: ["tasks", taskId] });
        queryClient.invalidateQueries({ queryKey: ["planning", userId] });
      }
    },
  });
}

export function useCompleteTask() {
  const queryClient = useQueryClient();
  const userId = useUserStore((state) => state.userId);

  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: number; data: Omit<TaskCompleteRequest, "user_id"> }) => {
      if (userId === null) throw new Error("User ID is required to complete a task.");
      return api.tasks.complete(taskId, { ...data, user_id: userId });
    },
    onSuccess: (response, { taskId }) => {
      const task = (response as MultiEngineResponse)?.result?.task as Task | undefined;
      if (task) {
        queryClient.setQueriesData<TaskListResponse>({ queryKey: ["tasks"] }, (old) => {
          if (!old?.tasks) return old;
          return {
            ...old,
            tasks: old.tasks.map((t) => (t.id === taskId ? { ...t, ...task } : t)),
          };
        });
        if (userId !== null) {
          queryClient.setQueryData(["tasks", taskId, userId], { task });
        }
      }
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["tasks", taskId] });
      queryClient.invalidateQueries({ queryKey: ["planning", userId] });
      queryClient.invalidateQueries({ queryKey: ["ml", "readiness"] });
      queryClient.invalidateQueries({ queryKey: ["ml", "status"] });
      queryClient.invalidateQueries({ queryKey: ["learning"] });
    },
    onError: (error, { taskId }) => {
      if (isAlreadyCompletedError(error)) {
        queryClient.invalidateQueries({ queryKey: ["tasks"] });
        queryClient.invalidateQueries({ queryKey: ["tasks", taskId] });
        queryClient.invalidateQueries({ queryKey: ["planning", userId] });
      }
    },
  });
}

export function useSubmitTaskFeedback() {
  const queryClient = useQueryClient();
  const userId = useUserStore((state) => state.userId);

  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: number; data: Omit<TaskFeedbackRequest, "user_id"> }) => {
      if (userId === null) throw new Error("User ID is required to submit feedback.");
      return api.tasks.feedback(taskId, { ...data, user_id: userId });
    },
    onSuccess: (_, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["tasks", taskId] });
      queryClient.invalidateQueries({ queryKey: ["ml", "readiness"] });
      queryClient.invalidateQueries({ queryKey: ["ml", "status"] });
      queryClient.invalidateQueries({ queryKey: ["learning"] });
    },
  });
}

export function useCreateExecutivePlan() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ExecutivePlanRequest) => api.ai.createExecutivePlan(data),
    onSuccess: (response, variables) => {
      queryClient.setQueryData(["optimization", "latest", variables.user_id], response);
    },
  });
}

export function useAIRecommendations() {
  return useMutation({
    mutationFn: ({ userId, daysBack }: { userId: number; daysBack?: number }) =>
      api.ai.recommendations(userId, daysBack),
  });
}

export function useAcceptPlan() {
  const queryClient = useQueryClient();
  const userId = useUserStore((state) => state.userId);

  return useMutation({
    mutationFn: (params: { schedule?: Array<Record<string, unknown>>; proposal_id?: string; version?: number } | Array<Record<string, unknown>>) => {
      if (userId === null) throw new Error("User ID is required to accept a plan.");
      if (Array.isArray(params)) {
        return api.ai.acceptPlan({ user_id: userId, schedule: params });
      }
      return api.ai.acceptPlan({ user_id: userId, ...params });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      if (userId) {
        queryClient.invalidateQueries({ queryKey: ["planning", userId] });
      }
      queryClient.invalidateQueries({ queryKey: ["system", "status"] });
    },
  });
}

export function useRejectPlan() {
  const queryClient = useQueryClient();
  const userId = useUserStore((state) => state.userId);

  return useMutation({
    mutationFn: (params?: { proposal_id?: string }) => {
      if (userId === null) throw new Error("User ID is required to reject a plan.");
      return api.ai.rejectPlan({ user_id: userId, proposal_id: params?.proposal_id });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["system", "status"] });
      if (userId) {
        queryClient.invalidateQueries({ queryKey: ["planning", userId] });
      }
    },
  });
}

export function useAICommand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CommandRequest) => api.ai.command(data),
    onSuccess: (data) => {
      if (data.intent === "create_task" || data.intent === "accept_plan") {
        queryClient.invalidateQueries({ queryKey: ["tasks"] });
      }
      // Planning intents create or update the persisted plan proposal.
      queryClient.invalidateQueries({ queryKey: ["planning"] });
      queryClient.invalidateQueries({ queryKey: ["jam", "conversations"] });
    },
  });
}

export function useProviderStatus() {
  return useQuery({
    queryKey: ["ai", "provider-status"],
    queryFn: api.ai.providerStatus,
    staleTime: 30_000,
  });
}

export function useTestProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.ai.testProvider(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai", "provider-status"] });
    },
  });
}

export function useJamConversations() {
  return useQuery({
    queryKey: ["jam", "conversations"],
    queryFn: api.jam.listConversations,
    staleTime: 10_000,
  });
}

export function useJamConversation(conversationId: string | null) {
  return useQuery({
    queryKey: ["jam", "conversations", conversationId],
    queryFn: () => (conversationId ? api.jam.getConversation(conversationId) : null),
    enabled: Boolean(conversationId),
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (title?: string) => api.jam.createConversation(title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jam", "conversations"] });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) => api.jam.deleteConversation(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jam", "conversations"] });
    },
  });
}

export function useBenchmarkDatasets() {
  return useQuery({
    queryKey: ["benchmarks", "datasets"],
    queryFn: api.benchmarks.getDatasets,
    staleTime: 60_000,
  });
}

export function useBenchmarkQuantum() {
  return useQuery({
    queryKey: ["benchmarks", "quantum"],
    queryFn: api.benchmarks.getQuantum,
    staleTime: 60_000,
  });
}

export function useBenchmarkRL() {
  return useQuery({
    queryKey: ["benchmarks", "rl"],
    queryFn: api.benchmarks.getRL,
    staleTime: 60_000,
  });
}

export function useBenchmarkVectorMemory() {
  return useQuery({
    queryKey: ["benchmarks", "vector-memory"],
    queryFn: api.benchmarks.getVectorMemory,
    staleTime: 60_000,
  });
}

