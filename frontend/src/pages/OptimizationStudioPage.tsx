import * as React from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Atom, CalendarClock, ChevronDown, CircleCheck, GitCompareArrows, Layers3, ListChecks, Network, Play, Plus, Scale, Sparkles, Telescope } from "lucide-react";
import type { Task } from "@/api/endpoints";
import { Page, PageHeader } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, KeyValue } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Field";
import { Callout, EmptyState, ErrorState, SkeletonRows } from "@/components/ui/Feedback";
import { Meter, Ring, scoreTone } from "@/components/ui/Meter";
import { PipelineRail, type PipelineStage } from "@/components/viz/PipelineRail";
import { ScheduleTimeline } from "@/components/viz/ScheduleTimeline";
import { Bars } from "@/components/viz/Charts";
import { useOptimization } from "@/features/optimization/useOptimization";
import { parseExecutive, type ExecutiveView } from "@/features/optimization/parse";
import { ineligibilityReason, priorityMeta } from "@/features/tasks/taskUtils";
import { formatDuration } from "@/utils/formatters";
import { formatPct, formatRelative } from "@/lib/format";
import { humanize, num, str, strs, toPercent } from "@/lib/data";
import { readinessTone } from "@/lib/status";
import { cn } from "@/lib/utils";

function stagesFor(view: ExecutiveView | null, running: boolean): PipelineStage[] {
  const base: Array<Omit<PipelineStage, "state" | "value">> = [
    { id: "classical", layer: "L4", label: "Classical optimization" },
    { id: "suitability", layer: "L5", label: "Quantum suitability" },
    { id: "quantum", layer: "L6", label: "Quantum candidate" },
    { id: "hybrid", layer: "L7", label: "Hybrid comparison" },
    { id: "executive", layer: "L8", label: "Executive decision" },
    { id: "recommend", layer: "L9", label: "Recommendation" },
  ];
  if (running) return base.map((s, i) => ({ ...s, state: i === 0 ? "running" : "pending" }));
  if (!view?.hasResult) return base.map((s) => ({ ...s, state: "pending" }));
  const o = view.optimization;
  const suitability = str(o.suitability.status);
  const candidate = str(o.candidate.status);
  const hybrid = str(o.hybrid.status);
  const stateOf = (status: string): PipelineStage["state"] =>
    !status ? "pending" : /NOT_SUPPORTED|NOT_SUITABLE|SKIPPED/.test(status) ? "skipped" : /NOT_READY|INVALID|NOT_COMPARABLE/.test(status) ? "blocked" : "done";
  const quantumProduced = stateOf(candidate) === "done";
  return [
    { ...base[0], state: view.candidatePlanCount > 0 ? "done" : "blocked", value: `${view.candidatePlanCount} candidate plans · matrix ${humanize(o.matrixStatus).toLowerCase()}` },
    { ...base[1], state: stateOf(suitability), value: humanize(suitability) },
    { ...base[2], state: stateOf(candidate), value: humanize(candidate) },
    { ...base[3], state: quantumProduced ? stateOf(hybrid) : "skipped", value: quantumProduced ? humanize(str(o.hybrid.objective_relation) || hybrid) : "No quantum candidate to compare" },
    { ...base[4], state: view.confidence !== null ? "done" : "pending", value: view.confidence !== null ? `${view.confidence.toFixed(1)}% confidence` : undefined },
    { ...base[5], state: view.recommended.title ? "done" : "pending", value: view.recommended.title || undefined },
  ];
}

function TaskSelector({ eligible, ineligible, selected, toggle, setAll }: {
  eligible: Task[];
  ineligible: Task[];
  selected: Set<number>;
  toggle: (id: number) => void;
  setAll: (on: boolean) => void;
}) {
  const [showIneligible, setShowIneligible] = React.useState(false);
  const totalMinutes = eligible.filter((t) => selected.has(t.id)).reduce((sum, t) => sum + (t.estimated_duration ?? 0), 0);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-content-tertiary">
        <span>{selected.size} of {eligible.length} selected · {formatDuration(totalMinutes)}</span>
        <button type="button" className="font-medium text-content-secondary hover:text-content-primary" onClick={() => setAll(selected.size !== eligible.length)}>
          {selected.size === eligible.length ? "Clear" : "Select all"}
        </button>
      </div>
      <ul className="scrollbar-thin max-h-[320px] space-y-1 overflow-y-auto pr-1">
        {eligible.map((task) => {
          const on = selected.has(task.id);
          const p = priorityMeta(task.priority);
          return (
            <li key={task.id}>
              <label className={cn("flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 transition-colors", on ? "border-primary/30 bg-primary/[0.06]" : "border-transparent hover:bg-surface-2")}>
                <input type="checkbox" checked={on} onChange={() => toggle(task.id)} className="size-4 accent-[hsl(var(--primary))]" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-content-primary">{task.title}</span>
                  <span className="text-[11px] text-content-tertiary"><span className="capitalize">{task.task_type}</span> · {formatDuration(task.estimated_duration)}</span>
                </span>
                <Badge tone={p.tone} className="font-mono">P{task.priority}</Badge>
              </label>
            </li>
          );
        })}
      </ul>
      {ineligible.length > 0 && (
        <div className="mt-3 border-t border-border-subtle pt-3 dark:border-border">
          <button type="button" onClick={() => setShowIneligible((v) => !v)} className="flex w-full items-center justify-between text-xs text-content-tertiary hover:text-content-secondary">
            <span>{ineligible.length} open task{ineligible.length === 1 ? "" : "s"} not eligible</span>
            <ChevronDown className={cn("size-3.5 transition-transform", showIneligible && "rotate-180")} />
          </button>
          {showIneligible && (
            <ul className="mt-2 space-y-1">
              {ineligible.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-2 rounded-md px-2 py-1 text-xs">
                  <span className="truncate text-content-secondary">{t.title}</span>
                  <span className="shrink-0 text-content-muted">{ineligibilityReason(t)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function SuitabilityCard({ view }: { view: ExecutiveView }) {
  const s = view.optimization.suitability;
  const c = view.optimization.candidate;
  const variables = num(s.variable_count);
  const limit = 8;
  const status = str(s.status);
  const reasons = strs(s.reasons);
  return (
    <Card className="h-full">
      <CardHeader
        icon={<Atom />}
        eyebrow="Layers 5 – 6"
        title="Quantum suitability"
        description="QAOA runs only when the QUBO fits the local simulator."
        action={<Badge tone={readinessTone(status)} dot>{humanize(status)}</Badge>}
      />
      <CardBody className="space-y-4">
        {variables !== null && (
          <div>
            <div className="mb-1.5 flex items-baseline justify-between text-xs">
              <span className="text-content-tertiary">Binary variables (tasks × candidate hours)</span>
              <span className="tabular font-mono text-content-primary">{variables} <span className="text-content-muted">/ {limit} qubit limit</span></span>
            </div>
            <Meter value={Math.min(variables, limit)} max={limit} tone={variables > limit ? "warning" : "quantum"} label="Variables against qubit limit" />
          </div>
        )}
        <dl className="grid grid-cols-3 gap-3">
          <KeyValue label="Tasks" value={str(s.task_count, "—")} mono />
          <KeyValue label="Hours" value={str(s.candidate_hour_count, "—")} mono />
          <KeyValue label="Constraints" value={str(s.constraint_count, "—")} mono />
        </dl>
        {reasons.length > 0 && (
          <ul className="space-y-1 text-[13px] text-content-secondary">
            {reasons.map((r) => <li key={r} className="flex gap-2"><span className="mt-2 size-1 shrink-0 rounded-full bg-content-muted" />{r}</li>)}
          </ul>
        )}
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="outline">Candidate: {humanize(str(c.status))}</Badge>
          <Badge tone="outline">Physical hardware: {s.physical_hardware ? "yes" : "no"}</Badge>
          <Badge tone="outline">Advantage claimed: {s.quantum_advantage_claimed ? "yes" : "no"}</Badge>
        </div>
        <Link to="/quantum" className="inline-flex items-center gap-1 text-[13px] font-medium text-quantum hover:underline">
          Open Quantum Lab <ArrowRight className="size-3.5" />
        </Link>
      </CardBody>
    </Card>
  );
}

function HybridCard({ view }: { view: ExecutiveView }) {
  const h = view.optimization.hybrid;
  const classical = h.classical as Record<string, unknown> | null;
  const quantum = h.quantum as Record<string, unknown> | null;
  const candidateStatus = str(view.optimization.candidate.status);
  // Without a quantum candidate there is nothing to compare: that's a skip, not a failure.
  const skipped = !quantum && !/SUCCESS|COMPLETE|READY$/.test(candidateStatus);
  return (
    <Card className="h-full">
      <CardHeader
        icon={<GitCompareArrows />}
        eyebrow="Layer 7"
        title="Hybrid comparison"
        description="Classical and quantum candidates are compared on the same objective."
        action={<Badge tone={skipped ? "neutral" : readinessTone(str(h.status))} dot title={humanize(str(h.status))}>{skipped ? "Skipped" : humanize(str(h.status))}</Badge>}
      />
      <CardBody className="space-y-4">
        {skipped && <p className="text-[13px] text-content-secondary">The quantum stage didn't produce a candidate ({humanize(candidateStatus).toLowerCase()}), so the classical plan stands without a hybrid comparison.</p>}
        <dl className="grid grid-cols-2 gap-3">
          <KeyValue label="Objective relation" value={humanize(str(h.objective_relation))} />
          <KeyValue label="Quantum auto-preferred" value={h.quantum_preferred_automatically ? "Yes" : "No"} />
          <KeyValue label="Classical objective" value={classical ? str(classical.objective_value ?? classical.objective, "Available") : "Not produced"} mono />
          <KeyValue label="Quantum objective" value={quantum ? str(quantum.objective_value ?? quantum.objective, "Available") : "Not produced"} mono />
        </dl>
        {strs(h.reasons).map((r) => (
          <p key={r} className="rounded-lg bg-surface-2 px-3 py-2 text-[13px] text-content-secondary">{r}</p>
        ))}
        <p className="text-xs text-content-tertiary">Objective source: {str(h.objective_source, "—")}</p>
      </CardBody>
    </Card>
  );
}

function DecisionCard({ view }: { view: ExecutiveView }) {
  const conf = view.confidence;
  const riskLevel = str(view.risk.executive_risk_level) || str(view.risk.risk_level);
  return (
    <Card className="relative overflow-hidden">
      <div className="pointer-events-none absolute -right-24 -top-24 size-64 rounded-full bg-primary/10 blur-3xl" />
      <CardBody className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
        <Ring value={conf ?? 0} size={92} stroke={7} tone={scoreTone(conf)} label="Executive confidence">
          <div className="text-center">
            <p className="tabular text-lg font-semibold leading-none">{conf !== null ? conf.toFixed(0) : "—"}<span className="text-xs text-content-tertiary">%</span></p>
            <p className="mt-0.5 text-[10px] text-content-muted">confidence</p>
          </div>
        </Ring>
        <div className="min-w-0 flex-1">
          <p className="eyebrow mb-1">Layer 8 · Executive decision</p>
          <h2 className="text-lg font-semibold tracking-tight">{view.reasoning.action || view.recommended.executiveRecommendation || "Decision pending"}</h2>
          <p className="mt-1 text-[13px] leading-relaxed text-content-secondary">{view.reasoning.why || view.summary}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {riskLevel && <Badge tone={riskLevel === "low" ? "success" : riskLevel === "medium" ? "warning" : "error"} dot>Risk {riskLevel}</Badge>}
            {view.recommended.title && <Badge tone="primary">Selected: {view.recommended.title}</Badge>}
            {num(view.risk.conflict_count) !== null && <Badge tone="neutral">{str(view.risk.conflict_count)} evidence conflicts resolved</Badge>}
            {view.optimization.authority && <Badge tone="outline">{view.optimization.authority}</Badge>}
          </div>
        </div>
        <Link to="/brain" className="shrink-0">
          <Button variant="secondary" rightIcon={<ArrowRight />}>Full reasoning</Button>
        </Link>
      </CardBody>
    </Card>
  );
}

function Results({ view }: { view: ExecutiveView }) {
  const navigate = useNavigate();
  const evalData = view.evaluations.map((e) => ({ name: e.title, overall: e.overall ?? 0, utility: e.utility ?? 0, recommended: e.recommended }));
  return (
    <div className="space-y-5">
      <DecisionCard view={view} />

      <div className="grid gap-5 2xl:grid-cols-[1.45fr_1fr] [&>*]:min-w-0">
        <Card>
          <CardHeader
            icon={<CalendarClock />}
            eyebrow="Layer 9 · Recommendation"
            title="Recommended daily schedule"
            description="Each task is placed near a predicted focus hour. Rows are independent so overlaps stay visible."
            action={<Badge tone="neutral">{view.schedule.length} tasks</Badge>}
          />
          <CardBody>
            {view.schedule.length ? (
              <ScheduleTimeline blocks={view.schedule} focusHours={view.focusHours} />
            ) : (
              <EmptyState compact title="No hour-level schedule in this result" description="The daily plan candidate did not include recommended hours." />
            )}
            <Callout tone="neutral" className="mt-4" title="Commit a schedule" action={
              <Button size="sm" variant="secondary" leftIcon={<Sparkles />} onClick={() => navigate(`/assistant?q=${encodeURIComponent("Use my existing tasks and goals. Plan my day.")}`)}>
                Plan with JAM
              </Button>
            }>
              This pipeline run is advisory and isn't saved as a proposal. To write intervals to your tasks, have JAM build a versioned plan proposal and accept it.
            </Callout>
          </CardBody>
        </Card>

        <Card>
          <CardHeader icon={<Scale />} eyebrow="Layer 4 · Candidates" title="Candidate plan scores" description={view.recommended.reasoning || "Overall decision score per candidate plan."} />
          <CardBody>
            {evalData.length ? (
              <>
                <Bars data={evalData} xKey="name" series={[{ key: "overall", name: "Overall score" }]} highlightKey="recommended" domain={[0, 100]} height={200} />
                <ul className="mt-3 divide-y divide-border-subtle dark:divide-border">
                  {[...view.evaluations].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99)).map((e) => (
                    <li key={e.id} className="flex items-center justify-between gap-3 py-2 text-[13px]">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="tabular w-5 font-mono text-xs text-content-muted">#{e.rank ?? "–"}</span>
                        <span className="truncate text-content-primary">{e.title}</span>
                        {e.recommended && <CircleCheck className="size-3.5 shrink-0 text-status-success" aria-label="Recommended" />}
                      </span>
                      <span className="tabular shrink-0 font-mono text-xs text-content-tertiary">
                        risk {e.risk?.toFixed(0) ?? "—"} · conf {e.confidence?.toFixed(0) ?? "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <EmptyState compact title="No candidate evaluations returned" />
            )}
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <SuitabilityCard view={view} />
        <HybridCard view={view} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<Telescope />} eyebrow="Future simulation" title="Projected outcome" description={str(view.rankedFuture.selected_scenario_name) ? `Scenario: ${str(view.rankedFuture.selected_scenario_name)}` : "Baseline scenario"} />
          <CardBody className="space-y-4">
            <dl className="grid grid-cols-3 gap-3">
              <KeyValue label="Success probability" value={formatPct(toPercent(view.simulation.success_probability), 1)} mono />
              <KeyValue label="Projected days" value={str((view.simulation.projected_state as Record<string, unknown> | undefined)?.projected_completion_days, "—")} mono />
              <KeyValue label="Future score" value={num(view.rankedFuture.overall_score)?.toFixed(1) ?? "—"} mono />
            </dl>
            <ul className="space-y-2.5">
              {view.objectiveScores.map((o) => (
                <li key={o.name}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-content-secondary">{o.name}{o.weight !== null && <span className="text-content-muted"> · weight {o.weight}</span>}</span>
                    <span className="tabular font-mono text-content-primary">{o.value.toFixed(1)}</span>
                  </div>
                  <Meter value={o.value} tone={scoreTone(o.value)} label={o.name} />
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>

        <Card>
          <CardHeader icon={<Network />} eyebrow="Dependencies" title="Execution order & critical path" description="From the dependency intelligence engine." />
          <CardBody className="space-y-4">
            <div>
              <p className="mb-2 text-xs text-content-tertiary">Execution order</p>
              <ol className="flex flex-wrap items-center gap-1.5">
                {strs(view.dependency.execution_order).map((id, i, arr) => {
                  const title = view.schedule.find((b) => b.key.startsWith(`${id}-`))?.title;
                  return (
                    <React.Fragment key={id}>
                      <li className="rounded-md border border-border bg-surface-2 px-2 py-1 text-xs text-content-primary">{title ?? `Task ${id}`}</li>
                      {i < arr.length - 1 && <ArrowRight className="size-3 text-content-muted" />}
                    </React.Fragment>
                  );
                })}
              </ol>
            </div>
            <dl className="grid grid-cols-3 gap-3">
              <KeyValue label="Critical path" value={str(view.dependency.critical_path_length, "—")} mono />
              <KeyValue label="Blocked" value={String(strs(view.dependency.blocked_tasks).length)} mono />
              <KeyValue label="Cycles" value={String((view.dependency.cycles as unknown[] | undefined)?.length ?? 0)} mono />
            </dl>
            <p className="text-xs text-content-tertiary">Task dependencies aren't editable through the current API, so tasks are treated as independent unless the planner infers otherwise.</p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

export function OptimizationStudioPage() {
  const { tasksQuery, eligible, ineligible, run, isRunning, error, result, ranAt } = useOptimization();
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [query, setQuery] = React.useState("");
  const initialized = React.useRef(false);

  React.useEffect(() => {
    if (!initialized.current && eligible.length) {
      setSelected(new Set(eligible.map((t) => t.id)));
      initialized.current = true;
    }
  }, [eligible]);

  const view = React.useMemo(() => (result ? parseExecutive(result) : null), [result]);
  const stages = stagesFor(view, isRunning);
  const selectedTasks = eligible.filter((t) => selected.has(t.id));

  const toggle = (id: number) => setSelected((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  return (
    <Page wide>
      <PageHeader
        layers="L4 – L9"
        title="Optimization Studio"
        description="Send your eligible tasks through classical optimization, quantum suitability, QAOA, hybrid comparison and the Executive Cognitive Brain — and see exactly why the final plan was chosen."
        actions={ranAt && <span className="text-xs text-content-tertiary">Last run {formatRelative(ranAt)}</span>}
      />

      <Card className="mb-5">
        <CardBody>
          <PipelineRail stages={stages} />
        </CardBody>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[340px_1fr] [&>*]:min-w-0">
        <div className="space-y-5 lg:sticky lg:top-20 lg:self-start">
          <Card>
            <CardHeader icon={<Layers3 />} eyebrow="Layer 1 input" title="Optimization input" description="Planned tasks with explicit minute estimates." />
            <CardBody>
              {tasksQuery.isLoading ? (
                <SkeletonRows rows={4} />
              ) : tasksQuery.isError ? (
                <ErrorState error={tasksQuery.error} onRetry={() => void tasksQuery.refetch()} />
              ) : eligible.length === 0 ? (
                <EmptyState
                  compact
                  icon={<ListChecks />}
                  title="No eligible tasks"
                  description="Create planned tasks with a minute estimate to optimize them."
                  action={<Link to="/tasks?new=1"><Button size="sm" leftIcon={<Plus />}>New task</Button></Link>}
                />
              ) : (
                <TaskSelector
                  eligible={eligible}
                  ineligible={ineligible}
                  selected={selected}
                  toggle={toggle}
                  setAll={(on) => setSelected(on ? new Set(eligible.map((t) => t.id)) : new Set())}
                />
              )}
              <div className="mt-4 space-y-2">
                <label htmlFor="opt-query" className="text-xs font-medium text-content-secondary">Context for the planner <span className="font-normal text-content-muted">(optional)</span></label>
                <Input id="opt-query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Protect the morning for deep work" />
              </div>
              <Button className="mt-4 w-full" size="lg" leftIcon={<Play />} isLoading={isRunning} disabled={selectedTasks.length === 0} onClick={() => run(selectedTasks, query)}>
                {isRunning ? "Running pipeline…" : result ? "Re-run pipeline" : "Run pipeline"}
              </Button>
            </CardBody>
          </Card>
        </div>

        <div className="min-w-0">
          {error && <ErrorState className="mb-5" error={error} title="The optimization pipeline failed" onRetry={() => run(selectedTasks, query)} />}
          {isRunning && !view ? (
            <Card>
              <CardBody className="space-y-4">
                <div className="flex items-center gap-3 text-sm text-content-secondary">
                  <span className="size-2 animate-pulse rounded-full bg-primary" />
                  Evaluating {selectedTasks.length} tasks across 13 layers…
                </div>
                <SkeletonRows rows={4} />
              </CardBody>
            </Card>
          ) : view ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: isRunning ? 0.5 : 1 }}>
              <Results view={view} />
            </motion.div>
          ) : (
            <Card className="overflow-hidden">
              <div className="bg-grid relative px-6 py-16 text-center">
                <div className="mx-auto mb-5 grid size-14 place-items-center rounded-2xl border border-border bg-surface-1 text-primary shadow-card">
                  <Scale className="size-6" />
                </div>
                <h2 className="text-lg font-semibold">Ready when you are</h2>
                <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-content-tertiary">
                  Choose the tasks to optimize and run the pipeline. Classical optimization always runs; quantum simulation is attempted only when the problem fits — and the executive brain decides.
                </p>
                <div className="mx-auto mt-6 grid max-w-lg grid-cols-3 gap-3 text-left">
                  {[
                    ["Classical", "Constraint-aware scheduling"],
                    ["Quantum-aware", "QUBO → Ising → QAOA"],
                    ["Explained", "Evidence, risk, trade-offs"],
                  ].map(([t, d]) => (
                    <div key={t} className="rounded-xl border border-border bg-surface-1 p-3">
                      <p className="text-[13px] font-medium">{t}</p>
                      <p className="mt-0.5 text-[11px] text-content-tertiary">{d}</p>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </Page>
  );
}
