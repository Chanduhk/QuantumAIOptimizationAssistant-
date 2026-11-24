import * as React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { AlarmClock, BrainCircuit, Database, Flame, Gauge, Lightbulb, ListOrdered, Route, Sparkles, Target, Zap } from "lucide-react";
import { useAIContext, useApplyRecommendation, useBehaviorPatterns, useRecommendations } from "@/api/hooks";
import { useUserStore } from "@/stores/userStore";
import { toast } from "@/components/ui/Toaster";
import type { ActionableProposal } from "@/api/endpoints";
import { Page, PageHeader } from "@/components/layout/Page";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, Skeleton, SkeletonRows } from "@/components/ui/Feedback";
import { Stat } from "@/components/ui/Stat";
import { AreaLine, Bars } from "@/components/viz/Charts";
import { formatRelative } from "@/lib/format";
import { get, humanize, num, rec, recs, str } from "@/lib/data";
import { cn } from "@/lib/utils";

function hourLabel(h: number) {
  return `${String(h).padStart(2, "0")}:00`;
}

function RecommendationGroup({ icon: Icon, title, items, tone }: { icon: React.ElementType; title: string; items: string[]; tone: string }) {
  if (!items.length) return null;
  return (
    <div className="rounded-xl border border-border-subtle p-4 dark:border-border">
      <p className="mb-2 flex items-center gap-2 text-[13px] font-medium text-content-primary">
        <span className={cn("grid size-6 place-items-center rounded-md", tone)}><Icon className="size-3.5" /></span>
        {title}
      </p>
      <ul className="space-y-1.5">
        {items.map((item, i) => {
          const [head, tail] = item.split(" -> ");
          return (
            <li key={i} className="text-[13px] leading-relaxed text-content-secondary">
              {head}
              {tail && <span className="mt-0.5 block text-xs text-content-tertiary">→ {tail}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function InsightsPage() {
  const userId = useUserStore((state) => state.userId);
  const patternsQuery = useBehaviorPatterns();
  const patterns = patternsQuery.data?.patterns ?? null;
  const hasData = Boolean(patterns && (patterns.tasks_analyzed ?? 0) > 0);
  const recsQuery = useRecommendations(90, hasData);
  const contextQuery = useAIContext(hasData);
  const applyMutation = useApplyRecommendation();

  const handleApplyProposal = (p: ActionableProposal) => {
    if (userId === null) return;
    applyMutation.mutate(
      {
        user_id: userId,
        proposal_id: p.proposal_id,
        action_type: p.action_type,
        payload: p.payload,
      },
      {
        onSuccess: () => {
          toast("success", "Recommendation Applied", `Applied "${p.title}" successfully.`);
          recsQuery.refetch();
        },
        onError: (err: any) => {
          toast("error", "Failed to Apply", err?.message || "Could not apply recommendation.");
        },
      }
    );
  };

  const hourly = Object.entries(patterns?.hourly_productivity ?? {})
    .map(([h, v]) => ({ hour: Number(h), value: v }))
    .filter((d) => Number.isFinite(d.hour))
    .sort((a, b) => a.hour - b.hour)
    .map((d) => ({ hour: hourLabel(d.hour), value: d.value }));
  const byType = Object.entries(patterns?.productivity_by_task_type ?? {}).map(([type, value]) => ({ type, value })).sort((a, b) => b.value - a.value);
  const durationByType = Object.entries(patterns?.average_duration_by_task_type ?? {}).map(([type, value]) => ({ type, value })).sort((a, b) => b.value - a.value);

  const context = rec(contextQuery.data?.result) ?? {};
  const memories = recs(get(context, "memory_context.recent_memories"));
  const memoryCount = num(get(context, "memory_context.memory_count"));
  const semantic = recs(context.semantic_matches);

  return (
    <Page wide>
      <PageHeader
        layers="L2 · L3"
        title="Intelligence"
        description="What HELIOX has learned about how you work — behaviour patterns from completed tasks, personalized recommendations, and the memory the assistant draws on."
        actions={
          <Link to="/system">
            <Badge tone="quantum" className="cursor-pointer transition-opacity hover:opacity-80">
              Continuous Learning: Active
            </Badge>
          </Link>
        }
      />

      {patternsQuery.isLoading ? (
        <div className="grid gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}</div>
      ) : patternsQuery.isError ? (
        <ErrorState error={patternsQuery.error} onRetry={() => void patternsQuery.refetch()} />
      ) : !hasData ? (
        <Card className="overflow-hidden">
          <div className="bg-grid">
            <EmptyState
              icon={<BrainCircuit />}
              title="Intelligence unlocks with your first completed task"
              description="Behaviour patterns, focus hours and recommendations are computed only from your real task outcomes — nothing here is simulated. Start and complete a task to begin."
              action={<Link to="/tasks"><Button>Go to tasks</Button></Link>}
            />
          </div>
        </Card>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Tasks analyzed" value={patterns?.tasks_analyzed ?? 0} icon={<Database />} sub="Completed in the last 90 days" />
            <Stat label="Avg productivity" value={num(patterns?.average_productivity)?.toFixed(0) ?? "—"} icon={<Gauge />} accent="primary" sub="Model score, 0–100" />
            <Stat label="Avg focus" value={num(patterns?.average_focus_score)?.toFixed(0) ?? "—"} icon={<Target />} accent="quantum" sub="Derived focus score, 0–100" />
            <Stat label="Avg energy" value={num(patterns?.average_energy_level)?.toFixed(0) ?? "—"} icon={<Flame />} accent="success" sub="Derived energy level, 0–100" />
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr] [&>*]:min-w-0">
            <Card>
              <CardHeader icon={<AlarmClock />} title="Productivity by hour of day" description="Average productivity of completed work, by the hour it started." />
              <CardBody>
                {hourly.length > 1 ? (
                  <AreaLine data={hourly} xKey="hour" yKey="value" name="Productivity" domain={[0, 100]} height={240} />
                ) : hourly.length === 1 ? (
                  <Bars data={hourly} xKey="hour" series={[{ key: "value", name: "Productivity" }]} domain={[0, 100]} height={240} />
                ) : (
                  <EmptyState compact title="Not enough hourly data" />
                )}
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-content-tertiary">
                  Best focus hours:
                  {(patterns?.best_focus_hours ?? []).map((h) => <Badge key={h} tone="primary" className="font-mono">{hourLabel(h)}</Badge>)}
                  {!patterns?.best_focus_hours?.length && <span>—</span>}
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardHeader icon={<Zap />} title="Productivity by task type" description={patterns?.preferred_task_types?.length ? `Preferred: ${patterns.preferred_task_types.join(", ")}` : undefined} />
              <CardBody>
                {byType.length ? <Bars data={byType} xKey="type" layout="vertical" series={[{ key: "value", name: "Productivity" }]} domain={[0, 100]} height={Math.max(140, byType.length * 44)} /> : <EmptyState compact title="No task-type data" />}
                {durationByType.length > 0 && (
                  <div className="mt-4 border-t border-border-subtle pt-3 dark:border-border">
                    <p className="mb-2 text-xs text-content-tertiary">Average duration by type (hours)</p>
                    <ul className="space-y-1">
                      {durationByType.map((d) => (
                        <li key={d.type} className="flex justify-between text-[13px]"><span className="capitalize text-content-secondary">{d.type}</span><span className="tabular font-mono">{d.value.toFixed(2)}h</span></li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader icon={<Lightbulb />} eyebrow="Layer 3 · AI intelligence" title="Personalized recommendations" description="Generated by the recommendation engine from your patterns and open tasks." action={<Button size="sm" variant="ghost" isLoading={recsQuery.isFetching} onClick={() => void recsQuery.refetch()}>Refresh</Button>} />
            <CardBody>
              {recsQuery.isLoading ? (
                <SkeletonRows rows={2} />
              ) : recsQuery.isError ? (
                <ErrorState error={recsQuery.error} onRetry={() => void recsQuery.refetch()} />
              ) : !recsQuery.data ? (
                <EmptyState compact title="No recommendations yet" />
              ) : (
                <div className="space-y-4">
                  {/* Actionable Proposals Section */}
                  {recsQuery.data.actionable_proposals && recsQuery.data.actionable_proposals.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                          Actionable AI Proposals (One-Click Optimization)
                        </span>
                        <Badge tone="primary" className="text-[10px]">
                          {recsQuery.data.actionable_proposals.length} available
                        </Badge>
                      </div>
                      <div className="grid gap-2.5 sm:grid-cols-2">
                        {recsQuery.data.actionable_proposals.map((p) => (
                          <div
                            key={p.proposal_id}
                            className="flex flex-col justify-between rounded-xl border border-primary/20 bg-primary/5 p-3.5 transition-colors hover:border-primary/40"
                          >
                            <div>
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-semibold text-content-primary">{p.title}</span>
                                <Badge tone="primary" className="text-[10px] capitalize">
                                  {p.category.replace("_", " ")}
                                </Badge>
                              </div>
                              <p className="mt-1 text-xs text-content-secondary">{p.reason}</p>
                              <p className="mt-1 text-[11px] font-medium text-primary">{p.impact_summary}</p>
                            </div>
                            <div className="mt-3 flex justify-end">
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => handleApplyProposal(p)}
                                isLoading={applyMutation.isPending}
                              >
                                Apply Action
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Cognitive Budget Banner */}
                  {recsQuery.data.cognitive_budget && (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-subtle bg-surface-2 p-3 text-xs">
                      <div className="flex items-center gap-2">
                        <Zap className="size-4 text-quantum" />
                        <div>
                          <span className="font-semibold text-content-primary">Cognitive Energy Utilization:</span>{" "}
                          <span className="text-content-secondary">
                            {recsQuery.data.cognitive_budget.deep_work_hours}h / {recsQuery.data.cognitive_budget.sustainable_limit_hours}h sustainable limit
                          </span>
                        </div>
                      </div>
                      <Badge
                        tone={
                          recsQuery.data.cognitive_budget.fatigue_risk === "high"
                            ? "error"
                            : recsQuery.data.cognitive_budget.fatigue_risk === "moderate"
                            ? "warning"
                            : "success"
                        }
                        className="capitalize text-[10px]"
                      >
                        Fatigue Risk: {recsQuery.data.cognitive_budget.fatigue_risk}
                      </Badge>
                    </div>
                  )}

                  {/* Grouped Recommendation Signals */}
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    <RecommendationGroup icon={AlarmClock} title="Focus windows" items={recsQuery.data.focus_hours.map((h) => `Protect ${h} for deep work`)} tone="bg-primary/10 text-primary" />
                    <RecommendationGroup icon={ListOrdered} title="Suggested task order" items={recsQuery.data.task_ordering.map((t, i) => `${i + 1}. ${t}`)} tone="bg-quantum/10 text-quantum" />
                    <RecommendationGroup icon={Sparkles} title="Behavioural insights" items={recsQuery.data.behavioral_insights} tone="bg-status-success/10 text-status-success" />
                    <RecommendationGroup icon={Route} title="Schedule improvements" items={recsQuery.data.schedule_improvements} tone="bg-surface-3 text-content-secondary" />
                    <RecommendationGroup icon={Target} title="Goal progress" items={recsQuery.data.goal_progress_alerts} tone="bg-status-warning/10 text-status-warning" />
                  </div>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader icon={<Database />} eyebrow="Layer 2 · Memory & knowledge" title="Assistant memory" description="Interactions stored in vector memory and recalled as planning context." action={memoryCount !== null && <Badge tone="neutral">{memoryCount} memories</Badge>} />
            <CardBody>
              {contextQuery.isLoading ? (
                <SkeletonRows rows={2} />
              ) : contextQuery.isError ? (
                <ErrorState error={contextQuery.error} onRetry={() => void contextQuery.refetch()} />
              ) : memories.length === 0 ? (
                <EmptyState compact title="No memories yet" description="Conversations with JAM are remembered here." />
              ) : (
                <ul className="divide-y divide-border-subtle dark:divide-border">
                  {memories.slice(0, 8).map((m, i) => {
                    const meta = rec(m.metadata) ?? {};
                    return (
                      <motion.li key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }} className="flex items-start justify-between gap-4 py-3">
                        <div className="min-w-0">
                          <p className="line-clamp-2 text-[13px] text-content-primary">{str(m.task_description, "Memory")}</p>
                          <p className="mt-0.5 text-[11px] text-content-tertiary">{humanize(str(meta.event_type))}{str(meta.intent) && ` · ${humanize(str(meta.intent))}`}</p>
                        </div>
                        <span className="shrink-0 text-[11px] text-content-muted">{formatRelative(str(meta.timestamp))}</span>
                      </motion.li>
                    );
                  })}
                </ul>
              )}
              {semantic.length > 0 && <p className="mt-3 text-xs text-content-tertiary">{semantic.length} semantically related memories found for the current context.</p>}
            </CardBody>
          </Card>
        </div>
      )}
    </Page>
  );
}
