import { describe, expect, it } from "vitest";
import { parseExecutive, proposalBlocks } from "@/features/optimization/parse";

// Trimmed from a real /api/v1/ai/executive-plan response.
const response = {
  result: {
    executive_summary: "Executive recommendation: Proceed with dependency-feasible plan (confidence 86.71%, risk medium).",
    executive_confidence: { confidence: 86.71 },
    risk_summary: { risk_level: "low", executive_risk_level: "medium", conflict_count: 10 },
    executive_reasoning: { recommended_action: "Proceed with dependency-feasible plan", why: "Strongest fused evidence.", expected_benefits: ["Feasible"], known_risks: [] },
    candidate_plans: {
      plans: [
        {
          plan_type: "daily_plan",
          plan: {
            best_focus_hours: [10, 11, 14],
            tasks: [
              { task_id: "21", title: "Write quarterly report", task_type: "work", priority: 5, recommended_hour: 10, estimated_duration: 90, predicted_productivity: 52.58 },
              { task_id: "22", title: "Study", task_type: "study", priority: 4, recommended_hour: 11, estimated_duration: 60 },
            ],
          },
        },
        { plan_type: "schedule", plan: [] },
        { plan_type: "optimized_schedule", plan: {} },
      ],
    },
    recommended_plan: {
      option_id: "candidate-3",
      title: "Optimized Schedule",
      overall_score: 67.39,
      decision_analysis: {
        options: [
          { option_id: "candidate-1", title: "Daily Plan", metadata: { plan_type: "daily_plan" } },
          { option_id: "candidate-3", title: "Optimized Schedule", metadata: { plan_type: "optimized_schedule" } },
        ],
        evaluations: [
          { option_id: "candidate-1", overall_score: 66.37, risk_score: 5 },
          { option_id: "candidate-3", overall_score: 67.39, risk_score: 5 },
        ],
        ranking: ["candidate-3", "candidate-1"],
      },
    },
    optimization_evidence: {
      mode: "PRODUCTION",
      prediction_matrix_status: "COMPLETE",
      quantum_suitability: { status: "NOT_SUPPORTED", variable_count: 51, reasons: ["QAOA variable count exceeds local simulator limit"] },
      quantum_candidate: { status: "NOT_SUPPORTED" },
      hybrid_comparison: { status: "INVALID_INPUT", objective_relation: "NOT_COMPARABLE" },
    },
    future_analysis: {
      ranked_futures: [{ selected_scenario_name: "Baseline", overall_score: 85.1, objective_scores: { Productivity: 73.25 }, optimization_summary: { objective_weights: { Productivity: 1 } } }],
    },
  },
};

describe("parseExecutive", () => {
  const view = parseExecutive(response);

  it("reads the executive decision", () => {
    expect(view.confidence).toBe(86.71);
    expect(view.reasoning.action).toBe("Proceed with dependency-feasible plan");
    expect(view.recommended.title).toBe("Optimized Schedule");
  });

  it("builds hour blocks from the daily plan", () => {
    expect(view.schedule).toHaveLength(2);
    expect(view.schedule[0]).toMatchObject({ title: "Write quarterly report", start: 10, end: 11.5, priority: 5 });
    expect(view.focusHours).toEqual([10, 11, 14]);
  });

  it("joins evaluations to option titles and ranks", () => {
    const best = view.evaluations.find((e) => e.recommended);
    expect(best).toMatchObject({ title: "Optimized Schedule", rank: 1, overall: 67.39 });
    expect(view.evaluations.find((e) => e.id === "candidate-1")?.rank).toBe(2);
  });

  it("surfaces quantum suitability honestly", () => {
    expect(view.optimization.suitability.status).toBe("NOT_SUPPORTED");
    expect(view.optimization.suitability.variable_count).toBe(51);
    expect(view.objectiveScores).toEqual([{ name: "Productivity", value: 73.25, weight: 1 }]);
  });

  it("handles an empty response without throwing", () => {
    const empty = parseExecutive(null);
    expect(empty.hasResult).toBe(false);
    expect(empty.schedule).toEqual([]);
  });
});

describe("proposalBlocks", () => {
  it("maps JAM proposal schedule items", () => {
    const blocks = proposalBlocks([
      { task_id: "proposed:a", title: "Call the bank", priority: 3, scheduled_hour: 9, scheduled_end_hour: 10, deadline_expression: "today" },
      { task_id: "x", title: "No hour" },
    ]);
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ title: "Call the bank", start: 9, end: 10, meta: "Due today" });
  });
});
