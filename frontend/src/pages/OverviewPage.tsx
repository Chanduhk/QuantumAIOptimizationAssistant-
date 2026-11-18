import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Activity, ArrowRight, ArrowUp, CalendarCheck2, CheckCircle2, CircleDot, GraduationCap, Layers, ListChecks, MessageSquareDot, PlayCircle, Plus, Sparkles, Workflow } from "lucide-react";
import type { Task } from "@/api/endpoints";
import { useAcceptPlan, useActivePlan, useComponentInventory, useCurrentUser, useMLReadiness, useProviderStatus, useQuantumStatus, useRejectPlan, useSystemHealth, useTasks } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Page } from "@/components/layout/Page";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge, StatusDot, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/Feedback";
import { Meter } from "@/components/ui/Meter";
import { Stat } from "@/components/ui/Stat";
import { toast } from "@/components/ui/Toaster";
import { LayerMap, type LayerSignal } from "@/components/viz/LayerMap";
import { ScheduleTimeline } from "@/components/viz/ScheduleTimeline";
import { TaskRow } from "@/features/tasks/TaskRow";
import { FeedbackDialog } from "@/features/tasks/FeedbackDialog";
import { durationRatio, hasFeedback, lifecycle } from "@/features/tasks/taskUtils";
import { proposalBlocks } from "@/features/optimization/parse";
import { formatDuration, parseUtcDate } from "@/utils/formatters";
import { formatRelative, greeting } from "@/lib/format";
import { providerState, readinessTone } from "@/lib/status";
import { humanize, recs } from "@/lib/data";
import { cn } from "@/lib/utils";
import { FadeIn, StaggerContainer, StaggerItem, AIActivityIndicator } from "@/components/motion";

function useTaskStats(tasks: Task[]) {
  return React.useMemo(() => {
    const planned = tasks.filter((t) => lifecycle(t) === "created");
    const started = tasks.filter((t) => lifecycle(t) === "started");
    const completed = tasks.filter((t) => lifecycle(t) === "completed");
    const rated = completed.filter(hasFeedback);
    const ratios = completed.map(durationRatio).filter((r): r is number => r !== null);
    const meanRatio = ratios.length ? ratios.reduce((a, b) => a + b, 0) / ratios.length : null;
    return {
      planned,
      started,
      completed,
      rated,
      plannedMinutes: planned.reduce((s, t) => s + (t.estimated_duration ?? 0), 0),
      meanRatio,
    };
  }, [tasks]);
}

function QuickAsk() {
  const navigate = useNavigate();
  const [text, setText] = React.useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) navigate(`/assistant?q=${encodeURIComponent(text.trim())}`);
      }}
      className="flex items-center gap-2 rounded-xl border border-border bg-surface-1 p-1.5 pl-3.5 shadow-card transition-colors focus-within:border-primary/40"
    >
      <Sparkles className="size-4 shrink-0 text-primary" />
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Tell JAM what's on your plate today…"
        aria-label="Ask JAM"
        className="h-8 min-w-0 flex-1 bg-transparent text-sm placeholder:text-content-muted focus:outline-none"
      />
      <Button type="submit" size="icon-sm" disabled={!text.trim()} aria-label="Send to JAM"><ArrowUp /></Button>
    </form>
  );
}

function ActiveProposal() {
  const { data: proposal, isLoading, isError, error, refetch } = useActivePlan();
  const accept = useAcceptPlan();
  const reject = useRejectPlan();
  const blocks = proposalBlocks(proposal?.schedule);

  return (
    <Card hoverLift className="h-full">
      <CardHeader
        icon={<CalendarCheck2 />}
        eyebrow="Layer 9 · Recommendation"
        title="Plan awaiting your decision"
        description={proposal ? proposal.goal_text || "Proposed by JAM" : "Proposals from JAM appear here until you accept or reject them."}
        action={proposal && <Badge tone="primary" dot>v{proposal.version} · {humanize(proposal.status)}</Badge>}
      />
      <CardBody>
        {isLoading ? (
          <SkeletonRows rows={3} />
        ) : isError ? (
          <ErrorState error={error} onRetry={() => void refetch()} />
        ) : !proposal ? (
          <EmptyState
            compact
            icon={<CalendarCheck2 />}
            title="No open proposal"
            description="Describe your day to JAM to get an optimized, explainable schedule."
            action={<Link to="/assistant"><Button size="sm" leftIcon={<Sparkles />}>Plan with JAM</Button></Link>}
          />
        ) : (
          <div className="space-y-4">
            {blocks.length ? <ScheduleTimeline blocks={blocks} /> : <p className="text-[13px] text-content-tertiary">This proposal has no scheduled items.</p>}
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle pt-4 dark:border-border">
              <Link to="/assistant" className="inline-flex items-center gap-1 text-[13px] font-medium text-content-secondary hover:text-content-primary">
                Refine in JAM <ArrowRight className="size-3.5" />
              </Link>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" isLoading={reject.isPending} disabled={accept.isPending}
                  onClick={() => reject.mutate({ proposal_id: proposal.id }, { onSuccess: () => toast("info", "Proposal rejected"), onError: (e) => toast("error", "Couldn't reject", getApiErrorMessage(e)) })}>
                  Reject
                </Button>
                <Button size="sm" isLoading={accept.isPending} disabled={reject.isPending}
                  onClick={() => accept.mutate({ schedule: recs(proposal.schedule), proposal_id: proposal.id, version: proposal.version }, { onSuccess: () => toast("success", "Plan accepted", "Scheduled intervals were saved to your tasks."), onError: (e) => toast("error", "Couldn't accept", getApiErrorMessage(e)) })}>
                  Accept plan
                </Button>
              </div>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

interface ActivityEvent {
  at: number;
  kind: "created" | "started" | "completed" | "rated";
  task: Task;
}

const eventMeta = {
  created: { icon: CircleDot, label: "Captured", cls: "text-content-tertiary" },
  started: { icon: PlayCircle, label: "Started", cls: "text-primary" },
  completed: { icon: CheckCircle2, label: "Completed", cls: "text-status-success" },
  rated: { icon: MessageSquareDot, label: "Rated", cls: "text-quantum" },
} as const;

function RecentActivity({ tasks }: { tasks: Task[] }) {
  const events = React.useMemo(() => {
    const out: ActivityEvent[] = [];
    for (const t of tasks) {
      const push = (value: string | null | undefined, kind: ActivityEvent["kind"]) => {
        const d = parseUtcDate(value);
        if (d) out.push({ at: d.getTime(), kind, task: t });
      };
      push(t.created_at, "created");
      if (t.lifecycle_state !== "created") push(t.start_time, "started");
      if (t.completed) push(t.end_time, "completed");
      push(t.feedback_submitted_at, "rated");
    }
    return out.sort((a, b) => b.at - a.at).slice(0, 7);
  }, [tasks]);

  if (!events.length) return <EmptyState compact icon={<Activity />} title="No activity yet" description="Task lifecycle events will show up here." />;
  return (
    <ol className="relative space-y-3.5 border-l border-border pl-5">
      {events.map((e, i) => {
        const meta = eventMeta[e.kind];
        return (
          <li key={`${e.task.id}-${e.kind}-${i}`} className="relative">
            <span className="absolute -left-[27px] grid size-3.5 place-items-center rounded-full bg-surface-1">
              <meta.icon className={cn("size-3.5", meta.cls)} />
            </span>
            <p className="truncate text-[13px] text-content-primary"><span className="text-content-tertiary">{meta.label}</span> {e.task.title}</p>
            <p className="text-[11px] text-content-muted">{formatRelative(e.at)}</p>
          </li>
        );
      })}
    </ol>
  );
}

export function OverviewPage() {
  const { data: user } = useCurrentUser();
  const tasksQuery = useTasks();
  const tasks = React.useMemo(() => tasksQuery.data?.tasks ?? [], [tasksQuery.data]);
  const stats = useTaskStats(tasks);
  const inventory = useComponentInventory();
  const readiness = useMLReadiness();
  const health = useSystemHealth();
  const quantum = useQuantumStatus();
  const provider = useProviderStatus();
  const [feedbackTask, setFeedbackTask] = React.useState<Task | null>(null);

  const productivity = readiness.data?.components?.ProductivityModel;
  const duration = readiness.data?.components?.DurationRatioModel;
  const rl = readiness.data?.components?.RLScheduler;

  const signals: Partial<Record<number, LayerSignal>> = {
    1: { value: `${stats.planned.length} planned · ${formatDuration(stats.plannedMinutes)}` },
    10: { value: `${stats.started.length} in progress` },
    11: { value: `${stats.completed.length} completed${stats.meanRatio ? ` · ×${stats.meanRatio.toFixed(2)}` : ""}` },
    12: { value: `${stats.rated.length}/${stats.completed.length} rated`, tone: stats.completed.length > stats.rated.length ? "warning" : undefined },
    13: readiness.data ? { value: humanize(readiness.data.overall_status).replace(/^Not ready /, "Gated: ").slice(0, 32), tone: readinessTone(readiness.data.overall_status) === "warning" ? "warning" : undefined } : undefined,
    5: quantum.data ? { value: `≤ ${String(quantum.data.qaoa_config?.max_qubits ?? 8)} qubits` } : undefined,
  };

  const upNext = [...stats.started, ...[...stats.planned].sort((a, b) => b.priority - a.priority)].slice(0, 5);
  const name = user?.email?.split("@")[0];
  const healthy = health.data?.status === "operational" && health.data.database_connected;
  const providerInfo = providerState(provider.data);

  const gates = [
    { label: "Duration model", c: duration },
    { label: "Productivity model", c: productivity },
    { label: "RL scheduler", c: rl },
  ];

  return (
    <Page wide>
      {/* Hero */}
      <FadeIn duration={0.5}>
      <section className="relative mb-8 overflow-hidden rounded-3xl border border-border-subtle bg-surface-1 dark:border-border">
        <div className="bg-grid absolute inset-0 opacity-70 [mask-image:linear-gradient(to_right,black,transparent_70%)]" />
        <div className="pointer-events-none absolute -right-20 -top-28 size-[380px] rounded-full bg-primary/15 blur-3xl dark:bg-primary/10" />
        <div className="pointer-events-none absolute -bottom-40 right-40 size-[300px] rounded-full bg-quantum/10 blur-3xl" />
        <div className="relative grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.4fr_1fr] lg:items-end">
          <div>
            <div className="mb-2 flex items-center gap-2.5">
              <p className="eyebrow">{new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</p>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-1/60 px-2 py-0.5 text-[11px] text-content-tertiary">
                <AIActivityIndicator active={healthy} className="size-2.5" />
                <span>{healthy ? "System operational" : "Checking status"}</span>
              </span>
            </div>
            <motion.h1 initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="text-[28px] font-semibold leading-tight tracking-[-0.02em] sm:text-[34px]">
              {greeting()}{name ? `, ${name}` : ""}.
            </motion.h1>
            <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-content-secondary">
              {tasksQuery.isLoading
                ? "Loading your workspace…"
                : stats.planned.length || stats.started.length
                  ? <>You have <span className="font-medium text-content-primary">{stats.planned.length} planned</span> ({formatDuration(stats.plannedMinutes)}) and <span className="font-medium text-content-primary">{stats.started.length} in progress</span>. {stats.completed.length > stats.rated.length && <>{stats.completed.length - stats.rated.length} finished task{stats.completed.length - stats.rated.length === 1 ? " is" : "s are"} waiting for feedback.</>}</>
                  : "Your slate is clear. Capture tasks or describe your day to JAM to get started."}
            </p>
            <div className="mt-5 max-w-xl"><QuickAsk /></div>
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            <Link to="/optimize" className="group rounded-2xl border border-border bg-surface-1/80 p-4 backdrop-blur transition-all hover:-translate-y-0.5 hover:border-primary/40">
              <Workflow className="size-5 text-primary" />
              <p className="mt-3 text-sm font-medium">Run optimization</p>
              <p className="mt-0.5 text-xs text-content-tertiary">Classical → quantum → executive</p>
            </Link>
            <Link to="/tasks?new=1" className="group rounded-2xl border border-border bg-surface-1/80 p-4 backdrop-blur transition-all hover:-translate-y-0.5 hover:border-quantum/40">
              <Plus className="size-5 text-quantum" />
              <p className="mt-3 text-sm font-medium">Capture a task</p>
              <p className="mt-0.5 text-xs text-content-tertiary">With an explicit estimate</p>
            </Link>
          </div>
        </div>
      </section>
      </FadeIn>

      {/* KPIs */}
      <StaggerContainer stagger={0.08} delay={0.15} className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StaggerItem><Stat label="Planned work" value={stats.planned.length} loading={tasksQuery.isLoading} icon={<ListChecks />} sub={formatDuration(stats.plannedMinutes) + " estimated"} /></StaggerItem>
        <StaggerItem><Stat label="In progress" value={stats.started.length} loading={tasksQuery.isLoading} icon={<PlayCircle />} accent="primary" sub="Executing now" /></StaggerItem>
        <StaggerItem>
        <Stat
          label="Completed"
          value={stats.completed.length}
          loading={tasksQuery.isLoading}
          icon={<CheckCircle2 />}
          accent="success"
          sub={stats.meanRatio ? <>Actual ÷ estimate <span className="tabular font-mono text-content-secondary">×{stats.meanRatio.toFixed(2)}</span></> : "No timed outcomes yet"}
        />
        </StaggerItem>
        <StaggerItem>
        <Stat
          label="Feedback coverage"
          value={stats.completed.length ? `${Math.round((stats.rated.length / stats.completed.length) * 100)}%` : "—"}
          loading={tasksQuery.isLoading}
          icon={<MessageSquareDot />}
          accent="quantum"
          sub={`${stats.rated.length} of ${stats.completed.length} outcomes rated`}
        />
        </StaggerItem>
      </StaggerContainer>

      <FadeIn delay={0.25}>
      <div className="mb-6 grid gap-5 xl:grid-cols-[1.35fr_1fr] [&>*]:min-w-0">
        <ActiveProposal />
        <Card hoverLift className="h-full">
          <CardHeader icon={<ListChecks />} title="Up next" description="In-progress work first, then highest priority." action={<Link to="/tasks" className="text-xs font-medium text-content-tertiary hover:text-content-primary">All tasks</Link>} />
          <CardBody>
            {tasksQuery.isLoading ? (
              <SkeletonRows rows={3} />
            ) : tasksQuery.isError ? (
              <ErrorState error={tasksQuery.error} onRetry={() => void tasksQuery.refetch()} />
            ) : upNext.length === 0 ? (
              <EmptyState compact icon={<ListChecks />} title="Nothing queued" action={<Link to="/tasks?new=1"><Button size="sm" variant="secondary" leftIcon={<Plus />}>New task</Button></Link>} />
            ) : (
              <ul className="space-y-2">
                {upNext.map((t) => <TaskRow key={t.id} task={t} compact onRequestFeedback={setFeedbackTask} />)}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
      </FadeIn>

      {/* Architecture */}
      <FadeIn delay={0.35}>
      <Card className="mb-6">
        <CardHeader
          icon={<Layers />}
          title="Architecture, live"
          description="The 13 layers HELIOX runs on, with component health from the system inventory and signals from your own data."
          action={<Link to="/system" className="text-xs font-medium text-content-tertiary hover:text-content-primary">Inventory</Link>}
        />
        <CardBody>
          {inventory.isError ? (
            <ErrorState error={inventory.error} onRetry={() => void inventory.refetch()} />
          ) : (
            <LayerMap components={inventory.data?.components ?? []} loading={inventory.isLoading} signals={signals} />
          )}
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-content-tertiary">
            <span className="inline-flex items-center gap-1.5"><StatusDot tone="success" />Operational</span>
            <span className="inline-flex items-center gap-1.5"><StatusDot tone="warning" />Running on a documented fallback</span>
            <span className="inline-flex items-center gap-1.5"><StatusDot tone="error" />Unavailable</span>
          </div>
        </CardBody>
      </Card>
      </FadeIn>

      <StaggerContainer stagger={0.1} delay={0.4} className="grid gap-5 lg:grid-cols-3">
        <StaggerItem>
        <Card hoverLift>
          <CardHeader icon={<GraduationCap />} title="Learning readiness" description="Personal models unlock as real outcomes accumulate." action={<Link to="/system" className="text-xs font-medium text-content-tertiary hover:text-content-primary">Details</Link>} />
          <CardBody>
            {readiness.isLoading ? (
              <SkeletonRows rows={3} />
            ) : readiness.isError ? (
              <ErrorState error={readiness.error} onRetry={() => void readiness.refetch()} />
            ) : (
              <ul className="space-y-4">
                {gates.map(({ label, c }) => (
                  <li key={label}>
                    <div className="mb-1.5 flex items-baseline justify-between text-xs">
                      <span className="text-content-secondary">{label}</span>
                      <span className="tabular font-mono text-content-primary">{c?.eligible_samples ?? 0}<span className="text-content-muted"> / {c?.required_samples ?? "—"}</span></span>
                    </div>
                    <Meter value={c?.eligible_samples ?? 0} max={c?.required_samples || 1} tone={readinessTone(c?.status) === "success" ? "success" : "primary"} label={`${label} samples`} />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
        </StaggerItem>

        <StaggerItem>
        <Card hoverLift>
          <CardHeader icon={<Activity />} title="Recent activity" />
          <CardBody>
            {tasksQuery.isLoading ? <SkeletonRows rows={3} /> : <RecentActivity tasks={tasks} />}
          </CardBody>
        </Card>
        </StaggerItem>

        <StaggerItem>
        <Card hoverLift>
          <CardHeader icon={<CircleDot />} title="System pulse" action={<Link to="/system" className="text-xs font-medium text-content-tertiary hover:text-content-primary">Status</Link>} />
          <CardBody>
            <ul className="divide-y divide-border-subtle text-[13px] dark:divide-border">
              {([
                { label: "API & database", ok: healthy, value: health.isError ? "Offline" : health.isLoading ? "Checking…" : healthy ? "Operational" : "Degraded", tone: health.isError ? "error" : healthy ? "success" : "warning" },
                { label: "Language parser", ok: true, value: providerInfo.short, tone: providerInfo.tone },
                { label: "Quantum simulator", ok: quantum.data?.available, value: quantum.isLoading ? "Checking…" : quantum.data?.available ? "Local, available" : "Unavailable", tone: quantum.data?.available ? "quantum" : "warning" },
                { label: "Components", ok: true, value: inventory.data ? `${inventory.data.components.filter((c) => c.can_execute_now).length}/${inventory.data.total_components} executable` : "Checking…", tone: "neutral" },
              ] satisfies Array<{ label: string; ok: unknown; value: string; tone: BadgeTone }>).map((row) => (
                <li key={row.label} className="flex items-center justify-between gap-3 py-2.5">
                  <span className="text-content-secondary">{row.label}</span>
                  <Badge tone={row.tone} dot>{row.value}</Badge>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
        </StaggerItem>
      </StaggerContainer>

      <FeedbackDialog task={feedbackTask} isOpen={feedbackTask !== null} onClose={() => setFeedbackTask(null)} />
    </Page>
  );
}
