import * as React from "react";
import { Play, Check, Clock } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useStartTask, useCompleteTask } from "@/api/hooks";
import { Task } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";

interface TaskRowProps {
  task: Task;
}

export function TaskRow({ task }: TaskRowProps) {
  const startMutation = useStartTask();
  const completeMutation = useCompleteTask();
  const { mutate: startTask, isPending: isStarting } = startMutation;
  const { mutate: completeTask, isPending: isCompleting } = completeMutation;

  const handleStart = () => {
    startTask({ taskId: task.id, data: {} });
  };

  const handleComplete = () => {
    completeTask({ taskId: task.id, data: {} });
  };

  const isPending = isStarting || isCompleting;

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 5: return "bg-red-500/10 text-red-500 border-red-500/20";
      case 4: return "bg-orange-500/10 text-orange-500 border-orange-500/20";
      case 3: return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
      case 2: return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case 1:
      default:
        return "bg-content-secondary/10 text-content-secondary border-border";
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
    if (minutes < 60) return `${minutes} min`;
    const h = Math.floor(minutes / 60);
    const m = Math.round(minutes % 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  };

  const estimatedDuration = task.estimated_duration === null
    ? "N/A"
    : task.estimated_duration_unit === "minutes"
      ? formatDuration(task.estimated_duration)
      : task.estimated_duration_unit === "hours"
        ? `${task.estimated_duration} h`
        : `${task.estimated_duration} (unit unknown)`;
  const actualDurationUnitVerified = task.outcome_valid === true
    && task.lifecycle_state === "completed"
    && task.start_time !== null
    && task.end_time !== null;
  const mutationError = startMutation.error ?? completeMutation.error;

  return (
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
          {task.lifecycle_state === "completed" && (
            <Badge variant="success">Completed</Badge>
          )}
          {task.lifecycle_state === "started" && (
            <Badge variant="default" className="bg-primary/10 text-primary">In Progress</Badge>
          )}
          {task.lifecycle_state === null && <Badge variant="outline">Lifecycle unknown</Badge>}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-content-secondary">
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            <span>Est: {estimatedDuration}</span>
          </div>
          {task.estimated_duration_source && (
            <span className="text-xs text-content-tertiary">Estimate source: {task.estimated_duration_source}</span>
          )}
          {task.actual_duration !== null && (
            <div className="flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5" />
              <span>{actualDurationUnitVerified
                ? `Actual: ${formatDuration(task.actual_duration)}`
                : `Actual duration recorded; unit unverified: ${task.actual_duration}`}</span>
            </div>
          )}
        </div>
        {mutationError && (
          <p role="alert" className="text-sm text-status-error">
            {getApiErrorMessage(mutationError, "Task update failed.")}
          </p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {task.lifecycle_state === "created" && (
          <Button
            size="sm"
            variant="secondary"
            onClick={handleStart}
            disabled={isPending}
            isLoading={isStarting}
          >
            <Play className="mr-1.5 h-3.5 w-3.5" />
            Start
          </Button>
        )}

        {task.lifecycle_state === "started" && (
          <Button
            size="sm"
            variant="primary"
            onClick={handleComplete}
            disabled={isPending}
            isLoading={isCompleting}
          >
            <Check className="mr-1.5 h-3.5 w-3.5" />
            Complete
          </Button>
        )}
      </div>
    </Card>
  );
}
