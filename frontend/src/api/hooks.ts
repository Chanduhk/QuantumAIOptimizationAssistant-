import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ExecutivePlanRequest, CommandRequest } from "./endpoints";
import { useUserStore } from "@/stores/userStore";

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

export function useTask(taskId: string) {
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
