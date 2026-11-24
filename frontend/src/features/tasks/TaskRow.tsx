import * as React from "react";
import { motion } from "framer-motion";
import { AlertCircle, AlertTriangle, Calendar, CheckCheck, Clock3, Link2, MessageSquarePlus, Pencil, Play, RotateCcw, Star, Target, Timer } from "lucide-react";
import type { Task, Goal } from "@/api/endpoints";
import { isAlreadyCompletedError, isAlreadyStartedError, useCompleteTask, useStartTask } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Toaster";
import { formatDuration } from "@/utils/formatters";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  durationRatio,
  elapsedMinutes,
  formatDeadlineCountdown,
  formatScheduledSlot,
  getTaskRiskMeta,
  hasFeedback,
  lifecycle,
  LIFECYCLE_META,
  priorityMeta,
} from "./taskUtils";

function useNow(intervalMs: number, enabled: boolean) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, enabled]);
  return now;
}

const stateRail: Record<string, string> = {
  created: "bg-content-muted/40",
  started: "bg-primary",
  completed: "bg-status-success",
  unknown: "bg-status-warning",
};

interface TaskRowProps {
  task: Task;
  onRequestFeedback: (task: Task) => void;
  onEdit?: (task: Task) => void;
  goal?: Goal;
  allTasks?: Task[];
  compact?: boolean;
}

export function TaskRow({ task, onRequestFeedback, onEdit, goal, allTasks, compact }: TaskRowProps) {
  const state = lifecycle(task);
  const startTask = useStartTask();
  const completeTask = useCompleteTask();
  const now = useNow(30_000, state === "started");
  const pending = startTask.isPending || completeTask.isPending;
  const priority = priorityMeta(task.priority);

  const onStart = () =>
    startTask.mutate(
      { taskId: task.id, data: {} },
      {
        onSuccess: () => toast("info", "Task started", "The clock is running — complete it when you're done."),
        onError: (error) => {
          if (isAlreadyStartedError(error)) {
            startTask.reset();
            toast("info", "Already started", "This task was already in progress; the list has been refreshed.");
          } else toast("error", "Couldn't start task", getApiErrorMessage(error));
        },
      }
    );

  const onComplete = () =>
    completeTask.mutate(
      { taskId: task.id, data: {} },
      {
        onSuccess: (response) => {
          const updated = (response.result?.task as Task | undefined) ?? task;
          onRequestFeedback({ ...task, ...updated });
        },
        onError: (error) => {
          if (isAlreadyCompletedError(error)) {
            completeTask.reset();
            toast("info", "Already completed", "The list has been refreshed.");
          } else toast("error", "Couldn't complete task", getApiErrorMessage(error));
        },
      }
    );

  const ratio = durationRatio(task);
  const elapsed = state === "started" ? elapsedMinutes(task, now) : null;
  const rated = hasFeedback(task);

  // Deadline & Countdown calculation
  const deadlineDt = task.deadline ? new Date(task.deadline) : null;
  const isOverdue =
    deadlineDt !== null &&
    !isNaN(deadlineDt.getTime()) &&
    state !== "completed" &&
    deadlineDt.getTime() < now;
  const countdown = formatDeadlineCountdown(task.deadline, now);
  const scheduledSlot = formatScheduledSlot(task.scheduled_start_time, task.scheduled_end_time);
  const riskMeta = getTaskRiskMeta(task, isOverdue);

  // Dependencies check
  const dependencyIds = React.useMemo(() => {
    if (!task.dependencies) return [];
    if (Array.isArray(task.dependencies)) return task.dependencies.map(Number).filter(Boolean);
    return [];
  }, [task.dependencies]);

  const hasIncompleteDependencies = React.useMemo(() => {
    if (!dependencyIds.length || !allTasks) return false;
    const taskMap = new Map(allTasks.map((t) => [t.id, t]));
    return dependencyIds.some((did) => {
      const dep = taskMap.get(did);
      return dep && !dep.completed;
    });
  }, [dependencyIds, allTasks]);

  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={cn(
        "group relative flex flex-col gap-3 overflow-hidden rounded-xl border border-border-subtle bg-surface-1 py-3.5 pl-5 pr-4 transition-colors hover:border-border dark:border-border dark:hover:border-content-muted/30 sm:flex-row sm:items-center",
        compact && "py-3"
      )}
    >
      <span className={cn("absolute inset-y-3 left-0 w-[3px] rounded-r-full", stateRail[state])} />

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className={cn("truncate text-sm font-medium", state === "completed" ? "text-content-secondary" : "text-content-primary")}>
            {task.title}
          </p>
          {state === "started" && <Badge tone="primary" dot pulse>{LIFECYCLE_META.started.label}</Badge>}
          {state === "unknown" && <Badge tone="warning">{LIFECYCLE_META.unknown.label}</Badge>}

          {/* Goal badge */}
          {goal && (
            <Badge tone="primary" className="inline-flex items-center gap-1 font-normal text-[11px]">
              <Target className="size-2.5" />
              {goal.title}
            </Badge>
          )}

          {/* Scheduled time slot badge */}
          {scheduledSlot && (
            <Badge tone="primary" className="inline-flex items-center gap-1 text-[11px] font-mono bg-sky-500/10 text-sky-400 border-sky-500/30">
              <Clock3 className="size-2.5" />
              {scheduledSlot}
            </Badge>
          )}

          {/* Deadline risk indicator (Green/Amber/Red/Blue) */}
          {riskMeta.level !== "none" && state !== "completed" && (
            <Badge
              tone={riskMeta.tone}
              className={cn("inline-flex items-center gap-1 text-[11px] font-medium border", riskMeta.badgeClass)}
              title={task.deadline_risk?.reasons?.[0] || riskMeta.label}
            >
              {riskMeta.level === "overdue" || riskMeta.level === "high" ? (
                <AlertCircle className="size-2.5" />
              ) : riskMeta.level === "moderate" ? (
                <AlertTriangle className="size-2.5" />
              ) : (
                <Timer className="size-2.5" />
              )}
              {riskMeta.label}
            </Badge>
          )}

          {/* Live Deadline & Countdown badge */}
          {countdown && (
            <Badge
              tone={countdown.isOverdue ? "error" : "neutral"}
              className={cn(
                "inline-flex items-center gap-1 text-[11px]",
                countdown.isOverdue ? "font-semibold text-red-400 bg-red-500/10 border-red-500/30" : "text-content-secondary"
              )}
              title={`Deadline: ${countdown.formattedDeadline}`}
            >
              <Calendar className="size-2.5" />
              <span>{countdown.countdownText}</span>
              <span className="text-[10px] opacity-70">({countdown.formattedDeadline})</span>
            </Badge>
          )}

          {/* Dynamic Priority Score */}
          {task.dynamic_priority != null && state !== "completed" && (
            <Badge
              tone={task.dynamic_priority >= 70 ? "primary" : task.dynamic_priority >= 45 ? "warning" : "neutral"}
              className="inline-flex items-center gap-1 text-[10px] font-mono"
              title={task.recommended_action || `Dynamic Priority: ${task.dynamic_priority}/100`}
            >
              <span>Score: {task.dynamic_priority}</span>
            </Badge>
          )}

          {/* Reschedule count indicator */}
          {task.reschedule_count != null && task.reschedule_count > 0 && (
            <Badge tone="outline" className="inline-flex items-center gap-1 text-[10px] text-content-tertiary" title="Intelligently rescheduled">
              <RotateCcw className="size-2.5" />
              {task.reschedule_count}×
            </Badge>
          )}

          {/* Dependency status badge */}
          {(task.is_blocked || hasIncompleteDependencies) && state !== "completed" && (
            <Badge tone="error" className="inline-flex items-center gap-1 text-[10px] bg-red-500/10 text-red-400 border-red-500/30">
              <Link2 className="size-2.5" />
              Blocked
            </Badge>
          )}

          {/* Bottleneck badge (blocks downstream tasks) */}
          {task.blocking_count != null && task.blocking_count > 0 && state !== "completed" && (
            <Badge tone="warning" className="inline-flex items-center gap-1 text-[10px]" title={`Completing this unblocks ${task.blocking_count} dependent task(s)`}>
              <Link2 className="size-2.5" />
              Blocks {task.blocking_count}
            </Badge>
          )}
        </div>

        {task.description && (
          <p className="mt-0.5 line-clamp-1 text-xs text-content-tertiary">
            {task.description}
          </p>
        )}

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-content-tertiary">
          <span className="capitalize">{task.task_type}</span>
          <span className="inline-flex items-center gap-1">
            <Clock3 className="size-3" />
            {state === "completed" && typeof task.actual_duration === "number" ? (
              <>
                <span className="tabular text-content-secondary">{formatDuration(task.actual_duration)}</span>
                <span className="text-content-muted">/ {formatDuration(task.estimated_duration)} est.</span>
                {ratio !== null && (
                  <span className={cn("tabular font-medium", ratio > 1.15 ? "text-status-warning" : ratio < 0.85 ? "text-quantum" : "text-status-success")}>
                    ×{ratio.toFixed(2)}
                  </span>
                )}
              </>
            ) : elapsed !== null ? (
              <span className="tabular text-primary">{formatDuration(elapsed)} elapsed · {formatDuration(task.estimated_duration)} est.</span>
            ) : (
              <span className="tabular">{formatDuration(task.estimated_duration)}</span>
            )}
          </span>
          {!compact && <span>Created {formatRelative(task.created_at)}</span>}
          {rated && (
            <span className="inline-flex items-center gap-1 text-content-secondary" title="Focus · Energy · Productivity">
              <Star className="size-3 fill-primary text-primary" />
              <span className="tabular">{task.focus_rating}·{task.energy_rating}·{task.productivity_rating}</span>
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 sm:justify-end">
        <Badge tone={priority.tone} className="font-mono">P{task.priority} · {priority.label}</Badge>
        {onEdit && state !== "completed" && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onEdit(task)}
            aria-label={`Edit ${task.title}`}
            className="text-content-tertiary hover:text-content-primary"
          >
            <Pencil className="size-3.5" />
          </Button>
        )}
        {state === "created" && (
          <Button size="sm" variant="secondary" leftIcon={<Play />} onClick={onStart} isLoading={startTask.isPending} disabled={pending} aria-label={`Start ${task.title}`}>
            Start
          </Button>
        )}
        {state === "started" && (
          <Button size="sm" leftIcon={<CheckCheck />} onClick={onComplete} isLoading={completeTask.isPending} disabled={pending} aria-label={`Complete ${task.title}`}>
            Complete
          </Button>
        )}
        {state === "completed" && (
          <Button size="sm" variant={rated ? "ghost" : "outline"} leftIcon={<MessageSquarePlus />} onClick={() => onRequestFeedback(task)} aria-label={`${rated ? "Edit" : "Add"} feedback for ${task.title}`}>
            {rated ? "Edit" : "Feedback"}
          </Button>
        )}
      </div>
    </motion.li>
  );
}
