import React, { useState } from "react";
import { useCreateExecutivePlan, useLatestExecutiveResult, useTasks, useAcceptPlan, useRejectPlan } from "@/api/hooks";
import type { ExecutivePlanResponse, Task } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { OptimizationPipelineVisual, type PipelineStage } from "@/components/visualizations/HelioxVisualizations";
import { useUserStore } from "@/stores/userStore";
import { AlertCircle, Brain, CalendarDays, Clock, ListChecks, Sparkles, Target, Check, CheckCircle2, X, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { TechnicalDetails } from "@/components/common/TechnicalDetails";
import { formatDuration, formatScore, formatStatus, formatHourSlot } from "@/utils/formatters";

function getPriorityColor(priority: number) {
  switch (priority) {
    case 5: return "bg-status-error/15 text-status-error border-status-error/30";
    case 4: return "bg-status-warning/15 text-status-warning border-status-warning/30";
    case 3: return "bg-primary/15 text-primary border-primary/30";
    case 2: return "bg-surface-3 text-content-secondary border-border/70";
    case 1:
    default:
      return "bg-surface-2 text-content-tertiary border-border/50";
  }
}

function getPriorityLabel(priority: number) {
  switch (priority) {
    case 5: return "Critical";
    case 4: return "High";
    case 3: return "Medium";
    case 2: return "Normal";
    case 1:
    default:
      return "Low";
  }
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function records(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => item !== null && typeof item === "object" && !Array.isArray(item))
    : [];
}

function text(value: unknown, fallback = "—"): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function isEligible(task: Task) {
  return (
    Number.isInteger(task.id) &&
    task.id > 0 &&
    task.lifecycle_state === "created" &&
    task.completed === false &&
    task.estimated_duration_unit === "minutes" &&
    typeof task.estimated_duration_source === "string" &&
    task.estimated_duration_source.trim().length > 0 &&
    typeof task.estimated_duration === "number" &&
    Number.isFinite(task.estimated_duration) &&
    task.estimated_duration > 0 &&
    Number.isInteger(task.priority) &&
    task.priority >= 1 &&
    task.priority <= 5 &&
    Boolean(task.title.trim()) &&
    Boolean(task.task_type.trim())
  );
}

function reason(task: Task): string {
  if (task.completed || task.lifecycle_state === "completed") {
    return "Completed tasks are historical records, not open planning candidates.";
  }
  if (task.lifecycle_state === "started") {
    return "Task is already in progress; remaining duration tracking is not yet supported.";
  }
  if (task.lifecycle_state !== "created") {
    return "Task lifecycle state is missing or unrecognized.";
  }
  if (task.estimated_duration === null || !Number.isFinite(task.estimated_duration) || task.estimated_duration <= 0) {
    return "A positive minute estimate is required.";
  }
  if (task.estimated_duration_unit !== "minutes") {
    return "Estimate unit is unknown; it was not set in minutes.";
  }
  if (!task.estimated_duration_source?.trim()) {
    return "Estimate provenance is missing.";
  }
  if (!Number.isInteger(task.priority) || task.priority < 1 || task.priority > 5) {
    return "Priority must be between 1 and 5.";
  }
  return "Task identity or required task fields are incomplete.";
}

function scheduleEntries(result: Record<string, unknown> | null): Record<string, unknown>[] {
  if (!result) return [];
  // 1. Direct or nested standard schedule keys
  for (const key of ["recommended_plan", "daily_plan", "optimized_schedule", "rl_schedule", "schedule"]) {
    const value = result[key];
    const direct = records(value);
    if (direct.length) return direct;
    const nested = record(value);
    if (nested) {
      for (const nestedKey of ["assignments", "schedule", "tasks", "optimized_schedule"]) {
        const list = records(nested[nestedKey]);
        if (list.length) return list;
      }
    }
  }

  // 2. Candidate plans
  const candidatePlans = record(result.candidate_plans);
  if (candidatePlans) {
    const plans = records(candidatePlans.plans);
    for (const p of plans) {
      const planInner = record(p.plan);
      if (planInner) {
        for (const nestedKey of ["assignments", "schedule", "tasks", "optimized_schedule"]) {
          const list = records(planInner[nestedKey]);
          if (list.length) return list;
        }
      }
    }
  }

  // 3. Optimization evidence: classical assignments or hybrid comparison
  const evidence = record(result.optimization_evidence);
  if (evidence) {
    const hybrid = record(evidence.hybrid_comparison);
    const classical = record(hybrid?.classical) ?? record(evidence.classical);
    if (classical) {
      const assignments = records(classical.assignments);
      if (assignments.length) return assignments;
    }
  }

  // 4. Classical candidate directly
  const classicalCandidate = record(result.classical_candidate);
  if (classicalCandidate) {
    const assignments = records(classicalCandidate.assignments);
    if (assignments.length) return assignments;
  }

  return [];
}

function PlanningEvidence({ response, tasks }: { response: ExecutivePlanResponse; tasks: Task[] }) {
  const [accepted, setAccepted] = useState(false);
  const [rejected, setRejected] = useState(false);
  const acceptMutation = useAcceptPlan();
  const rejectMutation = useRejectPlan();

  const result = record(response.result) ?? {};
  const evidence = record(result.optimization_evidence);
  const predictions = records(result.predicted_tasks ?? result.predictions);
  const schedule = scheduleEntries(result);
  const rawRecommendation = result.recommended_plan ?? result.executive_summary;
  const recommendationRecord = record(rawRecommendation);

  const proposalId = typeof result.proposal_id === "string"
    ? result.proposal_id
    : typeof rawRecommendation === "object" && rawRecommendation !== null && "proposal_id" in rawRecommendation
      ? String((rawRecommendation as Record<string, unknown>).proposal_id)
      : undefined;

  const handleAccept = async () => {
    try {
      await acceptMutation.mutateAsync({
        schedule,
        proposal_id: proposalId,
      });
      setAccepted(true);
      setRejected(false);
    } catch {
      // Handled by acceptMutation.error
    }
  };

  const handleReject = async () => {
    try {
      await rejectMutation.mutateAsync({
        proposal_id: proposalId,
      });
      setRejected(true);
      setAccepted(false);
    } catch {
      // Handled by rejectMutation.error
    }
  };

  const rawMatrixStatus = text(evidence?.prediction_matrix_status, "NOT_READY");
  const rawClassicalStatus = text(
    record(evidence?.hybrid_comparison)?.classical &&
      record(record(evidence?.hybrid_comparison)?.classical)?.status,
    text(record(result.classical_candidate)?.status, "NOT_READY")
  );
  const rawQuantumStatus = text(record(evidence?.quantum_suitability)?.status, "NOT_CHECKED");

  const matrixStatusFormatted = formatStatus(rawMatrixStatus, "prediction_matrix");
  const classicalStatusFormatted = formatStatus(rawClassicalStatus);
  const quantumStatusFormatted = formatStatus(rawQuantumStatus, "quantum_suitability");

  const pipeline: PipelineStage[] = [
    { label: "Task inputs", state: "complete", detail: "Eligible task inputs" },
    { label: "Prediction", state: rawMatrixStatus === "COMPLETE" ? "complete" : "blocked", detail: matrixStatusFormatted.label },
    { label: "Classical", state: rawClassicalStatus === "NOT_READY" ? "blocked" : "complete", detail: classicalStatusFormatted.label },
    { label: "Suitability", state: rawQuantumStatus === "SUITABLE" ? "complete" : "blocked", detail: quantumStatusFormatted.label },
    { label: "QAOA", state: record(evidence?.quantum_candidate)?.candidate ? "complete" : "pending", detail: text(record(evidence?.quantum_candidate)?.status, "Not run") },
    { label: "Hybrid", state: record(evidence?.hybrid_comparison) ? "complete" : "pending", detail: text(record(evidence?.hybrid_comparison)?.status, "Not compared") },
    { label: "Executive Brain", state: rawRecommendation ? "complete" : "pending", detail: rawRecommendation ? "Decision ready" : "Awaiting decision" },
  ];

  return (
    <div className="space-y-5">
      <OptimizationPipelineVisual stages={pipeline} />

      <div className="grid gap-4 xl:grid-cols-3">
        {/* Timeline Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-primary" />
                Generated timeline
              </CardTitle>
              <Badge variant={schedule.length > 0 ? "success" : "secondary"}>
                {schedule.length > 0 ? `${schedule.length} scheduled` : "No schedule entries"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {schedule.length > 0 ? (
              <ol className="space-y-3">
                {schedule.map((item, index) => {
                  const taskId = item.task_id ?? item.id;
                  const matchingTask = tasks.find((t) => String(t.id) === String(taskId));
                  const hour = item.scheduled_hour ?? item.optimized_hour ?? item.assigned_hour ?? item.hour;
                  const durationMin = typeof item.duration === "number"
                    ? (item.duration > 12 ? item.duration : item.duration * 60)
                    : (matchingTask?.estimated_duration ?? 60);
                  const durationHours = durationMin / 60;
                  const timeLabel = typeof hour === "number"
                    ? formatHourSlot(hour, durationHours)
                    : (typeof hour === "string" ? `${hour}:00` : "Slot pending");
                  const priority = Number(item.priority ?? matchingTask?.priority ?? 1);
                  const title = text(item.title ?? item.task_title ?? matchingTask?.title, `Task Assignment ${index + 1}`);
                  const score = item.prediction_score ?? item.score ?? item.expected_productivity;
                  const dependencies = Array.isArray(item.depends_on_task_ids)
                    ? (item.depends_on_task_ids as (string | number)[]).filter(Boolean)
                    : [];
                  const taskType = text(item.task_type ?? item.type ?? matchingTask?.task_type, "General");

                  return (
                    <li
                      key={text(item.task_id ?? item.id, String(index))}
                      className="rounded-lg border border-border bg-surface-2/50 p-3 space-y-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/20 text-[10px] font-bold text-primary">
                            {index + 1}
                          </span>
                          <p className="font-semibold text-content-primary text-sm truncate">
                            {title}
                          </p>
                        </div>
                        <span className="text-xs font-mono text-primary flex items-center gap-1 shrink-0 bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                          <Clock className="h-3 w-3" /> {timeLabel}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5 text-xs">
                        <Badge variant="outline" className={getPriorityColor(priority)}>
                          P{priority}: {getPriorityLabel(priority)}
                        </Badge>
                        <Badge variant="secondary">
                          {taskType}
                        </Badge>
                        <span className="text-content-secondary">
                          {formatDuration(durationMin)}
                        </span>
                        {score !== undefined && (
                          <span className="text-emerald-400 font-mono text-[11px] ml-auto">
                            Score: {formatScore(score as number)}
                          </span>
                        )}
                      </div>

                      {dependencies.length > 0 && (
                        <p className="text-[11px] text-content-tertiary">
                          Dependencies: {dependencies.map((d) => `#${d}`).join(", ")}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ol>
            ) : (
              <div className="rounded-lg border border-dashed border-border p-5 text-center text-xs text-content-secondary space-y-1">
                <p className="font-medium text-content-primary">No timeline schedule returned</p>
                <p>The backend evaluation completed without returning explicit hour-by-hour task allocations.</p>
              </div>
            )}
            <TechnicalDetails data={schedule.length ? schedule : undefined} title="Technical details (Schedule payload)" />
          </CardContent>
        </Card>

        {/* Prediction Evidence Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-4 w-4 text-primary" />
                Prediction evidence
              </CardTitle>
              <Badge variant={matrixStatusFormatted.variant as any}>
                {matrixStatusFormatted.label}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded bg-surface-2/50 p-2.5 text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-content-secondary">Non-triviality status:</span>
                <span className="font-semibold text-content-primary">
                  {text(evidence?.nontriviality_status, "Not returned")}
                </span>
              </div>
              <p className="text-[11px] text-content-tertiary">
                Confirms that predicted task-hour productivity values contain genuine variance.
              </p>
            </div>

            {predictions.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-content-tertiary">
                  Task Matrix Estimates ({predictions.length})
                </p>
                <ul className="space-y-2 max-h-48 overflow-auto">
                  {predictions.map((p, index) => (
                    <li
                      key={text(p.task_id, String(index))}
                      className="rounded border border-border bg-surface-2/30 p-2 text-xs space-y-1"
                    >
                      <p className="font-medium text-content-primary">
                        {text(p.title, `Task #${text(p.task_id, String(index + 1))}`)}
                      </p>
                      <div className="flex flex-wrap gap-2 text-[11px] text-content-secondary">
                        {p.predicted_duration !== undefined && (
                          <span>Duration: {formatDuration(p.predicted_duration as number)}</span>
                        )}
                        {p.expected_productivity !== undefined && (
                          <span>Productivity: {formatScore(p.expected_productivity as number)}</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-content-secondary">
                Per-task matrix cells were not included in this response. Predictions remain in heuristic baseline mode.
              </p>
            )}

            <TechnicalDetails data={predictions.length ? predictions : evidence} title="Technical details (Prediction evidence)" />
          </CardContent>
        </Card>

        {/* Executive Recommendation Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                Executive recommendation
              </CardTitle>
              <Badge variant="default">Advisory Brain</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {rawRecommendation !== undefined ? (
              <div className="rounded-lg border border-border bg-surface-2/40 p-3.5 space-y-2 text-xs">
                <h4 className="font-semibold text-content-primary text-sm">
                  {recommendationRecord?.title ? String(recommendationRecord.title) : "Executive Plan Proposal"}
                </h4>
                {typeof result.executive_summary === "string" && (
                  <p className="text-content-secondary leading-relaxed">
                    {result.executive_summary}
                  </p>
                )}
                {Boolean(recommendationRecord?.description) && (
                  <p className="text-content-secondary leading-relaxed">
                    {String(recommendationRecord?.description)}
                  </p>
                )}
                <div className="pt-2 text-[11px] text-content-tertiary">
                  Recommendation authority remains with the Executive Cognitive Brain.
                </div>
              </div>
            ) : (
              <p className="text-sm text-content-secondary">
                No recommendation field was returned by the backend.
              </p>
            )}

            {/* Action Buttons: Accept / Reject Plan */}
            <div className="space-y-2 pt-1 border-t border-border">
              {accepted ? (
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-emerald-400 space-y-2">
                  <div className="flex items-center gap-2 font-semibold text-sm">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    Plan accepted and scheduled
                  </div>
                  <p className="text-xs text-content-secondary">
                    Tasks have been updated with scheduled start times in your calendar. Proceed to the Tasks workspace to execute.
                  </p>
                  <Link
                    to="/tasks"
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline pt-1"
                  >
                    Open Tasks Workspace <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              ) : rejected ? (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-amber-400 text-xs">
                  Plan proposal rejected. You can generate a fresh plan from your backlog whenever ready.
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2 pt-2">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={handleAccept}
                    disabled={schedule.length === 0 || acceptMutation.isPending || rejectMutation.isPending}
                    isLoading={acceptMutation.isPending}
                    className="gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white"
                  >
                    <Check className="h-3.5 w-3.5" />
                    Accept plan
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={handleReject}
                    disabled={acceptMutation.isPending || rejectMutation.isPending}
                    isLoading={rejectMutation.isPending}
                    className="gap-1.5"
                  >
                    <X className="h-3.5 w-3.5" />
                    Reject
                  </Button>
                </div>
              )}

              {acceptMutation.error && (
                <p role="alert" className="text-xs text-status-error">
                  {getApiErrorMessage(acceptMutation.error, "Failed to accept plan.")}
                </p>
              )}
              {rejectMutation.error && (
                <p role="alert" className="text-xs text-status-error">
                  {getApiErrorMessage(rejectMutation.error, "Failed to reject plan.")}
                </p>
              )}
            </div>

            <TechnicalDetails data={rawRecommendation} title="Technical details (Executive payload)" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function PlanningPage() {
  const userId = useUserStore((state) => state.userId);
  const tasksQuery = useTasks();
  const mutation = useCreateExecutivePlan();
  const latest = useLatestExecutiveResult();
  const tasks = tasksQuery.data?.tasks ?? [];
  const eligible = tasks.filter(isEligible);
  const excluded = tasks.filter((task) => !isEligible(task));
  const response = mutation.data ?? latest.data;
  const result = record(response?.result);

  const generate = () => {
    if (userId === null || !eligible.length) return;
    mutation.mutate({
      user_id: userId,
      query: "Create a plan from eligible user tasks; preserve their recorded estimate provenance.",
      days_back: 90,
      tasks: eligible.map((task) => ({
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

  return (
    <div className="space-y-6 pb-8 sm:space-y-8">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Intelligent Scheduling · Daily Planning
          </p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-content-primary sm:text-3xl">
            My Schedule
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-content-secondary">
            Synthesizes unstarted backlog tasks with explicit minute estimates into an executable daily schedule proposal.
          </p>
        </div>
        <Button
          onClick={generate}
          disabled={userId === null || eligible.length === 0 || mutation.isPending}
          isLoading={mutation.isPending}
          className="gap-2"
        >
          <Sparkles className="h-4 w-4" />
          {mutation.isPending ? "Planning…" : response ? "Generate fresh plan" : "Generate plan"}
        </Button>
      </header>

      {tasksQuery.error && (
        <Card role="alert" className="border-status-error/20 bg-status-error/5">
          <CardContent className="p-4 text-sm text-status-error">
            {getApiErrorMessage(tasksQuery.error, "Tasks could not be loaded.")}
          </CardContent>
        </Card>
      )}

      {mutation.error && (
        <Card role="alert" className="border-status-error/20 bg-status-error/5">
          <CardContent className="p-4 text-sm text-status-error">
            Planning request failed: {getApiErrorMessage(mutation.error, "The backend could not generate a plan.")}
          </CardContent>
        </Card>
      )}

      {mutation.isPending && (
        <p role="status" className="text-sm text-content-secondary">
          Waiting for backend planning, prediction, and readiness checks...
        </p>
      )}

      {tasksQuery.isLoading ? (
        <div className="flex min-h-64 justify-center pt-20">
          <Spinner size="lg" />
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,.85fr)_minmax(0,1.15fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" />
                Task backlog
              </CardTitle>
              <p className="text-sm text-content-secondary">
                {eligible.length} eligible · {excluded.length} excluded from planning handoff
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {eligible.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-5 text-center">
                  <ListChecks className="mx-auto h-7 w-7 text-content-tertiary" />
                  <p className="mt-2 font-medium">No eligible planning tasks</p>
                  <p className="mt-1 text-sm text-content-secondary">
                    Create a task with an explicit minute estimate; completed, started, or legacy-unknown estimates stay excluded.
                  </p>
                  <Link className="mt-3 inline-flex text-sm font-medium text-primary hover:underline" to="/tasks">
                    Open Tasks
                  </Link>
                </div>
              ) : (
                <ul className="space-y-2">
                  {eligible.map((task) => (
                    <li key={task.id} className="rounded-lg border border-border bg-surface-2/40 p-3">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <p className="break-words text-sm font-medium">{task.title}</p>
                        <Badge variant="success">Eligible</Badge>
                      </div>
                      <p className="mt-1 text-xs text-content-secondary">
                        {task.task_type} · Priority {task.priority} · {formatDuration(task.estimated_duration)}
                      </p>
                      <p className="mt-1 break-all text-[11px] text-content-tertiary">
                        Estimate source: {task.estimated_duration_source}
                      </p>
                    </li>
                  ))}
                </ul>
              )}

              {excluded.length > 0 && (
                <details className="rounded-lg border border-border p-3">
                  <summary className="cursor-pointer text-sm font-medium text-content-secondary hover:text-content-primary">
                    Excluded tasks ({excluded.length})
                  </summary>
                  <ul className="mt-3 space-y-2">
                    {excluded.map((task) => (
                      <li key={task.id} className="text-xs text-content-secondary">
                        <span className="font-medium text-content-primary">{task.title}</span> — {reason(task)}
                      </li>
                    ))}
                  </ul>
                </details>
              )}

              {tasks.length === 0 && !tasksQuery.isLoading && (
                <p className="text-sm text-content-secondary">No tasks in this account yet.</p>
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
            {response ? (
              <PlanningEvidence response={response} tasks={tasks} />
            ) : (
              <Card className="flex min-h-80 items-center justify-center border-dashed">
                <CardContent className="max-w-md p-8 text-center">
                  <CalendarDays className="mx-auto h-9 w-9 text-content-tertiary" />
                  <p className="mt-3 font-semibold">No generated plan in this session</p>
                  <p className="mt-2 text-sm text-content-secondary">
                    When you run a plan, returned timeline, prediction evidence, and executive recommendation will appear here.
                  </p>
                </CardContent>
              </Card>
            )}

            {result && !record(result.optimization_evidence) && (
              <p className="flex items-center gap-2 text-xs text-content-tertiary">
                <AlertCircle className="h-4 w-4" />
                The backend returned a plan response without structured optimization evidence.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
