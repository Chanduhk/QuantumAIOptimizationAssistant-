import { Link } from "react-router-dom";
import { Activity, ArrowRight, Atom, BrainCircuit, CalendarDays, CheckCircle2, Clock3, Database, ListChecks, Server, Sparkles } from "lucide-react";
import { useComponentInventory, useDataCollectionStatus, useLatestExecutiveResult, useMLModelStatus, useMLReadiness, useQuantumStatus, useSystemHealth, useSystemStatus, useTasks } from "@/api/hooks";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { NeuralCore, type CoreActivityStatus } from "@/components/neural-core/NeuralCore";
import { mapBackendState, type NeuralCoreNode } from "@/components/neural-core/coreState";
import type { Task, ComponentInventoryItem } from "@/api/endpoints";
import { TechnicalDetails } from "@/components/common/TechnicalDetails";
import { formatDuration, formatLocalDateTime, formatStatus } from "@/utils/formatters";

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function valueText(value: unknown, fallback = "Not available") {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function MetricCard({ title, value, detail, icon: Icon, tone = "primary" }: { title: string; value: string; detail: string; icon: typeof Activity; tone?: "primary" | "warning" | "success" | "quantum" }) {
  const toneClass = { primary: "text-primary", warning: "text-status-warning", success: "text-status-success", quantum: "text-quantum" }[tone];
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3 p-4 sm:p-5">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-content-tertiary">{title}</p>
          <p className="mt-2 truncate text-xl font-semibold text-content-primary">{value}</p>
          <p className="mt-1 text-xs text-content-secondary">{detail}</p>
        </div>
        <span className={`rounded-lg bg-surface-2 p-2 ${toneClass}`}><Icon className="h-5 w-5" /></span>
      </CardContent>
    </Card>
  );
}

function activityTime(task: Task): string | null {
  const timestamp = task.end_time ?? task.start_time ?? task.created_at;
  if (!timestamp) return null;
  return formatLocalDateTime(timestamp);
}

export function DashboardPage() {
  const health = useSystemHealth();
  const system = useSystemStatus();
  const quantum = useQuantumStatus();
  const model = useMLModelStatus();
  const tasksQuery = useTasks();
  const dataQuery = useDataCollectionStatus();
  const mlReadiness = useMLReadiness();
  const latest = useLatestExecutiveResult();
  const inventory = useComponentInventory();
  const tasks = tasksQuery.data?.tasks ?? [];
  const taskDataAvailable = !tasksQuery.isLoading && !tasksQuery.isError && tasksQuery.data !== undefined;
  const active = tasks.filter((task) => task.lifecycle_state === "created" || task.lifecycle_state === "started");
  const completed = tasks.filter((task) => task.lifecycle_state === "completed" || task.completed);
  const report = record(dataQuery.data?.result.collection_report);
  const quality = record(dataQuery.data?.result.quality_audit);
  const optimizationEvidence = record(latest.data?.result.optimization_evidence);
  const suitability = record(optimizationEvidence?.quantum_suitability);
  const latestRecommendation = latest.data?.result.recommended_plan;
  const recentTasks = [...tasks].sort((a, b) => (Date.parse(b.end_time ?? b.start_time ?? b.created_at ?? "") || 0) - (Date.parse(a.end_time ?? a.start_time ?? a.created_at ?? "") || 0)).slice(0, 5);
  const apiHealthy = health.data?.status === "operational" && health.data.database_connected;
  const rawReadiness = valueText(quality?.readiness_status, "Not available");
  const predictionState = model.isError ? "ERROR" : model.isLoading ? "UNKNOWN" : mapBackendState("NOT_PROVEN");
  const planningState = latest.isError
    ? "ERROR"
    : !latest.data
      ? "UNKNOWN"
      : mapBackendState(optimizationEvidence?.prediction_matrix_status, false);

  const durationComp = mlReadiness.data?.components.DurationRatioModel;
  const prodComp = mlReadiness.data?.components.ProductivityModel;
  const rlComp = mlReadiness.data?.components.RLScheduler;

  const rawComponents = inventory.data?.components;
  const componentsList: ComponentInventoryItem[] = Array.isArray(rawComponents)
    ? rawComponents
    : rawComponents && typeof rawComponents === "object"
      ? Object.values(rawComponents as Record<string, ComponentInventoryItem>)
      : [];

  const vectorMem = componentsList.find((c) => (c.canonical_id ?? c.component_id) === "vector_memory_embedding");
  const classicalOpt = componentsList.find((c) => (c.canonical_id ?? c.component_id) === "classical_optimizer");
  const durationModel = componentsList.find((c) => (c.canonical_id ?? c.component_id) === "duration_ratio_model");

  const coreNodes: NeuralCoreNode[] = [
    {
      id: "memory",
      label: "Memory",
      state: vectorMem?.can_execute_now ? "READY" : "UNKNOWN",
      detail: vectorMem
        ? `${vectorMem.display_name ?? vectorMem.name ?? "Vector Memory"}: ${vectorMem.operational_state} (Local hash projection fallback)`
        : "Live memory readiness loading...",
      route: "/intelligence",
    },
    {
      id: "behavior",
      label: "Behavior",
      state: dataQuery.isError ? "ERROR" : dataQuery.isLoading ? "UNKNOWN" : mapBackendState(quality?.readiness_status),
      detail: quality ? valueText(quality.readiness_status, "Audit status not returned") : "User-scoped behavior audit status not available.",
      route: "/intelligence",
    },
    {
      id: "prediction",
      label: "Prediction",
      state: durationModel?.can_execute_now ? "READY" : predictionState,
      detail: durationModel?.can_execute_now
        ? "Duration baseline heuristic active; personalized ML training awaits data minimums."
        : "Model readiness is not available.",
      route: "/intelligence",
    },
    {
      id: "planning",
      label: "Planning",
      state: planningState,
      detail: latest.data ? `Latest matrix: ${valueText(optimizationEvidence?.prediction_matrix_status, "status not returned")}` : "No planning result is cached for this session.",
      route: "/planning",
    },
    {
      id: "optimization",
      label: "Optimization",
      state: classicalOpt?.can_execute_now ? "READY" : "NOT_READY",
      detail: classicalOpt?.can_execute_now
        ? "Classical & multi-objective optimizers operational (independent of ML models)."
        : "Optimization engines unavailable.",
      route: "/optimization",
    },
    {
      id: "quantum",
      label: "Quantum suitability",
      state: latest.isError ? "ERROR" : mapBackendState(suitability?.status),
      detail: typeof suitability?.status === "string" ? suitability.status : quantum.data?.available ? "Software simulator ready; problem suitability evaluated per run." : "Problem-specific suitability is not available.",
      route: "/quantum",
    },
    {
      id: "executive",
      label: "Executive Brain",
      state: latest.isError ? "ERROR" : latest.data?.result.executive_summary ? "READY" : "UNKNOWN",
      detail: latest.data?.result.executive_summary ? "Executive response is available in this session." : "No executive decision is cached for this session.",
      route: "/planning",
    },
  ];

  const inProgressTask = tasks.find((t) => t.lifecycle_state === "started");
  const isPlanningGenerating = latest.isLoading;

  const coreActivity: CoreActivityStatus = isPlanningGenerating
    ? {
        state: "processing",
        label: "Synthesizing Schedule",
        detail: "Evaluating multi-objective scheduling constraints",
      }
    : inProgressTask
    ? {
        state: "active_task",
        label: `Active: ${inProgressTask.title}`,
        detail: `${inProgressTask.task_type} · Priority ${inProgressTask.priority} · In progress`,
      }
    : tasks.length > 0 && active.length === 0 && completed.length > 0
    ? {
        state: "completed",
        label: "Workspace Idle · Completed",
        detail: "All active tasks finished for today",
      }
    : {
        state: "idle",
        label: "Workspace Idle · Ready",
        detail: "Awaiting task execution or assistant prompts",
      };

  return (
    <div className="space-y-6 pb-8 sm:space-y-8">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Personal Intelligence · Workspace</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-content-primary sm:text-3xl">Home</h2>
          <p className="mt-2 max-w-2xl text-sm text-content-secondary">
            A live overview from your authenticated task data and active HELIOX intelligence capabilities.
          </p>
        </div>
        <Link to="/tasks">
          <Button className="gap-2">Open My Tasks <ArrowRight className="h-4 w-4" /></Button>
        </Link>
      </header>

      <NeuralCore nodes={coreNodes} activity={coreActivity} />

      <section aria-label="Project status" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Active tasks"
          value={tasksQuery.isLoading ? "Loading" : tasksQuery.isError ? "Unavailable" : String(active.length)}
          detail={taskDataAvailable ? `${tasks.filter((task) => task.lifecycle_state === "started").length} in progress · ${tasks.filter((task) => task.lifecycle_state === "created").length} in backlog` : tasksQuery.isLoading ? "Loading task breakdown" : "Task breakdown unavailable"}
          icon={ListChecks}
          tone={tasksQuery.isError ? "warning" : "primary"}
        />
        <MetricCard
          title="Completed outcomes"
          value={tasksQuery.isLoading ? "Loading" : tasksQuery.isError ? "Unavailable" : String(completed.length)}
          detail={`${valueText(report?.valid_actual_duration_records, "No verified outcome count")} lifecycle-verified durations`}
          icon={CheckCircle2}
          tone="success"
        />
        <MetricCard
          title="Learning data"
          value={dataQuery.isLoading ? "Loading" : dataQuery.isError ? "Unavailable" : rawReadiness}
          detail={`${valueText(report?.f3_dataset_rows, "—")} eligible dataset rows reported`}
          icon={Database}
          tone={rawReadiness === "READY" ? "success" : "warning"}
        />
        <MetricCard
          title="API & database"
          value={health.isLoading ? "Checking" : health.isError ? "Unavailable" : apiHealthy ? "Operational" : health.data?.database_connected === false ? "Database unavailable" : "Status incomplete"}
          detail={health.data?.database_connected === true ? "Database reachable through FastAPI" : health.data?.database_connected === false ? "FastAPI reports the database is disconnected" : "Database state not returned"}
          icon={Server}
          tone={apiHealthy ? "success" : "warning"}
        />
      </section>

      {/* HELIOX Learning Section */}
      <Card className="border-border bg-gradient-to-r from-surface-1 via-surface-1 to-primary/5">
        <CardContent className="p-5 sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-md">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                  HELIOX Learning
                </span>
                <Badge variant="outline" className="text-[10px] border-border text-content-secondary">
                  Real data only
                </Badge>
              </div>
              <h3 className="mt-1 text-base font-semibold text-content-primary">
                Your data is helping HELIOX learn your working patterns
              </h3>
              <p className="mt-1 text-xs text-content-secondary leading-relaxed">
                Models stay in guarded baseline mode until sufficient genuine completed tasks and user ratings exist.
              </p>
            </div>

            <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-3 max-w-xl">
              <div className="rounded-lg border border-border/80 bg-surface-2/60 p-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-content-secondary">Duration model</span>
                  <span className="font-mono font-semibold text-primary">
                    {durationComp ? `${durationComp.eligible_samples} / ${durationComp.required_samples}` : "—"}
                  </span>
                </div>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                  <div
                    className="h-full bg-primary transition-all duration-500"
                    style={{
                      width: `${Math.min(100, ((durationComp?.eligible_samples ?? 0) / (durationComp?.required_samples ?? 10)) * 100)}%`,
                    }}
                  />
                </div>
              </div>

              <div className="rounded-lg border border-border/80 bg-surface-2/60 p-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-content-secondary">Productivity feedback</span>
                  <span className="font-mono font-semibold text-primary">
                    {prodComp ? `${prodComp.eligible_samples} / ${prodComp.required_samples}` : "—"}
                  </span>
                </div>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                  <div
                    className="h-full bg-primary transition-all duration-500"
                    style={{
                      width: `${Math.min(100, ((prodComp?.eligible_samples ?? 0) / (prodComp?.required_samples ?? 10)) * 100)}%`,
                    }}
                  />
                </div>
              </div>

              <div className="rounded-lg border border-border/80 bg-surface-2/60 p-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-content-secondary">Scheduling experience</span>
                  <span className="font-mono font-semibold text-primary">
                    {rlComp ? `${rlComp.eligible_samples} / ${rlComp.required_samples}` : "—"}
                  </span>
                </div>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                  <div
                    className="h-full bg-primary transition-all duration-500"
                    style={{
                      width: `${Math.min(100, ((rlComp?.eligible_samples ?? 0) / (rlComp?.required_samples ?? 25)) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            <Link to="/data-learning" className="shrink-0">
              <Button variant="secondary" size="sm" className="gap-1.5">
                Learning center
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-4 xl:grid-cols-[1.15fr_.85fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Recent task activity</CardTitle>
              <p className="mt-1 text-sm text-content-secondary">Created, started, and completed records from this account.</p>
            </div>
            <Link to="/tasks" className="text-xs font-medium text-primary hover:underline">All tasks</Link>
          </CardHeader>
          <CardContent>
            {tasksQuery.isLoading ? (
              <div className="flex justify-center py-8"><Spinner /></div>
            ) : tasksQuery.isError ? (
              <p role="alert" className="py-5 text-sm text-status-error">Task activity is unavailable.</p>
            ) : recentTasks.length === 0 ? (
              <p className="py-8 text-center text-sm text-content-secondary">No task activity yet. Create a task to begin.</p>
            ) : (
              <ul className="divide-y divide-border">
                {recentTasks.map((task) => (
                  <li key={task.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-content-primary">{task.title}</p>
                      <p className="mt-1 text-xs text-content-secondary">
                        {task.task_type} · Priority {task.priority} · {activityTime(task) ?? "Time unavailable"}
                      </p>
                    </div>
                    <Badge variant={task.lifecycle_state === "completed" ? "success" : task.lifecycle_state === "started" ? "default" : "secondary"}>
                      {task.lifecycle_state ?? "Unknown"}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-primary" />
                Planning &amp; decision
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {latest.data ? (
                <>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">Latest this session</Badge>
                    <span className="text-xs text-content-secondary">
                      {valueText(optimizationEvidence?.prediction_matrix_status, "Planning completed")}
                    </span>
                  </div>
                  {typeof latestRecommendation === "object" && latestRecommendation !== null ? (
                    <div className="rounded-md border border-border bg-surface-2 p-3 text-xs space-y-1">
                      <p className="font-semibold text-content-primary">
                        {String((latestRecommendation as Record<string, unknown>).title ?? (latestRecommendation as Record<string, unknown>).plan_name ?? "Recommended Execution Plan")}
                      </p>
                      {Boolean((latestRecommendation as Record<string, unknown>).description) && (
                        <p className="text-content-secondary line-clamp-2">
                          {String((latestRecommendation as Record<string, unknown>).description)}
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-content-secondary">Recommendation: not returned.</p>
                  )}
                  {latestRecommendation && (
                    <TechnicalDetails data={latestRecommendation} title="Technical details (Plan summary)" />
                  )}
                </>
              ) : (
                <p className="text-sm text-content-secondary">
                  No planning result is cached for this signed-in session. Generate one in Planning.
                </p>
              )}
              <Link to="/planning" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                Planning workspace <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Atom className="h-4 w-4 text-quantum" />
                Quantum simulation readiness
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={typeof suitability?.status === "string" && suitability.status === "SUITABLE" ? "success" : "warning"}>
                  {valueText(suitability?.status, "NOT_CHECKED")}
                </Badge>
                <span className="text-xs text-content-tertiary">
                  Problem-specific suitability is evaluated per optimization request.
                </span>
              </div>
              <p className="text-xs text-content-secondary">
                {quantum.data?.available ? "Local software simulator ready." : quantum.isError ? "Quantum status could not be retrieved." : "Simulator configuration not available."} No physical quantum hardware is used.
              </p>
              <Link to="/quantum" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                Quantum workspace <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <BrainCircuit className="h-4 w-4 text-primary" />
              Personal Intelligence &amp; Model Adaptation
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-medium text-content-primary">
                {model.data?.production_model_approved
                  ? "Personalized ML model active"
                  : "Deterministic baselines active · Personalized training guarded"}
              </p>
              <p className="mt-1 text-xs text-content-secondary">
                Adapts from genuine completed tasks in your workspace. Synthetic assumptions are never used.
              </p>
            </div>
            <Link to="/data-learning">
              <Button variant="secondary" size="sm">Learning Progress</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Ask JAM Assistant
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-medium text-content-primary">
                Conversational Task Planning &amp; Prioritization
              </p>
              <p className="mt-1 text-xs text-content-secondary">
                Natural-language assistance for daily task breakdown, schedule recommendations, and time management.
              </p>
            </div>
            <Link to="/assistant">
              <Button size="sm" className="gap-1.5">
                Open Ask JAM
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </section>

      <p className="flex items-center gap-2 text-xs text-content-tertiary">
        <Clock3 className="h-3.5 w-3.5" />
        Values reflect current API responses; session-only states are labeled clearly.
      </p>
    </div>
  );
}
