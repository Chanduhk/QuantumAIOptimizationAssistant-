import * as React from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, ChevronDown, CornerDownRight, Cpu, ShieldCheck, X } from "lucide-react";
import { useAcceptPlan, useActivePlan, useRejectPlan } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ScheduleTimeline } from "@/components/viz/ScheduleTimeline";
import { toast } from "@/components/ui/Toaster";
import { proposalBlocks } from "@/features/optimization/parse";
import { humanize, num, rec, recs, str, strs, type Rec } from "@/lib/data";
import { cn } from "@/lib/utils";

const REFINEMENTS = [
  "I only have two hours available now. Adjust the plan.",
  "Show me another feasible option.",
  "Leave 30 minutes for revision.",
  "Use my existing tasks and goals.",
];

function PipelineTrace({ trace }: { trace: Rec | null }) {
  const stages = recs(trace?.stages);
  if (!stages.length) return null;
  const total = num(trace?.total_duration_ms) ?? stages.reduce((s, x) => s + (num(x.duration_ms) ?? 0), 0);
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-[11px] text-content-tertiary">
        <span className="inline-flex items-center gap-1.5"><Cpu className="size-3" /> Pipeline trace</span>
        <span className="tabular font-mono">{total.toFixed(0)} ms</span>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-surface-3">
        {stages.map((s, i) => {
          const share = total > 0 ? ((num(s.duration_ms) ?? 0) / total) * 100 : 100 / stages.length;
          const ok = str(s.status) === "SUCCESS";
          return (
            <motion.span
              key={i}
              initial={{ width: 0 }}
              animate={{ width: `${Math.max(share, 3)}%` }}
              transition={{ duration: 0.6, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] }}
              title={`${humanize(str(s.stage))} · ${(num(s.duration_ms) ?? 0).toFixed(0)} ms · ${humanize(str(s.status))}`}
              className={cn("h-full border-r-2 border-surface-1 last:border-r-0", ok ? ["bg-quantum", "bg-primary", "bg-quantum/60", "bg-primary/60"][i % 4] : "bg-status-error")}
            />
          );
        })}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-content-tertiary">
        {stages.map((s, i) => (
          <span key={i}>{humanize(str(s.stage))} <span className="tabular font-mono text-content-muted">{(num(s.duration_ms) ?? 0).toFixed(0)}ms</span></span>
        ))}
      </div>
    </div>
  );
}

export function ProposalCard({ result, onRefine, fromHistory }: { result: Rec; onRefine?: (text: string) => void; fromHistory?: boolean }) {
  const blocks = proposalBlocks(result.schedule);
  const unscheduled = recs(result.unscheduled_tasks);
  const infeasible = recs(result.infeasible_tasks);
  const reasons = strs(result.reasons_for_prioritization);
  const tradeOffs = strs(result.trade_offs);
  const alternatives = strs(result.alternative_actions);
  const feasible = str(result.feasibility_status, "FEASIBLE") === "FEASIBLE";
  const demanded = num(result.total_demanded_hours);
  const available = num(result.available_hours);
  const proposalId = str(result.proposal_id);
  const version = num(result.proposal_version) ?? 1;
  const parser = str(result.parser_provenance) || str(rec(result.provenance)?.parser_provenance) || "deterministic_fallback";
  const llm = /openai|llm|gemini|anthropic/i.test(parser) && !/fallback/i.test(parser);

  const active = useActivePlan();
  const accept = useAcceptPlan();
  const reject = useRejectPlan();
  const [decision, setDecision] = React.useState<"accepted" | "rejected" | null>(null);
  const [showWhy, setShowWhy] = React.useState(false);
  const [refineText, setRefineText] = React.useState("");

  // A proposal is actionable only while it is the user's active, matching version.
  const activeProposal = active.data;
  const isCurrent = !proposalId || active.isLoading || (activeProposal?.id === proposalId && (activeProposal?.version ?? version) === version);
  const closedStatus = !isCurrent && !decision ? (fromHistory || activeProposal ? "Superseded or already resolved" : null) : null;

  const onAccept = () =>
    accept.mutate(
      { schedule: recs(result.schedule), proposal_id: proposalId || undefined, version: proposalId ? version : undefined },
      {
        onSuccess: (res) => {
          setDecision("accepted");
          const count = num(res.result?.persisted_count) ?? recs(result.schedule).length;
          toast("success", "Plan accepted", `${count} scheduled interval${count === 1 ? "" : "s"} saved to your tasks.`);
        },
        onError: (e) => toast("error", "Couldn't accept plan", getApiErrorMessage(e)),
      }
    );

  const onReject = () =>
    reject.mutate(
      { proposal_id: proposalId || undefined },
      {
        onSuccess: () => {
          setDecision("rejected");
          toast("info", "Proposal rejected", "No tasks were changed.");
        },
        onError: (e) => toast("error", "Couldn't reject plan", getApiErrorMessage(e)),
      }
    );

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface-1 shadow-card">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle bg-gradient-to-r from-primary/[0.07] to-transparent px-4 py-3 dark:border-border">
        <div className="flex min-w-0 items-center gap-2">
          <p className="text-sm font-semibold">Plan proposal</p>
          {proposalId && <span className="font-mono text-[11px] text-content-muted">v{version} · {proposalId.slice(0, 8)}</span>}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={llm ? "success" : "neutral"} title={`Parser: ${parser}`}>{llm ? "LLM parsed" : "Rule-based parse"}</Badge>
          {feasible ? <Badge tone="success" dot>Feasible</Badge> : <Badge tone="warning" dot>Overloaded</Badge>}
        </div>
      </div>

      <div className="space-y-4 p-4">
        <p className="text-[13px] leading-relaxed text-content-secondary">{str(result.executive_summary)}</p>

        <dl className="grid grid-cols-2 gap-3 rounded-xl bg-surface-2/60 p-3 sm:grid-cols-4">
          <div><dt className="text-[11px] text-content-tertiary">Workload</dt><dd className={cn("tabular font-mono text-sm", demanded !== null && available !== null && demanded > available ? "text-status-warning" : "text-content-primary")}>{demanded?.toFixed(1) ?? "—"}h</dd></div>
          <div><dt className="text-[11px] text-content-tertiary">Available</dt><dd className="tabular font-mono text-sm">{available?.toFixed(1) ?? "—"}h</dd></div>
          <div><dt className="text-[11px] text-content-tertiary">Quantum</dt><dd className="truncate text-sm">{humanize(str(result.quantum_suitability))}</dd></div>
          <div><dt className="text-[11px] text-content-tertiary">Behaviour model</dt><dd className="truncate text-sm" title={str(result.behavioral_details)}>{str(result.behavioral_provenance) === "PERSONAL_MODEL" ? "Personal" : "Heuristic"}</dd></div>
        </dl>

        {blocks.length > 0 && <ScheduleTimeline blocks={blocks} window={available ? [Math.min(...blocks.map((b) => b.start)), Math.min(...blocks.map((b) => b.start)) + available] : undefined} />}

        {!feasible && infeasible.length > 0 && (
          <div className="rounded-xl border border-status-warning/30 bg-status-warning/[0.07] p-3 text-[13px]">
            <p className="flex items-center gap-2 font-medium text-content-primary"><AlertTriangle className="size-4 text-status-warning" />{infeasible.length} task(s) don't fit the available window</p>
            <ul className="mt-1.5 space-y-0.5 text-content-secondary">
              {infeasible.map((t, i) => <li key={i}>• {str(t.title)} ({num(t.estimated_duration)?.toFixed(1)}h)</li>)}
            </ul>
            {alternatives.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {alternatives.map((a) => (
                  <button key={a} type="button" onClick={() => onRefine?.(a)} className="rounded-md border border-status-warning/30 px-2 py-1 text-left text-xs text-content-secondary hover:bg-status-warning/10">{a}</button>
                ))}
              </div>
            )}
          </div>
        )}

        {unscheduled.length > 0 && (
          <p className="text-xs text-content-tertiary">Deferred: {unscheduled.map((t) => str(t.title)).join(", ")}</p>
        )}

        <PipelineTrace trace={rec(result.trace)} />

        {(reasons.length > 0 || tradeOffs.length > 0) && (
          <div>
            <button type="button" onClick={() => setShowWhy((v) => !v)} className="flex items-center gap-1.5 text-xs font-medium text-content-secondary hover:text-content-primary" aria-expanded={showWhy}>
              <ShieldCheck className="size-3.5 text-quantum" /> Why this order
              <ChevronDown className={cn("size-3.5 transition-transform", showWhy && "rotate-180")} />
            </button>
            <AnimatePresence initial={false}>
              {showWhy && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                  <ul className="mt-2 space-y-1 text-xs text-content-secondary">
                    {reasons.map((r) => <li key={r}>• {r}</li>)}
                    {tradeOffs.map((t) => <li key={t} className="text-content-tertiary">⇄ {t}</li>)}
                    {str(result.behavioral_details) && <li className="text-content-tertiary">◦ {str(result.behavioral_details)}</li>}
                    {strs(result.quantum_reasons).map((q) => <li key={q} className="text-content-tertiary">◦ {q}</li>)}
                  </ul>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Refine + decide */}
      {decision === null && isCurrent && (
        <div className="space-y-2.5 border-t border-border-subtle bg-surface-2/40 px-4 py-3 dark:border-border">
          {onRefine && (
            <>
              <div className="scrollbar-none flex gap-1.5 overflow-x-auto py-0.5">
                {REFINEMENTS.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => onRefine(r)}
                    className="shrink-0 rounded-full border border-border bg-surface-1 px-2.5 py-1 text-xs text-content-secondary transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/50 hover:bg-primary/[0.08] hover:text-content-primary hover:shadow-sm"
                  >
                    {r}
                  </button>
                ))}
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (refineText.trim()) {
                    onRefine(refineText.trim());
                    setRefineText("");
                  }
                }}
                className="flex items-center gap-2"
              >
                <CornerDownRight className="size-4 shrink-0 text-content-muted" />
                <input
                  value={refineText}
                  onChange={(e) => setRefineText(e.target.value)}
                  placeholder="Refine: “move the report first”, “add a 1h buffer”…"
                  aria-label="Refine this plan"
                  className="h-8 flex-1 rounded-lg border border-border bg-surface-1 px-3 text-[13px] placeholder:text-content-muted focus:border-primary/50 focus:outline-none"
                />
                <Button type="submit" size="sm" variant="secondary" disabled={!refineText.trim()}>Refine</Button>
              </form>
            </>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border-subtle px-4 py-3 dark:border-border">
        <p className="text-xs text-content-tertiary">
          {decision === "accepted"
            ? "Accepted — intervals were written to your tasks."
            : decision === "rejected"
              ? "Rejected — nothing was changed."
              : closedStatus ?? "Accepting writes the scheduled intervals to your task database."}
        </p>
        {decision === "accepted" ? (
          <div className="flex items-center gap-2">
            <Badge tone="success" dot size="md">Accepted</Badge>
            <Link to="/tasks"><Button size="sm" variant="ghost">View tasks</Button></Link>
          </div>
        ) : decision === "rejected" ? (
          <Badge tone="neutral" size="md">Rejected</Badge>
        ) : isCurrent ? (
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" leftIcon={<X />} onClick={onReject} isLoading={reject.isPending} disabled={accept.isPending}>Reject</Button>
            <Button size="sm" leftIcon={<Check />} onClick={onAccept} isLoading={accept.isPending} disabled={reject.isPending}>Accept plan</Button>
          </div>
        ) : (
          <Badge tone="outline" size="md">Closed</Badge>
        )}
      </div>
    </div>
  );
}
