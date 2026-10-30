import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const queries = vi.hoisted(() => ({
  health: { data: { status: "operational", database_connected: true }, isLoading: false, isError: false },
  system: { data: { status: "operational", ai_metrics: {} }, isLoading: false, isError: false },
  quantum: { data: { available: true, direct_execution_exposed: false }, isLoading: false, isError: false },
  model: { data: { status: "uninitialized", models_registered: 0, in_memory_only: true }, isLoading: false, isError: false },
  tasks: { data: { tasks: [] as Array<Record<string, unknown>> }, isLoading: false, isError: false },
  collection: { data: { result: { quality_audit: { readiness_status: "CONDITIONALLY_READY_FOR_TRAINING_AUDIT" }, collection_report: {} } }, isLoading: false, isError: false },
  latest: { data: { result: { optimization_evidence: { prediction_matrix_status: "NOT_READY", quantum_suitability: { status: "NOT_READY" } }, executive_summary: "Current readiness evidence" } }, isLoading: false, isError: false },
  mlReadiness: { data: { overall_status: "NOT_READY_NO_DATA", components: {} }, isLoading: false, isError: false },
  inventory: { data: { total_components: 0, components: [] }, isLoading: false, isError: false },
}));

vi.mock("@/api/hooks", () => ({
  useSystemHealth: () => queries.health,
  useSystemStatus: () => queries.system,
  useQuantumStatus: () => queries.quantum,
  useMLModelStatus: () => queries.model,
  useTasks: () => queries.tasks,
  useDataCollectionStatus: () => queries.collection,
  useLatestExecutiveResult: () => queries.latest,
  useMLReadiness: () => queries.mlReadiness,
  useComponentInventory: () => queries.inventory,
}));

import { DashboardPage } from "@/pages/DashboardPage";

describe("DashboardPage", () => {
  beforeEach(() => {
    queries.tasks.isError = false;
    queries.latest.data = { result: { optimization_evidence: { prediction_matrix_status: "NOT_READY", quantum_suitability: { status: "NOT_READY" } }, executive_summary: "Current readiness evidence" } };
  });

  it("renders the Neural Core with backend-derived readiness and existing dashboard information", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => null);
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "HELIOX Neural Core" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Executive Brain\. Executive response is available in this session/ })).toBeInTheDocument();
    expect(screen.getAllByText("CONDITIONALLY_READY_FOR_TRAINING_AUDIT").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("NOT READY").length).toBeGreaterThan(0);
    expect(screen.getByText(/No physical quantum hardware is used/)).toBeInTheDocument();
    expect(screen.getByText("Recent task activity")).toBeInTheDocument();
  });

  it("does not claim live memory status when the backend does not expose it", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => null);
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getByRole("link", { name: /Memory\./ })).toBeInTheDocument();
  });

  it("does not show an empty cached task breakdown as a real zero after an API error", () => {
    queries.tasks.isError = true;
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => null);
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getByText("Task breakdown unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/0 in progress · 0 in backlog/)).not.toBeInTheDocument();
    queries.tasks.isError = false;
  });

  it("renders successfully when inventory components is an object map as returned by the live backend", () => {
    queries.inventory.data = {
      total_components: 16,
      components: {
        duration_ratio_model: {
          canonical_id: "duration_ratio_model",
          display_name: "Duration Prediction Model",
          operational_state: "AVAILABLE",
          can_execute_now: true,
        },
        classical_optimizer: {
          canonical_id: "classical_optimizer",
          display_name: "Classical Schedule Optimizer",
          operational_state: "AVAILABLE",
          can_execute_now: true,
        },
        vector_memory_embedding: {
          canonical_id: "vector_memory_embedding",
          display_name: "Vector Memory Embeddings",
          operational_state: "AVAILABLE",
          can_execute_now: true,
        },
      } as unknown as any,
    };
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => null);
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "HELIOX Neural Core" })).toBeInTheDocument();
    queries.inventory.data = { total_components: 0, components: [] };
  });
});
