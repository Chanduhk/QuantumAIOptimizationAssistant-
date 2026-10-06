import { useCreateExecutivePlan, useTasks } from "@/api/hooks";
import type { ExecutivePlanResponse, Task } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { useUserStore } from "@/stores/userStore";
import { AlertCircle, Zap } from "lucide-react";

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function json(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function EvidenceCard({ title, status, evidence }: { title: string; status?: string; evidence: unknown }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {status && <p className="text-sm font-medium text-content-secondary">{status}</p>}
      </CardHeader>
      <CardContent>
        {evidence === undefined || evidence === null ? (
          <p className="text-sm text-content-secondary">The backend did not provide this result.</p>
        ) : (
          <pre className="max-h-72 overflow-auto rounded-md bg-background-tertiary p-4 text-xs text-content-primary">{json(evidence)}</pre>
        )}
      </CardContent>
    </Card>
  );
}

export function OptimizationPage() {
  const userId = useUserStore((state) => state.userId);
  const { data, isLoading, error: taskError, refetch } = useTasks();
  const planMutation = useCreateExecutivePlan();

  const planningTasks = (data?.tasks ?? []).filter((task) =>
    Number.isInteger(task.id) && task.id > 0 &&
    task.completed === false &&
    task.lifecycle_state === "created" &&
    task.estimated_duration_unit === "minutes" &&
    typeof task.estimated_duration_source === "string" && task.estimated_duration_source.trim().length > 0 &&
    typeof task.estimated_duration === "number" &&
    Number.isFinite(task.estimated_duration) &&
    task.estimated_duration > 0 &&
    Number.isInteger(task.priority) && task.priority >= 1 && task.priority <= 5 &&
    task.task_type.trim().length > 0 && task.title.trim().length > 0,
  );
  const excludedCount = (data?.tasks.length ?? 0) - planningTasks.length;
  const exclusionReason = (task: Task) => {
    if (!Number.isInteger(task.id) || task.id <= 0) return "Task identity is invalid.";
    if (task.lifecycle_state === "completed" || task.completed) return "Completed tasks are not planning candidates.";
    if (task.lifecycle_state === "started") return "Remaining-duration semantics are not supported for started tasks.";
    if (task.lifecycle_state !== "created") return "Lifecycle state is missing or unknown.";
    if (task.estimated_duration === null || !Number.isFinite(task.estimated_duration) || task.estimated_duration <= 0) return "A finite positive estimate is required.";
    if (task.estimated_duration_unit !== "minutes") return "Estimate unit is unknown or not accepted by this handoff.";
    if (!task.estimated_duration_source?.trim()) return "Estimate provenance is missing.";
    if (!Number.isInteger(task.priority) || task.priority < 1 || task.priority > 5) return "Priority is invalid.";
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
        <h2 className="text-2xl font-bold tracking-tight text-content-primary">Classical & Hybrid Optimization</h2>
        <p className="text-content-secondary">Uses the existing executive planning API and its production readiness gates.</p>
      </div>

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
                Only created tasks with finite minute-unit estimates and recorded provenance are sent. Unknown legacy units, missing provenance, started tasks, and completed tasks are excluded without changing their data.
              </p>
              <div className="text-sm text-content-primary">
                {planningTasks.length} eligible / {data.tasks.length} loaded
                {excludedCount > 0 && <span className="text-content-secondary"> · {excludedCount} excluded by input contract</span>}
              </div>
              {planningTasks.length > 0 ? (
                <ul className="space-y-2">
                  {planningTasks.map((task) => (
                    <li key={task.id} className="flex flex-col gap-1 rounded-md border border-border-primary bg-background-tertiary/40 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                      <span className="break-words">{task.title}</span>
                      <span className="break-all text-content-secondary sm:shrink-0">P{task.priority} · {task.estimated_duration} min · {task.estimated_duration_source}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="flex gap-2 rounded-md border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-300">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  No task currently meets the planning input contract. No estimates are inferred from actual outcomes.
                </div>
              )}
              {excludedCount > 0 && (
                <details className="rounded-md border border-border-primary p-3 text-sm">
                  <summary className="cursor-pointer text-content-secondary">Why tasks are excluded ({excludedCount})</summary>
                  <ul className="mt-2 space-y-2">
                    {(data?.tasks ?? []).filter((task) => !planningTasks.some((eligible) => eligible.id === task.id)).map((task) => (
                      <li key={task.id} className="text-content-secondary"><span className="text-content-primary">{task.title}:</span> {exclusionReason(task)}</li>
                    ))}
                  </ul>
                </details>
              )}
              <Button onClick={runPlanning} disabled={userId === null || planningTasks.length === 0 || planMutation.isPending}>
                {planMutation.isPending ? <Spinner size="sm" /> : <Zap className="mr-2 h-4 w-4" />}
                {planMutation.isPending ? "Running executive pipeline…" : "Run Executive Planning"}
              </Button>
              {planMutation.isPending && <p role="status" className="text-sm text-content-secondary">Waiting for the backend planning and readiness checks to complete.</p>}
              {userId === null && <p role="alert" className="text-sm text-status-error">Sign in to use the authenticated optimization handoff.</p>}
            </CardContent>
          </Card>

          {message && <Card role="alert" className="border-status-error/20 bg-status-error/10"><CardContent className="p-4 text-status-error">{message}</CardContent></Card>}

          {planMutation.data && !planMutation.isPending && (
            <OptimizationResults response={planMutation.data} />
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
  const mode = typeof evidence?.mode === "string" ? evidence.mode : undefined;
  const modeLabel = mode === "DEVELOPMENT/DEMO"
    ? "DEVELOPMENT/DEMO — not production evidence"
    : mode === "TEST/SYNTHETIC"
      ? "TEST/SYNTHETIC — not production evidence"
      : mode;

  return (
    <section className="space-y-4" aria-label="Optimization results">
      {modeLabel && <p className="rounded-md border border-border-primary p-3 text-sm">Backend evidence mode: <strong>{modeLabel}</strong></p>}
      <p className="text-sm text-content-secondary">
        The quantum stage uses local software simulation only. No physical quantum hardware, quantum advantage, or quantum speedup is claimed. Candidate comparison is evidence for the Executive Cognitive Brain, which retains recommendation authority.
      </p>
      <div className="grid gap-4 xl:grid-cols-2">
        <EvidenceCard title="Prediction matrix" status={typeof evidence?.prediction_matrix_status === "string" ? evidence.prediction_matrix_status : undefined} evidence={evidence ? { nontriviality_status: evidence.nontriviality_status } : undefined} />
        <EvidenceCard title="Classical candidate" evidence={comparison?.classical ?? result.classical_candidate} />
        <EvidenceCard title="Quantum suitability" status={typeof suitability?.status === "string" ? suitability.status : undefined} evidence={suitability} />
        <EvidenceCard title="QAOA local simulation" status={typeof quantum?.status === "string" ? quantum.status : undefined} evidence={quantum} />
        <EvidenceCard title="Hybrid comparison" status={typeof comparison?.status === "string" ? comparison.status : undefined} evidence={comparison} />
        <EvidenceCard title="Executive Cognitive Brain recommendation" evidence={result.recommended_plan} />
      </div>
      {result.executive_summary !== undefined && <EvidenceCard title="Executive summary" evidence={result.executive_summary} />}
      {!evidence && <EvidenceCard title="Optimization evidence" evidence={undefined} />}
    </section>
  );
}
