import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Boxes, ChevronDown, Database, HeartPulse, Search, Server, Wrench } from "lucide-react";
import type { ComponentInventoryItem } from "@/api/endpoints";
import { useComponentInventory, useMLModelStatus, useSystemHealth, useSystemStatus } from "@/api/hooks";
import { Page, PageHeader } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, KeyValue } from "@/components/ui/Card";
import { Badge, StatusDot } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Field";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Tabs";
import { Stat } from "@/components/ui/Stat";
import { LAYERS } from "@/lib/architecture";
import { componentTone } from "@/lib/status";
import { formatRelative } from "@/lib/format";
import { humanize, num, str } from "@/lib/data";
import { cn } from "@/lib/utils";

const TYPE_GROUPS: Record<string, string> = {
  ml_model: "Models",
  pretrained_model: "Models",
  optimizer: "Optimizers",
  simulated_quantum: "Quantum",
  heuristic: "Engines",
  conversational: "Engines",
  data_provider: "Data & workers",
  worker: "Data & workers",
};

function layerFor(id: string) {
  return LAYERS.find((l) => l.components.includes(id));
}

function ComponentRow({ c }: { c: ComponentInventoryItem }) {
  const [open, setOpen] = React.useState(false);
  const layer = layerFor(c.canonical_id);
  const tone = componentTone(c.operational_state);
  return (
    <li className="rounded-xl border border-border-subtle bg-surface-1 transition-colors hover:border-border dark:border-border">
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-3 px-4 py-3 text-left" aria-expanded={open}>
        <StatusDot tone={tone} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-medium text-content-primary">{c.display_name}</span>
          <span className="block truncate font-mono text-[11px] text-content-muted">{c.canonical_id}</span>
        </span>
        <span className="hidden items-center gap-1.5 sm:flex">
          {layer && <Badge tone="outline" className="font-mono">L{layer.n}</Badge>}
          {c.fallback_active && <Badge tone="warning">Fallback</Badge>}
          <Badge tone={tone}>{humanize(c.operational_state)}</Badge>
        </span>
        <ChevronDown className={cn("size-4 shrink-0 text-content-muted transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="space-y-3 border-t border-border-subtle px-4 py-3 text-[13px] dark:border-border">
              <div className="flex flex-wrap gap-1.5 sm:hidden">
                {layer && <Badge tone="outline">L{layer.n}</Badge>}
                <Badge tone={tone}>{humanize(c.operational_state)}</Badge>
              </div>
              {(c.notes || c.description || c.status_explanation) && <p className="text-content-secondary">{c.status_explanation || c.notes || c.description}</p>}
              <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <KeyValue label="Type" value={humanize(c.component_type)} />
                <KeyValue label="Training" value={humanize(c.training_state ?? "—")} />
                <KeyValue label="Executable now" value={c.can_execute_now ? "Yes" : "No"} />
                <KeyValue label="Artifact" value={c.artifact_version ?? "—"} mono />
              </dl>
              {c.fallback_active && c.fallback_description && <p className="rounded-lg bg-status-warning/[0.07] px-3 py-2 text-xs text-content-secondary"><span className="font-medium text-content-primary">Fallback: </span>{c.fallback_description}</p>}
              {c.provenance && <p className="text-xs text-content-tertiary"><span className="text-content-secondary">Provenance:</span> {c.provenance}</p>}
              {c.recovery_action && <p className="flex gap-1.5 text-xs text-content-tertiary"><Wrench className="mt-0.5 size-3 shrink-0" />{c.recovery_action}</p>}
              <p className="truncate font-mono text-[11px] text-content-muted" title={c.module_path}>{c.module_path} · checked {formatRelative(c.last_check_timestamp)}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

export function SystemStatusPage() {
  const health = useSystemHealth();
  const status = useSystemStatus();
  const inventory = useComponentInventory();
  const models = useMLModelStatus();
  const [group, setGroup] = React.useState("All");
  const [query, setQuery] = React.useState("");

  const components = inventory.data?.components ?? [];
  const groups = ["All", ...Array.from(new Set(components.map((c) => TYPE_GROUPS[c.component_type] ?? "Other")))];
  const visible = components.filter((c) => {
    if (group !== "All" && (TYPE_GROUPS[c.component_type] ?? "Other") !== group) return false;
    const q = query.trim().toLowerCase();
    return !q || `${c.display_name} ${c.canonical_id} ${c.component_type}`.toLowerCase().includes(q);
  });
  const fallbacks = components.filter((c) => c.fallback_active).length;
  const executable = components.filter((c) => c.can_execute_now).length;
  const pool = health.data?.database_pool as Record<string, unknown> | undefined;
  const metrics = (status.data?.ai_metrics ?? {}) as Record<string, unknown>;
  const healthy = health.data?.status === "operational" && health.data.database_connected;

  return (
    <Page wide>
      <PageHeader title="System Status" description="Live health of the API, database and every registered engine — including which ones are running on documented fallbacks." />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="API" value={health.isError ? "Offline" : healthy ? "Operational" : health.isLoading ? "…" : "Degraded"} loading={health.isLoading} icon={<HeartPulse />} accent={health.isError ? "error" : healthy ? "success" : "warning"} sub={health.data ? `Checked ${formatRelative(health.data.timestamp)}` : "Polled every 30s"} />
        <Stat label="Database" value={health.data?.database_connected ? "Connected" : health.isLoading ? "…" : "Unavailable"} loading={health.isLoading} icon={<Database />} accent={health.data?.database_connected ? "success" : "error"} sub={pool ? `${str(pool.class, "Pool")} · ${str(pool.checked_out, "0")} checked out` : undefined} />
        <Stat label="Executable components" value={inventory.data ? `${executable}/${inventory.data.total_components}` : "—"} loading={inventory.isLoading} icon={<Boxes />} accent="quantum" sub={`${fallbacks} on fallback`} />
        <Stat label="Model registry" value={models.data ? humanize(models.data.status) : "—"} loading={models.isLoading} icon={<Server />} sub={models.data ? `${models.data.models_registered} registered${models.data.in_memory_only ? " · in-memory" : ""}` : undefined} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_320px] [&>*]:min-w-0">
        <Card>
          <CardHeader icon={<Boxes />} title="Component inventory" description="Every engine the system reports, mapped to its architecture layer." action={inventory.data && <Badge tone="neutral">{inventory.data.total_components}</Badge>} />
          <CardBody>
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <Segmented size="sm" ariaLabel="Component type" value={group} onChange={setGroup} items={groups.map((g) => ({ value: g, label: g }))} />
              <div className="relative md:w-60">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />
                <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter components" className="pl-9" aria-label="Filter components" />
              </div>
            </div>
            {inventory.isLoading ? <SkeletonRows rows={6} /> : inventory.isError ? <ErrorState error={inventory.error} onRetry={() => void inventory.refetch()} /> : visible.length === 0 ? (
              <EmptyState compact title="No components match" />
            ) : (
              <ul className="space-y-2">{visible.map((c) => <ComponentRow key={c.canonical_id} c={c} />)}</ul>
            )}
          </CardBody>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader icon={<HeartPulse />} title="Runtime metrics" description="Counters since the API process started." />
            <CardBody>
              {status.isLoading ? <SkeletonRows rows={3} /> : status.isError ? <ErrorState error={status.error} /> : (
                <dl className="space-y-2.5">
                  {Object.entries(metrics).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between text-[13px]">
                      <dt className="text-content-secondary">{humanize(k)}</dt>
                      <dd className="tabular font-mono">{num(v) !== null ? (num(v) as number).toLocaleString(undefined, { maximumFractionDigits: 2 }) : str(v, "—")}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </CardBody>
          </Card>
          <Card>
            <CardHeader icon={<Server />} title="Model governance" />
            <CardBody>
              {models.isLoading ? <SkeletonRows rows={3} /> : models.isError ? <ErrorState error={models.error} /> : models.data && (
                <dl className="space-y-2.5 text-[13px]">
                  {[
                    ["Production approved", models.data.production_model_approved],
                    ["Candidate in staging", models.data.candidate_model_staging],
                    ["Heuristic fallback", models.data.heuristic_fallback_active],
                    ["Demo artifacts locked", models.data.demo_artifacts_locked],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="flex items-center justify-between">
                      <dt className="text-content-secondary">{String(label)}</dt>
                      <dd><Badge tone={value ? "success" : "neutral"}>{value === undefined ? "—" : value ? "Yes" : "No"}</Badge></dd>
                    </div>
                  ))}
                  <div className="flex items-center justify-between">
                    <dt className="text-content-secondary">RL policy</dt>
                    <dd><Badge tone="neutral">{humanize(models.data.rl_policy_status ?? "—")}</Badge></dd>
                  </div>
                </dl>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </Page>
  );
}
