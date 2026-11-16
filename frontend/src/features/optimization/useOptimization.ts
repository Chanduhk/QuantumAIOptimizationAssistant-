import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { ExecutivePlanResponse, OrchestratorTaskInput, Task } from "@/api/endpoints";
import { useCreateExecutivePlan, useLatestExecutiveResult, useTasks } from "@/api/hooks";
import { useUserStore } from "@/stores/userStore";
import { isPlanningEligible } from "@/features/tasks/taskUtils";

const STORAGE_KEY = "heliox-latest-executive";

function readStored(userId: number): { at: number; data: ExecutivePlanResponse } | null {
  try {
    const raw = sessionStorage.getItem(`${STORAGE_KEY}:${userId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeStored(userId: number, data: ExecutivePlanResponse) {
  try {
    sessionStorage.setItem(`${STORAGE_KEY}:${userId}`, JSON.stringify({ at: Date.now(), data }));
  } catch {
    // Storage may be full or unavailable; the in-memory cache still works.
  }
}

export function mapTasksToOrchestratorInput(selected: Task[]): OrchestratorTaskInput[] {
  return selected.map((t) => {
    const depIds: string[] = Array.isArray(t.dependencies)
      ? t.dependencies
          .map((d) => (d != null ? String(d).trim() : ""))
          .filter((d) => d.length > 0)
      : [];
    return {
      id: String(t.id),
      title: t.title,
      description: t.description ?? undefined,
      type: t.task_type,
      priority: t.priority,
      duration: t.estimated_duration as number,
      estimated_duration_unit: (t.estimated_duration_unit as "minutes" | "hours") || "minutes",
      estimated_duration_source: t.estimated_duration_source ?? undefined,
      deadline: t.deadline ?? undefined,
      depends_on_task_ids: depIds,
      dependencies: depIds,
      goal_id: t.goal_id ?? undefined,
      context_info: t.context_info ?? undefined,
    };
  });
}

/**
 * Runs the executive planning pipeline (/ai/executive-plan) over the user's
 * eligible tasks and exposes the latest result. The result is not persisted
 * by the backend, so it is cached per session in the browser.
 */
export function useOptimization() {
  const userId = useUserStore((s) => s.userId);
  const queryClient = useQueryClient();
  const tasksQuery = useTasks();
  const latest = useLatestExecutiveResult();
  const mutation = useCreateExecutivePlan();
  const [ranAt, setRanAt] = React.useState<number | null>(null);

  // Rehydrate the last run after a reload.
  React.useEffect(() => {
    if (userId === null || latest.data) return;
    const stored = readStored(userId);
    if (stored) {
      queryClient.setQueryData(["optimization", "latest", userId], stored.data);
      setRanAt(stored.at);
    }
  }, [userId, latest.data, queryClient]);

  const tasks = React.useMemo(() => tasksQuery.data?.tasks ?? [], [tasksQuery.data]);
  const eligible = React.useMemo(() => tasks.filter(isPlanningEligible), [tasks]);
  const ineligible = React.useMemo(() => tasks.filter((t) => !isPlanningEligible(t) && t.lifecycle_state !== "completed" && !t.completed), [tasks]);

  const run = React.useCallback(
    (selected: Task[], query?: string) => {
      if (userId === null || selected.length === 0) return;
      mutation.mutate(
        {
          user_id: userId,
          query: query?.trim() || undefined,
          tasks: mapTasksToOrchestratorInput(selected),
        },
        {
          onSuccess: (data) => {
            writeStored(userId, data);
            setRanAt(Date.now());
          },
        }
      );
    },
    [mutation, userId]
  );

  return {
    tasksQuery,
    eligible,
    ineligible,
    run,
    isRunning: mutation.isPending,
    error: mutation.error,
    result: latest.data ?? null,
    ranAt,
  };
}
