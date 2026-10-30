import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mapBackendState, type NeuralCoreNode } from "@/components/neural-core/coreState";
import { NeuralCore } from "@/components/neural-core/NeuralCore";
import { OptimizationPipelineVisual, QuantumConceptVisual } from "@/components/visualizations/HelioxVisualizations";

const nodes: NeuralCoreNode[] = [
  { id: "memory", label: "Memory", state: "UNKNOWN", detail: "Status is not exposed.", route: "/intelligence" },
  { id: "executive", label: "Executive Brain", state: "NOT_READY", detail: "No result available.", route: "/planning" },
];

afterEach(() => vi.restoreAllMocks());

describe("HELIOX Neural Core", () => {
  it.each([
    ["operational", "READY"],
    ["PROCESSING", "PROCESSING"],
    ["NOT_READY", "NOT_READY"],
    ["CONDITIONALLY_READY_FOR_TRAINING_AUDIT", "NOT_PROVEN"],
    ["NOT_SUPPORTED", "UNAVAILABLE"],
    ["DEGRADED", "ERROR"],
    [undefined, "UNKNOWN"],
  ] as const)("maps backend status %s to %s", (value, expected) => {
    expect(mapBackendState(value)).toBe(expected);
  });

  it("uses the 2D fallback when WebGL is unavailable and retains accessible node navigation", async () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => null);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<NeuralCore nodes={nodes} />} />
          <Route path="/intelligence" element={<p>Intelligence destination</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /static conceptual HELIOX neural core/i })).toBeInTheDocument();
    expect(screen.getByText(/Executive evidence:/).parentElement).toHaveTextContent("NOT READY");
    expect(screen.getAllByRole("link", { name: /Memory/ }).length).toBeGreaterThan(0);
    fireEvent.click(screen.getAllByRole("link", { name: /Memory/ })[0]);
    expect(await screen.findByText("Intelligence destination")).toBeInTheDocument();
  });

  it("presents backend stage states without inventing optimization results", () => {
    render(<OptimizationPipelineVisual stages={[
      { label: "Prediction", state: "blocked", detail: "NOT_READY" },
      { label: "QAOA", state: "pending", detail: "Not run" },
    ]} />);
    expect(screen.getByText("NOT_READY")).toBeInTheDocument();
    expect(screen.getByText("Not run")).toBeInTheDocument();
    expect(screen.getByText(/not a circuit run/i)).toBeInTheDocument();
  });

  it("does not fabricate a graph when the API has no problem mapping", () => {
    render(<QuantumConceptVisual variableMapping={undefined} quadraticTerms={undefined} />);
    expect(screen.getByText("Quantum problem data unavailable")).toBeInTheDocument();
    expect(screen.getByText(/a conceptual sample graph is intentionally not shown/i)).toBeInTheDocument();
    expect(screen.queryByText("x₁")).not.toBeInTheDocument();
  });

  it("renders only returned variables and quadratic coefficients", () => {
    render(<QuantumConceptVisual
      variableMapping={[{ variable_id: "task-21@10", task_id: "task-21", candidate_hour: 10 }, { variable_id: "task-22@11", task_id: "task-22", candidate_hour: 11 }]}
      quadraticTerms={[{ variables: ["task-21@10", "task-22@11"], coefficient: -2.5 }]}
    />);
    expect(screen.getByText("task-21 · 10:00")).toBeInTheDocument();
    expect(screen.getByText("task-22 · 11:00")).toBeInTheDocument();
    expect(screen.getByText(/1 returned quadratic terms/i)).toBeInTheDocument();
    expect(screen.queryByText("x₁")).not.toBeInTheDocument();
  });
});
