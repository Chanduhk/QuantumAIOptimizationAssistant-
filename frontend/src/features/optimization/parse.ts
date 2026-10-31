import type { ExecutivePlanResponse } from "@/api/endpoints";
import { get, num, rec, recs, str, strs, type Rec } from "@/lib/data";

export interface ScheduleBlock {
  key: string;
  title: string;
  taskType: string;
  priority: number | null;
  start: number; // decimal hour
  end: number;
  rationale?: string;
  meta?: string;
  warning?: string;
  origin?: string;
}

export interface ObjectiveScore {
  name: string;
  value: number;
  weight: number | null;
}

/** Normalized, read-only view over the /ai/executive-plan result. */
export function parseExecutive(response: ExecutivePlanResponse | null | undefined) {
  const r = (response?.result ?? {}) as Rec;
  const evidence = rec(r.optimization_evidence) ?? rec(get(r, "executive_context.optimization_evidence")) ?? {};
  const reasoning = rec(r.executive_reasoning) ?? {};
  const trace = rec(get(r, "executive_trace.trace")) ?? {};
  const recommended = rec(r.recommended_plan) ?? {};
  const analysis = rec(recommended.decision_analysis) ?? {};
  const plans = recs(get(r, "candidate_plans.plans"));
  const options = recs(analysis.options);
  const ranking = strs(analysis.ranking);
  const evaluations = recs(analysis.evaluations).map((e) => {
    const option = options.find((o) => o.option_id === e.option_id);
    return {
      id: str(e.option_id),
      title: str(option?.title, str(e.option_id)),
      planType: str(get(option, "metadata.plan_type")),
      overall: num(e.overall_score),
      utility: num(e.utility_score),
      risk: num(e.risk_score),
      confidence: num(e.confidence_score),
      alignment: num(e.alignment_score),
      rank: ranking.indexOf(str(e.option_id)) + 1 || null,
      recommended: e.option_id === recommended.option_id,
    };
  });

  const dailyPlan = rec(plans.find((p) => p.plan_type === "daily_plan")?.plan);
  const dailyTasks = recs(dailyPlan?.tasks);
  const schedule: ScheduleBlock[] = dailyTasks
    .filter((t) => num(t.recommended_hour) !== null)
    .map((t, i) => {
      const start = num(t.recommended_hour) ?? 0;
      const minutes = num(t.estimated_duration) ?? 60;
      const productivity = num(t.predicted_productivity);
      return {
        key: `${str(t.task_id)}-${i}`,
        title: str(t.title, `Task ${str(t.task_id)}`),
        taskType: str(t.task_type),
        priority: num(t.priority),
        start,
        end: start + minutes / 60,
        rationale: str(t.rationale) || undefined,
        meta: productivity !== null ? `Predicted productivity ${productivity.toFixed(1)}` : undefined,
      };
    });

  const future = rec(r.future_analysis) ?? {};
  const ranked = rec(recs(future.ranked_futures)[0]) ?? {};
  const weights = rec(get(ranked, "optimization_summary.objective_weights")) ?? {};
  const objectiveScores: ObjectiveScore[] = Object.entries(rec(ranked.objective_scores) ?? {})
    .map(([name, value]) => ({ name, value: num(value) ?? 0, weight: num(weights[name]) }))
    .filter((o) => Number.isFinite(o.value));

  return {
    hasResult: Boolean(response?.result),
    summary: str(r.executive_summary),
    confidence: num(get(r, "executive_confidence.confidence")) ?? num(reasoning.confidence),
    risk: rec(r.risk_summary) ?? {},
    reasoning: {
      action: str(reasoning.recommended_action),
      why: str(reasoning.why),
      benefits: strs(reasoning.expected_benefits),
      risks: strs(reasoning.known_risks),
      alternatives: recs(reasoning.alternatives),
      priority: num(reasoning.executive_priority),
    },
    trace: {
      evidence: recs(trace.evidence_used),
      conflicts: recs(trace.conflicts_found),
      steps: strs(trace.reasoning_steps),
      tradeoffs: recs(trace.tradeoffs).length ? recs(trace.tradeoffs) : recs(get(r, "executive_tradeoffs.tradeoffs")),
      rejected: recs(trace.rejected_alternatives),
    },
    optimization: {
      mode: str(evidence.mode),
      matrixStatus: str(evidence.prediction_matrix_status),
      nontriviality: str(evidence.nontriviality_status),
      suitability: rec(evidence.quantum_suitability) ?? {},
      candidate: rec(evidence.quantum_candidate) ?? {},
      hybrid: rec(evidence.hybrid_comparison) ?? {},
      authority: str(evidence.executive_decision_authority),
    },
    recommended: {
      optionId: str(recommended.option_id),
      title: str(recommended.title),
      reasoning: str(recommended.reasoning),
      score: num(recommended.overall_score),
      executiveRecommendation: str(recommended.executive_recommendation),
    },
    evaluations,
    candidatePlanCount: plans.length,
    schedule,
    focusHours: (Array.isArray(dailyPlan?.best_focus_hours) ? (dailyPlan.best_focus_hours as unknown[]) : []).map(num).filter((n): n is number => n !== null),
    dependency: rec(get(r, "executive_objectives.dependency_state")) ?? {},
    simulation: rec(future.simulation) ?? {},
    strategic: rec(future.strategic_plan) ?? {},
    rankedFuture: ranked,
    objectiveScores,
    explanations: rec(r.explanations) ?? {},
    context: rec(get(r, "executive_context.context_snapshot")) ?? {},
    execution: {
      health: rec(r.execution_health) ?? {},
      summary: str(get(r, "execution_summary.summary")),
      explanation: str(get(r, "execution_summary.explanation")),
      alerts: recs(r.execution_alerts),
      recovery: recs(r.execution_recovery),
      status: str(get(r, "execution_dashboard.current_execution_status")),
      nextCheckpoint: rec(r.next_execution_checkpoint) ?? {},
    },
    resources: {
      health: rec(r.resource_health) ?? {},
      summary: str(get(r, "resource_summary.executive_summary")),
      conflicts: recs(r.resource_conflicts),
      recommendations: recs(r.resource_recommendations),
      forecast: rec(r.resource_forecast) ?? {},
      score: num(get(r, "executive_resource_score.score")),
    },
    governance: {
      health: rec(r.governance_health) ?? {},
      status: str(get(r, "governance_state.status")) || str(get(r, "governance_dashboard.governance_status")),
      summary: str(get(r, "governance_summary.executive_summary")),
      violations: recs(r.governance_violations),
      recommendations: recs(r.governance_recommendations),
      compliance: rec(r.governance_policy_compliance) ?? {},
      score: num(get(r, "executive_governance_score.score")),
      policies: strs(get(r, "governance_audit.policies_evaluated")),
    },
    learning: {
      calibration: rec(r.executive_confidence_calibration) ?? {},
      lessons: strs(r.executive_lessons),
      strategies: recs(r.executive_strategy_profile),
      experience: rec(r.executive_experience) ?? {},
    },
  };
}

export type ExecutiveView = ReturnType<typeof parseExecutive>;

/** Convert a JAM proposal schedule (scheduled_hour/scheduled_end_hour) to blocks. */
export function proposalBlocks(schedule: unknown): ScheduleBlock[] {
  return recs(schedule)
    .filter((item) => num(item.scheduled_hour) !== null)
    .map((item, i) => {
      const start = num(item.scheduled_hour) ?? 0;
      const hours = num(item.estimated_duration) ?? 1;
      const end = num(item.scheduled_end_hour) ?? start + hours;
      const deadline = str(item.deadline_expression) || str(item.deadline);
      return {
        key: `${str(item.task_id ?? item.id)}-${i}`,
        title: str(item.title, `Task ${str(item.task_id)}`),
        taskType: str(item.task_type),
        priority: num(item.priority),
        start,
        end,
        rationale: str(item.reason_for_order) || undefined,
        meta: deadline ? `Due ${deadline}` : undefined,
        warning: str(item.deadline_warning) || str(item.capacity_warning) || (item.fits_in_horizon === false ? "Outside the available horizon" : undefined),
        origin: str(item.origin) || undefined,
      };
    });
}
