import * as React from "react";
import { AlertCircle, AlertTriangle, Calendar, CheckCircle2, Clock3, Flame, Play, RefreshCw, Sparkles, Zap } from "lucide-react";
import { useAllocateSchedule, useDailyWorkload, useRescheduleTasks } from "@/api/hooks";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Toaster";
import { cn } from "@/lib/utils";

interface DailyWorkloadDashboardProps {
  onRefreshTasks?: () => void;
}

export function DailyWorkloadDashboard({ onRefreshTasks }: DailyWorkloadDashboardProps) {
  const { data: workload, isLoading, isError, refetch } = useDailyWorkload();
  const allocateMutation = useAllocateSchedule();
  const rescheduleMutation = useRescheduleTasks();

  const handleAllocate = () => {
    allocateMutation.mutate(
      { apply: true },
      {
        onSuccess: (res: any) => {
          const scheduledCount = res?.scheduled_tasks?.length ?? 0;
          toast("success", "Schedule Allocated", `Successfully scheduled ${scheduledCount} task(s) into non-overlapping slots.`);
          refetch();
          onRefreshTasks?.();
        },
        onError: (err: any) => {
          toast("error", "Allocation Failed", err?.message || "Failed to allocate schedule.");
        },
      }
    );
  };

  const handleReschedule = () => {
    rescheduleMutation.mutate(
      { reason: "Workload optimization requested from Tasks Dashboard", autoApply: true },
      {
        onSuccess: (res: any) => {
          const shifted = res?.shifted_tasks_count ?? 0;
          toast("success", "Tasks Rescheduled", `Rescheduled ${shifted} task(s) to resolve deadline pressures.`);
          refetch();
          onRefreshTasks?.();
        },
        onError: (err: any) => {
          toast("error", "Rescheduling Failed", err?.message || "Failed to reschedule tasks.");
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="mb-6 animate-pulse rounded-2xl border border-border-subtle bg-surface-1 p-5">
        <div className="h-5 w-48 rounded bg-surface-2" />
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="h-16 rounded bg-surface-2" />
          <div className="h-16 rounded bg-surface-2" />
          <div className="h-16 rounded bg-surface-2" />
          <div className="h-16 rounded bg-surface-2" />
        </div>
      </div>
    );
  }

  if (isError || !workload) {
    return null;
  }

  const {
    total_workload_hours = 0,
    completed_workload_hours = 0,
    remaining_workload_hours = 0,
    capacity_hours = 8,
    capacity_utilization_pct = 0,
    workload_status = "balanced",
    overdue_tasks_count = 0,
    high_risk_tasks_count = 0,
    upcoming_deadlines_count = 0,
    overdue_tasks = [],
    high_risk_tasks = [],
    scheduled_timeline = [],
  } = workload;

  // Capacity color determination
  const capacityColor =
    capacity_utilization_pct > 100
      ? "text-red-400 bg-red-500"
      : capacity_utilization_pct > 80
      ? "text-amber-400 bg-amber-500"
      : "text-emerald-400 bg-emerald-500";

  return (
    <div className="mb-6 rounded-2xl border border-border-subtle bg-surface-1 p-5 shadow-sm transition-all hover:border-border">
      {/* Header Row */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-content-primary">Daily Workload & Time Management</h2>
            <Badge
              tone={
                workload_status === "overloaded"
                  ? "error"
                  : workload_status === "near_capacity"
                  ? "warning"
                  : "success"
              }
              className="capitalize"
            >
              {workload_status.replace("_", " ")}
            </Badge>
          </div>
          <p className="mt-0.5 text-xs text-content-tertiary">
            Autonomous time allocation, non-overlapping task windows, and live deadline risk tracking.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            leftIcon={<Sparkles className="size-3.5 text-primary" />}
            onClick={handleAllocate}
            isLoading={allocateMutation.isPending}
            title="Automatically schedule pending tasks into non-overlapping hours"
          >
            Auto Schedule
          </Button>
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<RefreshCw className="size-3.5" />}
            onClick={handleReschedule}
            isLoading={rescheduleMutation.isPending}
            title="Recalculate remaining schedule and resolve pending conflicts"
          >
            Reschedule
          </Button>
        </div>
      </div>

      {/* Overdue / High Risk Alerts Banner */}
      {(overdue_tasks_count > 0 || high_risk_tasks_count > 0) && (
        <div className="mt-4 flex flex-col gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3.5 text-xs text-red-300">
          {overdue_tasks_count > 0 && (
            <div className="flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0 text-red-400" />
              <span>
                <strong>{overdue_tasks_count} overdue task(s):</strong>{" "}
                {overdue_tasks.map((t: any) => t.title).slice(0, 3).join(", ")}
                {overdue_tasks.length > 3 && ` +${overdue_tasks.length - 3} more`}
              </span>
            </div>
          )}
          {high_risk_tasks_count > 0 && (
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 shrink-0 text-amber-400" />
              <span className="text-amber-200">
                <strong>{high_risk_tasks_count} high-risk task(s):</strong>{" "}
                {high_risk_tasks.map((t: any) => t.title).slice(0, 3).join(", ")}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Metric Cards Row */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {/* Total Workload */}
        <div className="rounded-xl border border-border-subtle bg-surface-2/60 p-3.5">
          <span className="text-[11px] font-medium uppercase tracking-wider text-content-tertiary">Total Scheduled</span>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-bold text-content-primary">{total_workload_hours.toFixed(1)}h</span>
            <span className="text-xs text-content-muted">today</span>
          </div>
          <div className="mt-2 text-[11px] text-content-tertiary">
            Capacity: {capacity_hours.toFixed(1)}h limit
          </div>
        </div>

        {/* Completed Workload */}
        <div className="rounded-xl border border-border-subtle bg-surface-2/60 p-3.5">
          <span className="text-[11px] font-medium uppercase tracking-wider text-content-tertiary">Completed</span>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-bold text-emerald-400">{completed_workload_hours.toFixed(1)}h</span>
            <span className="text-xs text-content-muted">done</span>
          </div>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-emerald-400">
            <CheckCircle2 className="size-3" />
            <span>Outcomes verified</span>
          </div>
        </div>

        {/* Remaining Workload */}
        <div className="rounded-xl border border-border-subtle bg-surface-2/60 p-3.5">
          <span className="text-[11px] font-medium uppercase tracking-wider text-content-tertiary">Remaining</span>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-bold text-sky-400">{remaining_workload_hours.toFixed(1)}h</span>
            <span className="text-xs text-content-muted">pending</span>
          </div>
          <div className="mt-2 text-[11px] text-content-tertiary">
            {upcoming_deadlines_count} upcoming deadline(s)
          </div>
        </div>

        {/* Capacity Utilization Meter */}
        <div className="rounded-xl border border-border-subtle bg-surface-2/60 p-3.5">
          <span className="text-[11px] font-medium uppercase tracking-wider text-content-tertiary">Capacity Usage</span>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className={cn("text-xl font-bold", capacityColor.split(" ")[0])}>
              {capacity_utilization_pct.toFixed(0)}%
            </span>
            <span className="text-xs text-content-muted">of {capacity_hours.toFixed(1)}h</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
            <div
              className={cn("h-full rounded-full transition-all", capacityColor.split(" ")[1])}
              style={{ width: `${Math.min(100, capacity_utilization_pct)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Cognitive Energy & Fatigue Budget Banner */}
      {workload.cognitive_budget && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/20 bg-primary/5 p-3 text-xs">
          <div className="flex items-center gap-2">
            <Zap className="size-4 text-primary" />
            <div>
              <span className="font-semibold text-content-primary">Cognitive Energy Budget:</span>{" "}
              <span className="text-content-secondary">
                {workload.cognitive_budget.deep_work_hours}h / {workload.cognitive_budget.sustainable_limit_hours}h sustainable deep work limit
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              tone={
                workload.cognitive_budget.fatigue_risk === "high"
                  ? "error"
                  : workload.cognitive_budget.fatigue_risk === "moderate"
                  ? "warning"
                  : "success"
              }
              className="capitalize text-[10px]"
            >
              Fatigue Risk: {workload.cognitive_budget.fatigue_risk}
            </Badge>
            <span className="text-[11px] text-content-muted">
              ({workload.cognitive_budget.cognitive_utilization_pct}% loaded)
            </span>
          </div>
        </div>
      )}

      {/* Visual Timeline / Gantt Schedule Preview */}
      {scheduled_timeline.length > 0 && (
        <div className="mt-5 border-t border-border-subtle pt-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-medium text-content-secondary">Today's Scheduled Timeline (08:00 – 20:00)</span>
            <span className="text-[11px] text-content-muted">{scheduled_timeline.length} slot(s) assigned</span>
          </div>

          <div className="relative flex flex-col gap-1.5 rounded-xl border border-border-subtle bg-surface-2/30 p-3">
            {/* Hour marker ruler */}
            <div className="flex justify-between text-[10px] text-content-muted">
              <span>08:00</span>
              <span>10:00</span>
              <span>12:00</span>
              <span>14:00</span>
              <span>16:00</span>
              <span>18:00</span>
              <span>20:00</span>
            </div>

            {/* Timeline bars */}
            <div className="space-y-1.5 pt-1">
              {scheduled_timeline.slice(0, 5).map((item: any, idx: number) => {
                const sHour = item.scheduled_hour ?? 8;
                const eHour = item.scheduled_end_hour ?? sHour + 1;
                // Range 8 to 20 = 12 hours total
                const leftPct = Math.max(0, Math.min(100, ((sHour - 8) / 12) * 100));
                const widthPct = Math.max(8, Math.min(100 - leftPct, ((eHour - sHour) / 12) * 100));

                const isCompleted = item.completed;
                const isOverdue = item.is_overdue;

                return (
                  <div key={item.id ?? idx} className="relative h-6 w-full rounded bg-surface-3/50">
                    <div
                      className={cn(
                        "absolute inset-y-0 flex items-center rounded px-2 text-[10px] font-medium transition-all",
                        isCompleted
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                          : isOverdue
                          ? "bg-red-500/20 text-red-300 border border-red-500/40"
                          : "bg-primary/20 text-primary border border-primary/40"
                      )}
                      style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                      title={`${item.title} (${item.start_time ?? `${sHour}:00`} – ${item.end_time ?? `${eHour}:00`})`}
                    >
                      <span className="truncate">{item.title}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
