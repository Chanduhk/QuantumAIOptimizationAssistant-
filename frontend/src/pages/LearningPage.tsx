import * as React from "react";
import { motion } from "framer-motion";
import { BookOpenCheck, Boxes, CircleAlert, Cpu, Database, DatabaseZap, FlaskConical, GraduationCap, ListChecks, RotateCw, Search, ShieldCheck, Sparkles } from "lucide-react";
import type { MLReadinessComponent, MLTrainingJobRecord } from "@/api/endpoints";
import { useBenchmarkDatasets, useBenchmarkRL, useBenchmarkVectorMemory, useBootstrapPublicDataset, useDataCollectionStatus, useMLReadiness, useMLTrainingStatus, useRetryTraining, useTriggerTraining } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Page, PageHeader } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, KeyValue } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout, EmptyState, ErrorState, Skeleton, SkeletonRows } from "@/components/ui/Feedback";
import { Meter, Ring } from "@/components/ui/Meter";
import { Segmented } from "@/components/ui/Tabs";
import { toast } from "@/components/ui/Toaster";
import { Bars, Legend } from "@/components/viz/Charts";
import { formatRelative } from "@/lib/format";
import { humanize, num, rec, recs, str, type Rec } from "@/lib/data";
import { readinessTone } from "@/lib/status";
import { cn } from "@/lib/utils";

const MODEL_COPY: Record<string, { title: string; icon: React.ElementType; feeds: string }> = {
  DurationRatioModel: { title: "Duration model", icon: Cpu, feeds: "Completed tasks with start & end times" },
  ProductivityModel: { title: "Productivity model", icon: Sparkles, feeds: "Focus, energy & productivity ratings" },
  RLScheduler: { title: "RL scheduler", icon: GraduationCap, feeds: "Schedule adherence episodes" },
};

function GateCard({ name, c }: { name: string; c: MLReadinessComponent }) {
  const meta = MODEL_COPY[name] ?? { title: name, icon: Cpu, feeds: "" };
  const pct = c.required_samples ? Math.min(100, (c.eligible_samples / c.required_samples) * 100) : 0;
  const tone = readinessTone(c.status);
  return (
    <Card className="flex h-full flex-col">
      <CardHeader icon={<meta.icon />} title={meta.title} description={c.model_type} />
      <CardBody className="flex flex-1 flex-col gap-4">
        <div className="flex items-center gap-4">
          <Ring value={pct} size={72} stroke={6} tone={tone === "success" ? "success" : "primary"} label={`${meta.title} readiness`}>
            <span className="tabular text-sm font-semibold">{Math.round(pct)}%</span>
          </Ring>
          <div className="min-w-0">
            <Badge tone={tone} dot>{humanize(c.status)}</Badge>
            <p className="tabular mt-2 font-mono text-lg">{c.eligible_samples}<span className="text-sm text-content-muted"> / {c.required_samples} samples</span></p>
            <p className="text-[11px] text-content-tertiary">Fed by: {meta.feeds}</p>
          </div>
        </div>
        {c.blocking_reasons.length > 0 && (
          <div>
            <p className="mb-1 text-xs text-content-tertiary">Blocking</p>
            <ul className="space-y-1">
              {c.blocking_reasons.map((r) => <li key={r} className="flex gap-2 text-xs text-content-secondary"><CircleAlert className="mt-0.5 size-3 shrink-0 text-status-warning" />{humanize(r)}</li>)}
            </ul>
          </div>
        )}
        {c.data_collection_actions.length > 0 && (
          <div className="mt-auto rounded-lg bg-surface-2/60 p-3">
            <p className="mb-1 text-xs font-medium text-content-primary">To unlock</p>
            <ul className="space-y-0.5">{c.data_collection_actions.map((a) => <li key={a} className="text-xs text-content-secondary">• {a}</li>)}</ul>
          </div>
        )}
        <p className="text-[11px] text-content-muted">Label: {c.ground_truth_label_source}</p>
      </CardBody>
    </Card>
  );
}

function JobPanel({ job, title }: { job: MLTrainingJobRecord; title: string }) {
  const running = job.status === "running" || job.status === "queued";
  const [showLogs, setShowLogs] = React.useState(running);
  return (
    <div className="rounded-xl border border-border-subtle p-4 dark:border-border">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs text-content-tertiary">{title}</p>
          <p className="text-sm font-medium">{humanize(job.job_type)} <span className="font-mono text-[11px] text-content-muted">{job.job_id.slice(0, 8)}</span></p>
        </div>
        <Badge tone={job.status === "completed" ? "success" : job.status === "failed" ? "error" : job.status === "gated" ? "warning" : "primary"} dot pulse={running}>{humanize(job.status)}</Badge>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <Meter value={job.progress_pct} tone={job.status === "failed" ? "error" : "primary"} className="flex-1" label="Training progress" />
        <span className="tabular font-mono text-xs">{Math.round(job.progress_pct)}%</span>
      </div>
      <p className="mt-1.5 text-xs text-content-tertiary">{humanize(job.current_step)}{job.started_at_utc && ` · started ${formatRelative(job.started_at_utc)}`}</p>
      {job.error_message && <p className="mt-2 rounded-md bg-status-error/[0.06] px-2 py-1.5 text-xs text-status-error">{job.error_message}</p>}
      {job.step_logs.length > 0 && (
        <>
          <button type="button" onClick={() => setShowLogs((v) => !v)} className="mt-2 text-xs font-medium text-content-secondary hover:text-content-primary">{showLogs ? "Hide" : "Show"} {job.step_logs.length} log steps</button>
          {showLogs && (
            <ol className="scrollbar-thin mt-2 max-h-56 space-y-1.5 overflow-y-auto border-l border-border pl-4">
              {job.step_logs.map((log, i) => (
                <li key={i} className="text-xs">
                  <span className={cn("font-medium", log.status === "failed" ? "text-status-error" : "text-content-primary")}>{humanize(log.step)}</span>
                  <span className="text-content-tertiary"> — {log.message}</span>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </div>
  );
}

function TrainingController() {
  const status = useMLTrainingStatus();
  const trigger = useTriggerTraining();
  const retry = useRetryTraining();
  const bootstrap = useBootstrapPublicDataset();
  const [jobType, setJobType] = React.useState<"public_benchmark" | "personalized" | "all">("public_benchmark");
  const data = status.data;
  const busy = data?.controller_status === "running" || data?.controller_status === "queued";
  const models = [...(data?.production_models ?? []).map((m) => ({ ...m, lane: "Production" })), ...(data?.candidate_models ?? []).map((m) => ({ ...m, lane: "Candidate" }))];

  return (
    <Card>
      <CardHeader
        icon={<FlaskConical />}
        eyebrow="Layer 13 · Continuous learning"
        title="Training controller"
        description="Trains candidate models, validates them on held-out data and promotes only when gates pass."
        action={data && <Badge tone={busy ? "primary" : data.controller_status === "failed" ? "error" : "neutral"} dot pulse={busy}>{humanize(data.controller_status)}</Badge>}
      />
      <CardBody className="space-y-5">
        {status.isLoading ? <SkeletonRows rows={3} /> : status.isError ? <ErrorState error={status.error} onRetry={() => void status.refetch()} /> : (
          <>
            <div className="flex flex-col gap-3 rounded-xl bg-surface-2/60 p-3 sm:flex-row sm:items-center">
              <Segmented size="sm" ariaLabel="Training job type" value={jobType} onChange={setJobType} items={[{ value: "public_benchmark", label: "Public benchmark" }, { value: "personalized", label: "Personalized" }, { value: "all", label: "All" }]} />
              <div className="flex flex-1 flex-wrap justify-end gap-2">
                {data?.last_job?.status === "failed" && (
                  <Button size="sm" variant="ghost" leftIcon={<RotateCw />} isLoading={retry.isPending} disabled={busy}
                    onClick={() => retry.mutate(data.last_job?.job_id, { onSuccess: () => toast("info", "Retry queued"), onError: (e) => toast("error", "Retry failed", getApiErrorMessage(e)) })}>
                    Retry last
                  </Button>
                )}
                <Button size="sm" isLoading={trigger.isPending} disabled={busy}
                  onClick={() => trigger.mutate({ jobType }, {
                    onSuccess: (job) => toast(job.status === "gated" ? "warning" : "info", job.status === "gated" ? "Training gated" : "Training started", job.status === "gated" ? job.error_message || "Readiness gates are not satisfied yet." : `${humanize(job.job_type)} job ${job.job_id.slice(0, 8)} queued.`),
                    onError: (e) => toast("error", "Couldn't start training", getApiErrorMessage(e)),
                  })}>
                  Start training
                </Button>
              </div>
            </div>
            {jobType !== "public_benchmark" && <p className="-mt-2 text-xs text-content-tertiary">Personalized training runs only when readiness gates pass; otherwise the job is recorded as gated.</p>}

            {data?.active_job && <JobPanel job={data.active_job} title="Active job" />}
            {!data?.active_job && data?.last_job && <JobPanel job={data.last_job} title="Last job" />}
            {!data?.active_job && !data?.last_job && <p className="text-[13px] text-content-tertiary">No training jobs have run since the API started ({data?.total_jobs_executed ?? 0} executed).</p>}

            <div>
              <p className="mb-2 text-xs text-content-tertiary">Model registry</p>
              {models.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[520px] text-[13px]">
                    <thead><tr className="border-b border-border text-left text-xs text-content-tertiary"><th className="pb-2 font-medium">Model</th><th className="pb-2 font-medium">Lane</th><th className="pb-2 text-right font-medium">Score</th><th className="pb-2 pl-4 font-medium">Provenance</th></tr></thead>
                    <tbody className="divide-y divide-border-subtle dark:divide-border">
                      {models.map((m, i) => {
                        const metrics = rec(m.metrics) ?? {};
                        return (
                          <tr key={i}>
                            <td className="py-2.5"><span className="font-medium">{m.model_name}</span> <span className="font-mono text-[11px] text-content-muted">v{m.version}</span></td>
                            <td className="py-2.5"><Badge tone={m.lane === "Production" ? "success" : "quantum"}>{m.lane}{str(metrics.status) === "staging" ? " · staging" : ""}</Badge></td>
                            <td className="tabular py-2.5 text-right font-mono">{num(m.accuracy_score)?.toFixed(3) ?? "—"}</td>
                            <td className="max-w-[260px] truncate py-2.5 pl-4 text-xs text-content-tertiary" title={str(metrics.provenance)}>{str(metrics.provenance, "—")}{metrics.is_personalized === false ? " · not personalized" : ""}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : <p className="text-[13px] text-content-tertiary">No models registered.</p>}
            </div>

            <div className="flex flex-col gap-3 border-t border-border-subtle pt-4 dark:border-border sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-[13px] font-medium">Public benchmark dataset</p>
                <p className="truncate text-xs text-content-tertiary">
                  {data?.public_dataset ? `${data.public_dataset.name} · ${data.public_dataset.total_records.toLocaleString()} rows · ${data.public_dataset.license}` : "Not loaded into staging in this session."}
                </p>
              </div>
              <Button size="sm" variant="secondary" leftIcon={<DatabaseZap />} isLoading={bootstrap.isPending}
                onClick={() => bootstrap.mutate(false, { onSuccess: (d) => toast("success", "Dataset ready", `${d.name ?? "Public dataset"} verified (${d.total_records ?? "?"} rows).`), onError: (e) => toast("error", "Bootstrap failed", getApiErrorMessage(e)) })}>
                {data?.public_dataset ? "Re-verify dataset" : "Bootstrap dataset"}
              </Button>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

function DataQuality() {
  const q = useDataCollectionStatus();
  const result = rec(q.data?.result) ?? {};
  const report = rec(result.collection_report) ?? {};
  const audit = rec(result.quality_audit) ?? {};
  const rejections = Object.entries(rec(report.rejection_reason_counts) ?? {});
  const issues = Object.entries(rec(report.lifecycle_issue_counts) ?? {});
  const total = num(report.total_task_records) ?? 0;
  const funnel = [
    { label: "Task records", value: total },
    { label: "Completed", value: num(report.completed_records) ?? 0 },
    { label: "Lifecycle valid", value: num(report.lifecycle_valid_records) ?? 0 },
    { label: "Training-eligible", value: num(report.f3_eligible_records) ?? 0 },
  ];
  return (
    <Card>
      <CardHeader icon={<ShieldCheck />} title="Data quality pipeline" description="How your raw task records turn into training rows." action={str(audit.readiness_status) && <Badge tone={readinessTone(str(audit.readiness_status))} dot>{humanize(str(audit.readiness_status))}</Badge>} />
      <CardBody className="space-y-5">
        {q.isLoading ? <SkeletonRows rows={3} /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : (
          <>
            <ol className="space-y-2.5">
              {funnel.map((f, i) => (
                <motion.li key={f.label} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}>
                  <div className="mb-1 flex justify-between text-xs"><span className="text-content-secondary">{f.label}</span><span className="tabular font-mono">{f.value}</span></div>
                  <Meter value={f.value} max={Math.max(total, 1)} tone={i === funnel.length - 1 ? "success" : "quantum"} label={f.label} />
                </motion.li>
              ))}
            </ol>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <KeyValue label="Leakage check" value={humanize(str(audit.leakage_status))} />
              <KeyValue label="Task types" value={((report.task_types_represented as unknown[]) ?? []).length} mono />
              <KeyValue label="Valid durations" value={str(report.valid_actual_duration_records, "0")} mono />
            </dl>
            {(rejections.length > 0 || issues.length > 0) && (
              <div className="rounded-lg bg-surface-2/60 p-3">
                <p className="mb-1.5 text-xs font-medium">Why records were excluded</p>
                <ul className="space-y-1 text-xs text-content-secondary">
                  {rejections.map(([reason, count]) => <li key={reason} className="flex justify-between gap-3"><span className="min-w-0 truncate" title={reason}>{reason}</span><span className="tabular font-mono">{String(count)}</span></li>)}
                  {issues.map(([reason, count]) => <li key={reason} className="flex justify-between gap-3"><span>{humanize(reason)}</span><span className="tabular font-mono">{String(count)}</span></li>)}
                </ul>
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}

function Benchmarks() {
  const rl = useBenchmarkRL();
  const vm = useBenchmarkVectorMemory();
  const ds = useBenchmarkDatasets();
  const policySeries = [
    { key: "baseline_priority", name: "Priority-first" },
    { key: "baseline_edf", name: "Earliest deadline" },
    { key: "trained_q_policy", name: "Q-learning" },
  ];
  const rlData = Object.entries((rl.data ?? {}) as Record<string, Rec>).map(([scenario, policies]) => {
    const row: Record<string, unknown> = { name: humanize(scenario.replace(/^scenario_/, "")) };
    for (const s of policySeries) row[s.key] = num(rec(policies[s.key])?.mean_reward) ?? 0;
    return row;
  });
  const v = (vm.data ?? {}) as Rec;
  const recall = [
    { name: "Recall@1", value: (num(v.recall_at_1) ?? 0) * 100 },
    { name: "Recall@3", value: (num(v.recall_at_3) ?? 0) * 100 },
    { name: "Recall@5", value: (num(v.recall_at_5) ?? 0) * 100 },
    { name: "MRR", value: (num(v.mrr) ?? 0) * 100 },
  ];
  const catalog = recs(rec(ds.data)?.catalog);

  return (
    <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr] [&>*]:min-w-0">
      <Card>
        <CardHeader icon={<GraduationCap />} title="RL scheduler vs heuristics" description="Mean episode reward per benchmark scenario (higher is better)." />
        <CardBody>
          {rl.isLoading ? <Skeleton className="h-64 rounded-xl" /> : rl.isError ? <ErrorState error={rl.error} onRetry={() => void rl.refetch()} /> : (
            <>
              <Legend series={policySeries} className="mb-2" />
              <Bars data={rlData} xKey="name" series={policySeries} height={250} />
            </>
          )}
        </CardBody>
      </Card>
      <div className="space-y-5">
        <Card>
          <CardHeader icon={<Search />} eyebrow="Layer 2" title="Vector memory retrieval" description={str(v.notes)} action={v.is_fallback === true && <Badge tone="warning">Hash fallback</Badge>} />
          <CardBody>
            {vm.isLoading ? <Skeleton className="h-36 rounded-xl" /> : vm.isError ? <ErrorState error={vm.error} /> : (
              <>
                <ul className="space-y-2.5">
                  {recall.map((r) => (
                    <li key={r.name}>
                      <div className="mb-1 flex justify-between text-xs"><span className="text-content-secondary">{r.name}</span><span className="tabular font-mono">{r.value.toFixed(0)}%</span></div>
                      <Meter value={r.value} tone="quantum" label={r.name} />
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[11px] text-content-tertiary">{str(v.embedding_mode)} · {str(v.dimension)}-d · {str(v.corpus_size)} docs · {num(v.mean_latency_ms)?.toFixed(2)} ms</p>
              </>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader icon={<Boxes />} title="Dataset catalog" />
          <CardBody>
            {ds.isLoading ? <SkeletonRows rows={2} /> : (
              <ul className="space-y-2">
                {catalog.map((d) => (
                  <li key={str(d.dataset_id)} className="flex items-start justify-between gap-3 text-[13px]">
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{str(d.name)}</span>
                      <span className="text-xs text-content-tertiary">{num(d.total_records)?.toLocaleString()} records · {str(d.license).split(" (")[0]}</span>
                    </span>
                    <Badge tone={str(d.promotion_verdict).includes("UNSUITABLE") ? "warning" : "neutral"}>{humanize(str(d.promotion_verdict))}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

export function LearningPage() {
  const readiness = useMLReadiness();
  const report = readiness.data;
  const components = Object.entries(report?.components ?? {}).filter((e): e is [string, MLReadinessComponent] => Boolean(e[1]));

  return (
    <Page wide>
      <PageHeader
        layers="L13"
        title="Learning Loop"
        description="HELIOX only personalizes when it has earned it. Readiness gates hold models back until enough genuine outcomes and ratings exist — then training, validation and promotion take over."
      />

      {readiness.isLoading ? (
        <Skeleton className="mb-5 h-24 rounded-2xl" />
      ) : readiness.isError ? (
        <ErrorState className="mb-5" error={readiness.error} onRetry={() => void readiness.refetch()} />
      ) : report ? (
        <Callout tone={readinessTone(report.overall_status) === "success" ? "success" : "info"} className="mb-5" icon={<BookOpenCheck className="size-4 text-quantum" />} title={`Overall: ${humanize(report.overall_status)}`}>
          <p>{report.database_task_count} task records · {report.eligible_dataset_rows} eligible training rows · audited {formatRelative(report.audit_timestamp)}</p>
          {report.next_steps.length > 0 && <ul className="mt-1.5 space-y-0.5 text-xs">{report.next_steps.map((s) => <li key={s}>• {s}</li>)}</ul>}
        </Callout>
      ) : null}

      <div className="mb-5 grid gap-5 lg:grid-cols-3">
        {readiness.isLoading
          ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-80 rounded-2xl" />)
          : components.length
            ? components.map(([name, c]) => <GateCard key={name} name={name} c={c} />)
            : !readiness.isError && <Card className="lg:col-span-3"><EmptyState icon={<ListChecks />} title="No readiness components reported" /></Card>}
      </div>

      <div className="mb-5 grid gap-5 xl:grid-cols-[1.4fr_1fr] [&>*]:min-w-0">
        <TrainingController />
        <DataQuality />
      </div>

      <div className="mb-3 flex items-center gap-2">
        <Database className="size-4 text-content-tertiary" />
        <h2 className="text-[15px] font-semibold">Benchmarks</h2>
      </div>
      <Benchmarks />
    </Page>
  );
}
