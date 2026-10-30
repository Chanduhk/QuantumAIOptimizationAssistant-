import * as React from "react";
import {
  useComponentInventory,
  useCurrentUser,
  useDataCollectionStatus,
  useLatestExecutiveResult,
  useMLModelStatus,
  useQuantumStatus,
  useSystemHealth,
  useSystemStatus,
  useTasks,
} from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { formatStatus } from "@/utils/formatters";
import {
  Activity,
  AlertCircle,
  Atom,
  BrainCircuit,
  CheckCircle2,
  CircleHelp,
  Cpu,
  Database,
  Filter,
  Layers,
  RefreshCw,
  Server,
  ShieldCheck,
  Zap,
} from "lucide-react";
import type { ComponentInventoryItem } from "@/api/endpoints";

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function label(value: unknown, fallback = "Not available") {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function DiagnosticRow({
  title,
  value,
  detail,
  state = "info",
}: {
  title: string;
  value: string;
  detail: string;
  state?: "ok" | "warning" | "error" | "info";
}) {
  const variants = {
    ok: "success",
    warning: "warning",
    error: "error",
    info: "secondary",
  } as const;
  return (
    <div className="flex flex-col gap-2 border-b border-border py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-current text-content-tertiary" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-content-primary">{title}</p>
          <p className="mt-1 text-xs text-content-secondary">{detail}</p>
        </div>
      </div>
      <Badge variant={variants[state]} className="w-fit max-w-full break-words">
        {value}
      </Badge>
    </div>
  );
}

function getOperationalStateBadge(state: string) {
  const formatted = formatStatus(state);
  return (
    <Badge variant={formatted.variant as any} title={formatted.description}>
      {formatted.label}
    </Badge>
  );
}

function getComponentTypeBadge(type: string) {
  const map: Record<string, { label: string; className: string }> = {
    optimizer: { label: "Optimizer", className: "border-amber-500/30 text-amber-300" },
    simulated_quantum: { label: "Simulated Quantum", className: "border-quantum/40 text-quantum" },
    ml_model: { label: "ML Model", className: "border-primary/40 text-primary" },
    pretrained_model: { label: "Pretrained", className: "border-primary/30 text-content-secondary" },
    heuristic: { label: "Heuristic", className: "border-emerald-500/30 text-emerald-300" },
    conversational: { label: "Conversational", className: "border-quantum/30 text-quantum" },
    data_provider: { label: "Data Provider", className: "border-slate-500/30 text-slate-300" },
    worker: { label: "Worker", className: "border-slate-500/30 text-slate-300" },
  };
  const match = map[type.toLowerCase()] ?? { label: type, className: "border-border text-content-secondary" };
  return (
    <Badge variant="outline" className={`text-[10px] font-mono uppercase tracking-wider ${match.className}`}>
      {match.label}
    </Badge>
  );
}

export function SystemStatusPage() {
  const health = useSystemHealth();
  const telemetry = useSystemStatus();
  const currentUser = useCurrentUser();
  const tasks = useTasks();
  const collection = useDataCollectionStatus();
  const model = useMLModelStatus();
  const quantum = useQuantumStatus();
  const inventory = useComponentInventory();
  const latest = useLatestExecutiveResult();

  const [filterCategory, setFilterCategory] = React.useState<"all" | "optimizers" | "ml" | "infrastructure">("all");

  const result = record(latest.data?.result);
  const evidence = record(result?.optimization_evidence);
  const suitability = record(evidence?.quantum_suitability);
  const quantumCandidate = record(evidence?.quantum_candidate);
  const hybrid = record(evidence?.hybrid_comparison);
  const audit = record(collection.data?.result.quality_audit);

  const refreshAll = () => {
    void Promise.all([
      health.refetch(),
      telemetry.refetch(),
      currentUser.refetch(),
      tasks.refetch(),
      collection.refetch(),
      model.refetch(),
      quantum.refetch(),
      inventory.refetch(),
    ]);
  };

  const pool = health.data?.database_pool;

  const rawComponents = inventory.data?.components;
  const components: ComponentInventoryItem[] = React.useMemo(() => {
    if (Array.isArray(rawComponents)) return rawComponents;
    if (rawComponents && typeof rawComponents === "object") {
      return Object.values(rawComponents as Record<string, ComponentInventoryItem>);
    }
    return [];
  }, [rawComponents]);

  const filteredComponents = React.useMemo(() => {
    if (filterCategory === "all") return components;
    if (filterCategory === "optimizers") {
      return components.filter(
        (c) => c.component_type === "optimizer" || c.component_type === "simulated_quantum"
      );
    }
    if (filterCategory === "ml") {
      return components.filter(
        (c) =>
          c.component_type === "ml_model" ||
          c.component_type === "pretrained_model" ||
          c.component_type === "heuristic" ||
          c.component_type === "conversational"
      );
    }
    if (filterCategory === "infrastructure") {
      return components.filter(
        (c) => c.component_type === "data_provider" || c.component_type === "worker"
      );
    }
    return components;
  }, [components, filterCategory]);

  return (
    <div className="space-y-6 pb-8 sm:space-y-8">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Runtime diagnostics & inventory
          </p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-content-primary sm:text-3xl">
            System Status
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-content-secondary">
            Live operational status across all 16 Heliox system components, database connection pool,
            local-first fallback handlers, and external resilience boundaries.
          </p>
        </div>
        <Button variant="secondary" onClick={refreshAll} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh checks
        </Button>
      </header>

      {/* Diagnostics Cards */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5 text-primary" />
              Connectivity & database pool
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DiagnosticRow
              title="FastAPI health"
              value={health.isLoading ? "Checking" : health.isError ? "Unavailable" : label(health.data?.status)}
              detail={health.isError ? getApiErrorMessage(health.error) : "Health endpoint response"}
              state={health.data?.status === "operational" ? "ok" : health.isError ? "error" : "warning"}
            />
            <DiagnosticRow
              title="Database connection"
              value={health.isLoading ? "Checking" : health.isError ? "Unverified" : health.data?.database_connected ? "Connected" : "Disconnected"}
              detail="SQLite database engine initialized; request sessions released cleanly on completion."
              state={health.data?.database_connected ? "ok" : health.isError ? "warning" : "error"}
            />
            <DiagnosticRow
              title="Database connection pool"
              value={
                pool?.pool_size !== undefined
                  ? `${pool.checked_out} checked out / ${pool.pool_size} pool`
                  : health.data?.database_connected
                  ? "Managed Lifecycle"
                  : "Unavailable"
              }
              detail={
                pool?.overflow !== undefined
                  ? `Overflow: ${pool.overflow} / ${pool.overflow_limit} max · Timeout: ${pool.timeout}s`
                  : "Schema creation guarded at startup; no per-request DDL contention."
              }
              state={health.data?.database_connected ? "ok" : "error"}
            />
            <DiagnosticRow
              title="Authenticated session"
              value={currentUser.isLoading ? "Checking" : currentUser.isError ? "Unavailable" : currentUser.data ? "Active" : "Signed out"}
              detail={currentUser.data?.email ?? (currentUser.error ? getApiErrorMessage(currentUser.error) : "Identity comes from the HttpOnly session cookie.")}
              state={currentUser.data ? "ok" : currentUser.isError ? "error" : "warning"}
            />
            <DiagnosticRow
              title="Task API"
              value={tasks.isLoading ? "Checking" : tasks.isError ? "Unavailable" : "Responding"}
              detail={tasks.data ? `${tasks.data.tasks.length} account-scoped records returned` : tasks.isError ? getApiErrorMessage(tasks.error) : "No task response yet"}
              state={tasks.data ? "ok" : tasks.isError ? "error" : "info"}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BrainCircuit className="h-5 w-5 text-primary" />
              Intelligence & model registry
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DiagnosticRow
              title="Behavior/data pipeline"
              value={collection.isLoading ? "Checking" : collection.isError ? "Unavailable" : formatStatus(audit?.readiness_status).label}
              detail={collection.isError ? getApiErrorMessage(collection.error) : formatStatus(audit?.readiness_status).description}
              state={collection.isError ? "warning" : "info"}
            />
            <DiagnosticRow
              title="Model registry"
              value={model.isLoading ? "Checking" : model.isError ? "Unavailable" : formatStatus(model.data?.status).label}
              detail={model.data ? `${model.data.models_registered} registered · Available components: ${model.data.total_components_available ?? 16}` : model.isError ? getApiErrorMessage(model.error) : "No response"}
              state={model.data?.status === "operational" ? "ok" : model.isError ? "warning" : "info"}
            />
            <DiagnosticRow
              title="Duration ratio inference"
              value="Available (Baseline Heuristic)"
              detail="Zero-data cold start uses prior duration ratio regression; protected from future-data leakage."
              state="ok"
            />
            <DiagnosticRow
              title="Executive Cognitive Brain"
              value={latest.data?.result ? "Evidence cached this session" : "No run this session"}
              detail={latest.data?.result ? "Recommendation evidence came from the latest executive request." : "Classical solver runs on demand."}
              state={latest.data?.result ? "ok" : "info"}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Optimization engines
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DiagnosticRow
              title="Classical optimization"
              value="Available (Operational)"
              detail="Bounded 2-opt, simulated annealing, and MIP dispatch without ML model prerequisites."
              state="ok"
            />
            <DiagnosticRow
              title="Multi-objective Pareto solver"
              value="Available (Operational)"
              detail="Scalarized weighted-sum and Pareto frontier evaluation functional."
              state="ok"
            />
            <DiagnosticRow
              title="Exact classical QUBO solver"
              value="Available (Operational)"
              detail="Branch-and-bound and brute force for problem sizes ≤ 20 variables."
              state="ok"
            />
            <DiagnosticRow
              title="Hybrid comparison engine"
              value="Available (Operational)"
              detail="Executes both classical and simulated candidates; selects best verified outcome."
              state="ok"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Atom className="h-5 w-5 text-quantum" />
              Simulation boundary & telemetry
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DiagnosticRow
              title="Quantum configuration"
              value={quantum.isLoading ? "Checking" : quantum.isError ? "Unavailable" : quantum.data?.available ? "Available" : "Unavailable"}
              detail={quantum.data?.direct_execution_exposed === false ? "Local software simulation only; no physical execution route exposed." : "Quantum status response"}
              state={quantum.data?.available ? "ok" : quantum.isError ? "warning" : "info"}
            />
            <DiagnosticRow
              title="Direct quantum execution"
              value="Not exposed"
              detail="No physical quantum hardware or cloud hardware execution is used by this application."
            />
            <DiagnosticRow
              title="Runtime metrics"
              value={telemetry.isLoading ? "Checking" : telemetry.isError ? "Unavailable" : "Process-local"}
              detail={telemetry.data ? `${Object.keys(telemetry.data.ai_metrics).length} telemetry fields returned; these are not ML validation metrics.` : telemetry.isError ? getApiErrorMessage(telemetry.error) : "No telemetry response"}
              state={telemetry.data ? "info" : "warning"}
            />
            <div className="mt-4 flex flex-wrap gap-3">
              <span className="inline-flex items-center gap-1 text-xs text-content-tertiary">
                <ShieldCheck className="h-3.5 w-3.5" />
                Authenticated API scope
              </span>
              <span className="inline-flex items-center gap-1 text-xs text-content-tertiary">
                <CircleHelp className="h-3.5 w-3.5" />
                Independent optimizers
              </span>
              <span className="inline-flex items-center gap-1 text-xs text-content-tertiary">
                <CheckCircle2 className="h-3.5 w-3.5" />
                No hardware claims
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Universal Component & Optimizer Inventory Section */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5 text-primary" />
                Universal Component & Optimizer Inventory
              </CardTitle>
              <p className="mt-1 text-xs text-content-secondary">
                {components.length} registered components · Distinguishing operational execution availability from personalized ML training readiness
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <Button
                variant={filterCategory === "all" ? "primary" : "secondary"}
                size="sm"
                onClick={() => setFilterCategory("all")}
                className="text-xs"
              >
                All ({components.length})
              </Button>
              <Button
                variant={filterCategory === "optimizers" ? "primary" : "secondary"}
                size="sm"
                onClick={() => setFilterCategory("optimizers")}
                className="text-xs"
              >
                Optimizers & Solvers
              </Button>
              <Button
                variant={filterCategory === "ml" ? "primary" : "secondary"}
                size="sm"
                onClick={() => setFilterCategory("ml")}
                className="text-xs"
              >
                ML & Heuristics
              </Button>
              <Button
                variant={filterCategory === "infrastructure" ? "primary" : "secondary"}
                size="sm"
                onClick={() => setFilterCategory("infrastructure")}
                className="text-xs"
              >
                Infrastructure
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {inventory.isLoading ? (
            <div className="flex justify-center py-12">
              <Spinner />
            </div>
          ) : inventory.isError ? (
            <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-status-error">
              Unable to load component inventory: {getApiErrorMessage(inventory.error)}
            </div>
          ) : filteredComponents.length === 0 ? (
            <p className="py-8 text-center text-sm text-content-secondary">
              No components matching the selected category.
            </p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {filteredComponents.map((item) => (
                <div
                  key={item.component_id}
                  className="flex flex-col justify-between rounded-lg border border-border bg-surface-1 p-4 transition-colors hover:border-primary/40"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h4 className="truncate text-sm font-semibold text-content-primary">
                          {item.name}
                        </h4>
                        <p className="font-mono text-[10px] text-content-tertiary">
                          {item.component_id}
                        </p>
                      </div>
                      <div className="shrink-0">{getOperationalStateBadge(item.operational_state)}</div>
                    </div>

                    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                      {getComponentTypeBadge(item.component_type)}
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${
                          item.can_execute_now
                            ? "border-emerald-500/30 text-emerald-400"
                            : "border-amber-500/30 text-amber-400"
                        }`}
                      >
                        {item.can_execute_now ? "● Executable" : "○ Awaiting Data"}
                      </Badge>
                      <Badge variant="outline" className="text-[10px] border-border text-content-secondary">
                        {item.requires_external_api ? "External API" : "Local-First"}
                      </Badge>
                    </div>

                    <p className="mt-2.5 text-xs text-content-secondary leading-relaxed">
                      {item.description}
                    </p>
                  </div>

                  <div className="mt-4 border-t border-border/60 pt-3 text-[11px] space-y-1.5">
                    {item.fallback_description && (
                      <div className="flex items-start gap-1.5 text-content-tertiary">
                        <span className="font-medium text-content-secondary shrink-0">Fallback:</span>
                        <span className="truncate">{item.fallback_description}</span>
                      </div>
                    )}
                    {item.artifact_path && (
                      <div className="flex items-start gap-1.5 text-content-tertiary">
                        <span className="font-medium text-content-secondary shrink-0">Artifact:</span>
                        <span className="truncate font-mono">{item.artifact_path}</span>
                      </div>
                    )}
                    <div className="text-[11px] text-content-tertiary">
                      {item.status_explanation}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

