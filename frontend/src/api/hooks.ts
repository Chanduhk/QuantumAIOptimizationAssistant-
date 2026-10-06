import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ExecutivePlanRequest, CommandRequest, TaskCreateRequest, TaskStartRequest, TaskCompleteRequest, type AuthUser } from "./endpoints";
import { ApiRequestError } from "./client";
import { useUserStore } from "@/stores/userStore";

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

export function useMLModelStatus() {
  return useQuery({
    queryKey: ["ml", "status"],
    queryFn: api.ml.getModelStatus,
    refetchInterval: 30000,
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
    onSuccess: (_, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["tasks", taskId] });
      queryClient.invalidateQueries({ queryKey: ["planning", userId] });
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
    onSuccess: (_, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["tasks", taskId] });
      queryClient.invalidateQueries({ queryKey: ["planning", userId] });
    },
  });
}

export function useCreateExecutivePlan() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ExecutivePlanRequest) => api.ai.createExecutivePlan(data),
    onSuccess: () => {
      // Invalidate tasks as a new plan might create tasks
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

export function useAICommand() {
  return useMutation({
    mutationFn: (data: CommandRequest) => api.ai.command(data),
  });
}
