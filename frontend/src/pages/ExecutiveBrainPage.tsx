import * as React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { AlertOctagon, ArrowRight, BatteryMedium, BrainCircuit, Gavel, GitMerge, Lightbulb, Network, Play, Scale, Shield, Swords, Workflow } from "lucide-react";
import { Page, PageHeader, SectionTitle } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, KeyValue } from "@/components/ui/Card";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout, EmptyState, ErrorState } from "@/components/ui/Feedback";
import { Meter, Ring, scoreTone } from "@/components/ui/Meter";
import { Segmented } from "@/components/ui/Tabs";
import { useOptimization } from "@/features/optimization/useOptimization";
import { parseExecutive, type ExecutiveView } from "@/features/optimization/parse";
import { formatRelative } from "@/lib/format";
import { humanize, num, str, toPercent, type Rec } from "@/lib/data";
import { cn } from "@/lib/utils";

function severityTone(severity: string): BadgeTone {
  const s = severity.toLowerCase();
  if (s === "critical" || s === "high") return "error";
  if (s === "medium" || s === "warning" || s === "moderate") return "warning";
  return "neutral";
}

function MetricGrid({ metrics, invert = [] }: { metrics: Rec; invert?: string[] }) {
  const entries = Object.entries(metrics).filter(([, v]) => num(v) !== null);
  if (!entries.length) return <p className="text-[13px] text-content-tertiary">No metrics returned.</p>;
  return (
    <ul className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {entries.map(([key, value]) => {
        const v = num(value) as number;
        const inverted = invert.includes(key);
        return (
          <li key={key}>
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-content-secondary">{humanize(key)}{inverted && <span className="text-content-muted"> (lower is better)</span>}</span>
              <span className="tabular font-mono text-content-primary">{v.toFixed(1)}</span>
            </div>
            <Meter value={v} tone={scoreTone(v, inverted)} label={humanize(key)} />
          </li>
        );
      })}
    </ul>
  );
}

function ActionList({ items, titleKey, bodyKey, metaKey, severityKey, empty }: { items: Rec[]; titleKey: string; bodyKey?: string; metaKey?: string; severityKey?: string; empty: string }) {
  if (!items.length) return <p className="text-[13px] text-content-tertiary">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((item, i) => {
        const severity = severityKey ? str(item[severityKey]) : "";
        return (
          <li key={i} className="rounded-xl border border-border-subtle bg-surface-2/40 px-3.5 py-2.5 dark:border-border">
            <div className="flex items-start justify-between gap-3">
              <p className="text-[13px] font-medium capitalize text-content-primary">{str(item[titleKey])}</p>
              {severity && <Badge tone={severityTone(severity)}>{severity}</Badge>}
              {!severity && metaKey && num(item[metaKey]) !== null && <span className="tabular shrink-0 font-mono text-xs text-content-tertiary">{num(item[metaKey])?.toFixed(0)}</span>}
            </div>
            {bodyKey && str(item[bodyKey]) && <p className="mt-0.5 text-xs leading-relaxed text-content-tertiary">{str(item[bodyKey])}</p>}
          </li>
        );
      })}
    </ul>
  );
}

function ReasoningTab({ view }: { view: ExecutiveView }) {
  const maxScore = Math.max(100, ...view.trace.evidence.map((e) => num(e.score) ?? 0));
  return (
    <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr] [&>*]:min-w-0">
      <Card>
        <CardHeader icon={<Workflow />} title="Evidence sources" description="Every engine that contributed, its score and confidence." action={<Badge tone="neutral">{view.trace.evidence.length} sources</Badge>} />
        <CardBody>
          <ul className="divide-y divide-border-subtle dark:divide-border">
            {view.trace.evidence.map((e, i) => {
              const score = num(e.score) ?? 0;
              const confidence = toPercent(e.confidence);
              const selected = str(e.recommendation) === view.reasoning.action;
              return (
                <motion.li key={i} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }} className="py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 text-[13px] font-medium text-content-primary">
                        {str(e.source).replace(/([a-z])([A-Z])/g, "$1 $2")}
                        {selected && <Badge tone="success">Selected</Badge>}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-content-tertiary">{str(e.recommendation)}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="tabular font-mono text-sm text-content-primary">{score.toFixed(1)}</p>
                      <p className="tabular text-[11px] text-content-muted">{confidence !== null ? `${confidence.toFixed(0)}% conf.` : ""}</p>
                    </div>
                  </div>
                  <Meter className="mt-2" value={score} max={maxScore} tone={selected ? "primary" : "quantum"} label={`${str(e.source)} score`} />
                </motion.li>
              );
            })}
          </ul>
        </CardBody>
      </Card>

      <div className="space-y-5">
        <Card>
          <CardHeader icon={<Lightbulb />} title="Reasoning steps" />
          <CardBody>
            <ol className="relative space-y-3 border-l border-border pl-5">
              {view.trace.steps.map((step, i) => (
                <li key={i} className="relative text-[13px] leading-relaxed text-content-secondary">
                  <span className="absolute -left-[25px] top-1 grid size-2.5 place-items-center rounded-full border-2 border-surface-1 bg-primary" />
                  {step}
                </li>
              ))}
            </ol>
          </CardBody>
        </Card>
        <Card>
          <CardHeader icon={<GitMerge />} title="Alternatives considered" description="Runner-up recommendations and why they lost." />
          <CardBody>
            <ul className="space-y-2">
              {view.trace.rejected.map((alt, i) => (
                <li key={i} className="flex items-center justify-between gap-3 text-[13px]">
                  <span className="min-w-0">
                    <span className="block truncate text-content-primary">{str(alt.recommendation)}</span>
                    <span className="block truncate text-xs text-content-tertiary">{str(alt.source)} · {str(alt.why_rejected)}</span>
                  </span>
                  <span className="tabular shrink-0 font-mono text-xs text-content-tertiary">−{num(alt.score_gap)?.toFixed(1)}</span>
                </li>
              ))}
              {!view.trace.rejected.length && <p className="text-[13px] text-content-tertiary">No alternatives were recorded.</p>}
            </ul>
          </CardBody>
        </Card>
      </div>

      <Card className="xl:col-span-2">
        <CardHeader icon={<Swords />} title="Evidence conflicts" description="Where engines disagreed and how the brain resolved it." action={<Badge tone="neutral">{view.trace.conflicts.length}</Badge>} />
        <CardBody>
          <div className="grid gap-2 md:grid-cols-2">
            {view.trace.conflicts.map((c, i) => {
              const severity = num(c.severity) ?? 0;
              return (
                <div key={i} className="rounded-xl border border-border-subtle p-3 dark:border-border">
                  <div className="flex items-center justify-between gap-2 text-[13px]">
                    <span className="truncate font-medium text-content-primary">{str(c.source_a).replace(/Engine$/, "")} <span className="text-content-muted">vs</span> {str(c.source_b).replace(/Engine$/, "")}</span>
                    <span className="tabular shrink-0 font-mono text-xs text-content-tertiary">{severity.toFixed(0)}</span>
                  </div>
                  <Meter className="my-2" value={severity} tone={severity > 70 ? "error" : severity > 40 ? "warning" : "neutral"} label="Conflict severity" />
                  <p className="text-xs text-content-tertiary">{str(c.conflict_reason)} <span className="text-content-secondary">→ {str(c.resolution_strategy)}</span></p>
                </div>
              );
            })}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function TradeoffsTab({ view }: { view: ExecutiveView }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="lg:col-span-2">
        <CardHeader icon={<Scale />} title="Executive trade-offs" description="Benefit gained against cost incurred, per decision dimension." />
        <CardBody>
          <ul className="space-y-4">
            {view.trace.tradeoffs.map((t, i) => {
              const benefit = num(t.benefit) ?? 0;
              const cost = num(t.cost) ?? 0;
              return (
                <li key={i} className="grid items-center gap-3 sm:grid-cols-[180px_1fr]">
                  <div>
                    <p className="text-[13px] font-medium capitalize text-content-primary">{humanize(str(t.category))}</p>
                    <p className="text-[11px] text-content-tertiary">{str(t.explanation)}</p>
                  </div>
                  <div className="grid grid-cols-2 items-center gap-1">
                    <div className="flex justify-end">
                      <div className="flex h-5 w-full items-center justify-end">
                        <span className="tabular mr-2 font-mono text-[11px] text-content-tertiary">{cost.toFixed(0)}</span>
                        <motion.div initial={{ width: 0 }} animate={{ width: `${cost}%` }} className="h-3 rounded-l-[4px] bg-status-warning/70" />
                      </div>
                    </div>
                    <div className="flex h-5 items-center border-l border-content-muted/40">
                      <motion.div initial={{ width: 0 }} animate={{ width: `${benefit}%` }} className="h-3 rounded-r-[4px] bg-status-success/70" />
                      <span className="tabular ml-2 font-mono text-[11px] text-content-tertiary">{benefit.toFixed(0)}</span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="mt-4 flex gap-4 text-[11px] text-content-tertiary sm:ml-[192px]">
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm bg-status-warning/70" />Cost</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm bg-status-success/70" />Benefit</span>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardHeader icon={<Lightbulb />} title="Expected benefits" />
        <CardBody><ActionList items={view.reasoning.benefits.map((b) => ({ t: b }))} titleKey="t" empty="None listed." /></CardBody>
      </Card>
      <Card>
        <CardHeader icon={<AlertOctagon />} title="Known risks" />
        <CardBody><ActionList items={view.reasoning.risks.map((b) => ({ t: b }))} titleKey="t" empty="None listed." /></CardBody>
      </Card>
    </div>
  );
}

function ExecutionTab({ view }: { view: ExecutiveView }) {
  const forecast = view.resources.forecast;
  return (
    <div className="space-y-5">
      <Callout tone="info" title="These are projections, not tracked progress">
        Execution, resource and governance health are computed by the brain for this plan at decision time. Real execution is tracked on the Tasks and Outcomes pages.
      </Callout>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader icon={<Workflow />} eyebrow="Layer 10 projection" title="Execution health" action={view.execution.status && <Badge tone={view.execution.status === "at_risk" ? "warning" : "success"} dot>{humanize(view.execution.status)}</Badge>} description={view.execution.summary} />
          <CardBody className="space-y-5">
            <MetricGrid metrics={view.execution.health} invert={["execution_risk"]} />
            <div>
              <SectionTitle title="Alerts & recovery" />
              <ActionList items={view.execution.alerts} titleKey="message" bodyKey="recommended_action" severityKey="severity" empty="No alerts." />
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader icon={<BatteryMedium />} title="Cognitive resources" description={view.resources.summary} action={view.resources.score !== null && <Badge tone="neutral">Score {view.resources.score.toFixed(0)}</Badge>} />
          <CardBody className="space-y-5">
            <MetricGrid metrics={view.resources.health} invert={["cognitive_load"]} />
            {num(forecast.utilization) !== null && (
              <dl className="grid grid-cols-3 gap-3 rounded-xl bg-surface-2/60 p-3">
                <KeyValue label={`Utilization (${str(forecast.horizon_days)}d)`} value={`${num(forecast.utilization)?.toFixed(0)}%`} mono />
                <KeyValue label="Demand" value={num(forecast.projected_demand)?.toFixed(1)} mono />
                <KeyValue label="Capacity" value={num(forecast.available_capacity)?.toFixed(1)} mono />
              </dl>
            )}
            <ActionList items={view.resources.recommendations} titleKey="action" bodyKey="rationale" metaKey="expected_benefit" empty="No resource recommendations." />
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function GovernanceTab({ view }: { view: ExecutiveView }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader icon={<Shield />} title="Policy compliance" description={view.governance.summary} action={view.governance.status && <Badge tone={view.governance.status === "blocked" ? "error" : view.governance.status === "approved" ? "success" : "warning"} dot>{humanize(view.governance.status)}</Badge>} />
        <CardBody className="space-y-5">
          <MetricGrid metrics={view.governance.compliance} />
          {view.governance.policies.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {view.governance.policies.map((p) => <Badge key={p} tone="outline">{humanize(p.replace(/^policy-/, ""))}</Badge>)}
            </div>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader icon={<Gavel />} title="Violations & corrections" action={<Badge tone={view.governance.violations.length ? "warning" : "success"}>{view.governance.violations.length}</Badge>} />
        <CardBody className="space-y-4">
          <ActionList items={view.governance.violations} titleKey="description" bodyKey="recommended_correction" severityKey="severity" empty="No governance violations." />
        </CardBody>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader icon={<BrainCircuit />} eyebrow="Meta-cognition" title="Decision experience & calibration" description="How the brain's confidence compares with real outcomes so far." />
        <CardBody className="grid gap-5 md:grid-cols-3">
          <dl className="grid grid-cols-2 gap-3 md:col-span-1">
            <KeyValue label="Decisions" value={str(view.learning.experience.decision_count, "0")} mono />
            <KeyValue label="Success rate" value={`${(toPercent(view.learning.experience.success_rate) ?? 0).toFixed(0)}%`} mono />
            <KeyValue label="Calibration" value={humanize(str(view.learning.calibration.calibration_status))} />
            <KeyValue label="Completed" value={str(view.learning.calibration.completed_decisions, "0")} mono />
          </dl>
          <div className="md:col-span-2">
            <p className="mb-2 text-xs text-content-tertiary">Lessons</p>
            <ul className="space-y-1.5">
              {view.learning.lessons.map((l) => <li key={l} className="text-[13px] text-content-secondary">• {l}</li>)}
              {!view.learning.lessons.length && <li className="text-[13px] text-content-tertiary">No lessons yet.</li>}
            </ul>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

type Tab = "reasoning" | "tradeoffs" | "execution" | "governance";

export function ExecutiveBrainPage() {
  const { result, run, eligible, isRunning, error, ranAt, tasksQuery } = useOptimization();
  const [tab, setTab] = React.useState<Tab>("reasoning");
  const view = React.useMemo(() => (result ? parseExecutive(result) : null), [result]);
  const context = view?.context ?? {};
  const riskLevel = str(view?.risk.executive_risk_level) || str(view?.risk.risk_level);

  return (
    <Page wide>
      <PageHeader
        layers="L8"
        title="Executive Brain"
        description="The cognitive layer that fuses evidence from every engine, resolves conflicts, weighs risk and trade-offs, and issues the final decision."
        actions={
          <>
            {ranAt && <span className="text-xs text-content-tertiary">Decision from {formatRelative(ranAt)}</span>}
            <Button variant="secondary" leftIcon={<Play />} isLoading={isRunning} disabled={!eligible.length} onClick={() => run(eligible)}>
              {view ? "Re-evaluate" : "Evaluate my tasks"}
            </Button>
          </>
        }
      />

      {error && <ErrorState className="mb-5" error={error} onRetry={() => run(eligible)} />}

      {!view ? (
        <Card>
          <EmptyState
            icon={<Network />}
            title="No decision yet"
            description={eligible.length ? `Evaluate your ${eligible.length} eligible task${eligible.length === 1 ? "" : "s"} to see how the brain reasons about them.` : tasksQuery.isLoading ? "Loading your tasks…" : "Add planned tasks with minute estimates, then run an evaluation."}
            action={
              eligible.length ? (
                <Button leftIcon={<Play />} isLoading={isRunning} onClick={() => run(eligible)}>Evaluate my tasks</Button>
              ) : (
                <Link to="/tasks?new=1"><Button variant="secondary">Create a task</Button></Link>
              )
            }
          />
        </Card>
      ) : (
        <>
          <Card className="mb-5 overflow-hidden">
            <div className="grid gap-0 lg:grid-cols-[1fr_auto]">
              <CardBody className="flex flex-col gap-5 sm:flex-row sm:items-center">
                <Ring value={view.confidence ?? 0} size={104} stroke={8} tone={scoreTone(view.confidence)} label="Executive confidence">
                  <div className="text-center">
                    <p className="tabular text-xl font-semibold leading-none">{view.confidence?.toFixed(0) ?? "—"}<span className="text-xs text-content-tertiary">%</span></p>
                    <p className="mt-1 text-[10px] text-content-muted">confidence</p>
                  </div>
                </Ring>
                <div className="min-w-0">
                  <p className="eyebrow mb-1">Final decision</p>
                  <h2 className="text-xl font-semibold tracking-tight">{view.reasoning.action || "—"}</h2>
                  <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-content-secondary">{view.reasoning.why}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {riskLevel && <Badge tone={riskLevel === "low" ? "success" : riskLevel === "medium" ? "warning" : "error"} dot>Executive risk {riskLevel} · {num(view.risk.executive_risk_score)?.toFixed(0)}</Badge>}
                    {view.recommended.title && <Badge tone="primary">Plan: {view.recommended.title}</Badge>}
                    <Badge tone="neutral">{view.trace.evidence.length} sources · {view.trace.conflicts.length} conflicts</Badge>
                  </div>
                </div>
              </CardBody>
              <div className="grid grid-cols-3 border-t border-border-subtle dark:border-border lg:w-[360px] lg:grid-cols-1 lg:border-l lg:border-t-0">
                {[
                  ["Focus", str(context.focus_state)],
                  ["Workload", str(context.workload_state)],
                  ["Energy", str(context.energy_state)],
                ].map(([label, value]) => (
                  <div key={label} className="flex flex-col justify-center border-r border-border-subtle px-5 py-3 last:border-r-0 dark:border-border lg:border-b lg:border-r-0 lg:last:border-b-0">
                    <p className="text-[11px] text-content-tertiary">{label} context</p>
                    <p className={cn("text-sm font-medium capitalize", value === "overload" ? "text-status-warning" : "text-content-primary")}>{value || "—"}</p>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Segmented<Tab>
            className="mb-5"
            ariaLabel="Executive brain views"
            value={tab}
            onChange={setTab}
            items={[
              { value: "reasoning", label: "Evidence & reasoning" },
              { value: "tradeoffs", label: "Trade-offs" },
              { value: "execution", label: "Execution & resources" },
              { value: "governance", label: "Governance" },
            ]}
          />
          <motion.div key={tab} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
            {tab === "reasoning" && <ReasoningTab view={view} />}
            {tab === "tradeoffs" && <TradeoffsTab view={view} />}
            {tab === "execution" && <ExecutionTab view={view} />}
            {tab === "governance" && <GovernanceTab view={view} />}
          </motion.div>

          <div className="mt-6 flex justify-end">
            <Link to="/optimize" className="inline-flex items-center gap-1 text-[13px] font-medium text-content-secondary hover:text-content-primary">
              Back to the full pipeline <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </>
      )}
    </Page>
  );
}
