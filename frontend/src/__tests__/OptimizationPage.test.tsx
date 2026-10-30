import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mutate, tasksResult, mutationResult } = vi.hoisted(() => ({
  mutate: vi.fn(),
  tasksResult: { data: { tasks: [] as Array<Record<string, unknown>> }, isLoading: false, error: null as unknown, refetch: vi.fn() },
  mutationResult: { mutate: vi.fn(), isPending: false, error: null as unknown, data: null as unknown },
}));

vi.mock("@/api/hooks", () => ({
  useTasks: () => tasksResult,
  useCreateExecutivePlan: () => ({ ...mutationResult, mutate }),
  useLatestExecutiveResult: () => ({ data: null, isLoading: false, error: null }),
  useBenchmarkQuantum: () => ({ data: null, isLoading: false, error: null }),
}));

import { OptimizationPage } from "@/pages/OptimizationPage";
import { useUserStore } from "@/stores/userStore";

const eligibleTask = {
  id: 7,
  user_id: 101,
  title: "Review proposal",
  task_type: "work",
  priority: 2,
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

describe("OptimizationPage", () => {
  beforeEach(() => {
    mutate.mockReset();
    tasksResult.data = { tasks: [eligibleTask] };
    tasksResult.isLoading = false;
    tasksResult.error = null;
    mutationResult.isPending = false;
    mutationResult.error = null;
    mutationResult.data = null;
    useUserStore.getState().setUserId(101);
  });

  it("sends only eligible tasks with identity and minute provenance", () => {
    render(<OptimizationPage />);
    fireEvent.click(screen.getByRole("button", { name: "Run Executive Planning" }));
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({
      user_id: 101,
      tasks: [{
        id: 7,
        title: "Review proposal",
        type: "work",
        priority: 2,
        duration: 45,
        estimated_duration_unit: "minutes",
        estimated_duration_source: "task_api",
      }],
    }));
  });

  it("excludes unknown duration provenance and explains why", () => {
    tasksResult.data = { tasks: [{ ...eligibleTask, estimated_duration_unit: null, estimated_duration_source: null }] };
    render(<OptimizationPage />);
    expect(screen.getByText(/No task currently meets/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Executive Planning" })).toBeDisabled();
    fireEvent.click(screen.getByText(/Why tasks are excluded/));
    expect(screen.getByText(/Estimate unit is unknown/)).toBeInTheDocument();
  });

  it("renders backend suitability, QAOA, hybrid, and executive evidence without choosing a winner", () => {
    mutationResult.data = {
      result: {
        optimization_evidence: {
          mode: "PRODUCTION",
          prediction_matrix_status: "NOT_READY",
          quantum_suitability: { status: "NOT_READY", reasons: ["training data unavailable"] },
          quantum_candidate: { status: "NOT_READY", candidate: null, reason: "training data unavailable" },
          hybrid_comparison: { status: "NOT_READY", reasons: ["candidate unavailable"] },
          executive_decision_authority: "Executive Cognitive Brain",
        },
        recommended_plan: { title: "Executive recommendation" },
      },
    };
    render(<OptimizationPage />);
    expect(screen.getAllByText("NOT_READY", { selector: "p" }).length).toBeGreaterThanOrEqual(4);
    expect(screen.getAllByText(/training data unavailable/)).toHaveLength(2);
    expect(screen.getByText(/Executive recommendation/)).toBeInTheDocument();
    expect(screen.getByText(/local software simulation only/)).toBeInTheDocument();
  });

  it("renders actual candidate assignments and objective evidence when returned", () => {
    mutationResult.data = {
      result: {
        optimization_evidence: {
          mode: "PRODUCTION",
          prediction_matrix_status: "COMPLETE",
          quantum_suitability: { status: "SUITABLE", reasons: [] },
          quantum_candidate: { status: "CANDIDATE", candidate: { assignments: [{ task_id: 7, candidate_hour: 9 }], objective_value: 3.2, feasible: true, repaired: false } },
          hybrid_comparison: {
            status: "COMPARED",
            classical: { assignments: [{ task_id: 7, assigned_hour: 10 }], objective_value: 3.1, feasibility: "FEASIBLE" },
            quantum: { assignments: [{ task_id: 7, assigned_hour: 9 }], objective_value: 3.2, feasibility: "FEASIBLE" },
            objective_relation: "QUANTUM_HIGHER",
          },
        },
        recommended_plan: { title: "Executive recommendation" },
      },
    };
    render(<OptimizationPage />);
    expect(screen.getAllByText("SUITABLE").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("COMPARED").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/assigned_hour/)).toHaveLength(2);
    expect(screen.getByText(/objective_relation/)).toBeInTheDocument();
    expect(screen.getByText(/Executive recommendation/)).toBeInTheDocument();
  });

  it.each(["NOT_SUITABLE", "NOT_SUPPORTED"])("shows the backend %s reason", (status) => {
    mutationResult.data = {
      result: {
        optimization_evidence: {
          mode: "PRODUCTION",
          quantum_suitability: { status, reasons: ["backend reason"] },
          quantum_candidate: { status, candidate: null, reason: "backend reason" },
          hybrid_comparison: { status: "NOT_READY", reasons: ["candidate unavailable"] },
        },
        recommended_plan: {},
      },
    };
    render(<OptimizationPage />);
    expect(screen.getAllByText(status).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/backend reason/)).toHaveLength(2);
  });

  it("shows recoverable backend errors", () => {
    mutationResult.error = new Error("Service unavailable");
    render(<OptimizationPage />);
    expect(screen.getByRole("alert")).toHaveTextContent("Service unavailable");
  });

  it("labels development demo evidence and does not present it as production", () => {
    mutationResult.data = {
      result: {
        optimization_evidence: { mode: "DEVELOPMENT/DEMO", quantum_candidate: null },
        recommended_plan: {},
      },
    };
    render(<OptimizationPage />);
    expect(screen.getByText(/DEVELOPMENT\/DEMO — not production evidence/)).toBeInTheDocument();
  });
});
