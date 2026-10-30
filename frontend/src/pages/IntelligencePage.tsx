import React from "react";
import {
  useAIRecommendations,
  useBehaviorPatterns,
  useDataCollectionStatus,
  useMLModelStatus,
  useSystemStatus,
  useTasks,
} from "@/api/hooks";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  BrainCircuit,
  ChartNoAxesCombined,
  Clock,
  Database,
  Info,
  Lightbulb,
  ListOrdered,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useUserStore } from "@/stores/userStore";
import type { UserBehaviorPatterns } from "@/api/endpoints";
import { formatScore, formatStatus, normalizeErrorMessage } from "@/utils/formatters";
import { TechnicalDetails } from "@/components/common/TechnicalDetails";

function metric(value: unknown, suffix = "") {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(1)}${suffix}`
    : "Not available";
}

function PatternMetric({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: unknown;
  sublabel?: string;
}) {
  const displayValue =
    typeof value === "string" || typeof value === "number"
      ? String(value)
      : "Not available";

  return (
    <div className="rounded-lg border border-border bg-surface-2/70 p-3">
      <div className="flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-content-tertiary">
          {label}
        </p>
        <span className="text-[10px] text-content-tertiary font-mono">Heuristic</span>
      </div>
      <p className="mt-2 text-lg font-semibold text-content-primary">{displayValue}</p>
      {sublabel && (
        <p className="mt-1 text-[11px] text-content-secondary">{sublabel}</p>
      )}
    </div>
  );
}

function listOfStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

export function IntelligencePage() {
  const userId = useUserStore((state) => state.userId);
  const tasks = useTasks();
  const completedCount =
    tasks.data?.tasks.filter(
      (task) => task.lifecycle_state === "completed" && task.outcome_valid === true
    ).length ?? 0;
  const patterns = useBehaviorPatterns(completedCount > 0);
  const collection = useDataCollectionStatus();
  const model = useMLModelStatus();
  const telemetry = useSystemStatus();
  const recommendations = useAIRecommendations();
  const behavior: UserBehaviorPatterns | undefined = patterns.data?.patterns;
  const hasVerifiedHistory =
    typeof behavior?.tasks_analyzed === "number" && behavior.tasks_analyzed > 0;

  const requestRecommendations = () => {
    if (userId !== null) recommendations.mutate({ userId, daysBack: 90 });
  };

  const modelStatus = formatStatus(model.data?.status ?? (model.isError ? "ERROR" : "UNINITIALIZED"));
  const auditStatus = formatStatus(
    collection.data?.result.quality_audit?.readiness_status ??
      (collection.isError ? "ERROR" : "NOT_READY_INSUFFICIENT_DATA")
  );

  const normalizedRecError = recommendations.error
    ? normalizeErrorMessage(recommendations.error, "Recommendation request could not be completed.")
    : null;

  return (
    <div className="space-y-6 pb-8 sm:space-y-8">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Behavior · Personal Observations
          </p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-content-primary sm:text-3xl">
            My Insights
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-content-secondary">
            User-scoped analysis of your completed task records and behavioral patterns. Honest metrics derived from verified runtime data.
          </p>
        </div>
        <Link to="/data-learning">
          <Button variant="secondary" className="gap-2">
            <Database className="h-4 w-4" />
            Data readiness &amp; learning
          </Button>
        </Link>
      </header>

      {/* METRIC OVERVIEW CARDS */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-content-tertiary">Verified completed tasks</p>
            <p className="mt-2 text-2xl font-semibold">
              {tasks.isLoading ? "…" : tasks.isError ? "Unavailable" : completedCount}
            </p>
            <p className="mt-1 text-xs text-content-secondary">
              Personal history in your account
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-content-tertiary">Model registry status</p>
            <p className="mt-2 text-lg font-semibold">{modelStatus.label}</p>
            <p className="mt-1 text-xs text-content-secondary">
              {model.data?.models_registered ?? "0"} registered in local runtime
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-content-tertiary">Personal dataset readiness</p>
            <p className="mt-2 text-lg font-semibold">{auditStatus.label}</p>
            <p className="mt-1 text-xs text-content-secondary">
              {auditStatus.description}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-content-tertiary">Prediction engine calls</p>
            <p className="mt-2 text-2xl font-semibold">
              {telemetry.isLoading
                ? "…"
                : telemetry.isError
                ? "Unavailable"
                : String(telemetry.data?.ai_metrics.prediction_count ?? "0")}
            </p>
            <p className="mt-1 text-xs text-content-secondary">
              Inference requests recorded in this session
            </p>
          </CardContent>
        </Card>
      </section>

      {/* MAIN TWO-COLUMN SECTION */}
      <section className="grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
        {/* Behavioral Intelligence Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <BrainCircuit className="h-5 w-5 text-primary" />
                Behavioral intelligence
              </CardTitle>
              <Badge variant="outline" className="text-[10px]">
                Heuristic Estimation
              </Badge>
            </div>
            <p className="text-sm text-content-secondary">
              Aggregated from verified task completions and feedback ratings from your account.
            </p>
          </CardHeader>
          <CardContent>
            {tasks.isLoading || (completedCount > 0 && patterns.isLoading) ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : tasks.isError ? (
              <p role="alert" className="text-sm text-status-error">
                Task history could not be loaded. Check your connection and try again.
              </p>
            ) : completedCount === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-center">
                <Activity className="mx-auto h-7 w-7 text-content-tertiary" />
                <p className="mt-3 font-medium">Not enough personal data yet</p>
                <p className="mt-1 text-sm text-content-secondary">
                  Complete tasks with duration feedback to help HELIOX discover your optimal working hours and productivity patterns.
                </p>
                <Link to="/tasks" className="mt-3 inline-block">
                  <Button variant="secondary" size="sm">
                    Open Tasks
                  </Button>
                </Link>
              </div>
            ) : patterns.isError ? (
              <p role="alert" className="text-sm text-status-warning">
                Behavior report unavailable. Try completing more tasks to establish a baseline.
              </p>
            ) : hasVerifiedHistory ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <PatternMetric
                    label="Tasks analyzed"
                    value={behavior?.tasks_analyzed ?? "Not available"}
                    sublabel="Completed with verified timestamps"
                  />
                  <PatternMetric
                    label="Productivity proxy"
                    value={metric(behavior?.average_productivity)}
                    sublabel="Estimated from duration efficiency"
                  />
                  <PatternMetric
                    label="Focus proxy"
                    value={metric(behavior?.average_focus_score)}
                    sublabel="Based on logged focus ratings"
                  />
                  <PatternMetric
                    label="Energy proxy"
                    value={metric(behavior?.average_energy_level)}
                    sublabel="Self-reported energy indicators"
                  />
                </div>

                <div className="mt-4 rounded-lg border border-border bg-surface-2/40 p-3 text-xs leading-relaxed text-content-secondary flex items-start gap-2.5">
                  <Info className="h-4 w-4 shrink-0 mt-0.5 text-primary" />
                  <div>
                    <span className="font-semibold text-content-primary">
                      Source and limitations note:
                    </span>{" "}
                    These historical scores are heuristic approximations derived from logged task completions and user feedback. They are heuristic estimates rather than measured physiological ground truth, and their accuracy increases as you record more feedback.
                  </div>
                </div>

                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-content-tertiary">
                      Frequent task types
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {listOfStrings(behavior?.preferred_task_types).length ? (
                        listOfStrings(behavior?.preferred_task_types).map((type) => (
                          <Badge key={type} variant="secondary">
                            {type}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-sm text-content-secondary">
                          No category pattern identified yet
                        </span>
                      )}
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-content-tertiary">
                      Discovered focus hours
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {Array.isArray(behavior?.best_focus_hours) &&
                      behavior.best_focus_hours.length ? (
                        behavior.best_focus_hours.map((hour) => (
                          <Badge key={hour} variant="outline" className="font-mono">
                            {hour}:00
                          </Badge>
                        ))
                      ) : (
                        <span className="text-sm text-content-secondary">
                          Awaiting more task data across different hours
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-content-secondary">
                The system has not recorded enough completed tasks to calculate behavioral patterns.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Prediction Engine & Recommendations Column */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ChartNoAxesCombined className="h-5 w-5 text-primary" />
                Prediction Engine
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={model.data?.status === "operational" ? "success" : "warning"}>
                  {modelStatus.label}
                </Badge>
                <span className="text-xs text-content-secondary">
                  {model.data?.in_memory_only
                    ? "In-memory model registry"
                    : "Registry mode active"}
                </span>
              </div>
              <p className="text-sm text-content-secondary leading-relaxed">
                Duration and productivity predictions currently use baseline heuristic estimators with strict zero-leakage boundaries. Models stay in guarded baseline mode until sufficient verified data exists.
              </p>
              <div className="flex items-center gap-2 rounded-md bg-surface-2 p-3 text-xs text-content-tertiary">
                <Zap className="h-4 w-4 shrink-0 text-quantum" />
                Personalized fine-tuning is triggered automatically once dataset readiness thresholds are met in Data &amp; Learning.
              </div>
            </CardContent>
          </Card>

          {/* Recommendations Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-primary" />
                Personalized AI Recommendations
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-content-secondary">
                Generates prioritized schedule adjustments and daily focus suggestions from your task profile.
              </p>

              <Button
                onClick={requestRecommendations}
                disabled={userId === null || recommendations.isPending}
                isLoading={recommendations.isPending}
              >
                {recommendations.isPending ? "Generating recommendations…" : "Get recommendations"}
              </Button>

              {/* Normalized Recommendation Error */}
              {normalizedRecError && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3.5 space-y-2 text-xs">
                  <div className="flex items-start gap-2 text-amber-300 font-semibold">
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>{normalizedRecError.title}</span>
                  </div>
                  <p className="text-amber-200/90 leading-relaxed pl-6">
                    {normalizedRecError.explanation}
                  </p>
                  {normalizedRecError.actionSuggestion && (
                    <p className="text-amber-300/80 pl-6 font-medium">
                      Next step: {normalizedRecError.actionSuggestion}
                    </p>
                  )}
                  <div className="pl-6 pt-1 flex items-center gap-3">
                    {normalizedRecError.isRetryable && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={requestRecommendations}
                        className="gap-1.5 h-7 text-xs"
                      >
                        <RefreshCw className="h-3 w-3" /> Retry
                      </Button>
                    )}
                    <Link to="/tasks" className="text-xs text-primary hover:underline">
                      Go to Tasks &rarr;
                    </Link>
                  </div>
                </div>
              )}

              {/* Polished Recommendation Results */}
              {recommendations.data && (
                <div className="space-y-4 pt-1">
                  {/* Focus hours */}
                  {Array.isArray(recommendations.data.focus_hours) &&
                    recommendations.data.focus_hours.length > 0 && (
                      <div className="rounded-lg border border-border bg-surface-2/40 p-3 space-y-1.5">
                        <p className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5 text-primary" />
                          Recommended Focus Hours
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {recommendations.data.focus_hours.map((h: string) => (
                            <Badge key={h} variant="default" className="font-mono text-xs">
                              {h}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                  {/* Schedule Improvements */}
                  {Array.isArray(recommendations.data.schedule_improvements) &&
                    recommendations.data.schedule_improvements.length > 0 && (
                      <div className="rounded-lg border border-border bg-surface-2/40 p-3 space-y-1.5">
                        <p className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                          <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
                          Schedule Optimization Suggestions
                        </p>
                        <ul className="list-disc pl-4 space-y-1 text-xs text-content-secondary">
                          {recommendations.data.schedule_improvements.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                  {/* Behavioral Insights */}
                  {Array.isArray(recommendations.data.behavioral_insights) &&
                    recommendations.data.behavioral_insights.length > 0 && (
                      <div className="rounded-lg border border-border bg-surface-2/40 p-3 space-y-1.5">
                        <p className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                          <Sparkles className="h-3.5 w-3.5 text-primary" />
                          Personal Productivity Insights
                        </p>
                        <ul className="list-disc pl-4 space-y-1 text-xs text-content-secondary">
                          {recommendations.data.behavioral_insights.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                  {/* Priority Task Ordering */}
                  {Array.isArray(recommendations.data.task_ordering) &&
                    recommendations.data.task_ordering.length > 0 && (
                      <div className="rounded-lg border border-border bg-surface-2/40 p-3 space-y-1.5">
                        <p className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                          <ListOrdered className="h-3.5 w-3.5 text-primary" />
                          Recommended Execution Order
                        </p>
                        <ol className="list-decimal pl-4 space-y-1 text-xs text-content-secondary">
                          {recommendations.data.task_ordering.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ol>
                      </div>
                    )}

                  <TechnicalDetails
                    data={recommendations.data}
                    title="Technical details (Recommendation payload)"
                  />
                </div>
              )}

              <Link
                to="/planning"
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Open Planning Workspace
              </Link>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* FOOTER NOTICE */}
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium">Training data readiness &amp; audit</p>
            <p className="mt-1 text-sm text-content-secondary">
              Review real sample counts, dataset quality checks, and training thresholds in Data &amp; Learning.
            </p>
          </div>
          <Link
            to="/data-learning"
            className="inline-flex shrink-0 items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            <Database className="h-4 w-4" />
            Review data readiness
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
