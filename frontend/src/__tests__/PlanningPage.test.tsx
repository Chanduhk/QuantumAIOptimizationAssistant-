import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mutate, tasksResult, mutationResult } = vi.hoisted(() => ({
  mutate: vi.fn(),
  tasksResult: { data: { tasks: [] as Array<Record<string, unknown>> }, isLoading: false, error: null as unknown },
  mutationResult: { mutate: vi.fn(), isPending: false, error: null as unknown, data: null as unknown },
}));

vi.mock("@/api/hooks", () => ({
  useTasks: () => tasksResult,
  useCreateExecutivePlan: () => ({ ...mutationResult, mutate }),
  useLatestExecutiveResult: () => ({ data: null, isLoading: false, error: null }),
  useAcceptPlan: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false, error: null }),
  useRejectPlan: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false, error: null }),
}));

import { PlanningPage } from "@/pages/PlanningPage";
import { useUserStore } from "@/stores/userStore";

const planningTask = {
  id: 8,
  user_id: 303,
  title: "Prepare a review",
  task_type: "focus",
  priority: 3,
  estimated_duration: 45,
  estimated_duration_unit: "minutes",
  estimated_duration_source: "task_api",
  actual_duration: null,
  created_at: null,
  start_time: null,
  end_time: null,
  completed: false,
  lifecycle_state: "created",
  outcome_valid: null,
};

describe("PlanningPage provenance handoff", () => {
  beforeEach(() => {
    mutate.mockReset();
    tasksResult.data = { tasks: [planningTask] };
    tasksResult.isLoading = false;
    tasksResult.error = null;
    mutationResult.isPending = false;
    mutationResult.error = null;
    mutationResult.data = null;
    useUserStore.getState().setUserId(303);
  });

  it("passes the recorded estimate unit and source through to FastAPI", () => {
    render(<MemoryRouter><PlanningPage /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({
      user_id: 303,
      tasks: [expect.objectContaining({
        id: 8,
        duration: 45,
        estimated_duration_unit: "minutes",
        estimated_duration_source: "task_api",
      })],
    }));
  });

  it("rejects unknown legacy provenance locally without changing it", () => {
    tasksResult.data = { tasks: [{ ...planningTask, estimated_duration_unit: null, estimated_duration_source: null }] };
    render(<MemoryRouter><PlanningPage /></MemoryRouter>);
    expect(screen.getByRole("button", { name: "Generate plan" })).toBeDisabled();
    expect(screen.getByText(/Estimate unit is unknown/)).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });
});
