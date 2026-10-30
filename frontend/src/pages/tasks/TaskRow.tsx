import * as React from "react";
import { Play, Check, Clock, Star, MessageSquarePlus } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useStartTask, useCompleteTask, isAlreadyStartedError, isAlreadyCompletedError } from "@/api/hooks";
import { Task } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { formatLocalTime } from "@/utils/formatters";
import { TaskFeedbackModal } from "./TaskFeedbackModal";

interface TaskRowProps {
  task: Task;
}

export function TaskRow({ task }: TaskRowProps) {
  const startMutation = useStartTask();
  const completeMutation = useCompleteTask();
  const { mutate: startTask, isPending: isStarting } = startMutation;
  const { mutate: completeTask, isPending: isCompleting } = completeMutation;
  const [isFeedbackOpen, setIsFeedbackOpen] = React.useState(false);

  const isCompleted =
    Boolean(task.completed) ||
    task.lifecycle_state === "completed";

  const isStarted =
    !isCompleted &&
    (task.lifecycle_state === "started" || Boolean(task.start_time));

  const isPendingState =
    !isCompleted &&
    !isStarted;

  const handleStart = () => {
    startTask(
      { taskId: task.id, data: {} },
      {
        onError: (error) => {
          if (isAlreadyStartedError(error)) {
            startMutation.reset();
          }
        },
      }
    );
  };

  const handleComplete = () => {
    completeTask(
      { taskId: task.id, data: {} },
      {
        onSuccess: () => {
          setIsFeedbackOpen(true);
        },
        onError: (error) => {
          if (isAlreadyCompletedError(error)) {
            completeMutation.reset();
          }
        },
      }
    );
  };

  const isActionPending = isStarting || isCompleting;

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 5: return "bg-status-error/15 text-status-error border-status-error/30";
      case 4: return "bg-status-warning/15 text-status-warning border-status-warning/30";
      case 3: return "bg-primary/15 text-primary border-primary/30";
      case 2: return "bg-surface-3 text-content-secondary border-border/70";
      case 1:
      default:
        return "bg-surface-2 text-content-tertiary border-border/50";
    }
  };

  const getPriorityLabel = (priority: number) => {
    switch (priority) {
      case 5: return "Critical";
      case 4: return "High";
      case 3: return "Medium";
      case 2: return "Normal";
      case 1:
      default:
        return "Low";
    }
  };

  const formatDuration = (minutes: number | null | undefined) => {
    if (minutes === null || minutes === undefined) return "N/A";
    if (!Number.isFinite(minutes)) return "Unavailable";
    const magnitude = Math.round(Math.abs(minutes) * 10) / 10;
    const sign = minutes < 0 ? "-" : "";
    const formatNumber = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(1);
    if (magnitude < 60) return `${sign}${formatNumber(magnitude)} min`;
    const h = Math.floor(magnitude / 60);
    const m = Math.round((magnitude % 60) * 10) / 10;
    return m > 0 ? `${sign}${h}h ${formatNumber(m)}m` : `${sign}${h}h`;
  };

  const estimatedDuration = task.estimated_duration === null
    ? "N/A"
    : task.estimated_duration_unit === "minutes"
      ? formatDuration(task.estimated_duration)
      : task.estimated_duration_unit === "hours"
        ? `${task.estimated_duration} h`
        : `${task.estimated_duration} (unit unknown)`;

  const actualDurationUnitVerified = task.outcome_valid === true
    && isCompleted
    && task.start_time !== null
    && task.end_time !== null;

  const estimateActualDelta = actualDurationUnitVerified
    && task.estimated_duration_unit === "minutes"
    && typeof task.estimated_duration === "number"
    && Number.isFinite(task.estimated_duration)
    && typeof task.actual_duration === "number"
    && Number.isFinite(task.actual_duration)
    ? task.actual_duration - task.estimated_duration
    : null;

  const hasFeedback =
    task.focus_rating !== null &&
    task.focus_rating !== undefined &&
    task.productivity_rating !== null &&
    task.productivity_rating !== undefined;

  const startTimeFormatted = task.start_time
    ? formatLocalTime(task.start_time)
    : null;

  const mutationError =
    (startMutation.error && !isAlreadyStartedError(startMutation.error) ? startMutation.error : null) ??
    (completeMutation.error && !isAlreadyCompletedError(completeMutation.error) ? completeMutation.error : null);

  return (
    <>
      <Card className="flex flex-col gap-3 p-4 transition-colors hover:bg-surface-2/50 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h3 className="text-base font-medium text-content-primary">
              {task.title}
            </h3>
            <Badge variant="outline" className={getPriorityColor(task.priority)}>
              P{task.priority}: {getPriorityLabel(task.priority)}
            </Badge>
            <Badge variant="secondary">
              {task.task_type}
            </Badge>
            {isCompleted && (
              <Badge variant="success" className="gap-1">
                ✓ Completed
              </Badge>
            )}
            {isStarted && (
              <Badge variant="default" className="bg-primary/10 text-primary border-primary/20">
                ● In progress
              </Badge>
            )}
            {isPendingState && (
              <Badge variant="outline" className="text-content-secondary border-border">
                ○ Pending
              </Badge>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-content-secondary">
            {isPendingState && (
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                <span>Estimate: {estimatedDuration}</span>
              </div>
            )}
            {isStarted && (
              <>
                <div className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-primary" />
                  <span>Started: {startTimeFormatted ?? "Recently"}</span>
                </div>
                <span>Est: {estimatedDuration}</span>
              </>
            )}
            {isCompleted && (
              <>
                <div className="flex items-center gap-1.5">
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span>
                    {actualDurationUnitVerified
                      ? `Actual: ${formatDuration(task.actual_duration)}`
                      : `Actual: ${task.actual_duration ?? "Recorded"} (unverified)`}
                  </span>
                </div>
                <span>Est: {estimatedDuration}</span>
                {estimateActualDelta !== null && (
                  <span aria-label="Actual minus estimated duration">
                    Diff: {estimateActualDelta > 0 ? "+" : ""}{formatDuration(estimateActualDelta)}
                  </span>
                )}
                <span className="font-medium text-content-secondary">
                  Feedback:{" "}
                  {hasFeedback ? (
                    <span className="text-emerald-400 font-normal">
                      Recorded ({task.productivity_rating}★ · {Math.round(((task.productivity_rating ?? 1) - 1) * 25)}/100 self-reported)
                    </span>
                  ) : (
                    <span className="text-content-tertiary font-normal">Not provided</span>
                  )}
                </span>
              </>
            )}
            {task.estimated_duration_source && (
              <span className="text-xs text-content-tertiary">Source: {task.estimated_duration_source}</span>
            )}
          </div>
          {mutationError && (
            <p role="alert" className="text-sm text-status-error">
              {getApiErrorMessage(mutationError, "Task update failed.")}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {isPendingState && (
            <Button
              size="sm"
              variant="secondary"
              onClick={handleStart}
              disabled={isActionPending}
              isLoading={isStarting}
            >
              <Play className="mr-1.5 h-3.5 w-3.5" />
              Start
            </Button>
          )}

          {isStarted && (
            <Button
              size="sm"
              variant="primary"
              onClick={handleComplete}
              disabled={isActionPending}
              isLoading={isCompleting}
            >
              <Check className="mr-1.5 h-3.5 w-3.5" />
              Complete
            </Button>
          )}

          {isCompleted && (
            <Button
              size="sm"
              variant={hasFeedback ? "ghost" : "secondary"}
              onClick={() => setIsFeedbackOpen(true)}
              className="gap-1.5"
            >
              {hasFeedback ? (
                <>
                  <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                  View Outcome
                </>
              ) : (
                <>
                  <MessageSquarePlus className="h-3.5 w-3.5" />
                  Add Feedback
                </>
              )}
            </Button>
          )}
        </div>
      </Card>

      {isFeedbackOpen && (
        <TaskFeedbackModal
          isOpen={isFeedbackOpen}
          onClose={() => setIsFeedbackOpen(false)}
          task={task}
        />
      )}
    </>
  );
}
