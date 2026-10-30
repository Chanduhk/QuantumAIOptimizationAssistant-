import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  formatDuration,
  formatEnergy,
  formatObjectiveRelation,
  formatPercentage,
  formatScore,
  formatStatus,
  normalizeErrorMessage,
} from "@/utils/formatters";
import { TechnicalDetails } from "@/components/common/TechnicalDetails";
import { HumanStatusBadge } from "@/components/common/HumanStatusBadge";

describe("Formatters and Status Normalization", () => {
  describe("formatStatus", () => {
    it("formats NOT_READY_INSUFFICIENT_DATA into human language", () => {
      const result = formatStatus("NOT_READY_INSUFFICIENT_DATA");
      expect(result.label).toBe("Not enough personal data yet");
      expect(result.description).toContain("Complete more tasks and record genuine feedback");
      expect(result.variant).toBe("warning");
    });

    it("formats NOT_PROVEN into human language", () => {
      const result = formatStatus("NOT_PROVEN");
      expect(result.label).toBe("Not yet validated");
      expect(result.description).toContain("empirical evidence");
      expect(result.variant).toBe("outline");
    });

    it("formats NOT_SUITABLE with quantum context into actionable explanation", () => {
      const result = formatStatus("NOT_SUITABLE", "quantum");
      expect(result.label).toBe("Not suitable for simulation");
      expect(result.description).toContain("classical solvers");
      expect(result.variant).toBe("secondary");
    });

    it("formats NOT_READY for hybrid comparison with context-specific explanation", () => {
      const result = formatStatus("NOT_READY", "hybrid_comparison");
      expect(result.label).toBe("Comparison pending");
      expect(result.description).toContain("both classical and simulation candidate results are required");
      expect(result.variant).toBe("outline");
    });

    it("formats uninitialized status into model readiness language", () => {
      const result = formatStatus("uninitialized");
      expect(result.label).toBe("Model not yet initialized");
      expect(result.description).toContain("baseline calibration");
      expect(result.variant).toBe("secondary");
    });

    it("formats UNKNOWN or null into status unavailable", () => {
      expect(formatStatus("UNKNOWN").label).toBe("Status unavailable");
      expect(formatStatus(null).label).toBe("Status unavailable");
      expect(formatStatus(undefined).label).toBe("Status unavailable");
    });

    it("formats READY and COMPLETE accurately", () => {
      expect(formatStatus("READY").label).toBe("Available");
      expect(formatStatus("COMPLETE").label).toBe("Completed");
    });

    it("converts unknown status strings to title-cased readable text", () => {
      const result = formatStatus("CUSTOM_PIPELINE_STATE");
      expect(result.label).toBe("Custom Pipeline State");
      expect(result.description).toContain("CUSTOM_PIPELINE_STATE");
    });
  });

  describe("formatDuration", () => {
    it("handles null and undefined gracefully without throwing", () => {
      expect(formatDuration(null)).toBe("Not recorded");
      expect(formatDuration(undefined)).toBe("Not recorded");
      expect(formatDuration(NaN)).toBe("Not recorded");
    });

    it("formats minutes correctly under 60 minutes", () => {
      expect(formatDuration(0)).toBe("0 min");
      expect(formatDuration(25)).toBe("25 min");
      expect(formatDuration(45.4)).toBe("45 min");
    });

    it("formats durations of 60 minutes or more into hours and minutes", () => {
      expect(formatDuration(60)).toBe("1h");
      expect(formatDuration(90)).toBe("1h 30m");
      expect(formatDuration(150)).toBe("2h 30m");
    });
  });

  describe("formatScore, formatPercentage, formatEnergy", () => {
    it("formats scores safely with fallback", () => {
      expect(formatScore(null)).toBe("—");
      expect(formatScore(undefined)).toBe("—");
      expect(formatScore(3.14159, 2)).toBe("3.14");
    });

    it("formats percentages accurately", () => {
      expect(formatPercentage(null)).toBe("—");
      expect(formatPercentage(0.752)).toBe("75.2%");
      expect(formatPercentage(1.0)).toBe("100.0%");
    });

    it("formats Hamiltonian energy metrics", () => {
      expect(formatEnergy(null)).toBe("—");
      expect(formatEnergy(-4.205)).toBe("-4.2050 (energy)");
    });
  });

  describe("formatObjectiveRelation", () => {
    it("translates QUANTUM_HIGHER and CLASSICAL_HIGHER", () => {
      const q = formatObjectiveRelation("QUANTUM_HIGHER");
      expect(q.label).toBe("Simulation objective higher");
      expect(q.explanation).toContain("QAOA simulation");

      const c = formatObjectiveRelation("CLASSICAL_HIGHER");
      expect(c.label).toBe("Classical objective higher");
      expect(c.explanation).toContain("classical solver");
    });

    it("translates EQUAL and handles uncompared state", () => {
      const eq = formatObjectiveRelation("EQUAL");
      expect(eq.label).toBe("Equivalent objective scores");

      const missing = formatObjectiveRelation(null);
      expect(missing.label).toBe("Not compared");
    });
  });

  describe("normalizeErrorMessage", () => {
    it("identifies missing completed task history and explains the cause clearly", () => {
      const norm = normalizeErrorMessage("No completed tasks found for the user.");
      expect(norm.title).toBe("Completed Task History Needed");
      expect(norm.explanation).toContain("requires at least one completed task");
      expect(norm.isRetryable).toBe(false);
    });

    it("identifies missing active tasks", () => {
      const norm = normalizeErrorMessage("No active tasks to schedule.");
      expect(norm.title).toBe("No Active Tasks Found");
      expect(norm.actionSuggestion).toContain("Tasks");
      expect(norm.isRetryable).toBe(false);
    });

    it("identifies network and connection failures with retry guidance", () => {
      const norm = normalizeErrorMessage("Failed to fetch");
      expect(norm.title).toBe("Connection Unavailable");
      expect(norm.isRetryable).toBe(true);
    });
  });

  describe("TechnicalDetails component", () => {
    it("is closed by default and reveals masked data upon interaction", () => {
      const sensitiveData = {
        task_id: 101,
        user_token: "secret_123456",
        authorization: "Bearer abcdef1234567890",
      };

      render(<TechnicalDetails data={sensitiveData} title="Diagnostics" />);
      expect(screen.queryByText(/\[PROTECTED_CREDENTIAL\]/)).not.toBeInTheDocument();

      const button = screen.getByRole("button", { name: /Diagnostics/ });
      fireEvent.click(button);

      expect(screen.getByText(/\[PROTECTED_CREDENTIAL\]/)).toBeInTheDocument();
      expect(screen.queryByText("secret_123456")).not.toBeInTheDocument();
    });

    it("renders nothing when no data or children are provided", () => {
      const { container } = render(<TechnicalDetails data={null} />);
      expect(container).toBeEmptyDOMElement();
    });
  });

  describe("HumanStatusBadge component", () => {
    it("renders formatted badge label with description", () => {
      render(
        <HumanStatusBadge
          status="NOT_READY_INSUFFICIENT_DATA"
          showDescription
        />
      );
      expect(screen.getByText("Not enough personal data yet")).toBeInTheDocument();
      expect(
        screen.getByText(/Complete more tasks and record genuine feedback/)
      ).toBeInTheDocument();
    });
  });
});
