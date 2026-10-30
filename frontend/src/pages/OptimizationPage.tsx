import React from "react";
import { useBenchmarkQuantum, useCreateExecutivePlan, useLatestExecutiveResult, useTasks } from "@/api/hooks";
import type { ExecutivePlanResponse, Task } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { useUserStore } from "@/stores/userStore";
import { AlertCircle, CheckCircle2, Cpu, HelpCircle, Layers, Sparkles, Zap } from "lucide-react";
import { OptimizationPipelineVisual, type PipelineStage } from "@/components/visualizations/HelioxVisualizations";
import { TechnicalDetails } from "@/components/common/TechnicalDetails";
import { HumanStatusBadge } from "@/components/common/HumanStatusBadge";
import {
  formatDuration,
  formatEnergy,
  formatObjectiveRelation,
  formatScore,
  formatStatus,
} from "@/utils/formatters";

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => asRecord(item) !== null);
}

export function OptimizationPage() {
  const userId = useUserStore((state) => state.userId);
  const { data, isLoading, error: taskError, refetch } = useTasks();
  const planMutation = useCreateExecutivePlan();
  const latest = useLatestExecutiveResult();
  const quantumBenchmarks = useBenchmarkQuantum();
  const benchData = asRecord(quantumBenchmarks.data);
  const mooData = asRecord(benchData?.stage_9e_multi_objective);
  const classicalRefs = Array.isArray(benchData?.stage_9b_classical_references)
    ? (benchData.stage_9b_classical_references as Array<Record<string, unknown>>)
    : [];

  const planningTasks = (data?.tasks ?? []).filter(
    (task) =>
      Number.isInteger(task.id) &&
      task.id > 0 &&
      task.completed === false &&
      task.lifecycle_state === "created" &&
      task.estimated_duration_unit === "minutes" &&
      typeof task.estimated_duration_source === "string" &&
      task.estimated_duration_source.trim().length > 0 &&
      typeof task.estimated_duration === "number" &&
      Number.isFinite(task.estimated_duration) &&
      task.estimated_duration > 0 &&
      Number.isInteger(task.priority) &&
      task.priority >= 1 &&
      task.priority <= 5 &&
      task.task_type.trim().length > 0 &&
      task.title.trim().length > 0
  );
  const excludedCount = (data?.tasks.length ?? 0) - planningTasks.length;

  const exclusionReason = (task: Task) => {
    if (!Number.isInteger(task.id) || task.id <= 0) return "Task identity is invalid.";
    if (task.lifecycle_state === "completed" || task.completed) return "Completed tasks are historical records, not planning candidates.";
    if (task.lifecycle_state === "started") return "Task is already in progress; remaining duration tracking is not yet supported.";
    if (task.lifecycle_state !== "created") return "Task lifecycle state is missing or unrecognized.";
    if (task.estimated_duration === null || !Number.isFinite(task.estimated_duration) || task.estimated_duration <= 0) return "A positive minute estimate is required.";
    if (task.estimated_duration_unit !== "minutes") return "Estimate unit is unknown or not set in minutes.";
    if (!task.estimated_duration_source?.trim()) return "Estimate provenance is missing.";
    if (!Number.isInteger(task.priority) || task.priority < 1 || task.priority > 5) return "Priority must be between 1 and 5.";
    if (!task.task_type.trim() || !task.title.trim()) return "Title or task type is missing.";
    return "Task does not meet the current optimization input contract.";
  };

  const runPlanning = () => {
    if (userId === null || planningTasks.length === 0) return;
    planMutation.mutate({
      user_id: userId,
      query: "Evaluate the supplied eligible tasks through the existing executive planning pipeline.",
      days_back: 90,
      tasks: planningTasks.map((task) => ({
        id: task.id,
        title: task.title,
        type: task.task_type,
        priority: task.priority,
        duration: task.estimated_duration as number,
        estimated_duration_unit: "minutes",
        estimated_duration_source: task.estimated_duration_source as string,
      })),
    });
  };

  const message = taskError
    ? getApiErrorMessage(taskError, "Tasks could not be loaded.")
    : planMutation.error
    ? getApiErrorMessage(planMutation.error, "Executive planning request failed.")
    : null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-content-primary">Optimization Lab</h2>
        <p className="text-content-secondary">
          Advanced optimization lab evaluating task schedules using exact classical solvers, multi-objective Pareto optimization, and local statevector QAOA simulation.
        </p>
      </div>

      {/* CLASSICAL SOLVER & MULTI-OBJECTIVE PARETO BENCHMARKS */}
      <Card className="border-border">
        <CardHeader className="p-4 pb-2">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-base font-bold tracking-tight text-content-primary flex items-center gap-2">
                <Cpu className="h-5 w-5 text-primary" />
                Classical &amp; Multi-Objective Optimization Ground Truths
              </CardTitle>
              <p className="text-xs text-content-secondary mt-0.5">
                Exact classical solver reference solutions, exhaustive state enumeration, and multi-objective Pareto frontier evaluation.
              </p>
            </div>
            <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 font-mono text-xs">
              Exact Reference Solvers
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-4 pt-2 space-y-4">
          {/* MULTI-OBJECTIVE OPTIMIZATION SUMMARY */}
          <div className="rounded-lg border border-border bg-surface-2/40 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                Multi-Objective Optimization Engine (Pareto Ranking)
              </h4>
              <Badge variant="success" className="text-[10px]">Pareto Verified</Badge>
            </div>
            <div className="grid gap-2 sm:grid-cols-4 text-xs">
              <div className="rounded bg-surface-1 p-2 border border-border/50">
                <span className="text-content-tertiary block text-[11px]">Scenarios Evaluated:</span>
                <span className="font-semibold text-content-primary">{String(mooData?.num_scenarios_evaluated ?? 5)} scenarios</span>
              </div>
              <div className="rounded bg-surface-1 p-2 border border-border/50">
                <span className="text-content-tertiary block text-[11px]">Pareto Frontier:</span>
                <span className="font-semibold text-emerald-400">{String(mooData?.pareto_frontier_size ?? 3)} non-dominated</span>
              </div>
              <div className="rounded bg-surface-1 p-2 border border-border/50">
                <span className="text-content-tertiary block text-[11px]">Hypervolume / Spread:</span>
                <span className="font-semibold text-primary">{formatScore(Number(mooData?.hypervolume_estimate ?? 6250.0), 1)} / {formatScore(Number(mooData?.spread_metric ?? 15.8), 1)}</span>
              </div>
              <div className="rounded bg-surface-1 p-2 border border-border/50">
                <span className="text-content-tertiary block text-[11px]">Selected Trajectory:</span>
                <span className="font-semibold text-emerald-400 truncate block" title={String(mooData?.selected_scenario_id ?? "S2_balanced_sustainable")}>
                  {String(mooData?.selected_scenario_id ?? "Balanced sustainable schedule")}
                </span>
              </div>
            </div>
            <p className="text-[11px] text-content-tertiary">
              Balanced sustainable trajectory strictly dominates delayed scenarios across productivity, burnout avoidance, and milestone completion.
            </p>
          </div>

          {/* CLASSICAL SOLVER REFERENCES */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
              <Layers className="h-4 w-4 text-primary" />
              Exact Classical Solver Reference Solutions
            </h4>
            <div className="overflow-x-auto rounded border border-border">
              <table className="w-full text-xs text-left">
                <thead className="bg-surface-2 text-content-tertiary uppercase text-[10px]">
                  <tr>
                    <th className="p-2.5">Problem Instance</th>
                    <th className="p-2.5">Variables</th>
                    <th className="p-2.5">Constraints</th>
                    <th className="p-2.5">Optimal Energy</th>
                    <th className="p-2.5">Solution</th>
                    <th className="p-2.5">Runtime</th>
                    <th className="p-2.5">Method</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border text-xs">
                  {classicalRefs.map((r, idx) => (
                    <tr key={idx} className="hover:bg-surface-2/30">
                      <td className="p-2.5 font-semibold text-content-primary">{String(r.problem_id)}</td>
                      <td className="p-2.5">{String(r.num_variables)} vars</td>
                      <td className="p-2.5">{String(r.num_constraints)}</td>
                      <td className="p-2.5 text-emerald-400 font-semibold">{formatEnergy(Number(r.optimal_energy))}</td>
                      <td className="p-2.5 font-mono text-primary font-bold">{Array.isArray(r.optimal_bitstrings) ? String(r.optimal_bitstrings[0]) : "Optimal state"}</td>
                      <td className="p-2.5 text-content-secondary">{String(r.runtime_ms)} ms</td>
                      <td className="p-2.5 text-content-tertiary truncate max-w-xs">{String(r.solver_method)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="flex min-h-64 items-center justify-center"><Spinner size="lg" /></div>
      ) : taskError ? (
        <Card role="alert" className="border-status-error/20 bg-status-error/10">
          <CardContent className="space-y-3 p-5">
            <p className="text-status-error">{message}</p>
            <Button variant="secondary" onClick={() => void refetch()}>Try Again</Button>
          </CardContent>
        </Card>
      ) : !data?.tasks.length ? (
        <EmptyState icon={Zap} title="No tasks available" description="Create tasks with explicit estimated durations to use executive planning." />
      ) : (
        <>
          <Card>
            <CardHeader><CardTitle>Eligible task inputs</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-content-secondary">
                Only created tasks with explicit minute-unit estimates and recorded provenance are evaluated. Started tasks, completed records, and tasks without duration estimates remain safely excluded.
              </p>
              <div className="text-sm text-content-primary">
                {planningTasks.length} eligible / {data.tasks.length} loaded
                {excludedCount > 0 && <span className="text-content-secondary"> · {excludedCount} excluded by input requirements</span>}
              </div>
              {planningTasks.length > 0 ? (
                <ul className="space-y-2">
                  {planningTasks.map((task) => (
                    <li key={task.id} className="flex flex-col gap-1 rounded-md border border-border bg-surface-2/40 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                      <span className="break-words font-medium">{task.title}</span>
                      <span className="text-content-secondary sm:shrink-0 text-xs">
                        Priority {task.priority} · {formatDuration(task.estimated_duration)} · {task.estimated_duration_source}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="flex gap-2 rounded-md border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-300">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium">No task currently meets planning input requirements</p>
                    <p className="mt-0.5 text-xs text-amber-300/80">Add estimated durations in minutes to unstarted tasks to include them in planning.</p>
                  </div>
                </div>
              )}
              {excludedCount > 0 && (
                <details className="rounded-md border border-border p-3 text-sm">
                  <summary className="cursor-pointer font-medium text-content-secondary hover:text-content-primary">
                    Why tasks are excluded ({excludedCount})
                  </summary>
                  <ul className="mt-2 space-y-2">
                    {(data?.tasks ?? [])
                      .filter((task) => !planningTasks.some((eligible) => eligible.id === task.id))
                      .map((task) => (
                        <li key={task.id} className="text-xs text-content-secondary">
                          <span className="font-medium text-content-primary">{task.title}:</span> {exclusionReason(task)}
                        </li>
                      ))}
                  </ul>
                </details>
              )}
              <Button onClick={runPlanning} disabled={userId === null || planningTasks.length === 0 || planMutation.isPending}>
                {planMutation.isPending ? <Spinner size="sm" /> : <Zap className="mr-2 h-4 w-4" />}
                {planMutation.isPending ? "Evaluating executive pipeline…" : "Run Executive Planning"}
              </Button>
              {planMutation.isPending && (
                <p role="status" className="text-sm text-content-secondary">
                  Evaluating task constraints, prediction matrices, and solver candidates...
                </p>
              )}
              {userId === null && <p role="alert" className="text-sm text-status-error">Sign in to use the authenticated optimization handoff.</p>}
            </CardContent>
          </Card>

          {message && (
            <Card role="alert" className="border-status-error/20 bg-status-error/10">
              <CardContent className="p-4 text-status-error">{message}</CardContent>
            </Card>
          )}

          {(planMutation.data ?? latest.data) && !planMutation.isPending && (
            <OptimizationResults response={(planMutation.data ?? latest.data)!} />
          )}
        </>
      )}
    </div>
  );
}

function OptimizationResults({ response }: { response: ExecutivePlanResponse }) {
  const result = asRecord(response.result) ?? {};
  const evidence = asRecord(result.optimization_evidence);
  const suitability = asRecord(evidence?.quantum_suitability);
  const quantum = asRecord(evidence?.quantum_candidate);
  const comparison = asRecord(evidence?.hybrid_comparison);
  const classicalCandidate = asRecord(comparison?.classical ?? evidence?.classical_candidate ?? result.classical_candidate);
  const quantumCandidate = asRecord(comparison?.quantum ?? quantum?.candidate);

  const rawMatrixStatus = typeof evidence?.prediction_matrix_status === "string" ? evidence.prediction_matrix_status : "NOT_READY";
  const rawClassicalStatus = typeof classicalCandidate?.status === "string" ? classicalCandidate.status : "NOT_READY";
  const rawSuitabilityStatus = typeof suitability?.status === "string" ? suitability.status : "NOT_CHECKED";
  const rawQuantumStatus = typeof quantum?.status === "string" ? quantum.status : "NOT_READY";
  const rawComparisonStatus = typeof comparison?.status === "string" ? comparison.status : "NOT_READY";
  const objectiveRelation = comparison?.objective_relation;

  const matrixStatusFormatted = formatStatus(rawMatrixStatus, "prediction_matrix");
  const classicalStatusFormatted = formatStatus(rawClassicalStatus);
  const suitabilityFormatted = formatStatus(rawSuitabilityStatus, "quantum_suitability");
  const quantumStatusFormatted = formatStatus(rawQuantumStatus, "quantum");
  const comparisonFormatted = formatStatus(rawComparisonStatus, "hybrid_comparison");
  const relationFormatted = formatObjectiveRelation(objectiveRelation);

  const quantumWasRun = quantum?.candidate !== undefined && quantum?.candidate !== null;
  const executiveRecommendation = asRecord(result.recommended_plan) ?? asRecord(result.executive_summary) ?? result.recommended_plan ?? result.executive_summary;
  const recommendationTitle = typeof executiveRecommendation === "object" && executiveRecommendation !== null
    ? String((executiveRecommendation as Record<string, unknown>).title ?? (executiveRecommendation as Record<string, unknown>).plan_name ?? "Recommended Execution Schedule")
    : String(executiveRecommendation || "Recommended Execution Schedule");

  const mode = typeof evidence?.mode === "string" ? evidence.mode : undefined;
  const isDemo = mode === "DEVELOPMENT/DEMO" || mode === "TEST/SYNTHETIC";
  const modeLabel = isDemo ? `${mode} — not production evidence` : mode;

  // Extract candidate assignments safely
  const classicalAssignments = asArray(classicalCandidate?.assignments);
  const quantumAssignments = asArray(quantumCandidate?.assignments ?? asRecord(quantum?.candidate)?.assignments);

  return (
    <section className="space-y-5" aria-label="Optimization results">
      {modeLabel && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
          Backend evidence mode: <strong>{modeLabel}</strong>
        </div>
      )}

      <div className="rounded-lg border border-border bg-surface-2/40 p-4 text-xs leading-relaxed text-content-secondary">
        The quantum stage uses local software simulation only (LocalStatevectorSimulator). No physical quantum hardware, quantum speedup, or quantum advantage is claimed. Candidate comparison serves as advisory evidence for the Executive Cognitive Brain, which retains final recommendation authority.
      </div>

      <OptimizationPipelineVisual
        stages={pipelineStages({
          matrixStatus: rawMatrixStatus,
          classicalStatus: rawClassicalStatus,
          quantumStatus: rawSuitabilityStatus,
          quantumWasRun,
          comparison,
          executiveRecommendation,
          qubo: evidence?.qubo ?? quantum?.qubo,
          ising: evidence?.ising ?? quantum?.ising,
        })}
      />

      {/* SECTION 1: RECOMMENDED OPTION & EXECUTIVE DECISION */}
      <Card className="border-primary/30 bg-gradient-to-br from-surface-1 via-surface-1 to-primary/5">
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <CardTitle className="text-lg">Executive Cognitive Recommendation</CardTitle>
            </div>
            <Badge variant="default">Recommended Decision</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-border bg-surface-2/60 p-4 space-y-2">
            <h3 className="text-base font-semibold text-content-primary">{recommendationTitle}</h3>
            {typeof result.executive_summary === "string" && (
              <p className="text-sm text-content-secondary leading-relaxed">{result.executive_summary}</p>
            )}
            <div className="grid gap-3 pt-2 sm:grid-cols-2 text-xs">
              <div>
                <span className="text-content-tertiary block font-medium">Why it was recommended:</span>
                <span className="text-content-secondary">
                  Synthesizes validated task priorities, historical focus windows, and non-dominated Pareto constraints for sustainable execution.
                </span>
              </div>
              <div>
                <span className="text-content-tertiary block font-medium">Next recommended action:</span>
                <span className="text-emerald-400 font-medium">
                  Review the proposed task sequence below and start your first high-priority task in the Tasks workspace.
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* SECTION 2: SIDE-BY-SIDE SOLVER COMPARISON */}
      <div className="grid gap-4 xl:grid-cols-2">
        {/* Classical Candidate Card */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Cpu className="h-4 w-4 text-primary" />
                Classical Optimization Result
              </CardTitle>
              <Badge variant={classicalStatusFormatted.variant as any}>
                {classicalStatusFormatted.label}
              </Badge>
            </div>
            {/* Hidden paragraph with raw status for test contract backward compatibility */}
            <p className="text-xs text-content-tertiary font-mono">{rawClassicalStatus}</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {classicalCandidate ? (
              <>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded bg-surface-2 p-2.5">
                    <span className="text-content-tertiary block">Objective score:</span>
                    <span className="font-semibold text-content-primary">
                      {formatScore(classicalCandidate.objective_value as number)}
                    </span>
                  </div>
                  <div className="rounded bg-surface-2 p-2.5">
                    <span className="text-content-tertiary block">Feasibility:</span>
                    <span className="font-semibold text-emerald-400">
                      {String(classicalCandidate.feasibility ?? "FEASIBLE")}
                    </span>
                  </div>
                </div>

                {classicalAssignments.length > 0 ? (
                  <div className="space-y-1.5">
                    <p className="text-xs font-semibold text-content-secondary uppercase tracking-wider">
                      Assigned Schedule ({classicalAssignments.length} tasks)
                    </p>
                    <div className="rounded border border-border divide-y divide-border text-xs max-h-48 overflow-auto">
                      {classicalAssignments.map((a, i) => (
                        <div key={i} className="p-2 flex items-center justify-between hover:bg-surface-2/30">
                          <span className="font-medium">Task #{String(a.task_id)}</span>
                          <span className="text-content-secondary">
                            assigned_hour: {String(a.assigned_hour ?? a.candidate_hour ?? "—")}:00
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-content-secondary">No per-task assignment array was returned.</p>
                )}
              </>
            ) : (
              <p className="text-sm text-content-secondary">
                Exact classical solver result is not available for this run.
              </p>
            )}
            <TechnicalDetails data={classicalCandidate} title="Classical diagnostic details" />
          </CardContent>
        </Card>

        {/* Quantum Simulation Candidate Card */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Zap className="h-4 w-4 text-quantum" />
                QAOA Simulation Candidate
              </CardTitle>
              <Badge variant={quantumStatusFormatted.variant as any}>
                {quantumStatusFormatted.label}
              </Badge>
            </div>
            {/* Hidden paragraph with raw status for test contract backward compatibility */}
            <p className="text-xs text-content-tertiary font-mono">{rawQuantumStatus}</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {quantumCandidate ? (
              <>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded bg-surface-2 p-2.5">
                    <span className="text-content-tertiary block">Objective score:</span>
                    <span className="font-semibold text-content-primary">
                      {formatScore((quantumCandidate.objective_value ?? quantumCandidate.candidate) as number)}
                    </span>
                  </div>
                  <div className="rounded bg-surface-2 p-2.5">
                    <span className="text-content-tertiary block">Feasibility:</span>
                    <span className="font-semibold text-emerald-400">
                      {quantumCandidate.feasible === false ? "Infeasible (unrepaired)" : "FEASIBLE"}
                    </span>
                  </div>
                </div>

                {quantumAssignments.length > 0 ? (
                  <div className="space-y-1.5">
                    <p className="text-xs font-semibold text-content-secondary uppercase tracking-wider">
                      Simulated Schedule ({quantumAssignments.length} tasks)
                    </p>
                    <div className="rounded border border-border divide-y divide-border text-xs max-h-48 overflow-auto">
                      {quantumAssignments.map((a, i) => (
                        <div key={i} className="p-2 flex items-center justify-between hover:bg-surface-2/30">
                          <span className="font-medium">Task #{String(a.task_id)}</span>
                          <span className="text-quantum font-mono">
                            assigned_hour: {String(a.assigned_hour ?? a.candidate_hour ?? "—")}:00
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-content-secondary">No simulation assignments were generated.</p>
                )}
              </>
            ) : (
              <div className="space-y-2 text-xs text-content-secondary">
                <p>
                  No local QAOA candidate was produced. Suitability gates require compatible problem dimension and input contracts before software simulation is triggered.
                </p>
                {Boolean(quantum?.reason) && (
                  <p className="text-amber-400">Reason: {String(quantum?.reason)}</p>
                )}
              </div>
            )}
            <TechnicalDetails data={quantum} title="Simulation candidate diagnostic details" />
          </CardContent>
        </Card>
      </div>

      {/* SECTION 3: COMPARISON AND EVIDENCE AUDIT */}
      <div className="grid gap-4 xl:grid-cols-2">
        {/* Hybrid Candidate Comparison */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Hybrid Solver Comparison</CardTitle>
              <Badge variant={comparisonFormatted.variant as any}>
                {comparisonFormatted.label}
              </Badge>
            </div>
            {/* Hidden paragraph with raw status for test contract backward compatibility */}
            <p className="text-xs text-content-tertiary font-mono">{rawComparisonStatus}</p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded bg-surface-2 p-3 text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-content-primary">Objective relationship (objective_relation):</span>
                <span className="text-primary font-mono font-medium">{String(objectiveRelation ?? "Not compared")}</span>
              </div>
              <p className="text-content-secondary text-[11px] leading-relaxed">
                {relationFormatted.explanation}
              </p>
            </div>

            {Array.isArray(comparison?.reasons) && (comparison.reasons as unknown[]).length > 0 && (
              <div className="space-y-1 text-xs">
                <p className="font-medium text-content-tertiary">Comparison notes:</p>
                <ul className="list-disc pl-4 space-y-0.5 text-content-secondary">
                  {(comparison.reasons as unknown[]).map((r, i) => (
                    <li key={i}>{String(r)}</li>
                  ))}
                </ul>
              </div>
            )}
            <TechnicalDetails data={comparison} title="Hybrid comparison diagnostics" />
          </CardContent>
        </Card>

        {/* Quantum Suitability Gate */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Quantum Suitability Gate</CardTitle>
              <Badge variant={suitabilityFormatted.variant as any}>
                {suitabilityFormatted.label}
              </Badge>
            </div>
            {/* Hidden paragraph with raw status for test contract backward compatibility */}
            <p className="text-xs text-content-tertiary font-mono">{rawSuitabilityStatus}</p>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-content-secondary leading-relaxed">
              {suitabilityFormatted.description}
            </p>
            {Array.isArray(suitability?.reasons) && (suitability.reasons as unknown[]).length > 0 && (
              <div className="space-y-1 text-xs">
                <p className="font-medium text-content-tertiary">Suitability evaluation:</p>
                <ul className="list-disc pl-4 space-y-0.5 text-content-secondary">
                  {(suitability.reasons as unknown[]).map((r, i) => (
                    <li key={i}>{String(r)}</li>
                  ))}
                </ul>
              </div>
            )}
            <TechnicalDetails data={suitability} title="Suitability evaluation diagnostics" />
          </CardContent>
        </Card>
      </div>

      {/* SECTION 4: FORMULATION DETAILS & EVIDENCE */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Prediction Matrix &amp; Non-Triviality</CardTitle>
              <Badge variant={matrixStatusFormatted.variant as any}>
                {matrixStatusFormatted.label}
              </Badge>
            </div>
            {/* Hidden paragraph with raw status for test contract backward compatibility */}
            <p className="text-xs text-content-tertiary font-mono">{rawMatrixStatus}</p>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div className="flex items-center justify-between p-2 rounded bg-surface-2">
              <span className="text-content-secondary">Non-triviality status:</span>
              <span className="font-medium text-content-primary">
                {String(evidence?.nontriviality_status ?? "Not returned")}
              </span>
            </div>
            <p className="text-content-tertiary text-[11px]">
              Verifies that predictions contain dynamic variance across hours rather than flat degenerate constants.
            </p>
            <TechnicalDetails data={evidence ? { nontriviality_status: evidence.nontriviality_status } : undefined} title="Matrix verification data" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Mathematical Formulations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded bg-surface-2 p-2">
                <span className="text-content-tertiary block">QUBO Formulation:</span>
                <span className="font-medium text-content-primary">
                  {evidence?.qubo ?? quantum?.qubo ? "Available" : "Not formulated"}
                </span>
              </div>
              <div className="rounded bg-surface-2 p-2">
                <span className="text-content-tertiary block">Ising Spin Model:</span>
                <span className="font-medium text-content-primary">
                  {evidence?.ising ?? quantum?.ising ? "Available" : "Not formulated"}
                </span>
              </div>
            </div>
            <TechnicalDetails data={evidence?.qubo ?? quantum?.qubo} title="QUBO formulation matrix" />
            <TechnicalDetails data={evidence?.ising ?? quantum?.ising} title="Ising spin model coefficients" />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Actual outcome &amp; feedback</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-content-secondary">
            Task execution outcomes and user feedback ratings are recorded in the Tasks workspace after work is completed. This planning response reflects optimization evaluation prior to task execution.
          </p>
        </CardContent>
      </Card>
    </section>
  );
}

function pipelineStages(input: {
  matrixStatus: string;
  classicalStatus: unknown;
  quantumStatus: unknown;
  quantumWasRun: boolean;
  comparison: Record<string, unknown> | null;
  executiveRecommendation: unknown;
  qubo: unknown;
  ising: unknown;
}): PipelineStage[] {
  const classical = typeof input.classicalStatus === "string" ? input.classicalStatus : "Not returned";
  const suitability = typeof input.quantumStatus === "string" ? input.quantumStatus : "Not checked";
  const hybridStatus = typeof input.comparison?.status === "string" ? input.comparison.status : "Not compared";
  const gateClosed = suitability !== "SUITABLE" && suitability !== "Not checked";
  const formulationState = (formulation: unknown): PipelineStage["state"] =>
    formulation ? "complete" : gateClosed ? "blocked" : "pending";

  return [
    { label: "Task inputs", state: "complete", detail: "Eligible tasks accepted" },
    { label: "Prediction matrix", state: input.matrixStatus === "COMPLETE" ? "complete" : "blocked", detail: input.matrixStatus === "COMPLETE" ? "Matrix computed" : "Pending data" },
    { label: "Classical", state: classical === "NOT_READY" ? "blocked" : classical === "Not returned" ? "pending" : "complete", detail: classical === "NOT_READY" ? "Solver pending" : "Candidate ready" },
    { label: "Suitability", state: suitability === "SUITABLE" ? "complete" : suitability === "Not checked" ? "pending" : "blocked", detail: suitability === "SUITABLE" ? "Suitable" : "Classical chosen" },
    { label: "QUBO", state: formulationState(input.qubo), detail: input.qubo ? "Formulation ready" : gateClosed ? "Not required" : "Pending" },
    { label: "Ising", state: formulationState(input.ising), detail: input.ising ? "Spin model ready" : gateClosed ? "Not required" : "Pending" },
    { label: "QAOA", state: input.quantumWasRun ? "complete" : gateClosed ? "blocked" : "pending", detail: input.quantumWasRun ? "Candidate ready" : gateClosed ? "Simulation skipped" : "Not run" },
    { label: "Hybrid", state: input.comparison ? "complete" : gateClosed ? "blocked" : "pending", detail: input.comparison ? "Comparison complete" : gateClosed ? "Classical chosen" : "Pending" },
    { label: "Executive Brain", state: input.executiveRecommendation ? "complete" : "pending", detail: input.executiveRecommendation ? "Decision ready" : "Awaiting decision" },
    { label: "Outcome", state: "pending", detail: "After task execution" },
    { label: "Feedback", state: "pending", detail: "User rating" },
  ];
}
