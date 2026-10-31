import * as React from "react";
import { Link } from "react-router-dom";
import { Activity, CheckCircle2, Hourglass, MessageSquareDot, PlayCircle, Scale, Star, Target } from "lucide-react";
import type { Task } from "@/api/endpoints";
import { useTasks } from "@/api/hooks";
import { Page, PageHeader } from "@/components/layout/Page";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout, EmptyState, ErrorState, Skeleton, SkeletonRows } from "@/components/ui/Feedback";
import { Stat } from "@/components/ui/Stat";
import { Bars, EstimateScatter, Legend } from "@/components/viz/Charts";
import { TaskRow } from "@/features/tasks/TaskRow";
import { FeedbackDialog } from "@/features/tasks/FeedbackDialog";
import { durationRatio, hasFeedback, lifecycle } from "@/features/tasks/taskUtils";
import { formatDuration, parseUtcDate } from "@/utils/formatters";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

function median(values: number[]): number | null {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

function mean(values: number[]): number | null {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

export function OutcomesPage() {
  const { data, isLoading, isError, error, refetch } = useTasks();
  const [feedbackTask, setFeedbackTask] = React.useState<Task | null>(null);
  const tasks = React.useMemo(() => data?.tasks ?? [], [data]);

  const started = tasks.filter((t) => lifecycle(t) === "started");
  const completed = React.useMemo(
    () => tasks.filter((t) => lifecycle(t) === "completed").sort((a, b) => (parseUtcDate(b.end_time)?.getTime() ?? 0) - (parseUtcDate(a.end_time)?.getTime() ?? 0)),
    [tasks]
  );
  const awaiting = completed.filter((t) => !hasFeedback(t));
  const rated = completed.filter(hasFeedback);
  const timed = completed.filter((t) => durationRatio(t) !== null);
  const ratios = timed.map((t) => durationRatio(t) as number);
  const onEstimate = ratios.filter((r) => r >= 0.85 && r <= 1.15).length;
  const medianRatio = median(ratios);

  const scatter = timed.map((t) => ({ estimated: t.estimated_duration as number, actual: t.actual_duration as number, title: t.title }));
  const ratingSeries = [
    { key: "focus", name: "Focus" },
    { key: "energy", name: "Energy" },
    { key: "productivity", name: "Productivity" },
  ];
  const ratingData = rated
    .slice(0, 10)
    .reverse()
    .map((t) => ({ name: t.title.length > 14 ? `${t.title.slice(0, 13)}…` : t.title, focus: t.focus_rating ?? 0, energy: t.energy_rating ?? 0, productivity: t.productivity_rating ?? 0 }));
  const avg = (key: "focus_rating" | "energy_rating" | "productivity_rating") => mean(rated.map((t) => t[key] as number));

  return (
    <Page wide>
      <PageHeader
        layers="L10 – L12"
        title="Outcomes"
        description="What actually happened: work in flight, real durations against estimates, and your ratings — the ground truth that closes the loop back into learning."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="In progress" value={started.length} loading={isLoading} icon={<PlayCircle />} accent="primary" sub="Layer 10 · execution" />
        <Stat label="Completed" value={completed.length} loading={isLoading} icon={<CheckCircle2 />} accent="success" sub="Layer 11 · outcomes" />
        <Stat label="Median actual ÷ estimate" value={medianRatio !== null ? `×${medianRatio.toFixed(2)}` : "—"} loading={isLoading} icon={<Scale />} sub={`${timed.length} timed outcomes`} />
        <Stat label="Within ±15% of estimate" value={timed.length ? `${Math.round((onEstimate / timed.length) * 100)}%` : "—"} loading={isLoading} icon={<Target />} accent="quantum" sub={`${onEstimate} of ${timed.length}`} />
        <Stat label="Rated" value={`${rated.length}/${completed.length}`} loading={isLoading} icon={<MessageSquareDot />} accent={awaiting.length ? "warning" : "neutral"} sub="Layer 12 · feedback" className="col-span-2 lg:col-span-1" />
      </div>

      {isError && <ErrorState className="mb-5" error={error} onRetry={() => void refetch()} />}

      {awaiting.length > 0 && (
        <Callout tone="warning" className="mb-5" title={`${awaiting.length} completed task${awaiting.length === 1 ? " needs" : "s need"} your rating`} action={<Button size="sm" variant="secondary" onClick={() => setFeedbackTask(awaiting[0])}>Rate now</Button>}>
          Each rating is a genuine label for the productivity model — it needs at least 10 before personal training unlocks.
        </Callout>
      )}

      <div className="mb-5 grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader icon={<Hourglass />} title="Estimated vs actual duration" description="Each dot is a completed task. Points above the diagonal took longer than planned." />
          <CardBody>
            {isLoading ? <Skeleton className="h-[260px] rounded-xl" /> : scatter.length ? (
              <>
                <EstimateScatter data={scatter} />
                <p className="mt-2 text-[11px] text-content-tertiary">Minutes. The diagonal marks a perfect estimate. Durations are measured from start and complete timestamps.</p>
              </>
            ) : (
              <EmptyState compact icon={<Hourglass />} title="No timed outcomes yet" description="Start and complete tasks to compare actual durations with estimates." />
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader icon={<Star />} title="Self-reported ratings" description="Your last 10 rated tasks, 1–5." />
          <CardBody>
            {isLoading ? <Skeleton className="h-[260px] rounded-xl" /> : ratingData.length ? (
              <>
                <Legend series={ratingSeries} className="mb-2" />
                <Bars data={ratingData} xKey="name" series={ratingSeries} domain={[0, 5]} height={232} />
                <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                  {([["Focus", "focus_rating"], ["Energy", "energy_rating"], ["Productivity", "productivity_rating"]] as const).map(([label, key]) => (
                    <div key={key} className="rounded-lg bg-surface-2/60 py-2">
                      <p className="tabular font-mono text-sm">{avg(key)?.toFixed(1) ?? "—"}</p>
                      <p className="text-[11px] text-content-tertiary">avg {label.toLowerCase()}</p>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <EmptyState compact icon={<Star />} title="No ratings yet" description="Rate completed tasks to see focus, energy and productivity trends." />
            )}
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_1.3fr] [&>*]:min-w-0">
        <Card>
          <CardHeader icon={<Activity />} eyebrow="Layer 10" title="Executing now" action={<Badge tone="primary">{started.length}</Badge>} />
          <CardBody>
            {isLoading ? <SkeletonRows rows={2} /> : started.length ? (
              <ul className="space-y-2">{started.map((t) => <TaskRow key={t.id} task={t} compact onRequestFeedback={setFeedbackTask} />)}</ul>
            ) : (
              <EmptyState compact icon={<PlayCircle />} title="Nothing in progress" description={<>Start a task from <Link to="/tasks" className="text-primary hover:underline">Tasks</Link> to track execution.</>} />
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader icon={<CheckCircle2 />} eyebrow="Layer 11 – 12" title="Outcome history" description="Most recent first." />
          <CardBody className="overflow-x-auto p-0 pb-2">
            {isLoading ? <div className="p-5"><SkeletonRows rows={3} /></div> : completed.length ? (
              <table className="w-full min-w-[560px] text-[13px]">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-content-tertiary">
                    <th className="px-5 pb-2 font-medium">Task</th>
                    <th className="pb-2 text-right font-medium">Estimate</th>
                    <th className="pb-2 text-right font-medium">Actual</th>
                    <th className="pb-2 text-right font-medium">Ratio</th>
                    <th className="pb-2 text-center font-medium">F · E · P</th>
                    <th className="px-5 pb-2 text-right font-medium">Finished</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle dark:divide-border">
                  {completed.slice(0, 25).map((t) => {
                    const ratio = durationRatio(t);
                    return (
                      <tr key={t.id} className="hover:bg-surface-2/40">
                        <td className="max-w-[220px] truncate px-5 py-2.5 text-content-primary">{t.title}</td>
                        <td className="tabular py-2.5 text-right font-mono text-content-tertiary">{formatDuration(t.estimated_duration)}</td>
                        <td className="tabular py-2.5 text-right font-mono">{formatDuration(t.actual_duration)}</td>
                        <td className={cn("tabular py-2.5 text-right font-mono", ratio === null ? "text-content-muted" : ratio > 1.15 ? "text-status-warning" : ratio < 0.85 ? "text-quantum" : "text-status-success")}>{ratio !== null ? `×${ratio.toFixed(2)}` : "—"}</td>
                        <td className="py-2.5 text-center">
                          {hasFeedback(t) ? (
                            <span className="tabular font-mono text-content-secondary">{t.focus_rating}·{t.energy_rating}·{t.productivity_rating}</span>
                          ) : (
                            <button type="button" onClick={() => setFeedbackTask(t)} className="text-xs font-medium text-primary hover:underline">Rate</button>
                          )}
                        </td>
                        <td className="px-5 py-2.5 text-right text-xs text-content-tertiary">{formatRelative(t.end_time)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <EmptyState compact icon={<CheckCircle2 />} title="No completed tasks yet" />
            )}
          </CardBody>
        </Card>
      </div>

      <FeedbackDialog task={feedbackTask} isOpen={feedbackTask !== null} onClose={() => setFeedbackTask(null)} />
    </Page>
  );
}
