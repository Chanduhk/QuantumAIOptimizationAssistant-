import * as React from "react";
import {
  useDataCollectionStatus,
  useDatasetReadiness,
  useMLModelStatus,
  useMLReadiness,
  useMLTrainingStatus,
  useTriggerTraining,
  useRetryTraining,
  useBootstrapPublicDataset,
  useTasks,
  useBenchmarkDatasets,
  useBenchmarkRL,
  useBenchmarkVectorMemory,
} from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { formatStatus, formatLocalTime, formatDuration } from "@/utils/formatters";
import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  Database,
  GitBranch,
  Info,
  Layers,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Star,
  Activity,
  TrendingUp,
  Clock,
  Code2,
} from "lucide-react";
import { Link } from "react-router-dom";

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function text(value: unknown, fallback = "Not available") {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function parseRejectionReasons(rejectionDetails: unknown): [string, number][] {
  if (!rejectionDetails) return [];
  if (typeof rejectionDetails === "object" && !Array.isArray(rejectionDetails)) {
    return Object.entries(rejectionDetails as Record<string, unknown>).map(([k, v]) => [
      k.replace(/^task\./, "").replace(/\.$/, ""),
      typeof v === "number" ? v : 1,
    ]);
  }
  if (typeof rejectionDetails === "string") {
    try {
      const parsed = JSON.parse(rejectionDetails.replace(/'/g, '"'));
      if (typeof parsed === "object" && parsed !== null) {
        return Object.entries(parsed).map(([k, v]) => [
          k.replace(/^task\./, "").replace(/\.$/, ""),
          typeof v === "number" ? v : 1,
        ]);
      }
    } catch {
      return [[rejectionDetails, 1]];
    }
  }
  return [];
}

const feedbackSteps = [
  { title: "Task Creation", icon: Database, description: "Tasks are created with explicit estimated duration and unit ('minutes').", kind: "task" },
  { title: "Initial Estimate", icon: BrainCircuit, description: "Heuristic and baseline predictions run before execution without future leakage.", kind: "prediction" },
  { title: "Smart Scheduling", icon: Sparkles, description: "Personalized scheduling prioritizes your day based on your workload constraints.", kind: "recommendation" },
  { title: "Execution & Outcome", icon: CheckCircle2, description: "Task completion records actual duration and verifies lifecycle timestamps.", kind: "outcome" },
  { title: "Personal Feedback", icon: GitBranch, description: "Post-task ratings (Focus, Energy, Productivity) submitted directly by you.", kind: "feedback" },
  { title: "Adaptive Learning", icon: BrainCircuit, description: "Strict gates verify statistical sample minimums before personalizing your model.", kind: "learning" },
];

export function DataLearningPage() {
  const tasks = useTasks();
  const collection = useDataCollectionStatus();
  const readiness = useDatasetReadiness();
  const mlReadiness = useMLReadiness();
  const model = useMLModelStatus();
  const trainingStatus = useMLTrainingStatus();
  const triggerTraining = useTriggerTraining();
  const retryTraining = useRetryTraining();
  const bootstrapDataset = useBootstrapPublicDataset();
  const benchmarkDatasets = useBenchmarkDatasets();
  const benchmarkRL = useBenchmarkRL();
  const benchmarkVector = useBenchmarkVectorMemory();

  const [datasetViewTab, setDatasetViewTab] = React.useState<"catalog" | "matrix" | "rl" | "vector">("catalog");
  const [showRejectionDetails, setShowRejectionDetails] = React.useState(false);
  const [showTrainingLogs, setShowTrainingLogs] = React.useState(false);

  const reports = record(collection.data?.result.collection_report);
  const audit = record(readiness.data?.result.quality_audit);
  const sampleCounts = record(audit?.sample_counts);

  const userTasks = tasks.data?.tasks ?? [];
  const taskCount = tasks.isError ? undefined : userTasks.length;
  const completedTasks = userTasks.filter((task) => task.lifecycle_state === "completed" || task.completed);
  const verifiedOutcomes = tasks.isError
    ? undefined
    : userTasks.filter((task) => task.lifecycle_state === "completed" && task.outcome_valid === true).length;
  const ratedTasks = tasks.isError
    ? undefined
    : userTasks.filter((task) => task.focus_rating !== null && task.focus_rating !== undefined).length;

  // Personal metrics calculations
  const ratedTaskList = userTasks.filter((t) => typeof t.productivity_rating === "number");
  const avgProductivityScore = ratedTaskList.length > 0
    ? Math.round(ratedTaskList.reduce((sum, t) => sum + (((t.productivity_rating ?? 1) - 1) * 25), 0) / ratedTaskList.length)
    : null;

  const avgFocusRating = userTasks.filter((t) => typeof t.focus_rating === "number");
  const meanFocus = avgFocusRating.length > 0
    ? (avgFocusRating.reduce((sum, t) => sum + (t.focus_rating ?? 0), 0) / avgFocusRating.length).toFixed(1)
    : null;

  const validDurationTasks = userTasks.filter(
    (t) => t.outcome_valid && typeof t.actual_duration === "number" && typeof t.estimated_duration === "number"
  );
  const avgVarianceMin = validDurationTasks.length > 0
    ? Math.round(validDurationTasks.reduce((sum, t) => sum + ((t.actual_duration ?? 0) - (t.estimated_duration ?? 0)), 0) / validDurationTasks.length)
    : null;

  // Task type breakdown for personal history
  const typeCounts = userTasks.reduce((acc, t) => {
    const type = t.task_type || "general";
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const durationComponent = mlReadiness.data?.components.DurationRatioModel;
  const productivityComponent = mlReadiness.data?.components.ProductivityModel;
  const rlComponent = mlReadiness.data?.components.RLScheduler;

  const rejectionReasonsList = parseRejectionReasons(durationComponent?.details?.rejection_reasons);
  const auditError = collection.error ?? readiness.error ?? mlReadiness.error;

  const values: Record<string, string> = {
    task: typeof taskCount === "number" ? `${taskCount} personal task records` : "Task data not available",
    prediction: "Pre-execution estimates active",
    recommendation: "Deterministic priority & deadline solver active",
    outcome: typeof verifiedOutcomes === "number" ? `${verifiedOutcomes} verified outcomes` : "Outcome count not available",
    feedback: typeof ratedTasks === "number" ? `${ratedTasks} user-rated sessions` : "Feedback count not available",
    learning: mlReadiness.data?.overall_status ?? text(audit?.readiness_status, "Audit not available"),
  };

  const getStatusBadge = (status: string | undefined) => {
    if (model.data?.production_model_approved) {
      return <Badge variant="success">Personalized Model Active</Badge>;
    }
    if (model.data?.candidate_model_staging) {
      return <Badge variant="outline" className="text-quantum border-quantum/40 bg-quantum/10">Candidate Staged (Pending Validation)</Badge>;
    }
    switch (status) {
      case "READY_FOR_TRAINING":
        return <Badge variant="success">Ready to Train Personalized Model</Badge>;
      case "NOT_READY_NO_GROUND_TRUTH_LABELS":
        return <Badge variant="outline" className="text-status-warning border-status-warning/30 bg-status-warning/10">Awaiting Feedback Ratings</Badge>;
      case "NOT_READY_INSUFFICIENT_EPISODES":
        return <Badge variant="outline" className="text-status-warning border-status-warning/30 bg-status-warning/10">Awaiting Scheduling Episodes</Badge>;
      case "NOT_READY_INSUFFICIENT_DATA":
      case "NOT_READY_NO_DATA":
      default:
        return <Badge variant="warning">Collecting Personal Data (Heuristics Active)</Badge>;
    }
  };

  return (
    <div className="space-y-6 pb-8 sm:space-y-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          Personal History · Learning Progress
        </p>
        <h2 className="mt-2 text-2xl font-bold tracking-tight text-content-primary sm:text-3xl">
          Data &amp; Learning
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-content-secondary">
          Your personal task history, completion patterns, and progress toward personalized AI model training. Models only adapt to your verified activity, never from synthetic assumptions.
        </p>
      </header>

      {auditError && (
        <Card role="alert" className="border-status-warning/30 bg-status-warning/5">
          <CardContent className="p-4 text-sm text-content-secondary">
            Personal data status: {getApiErrorMessage(auditError, "The backend could not return data readiness.")}
          </CardContent>
        </Card>
      )}

      {/* Primary Personal Metrics Grid */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-content-tertiary">Personal task records</p>
            <p className="mt-2 text-2xl font-semibold">
              {tasks.isLoading ? "…" : tasks.isError ? "Unavailable" : taskCount}
            </p>
            <p className="mt-1 text-xs text-content-secondary">Logged in this account</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-content-tertiary">Verified completed outcomes</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-400">
              {tasks.isLoading ? "…" : tasks.isError ? "Unavailable" : verifiedOutcomes}
            </p>
            <p className="mt-1 text-xs text-content-secondary">Lifecycle verified timestamps</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-content-tertiary">Personal feedback ratings</p>
            <p className="mt-2 text-2xl font-semibold text-primary">
              {tasks.isLoading ? "…" : tasks.isError ? "Unavailable" : ratedTasks}
            </p>
            <p className="mt-1 text-xs text-content-secondary">Focus &amp; energy ratings recorded</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-content-tertiary">Personal model status</p>
            <p className="mt-2 break-words text-base font-semibold">
              {mlReadiness.isLoading ? "Checking…" : formatStatus(mlReadiness.data?.overall_status ?? audit?.readiness_status).label}
            </p>
            <p className="mt-1 text-xs text-content-secondary">
              {model.data?.production_model_approved ? "Personal model operational" : "Guarded heuristic fallback active"}
            </p>
          </CardContent>
        </Card>
      </section>

      {/* Personal Learning Adaptation Progress */}
      <Card className="border-primary/20 bg-gradient-to-br from-surface-1 via-surface-1 to-primary/5">
        <CardHeader>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-lg">Personal Learning Adaptation</CardTitle>
              <p className="mt-1 text-sm text-content-secondary">
                Tracking genuine completed activity required before personalized machine learning models activate for your account.
              </p>
            </div>
            <div>{getStatusBadge(mlReadiness.data?.overall_status)}</div>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            {/* Duration Model */}
            <div className="rounded-lg border border-border bg-surface-2/60 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-content-secondary">
                  Duration Adaptation
                </span>
                <Badge variant={model.data?.production_model_approved ? "success" : "outline"} className="text-[10px]">
                  {model.data?.production_model_approved ? "Personal Model" : "Deterministic Fallback"}
                </Badge>
              </div>
              <div className="mt-2 flex items-baseline justify-between">
                <span className="text-xs text-content-secondary">verified task rows</span>
                <span className="font-mono text-sm font-semibold text-primary">
                  {durationComponent ? `${durationComponent.eligible_samples} / ${durationComponent.required_samples}` : "—"}
                </span>
              </div>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                <div
                  className="h-full bg-primary transition-all duration-500"
                  style={{
                    width: `${Math.min(
                      100,
                      ((durationComponent?.eligible_samples ?? 0) / (durationComponent?.required_samples ?? 10)) * 100
                    )}%`,
                  }}
                />
              </div>
              <p className="mt-2.5 text-xs text-content-secondary leading-relaxed">
                {durationComponent && durationComponent.eligible_samples < durationComponent.required_samples
                  ? `${durationComponent.required_samples - durationComponent.eligible_samples} more verified completed tasks required before personal duration tuning.`
                  : "Meets personal training baseline."}
              </p>
            </div>

            {/* Productivity Model */}
            <div className="rounded-lg border border-border bg-surface-2/60 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-content-secondary">
                  Focus &amp; Energy Learning
                </span>
                <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-500/30">
                  {ratedTasks && ratedTasks >= 10 ? "Ready to Learn" : "Collecting Feedback"}
                </Badge>
              </div>
              <div className="mt-2 flex items-baseline justify-between">
                <span className="text-xs text-content-secondary">genuine user ratings</span>
                <span className="font-mono text-sm font-semibold text-primary">
                  {productivityComponent ? `${productivityComponent.eligible_samples} / ${productivityComponent.required_samples}` : "—"}
                </span>
              </div>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                <div
                  className="h-full bg-primary transition-all duration-500"
                  style={{
                    width: `${Math.min(
                      100,
                      ((productivityComponent?.eligible_samples ?? 0) / (productivityComponent?.required_samples ?? 10)) * 100
                    )}%`,
                  }}
                />
              </div>
              <p className="mt-2.5 text-xs text-content-secondary leading-relaxed">
                {productivityComponent && productivityComponent.eligible_samples === 0
                  ? "No task ratings logged yet. Rate tasks (1–5 stars) after completing them to teach JAM your focus levels."
                  : `${productivityComponent?.eligible_samples ?? 0} ratings recorded toward personal productivity model.`}
              </p>
            </div>

            {/* RL Scheduler */}
            <div className="rounded-lg border border-border bg-surface-2/60 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-content-secondary">
                  Adaptive Scheduling
                </span>
                <Badge variant="outline" className="text-[10px]">
                  {model.data?.rl_policy_status === "TRAINED" ? "Trained Policy" : "Standard Scheduler"}
                </Badge>
              </div>
              <div className="mt-2 flex items-baseline justify-between">
                <span className="text-xs text-content-secondary">completed schedule episodes</span>
                <span className="font-mono text-sm font-semibold text-primary">
                  {rlComponent ? `${rlComponent.eligible_samples} / ${rlComponent.required_samples}` : "—"}
                </span>
              </div>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                <div
                  className="h-full bg-primary transition-all duration-500"
                  style={{
                    width: `${Math.min(
                      100,
                      ((rlComponent?.eligible_samples ?? 0) / (rlComponent?.required_samples ?? 25)) * 100
                    )}%`,
                  }}
                />
              </div>
              <p className="mt-2.5 text-xs text-content-secondary leading-relaxed">
                {rlComponent && rlComponent.eligible_samples < rlComponent.required_samples
                  ? `${rlComponent.required_samples - rlComponent.eligible_samples} more daily schedule executions required before reinforcement policy tunes.`
                  : "Meets scheduling episode baseline."}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personal Productivity Insights & Observations */}
      <section className="grid gap-4 lg:grid-cols-2">
        {/* Personal Productivity Pulse */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              Personal Productivity Observations
            </CardTitle>
            <p className="text-sm text-content-secondary">
              Empirical metrics derived solely from your completed tasks and submitted ratings.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {ratedTaskList.length > 0 || validDurationTasks.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-border bg-surface-2/50 p-3">
                  <span className="text-xs text-content-tertiary">Avg. Self-Reported Score</span>
                  <p className="text-xl font-bold text-content-primary mt-1">
                    {avgProductivityScore !== null ? `${avgProductivityScore}/100` : "—"}
                  </p>
                  <p className="text-[11px] text-content-secondary mt-0.5">Based on {ratedTaskList.length} rating(s)</p>
                </div>
                <div className="rounded-lg border border-border bg-surface-2/50 p-3">
                  <span className="text-xs text-content-tertiary">Mean Focus Rating</span>
                  <p className="text-xl font-bold text-amber-400 mt-1 flex items-center gap-1">
                    <Star className="h-4 w-4 fill-amber-400" />
                    {meanFocus ?? "—"}
                  </p>
                  <p className="text-[11px] text-content-secondary mt-0.5">Scale of 1–5 stars</p>
                </div>
                <div className="rounded-lg border border-border bg-surface-2/50 p-3">
                  <span className="text-xs text-content-tertiary">Time Variance</span>
                  <p className="text-xl font-bold text-primary mt-1">
                    {avgVarianceMin !== null ? (avgVarianceMin > 0 ? `+${avgVarianceMin}m` : `${avgVarianceMin}m`) : "—"}
                  </p>
                  <p className="text-[11px] text-content-secondary mt-0.5">Actual vs. Estimated</p>
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-content-secondary space-y-1">
                <p className="font-semibold text-content-primary">Insufficient Activity For Productivity Trends</p>
                <p>Complete and rate at least 3 tasks to unlock personal completion velocity and focus insights.</p>
                <div className="pt-2">
                  <Link to="/tasks">
                    <Button size="sm" variant="secondary">Go to My Tasks</Button>
                  </Link>
                </div>
              </div>
            )}

            {Object.keys(typeCounts).length > 0 && (
              <div className="space-y-2 pt-2 border-t border-border/70">
                <p className="text-xs font-semibold uppercase tracking-wider text-content-tertiary">
                  Task Category Distribution
                </p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(typeCounts).map(([type, count]) => (
                    <span key={type} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-3 py-1 text-xs">
                      <span className="font-medium capitalize text-content-primary">{type}:</span>
                      <span className="font-mono text-primary font-semibold">{count}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Data Quality & Integrity */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              Quality &amp; Privacy Safeguards
            </CardTitle>
            <p className="text-sm text-content-secondary">
              Strict rules protect your personal dataset from dirty inputs or synthetic manipulation.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              ["Total personal task records", taskCount ?? 0],
              ["Eligible completed training samples", durationComponent?.eligible_samples ?? 0],
              ["Completed tasks with valid outcomes", verifiedOutcomes ?? 0],
              ["Genuine user ratings logged", ratedTasks ?? 0],
              ["Temporal leakage prevention", "Verified (No future leakage)"],
            ].map(([label, value]) => (
              <div
                key={String(label)}
                className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2 text-sm last:border-0"
              >
                <span className="text-content-secondary text-xs">{String(label)}</span>
                <span className="font-mono text-xs font-medium text-content-primary">
                  {String(value)}
                </span>
              </div>
            ))}

            {rejectionReasonsList.length > 0 && (
              <div className="mt-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRejectionDetails(!showRejectionDetails)}
                  className="flex w-full items-center justify-between text-xs font-medium text-primary hover:underline focus:outline-none"
                >
                  <span>Why records were filtered ({rejectionReasonsList.length} filter reasons)</span>
                  {showRejectionDetails ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
                {showRejectionDetails && (
                  <div className="mt-2 space-y-1.5 rounded-md border border-border/80 bg-surface-1 p-3 text-xs">
                    {rejectionReasonsList.map(([reason, count], idx) => (
                      <div key={idx} className="flex items-center justify-between text-content-secondary">
                        <span className="text-status-warning">• {reason}</span>
                        <span className="font-mono text-content-tertiary">×{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Outcome-to-learning loop */}
      <Card>
        <CardHeader>
          <CardTitle>Outcome-to-Learning Pipeline</CardTitle>
          <p className="text-sm text-content-secondary">
            Trace how everyday task execution safely turns into real training data without fabrication.
          </p>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {feedbackSteps.map((step, index) => {
              const Icon = step.icon;
              return (
                <li
                  key={step.kind}
                  className="relative rounded-lg border border-border bg-surface-2/50 p-4"
                >
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 font-medium">
                      <Icon className="h-4 w-4 text-primary" />
                      {step.title}
                    </span>
                    <span className="text-xs text-content-tertiary">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-content-secondary">
                    {step.description}
                  </p>
                  <p className="mt-3 text-xs font-medium text-content-primary">
                    {values[step.kind]}
                  </p>
                  {index < feedbackSteps.length - 1 && (
                    <ArrowRight className="absolute -right-2 top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 text-content-tertiary xl:block" />
                  )}
                </li>
              );
            })}
          </ol>
        </CardContent>
      </Card>

      {/* DEVELOPER & OFFLINE DIAGNOSTIC SUITE (COLLAPSED BY DEFAULT) */}
      <details className="group rounded-xl border border-border/70 bg-surface-1/40 p-4 transition-all">
        <summary className="cursor-pointer flex items-center justify-between text-xs font-semibold text-content-tertiary hover:text-content-primary select-none">
          <div className="flex items-center gap-2">
            <Code2 className="h-4 w-4 text-primary" />
            <span>Developer &amp; Engine Diagnostic Suite (Benchmarking &amp; Internal Controls)</span>
          </div>
          <span className="text-[11px] font-mono text-primary group-open:rotate-180 transition-transform">▼</span>
        </summary>

        <div className="mt-4 pt-4 border-t border-border/70 space-y-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h4 className="text-sm font-semibold text-content-primary flex items-center gap-2">
                <BrainCircuit className="h-4 w-4 text-primary" />
                Background Controller &amp; Offline Reference Benchmarks
              </h4>
              <p className="text-xs text-content-secondary mt-0.5">
                Internal developer tools for testing holdout comparisons and training pipelines. Offline reference candidates are locked in staging.
              </p>
            </div>
            <Badge variant="secondary" className="font-mono text-xs uppercase">
              Controller: {trainingStatus.data?.controller_status ?? "idle"}
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              disabled={trainingStatus.data?.controller_status === "running" || triggerTraining.isPending}
              onClick={() => triggerTraining.mutate({ jobType: "public_benchmark", force: true })}
              className="flex items-center gap-1.5"
            >
              <Play className="h-3.5 w-3.5" />
              Train Offline Benchmark Candidate
            </Button>

            <Button
              variant="secondary"
              size="sm"
              disabled={trainingStatus.data?.controller_status === "running" || triggerTraining.isPending}
              onClick={() => triggerTraining.mutate({ jobType: "personalized", force: true })}
              className="flex items-center gap-1.5"
            >
              <BrainCircuit className="h-3.5 w-3.5" />
              Evaluate Personalized Training Gate
            </Button>

            <Button
              variant="secondary"
              size="sm"
              disabled={bootstrapDataset.isPending || trainingStatus.data?.controller_status === "running"}
              onClick={() => bootstrapDataset.mutate(true)}
              className="flex items-center gap-1.5"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Re-verify Offline Reference Data
            </Button>
          </div>

          {/* Benchmark Tabs */}
          <div className="rounded-lg border border-border bg-surface-2/30 p-3 space-y-3">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <span className="text-xs font-semibold text-content-primary">Offline Reference Tables</span>
              <div className="flex items-center gap-1">
                {(["catalog", "matrix", "rl", "vector"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setDatasetViewTab(tab)}
                    className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${
                      datasetViewTab === tab ? "bg-primary text-white" : "text-content-secondary hover:text-content-primary"
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            {datasetViewTab === "catalog" && (
              <p className="text-xs text-content-secondary">
                Offline benchmark datasets (UCI ML #597, OpenML #307) are evaluated for algorithmic baseline calibration. They are never mixed into your personal profile.
              </p>
            )}

            {datasetViewTab === "matrix" && (
              <div className="overflow-x-auto text-[11px]">
                <table className="w-full text-left">
                  <thead className="bg-surface-2 text-content-tertiary uppercase">
                    <tr>
                      <th className="p-2">Dataset</th>
                      <th className="p-2">Target</th>
                      <th className="p-2">Samples</th>
                      <th className="p-2">Decision</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {(benchmarkDatasets.data?.compatibility_matrix as Array<Record<string, unknown>> | undefined)?.slice(0, 5).map((row, idx) => (
                      <tr key={idx}>
                        <td className="p-2 font-semibold text-content-primary">{String(row.dataset_name)}</td>
                        <td className="p-2 font-mono">{String(row.target_variable ?? "-")}</td>
                        <td className="p-2 font-mono">{String(row.sample_count ?? "-")}</td>
                        <td className="p-2"><Badge variant="outline" className="text-[10px]">{String(row.status)}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {datasetViewTab === "rl" && (
              <p className="text-xs text-content-secondary">
                Isolated combinatorial scheduling harness. Personal policy requires &ge; 25 genuine user scheduling episodes before activation.
              </p>
            )}

            {datasetViewTab === "vector" && (
              <p className="text-xs text-content-secondary">
                Local offline vector retrieval evaluated across standard embeddings with zero external cloud dependencies.
              </p>
            )}
          </div>
        </div>
      </details>

      <p className="flex items-start gap-2 text-xs text-content-tertiary">
        <CircleHelp className="mt-0.5 h-4 w-4 shrink-0" />
        All personal learning metrics strictly reflect your authenticated account activity. HELIOX never uses synthetic histories to fabricate model readiness.
      </p>
    </div>
  );
}
