import * as React from "react";
import type { Task } from "@/api/endpoints";
import { useUpdateTask, useDeleteTask, useGoals, useTasks } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Dialog } from "@/components/ui/Dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Toaster";
import { cn } from "@/lib/utils";
import { PRIORITY_META, TASK_TYPE_SUGGESTIONS } from "./taskUtils";
import { Trash2 } from "lucide-react";

export function TaskEditDialog({
  task,
  isOpen,
  onClose,
}: {
  task: Task | null;
  isOpen: boolean;
  onClose: () => void;
}) {
  const updateTask = useUpdateTask();
  const deleteTask = useDeleteTask();
  const goalsQuery = useGoals();
  const tasksQuery = useTasks();

  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [taskType, setTaskType] = React.useState("work");
  const [priority, setPriority] = React.useState(3);
  const [duration, setDuration] = React.useState("60");
  const [deadlinestr, setDeadlinestr] = React.useState("");
  const [goalId, setGoalId] = React.useState("");
  const [selectedDependencies, setSelectedDependencies] = React.useState<number[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = React.useState(false);

  const activeGoals = React.useMemo(() => goalsQuery.data?.goals ?? [], [goalsQuery.data]);
  const otherTasks = React.useMemo(
    () => (tasksQuery.data?.tasks ?? []).filter((t) => task && t.id !== task.id),
    [tasksQuery.data, task]
  );

  React.useEffect(() => {
    if (task && isOpen) {
      setTitle(task.title || "");
      setDescription(task.description || "");
      setTaskType(task.task_type || "work");
      setPriority(task.priority || 3);
      setDuration(String(task.estimated_duration || 60));
      setGoalId(task.goal_id ? String(task.goal_id) : "");
      
      // format deadline for datetime-local input YYYY-MM-DDTHH:mm
      if (task.deadline) {
        try {
          const d = new Date(task.deadline);
          const localIso = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
            .toISOString()
            .slice(0, 16);
          setDeadlinestr(localIso);
        } catch {
          setDeadlinestr("");
        }
      } else {
        setDeadlinestr("");
      }

      // dependencies
      if (Array.isArray(task.dependencies)) {
        setSelectedDependencies(task.dependencies.map(Number).filter(Boolean));
      } else {
        setSelectedDependencies([]);
      }

      setError(null);
      setConfirmDelete(false);
      updateTask.reset();
      deleteTask.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task, isOpen]);

  if (!task) return null;

  const toggleDependency = (id: number) => {
    setSelectedDependencies((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const minutes = Number(duration);
    if (!title.trim()) return setError("Give the task a title.");
    if (!taskType.trim()) return setError("Choose or type a task type.");
    if (!Number.isFinite(minutes) || minutes <= 0)
      return setError("Estimated duration must be a positive number of minutes.");
    setError(null);

    let formattedDeadline: string | undefined = undefined;
    const clearDeadline = !deadlinestr.trim() && Boolean(task.deadline);
    if (deadlinestr.trim()) {
      try {
        const d = new Date(deadlinestr);
        if (isNaN(d.getTime())) return setError("Invalid deadline date/time.");
        formattedDeadline = d.toISOString();
      } catch {
        return setError("Invalid deadline format.");
      }
    }

    const clearGoal = !goalId && Boolean(task.goal_id);
    const clearDependencies = selectedDependencies.length === 0 && Boolean(task.dependencies?.length);

    updateTask.mutate(
      {
        taskId: task.id,
        data: {
          title: title.trim(),
          description: description.trim() || undefined,
          task_type: taskType.trim().toLowerCase(),
          priority,
          estimated_duration: minutes,
          estimated_duration_unit: "minutes",
          deadline: formattedDeadline,
          clear_deadline: clearDeadline,
          goal_id: goalId ? Number(goalId) : undefined,
          clear_goal: clearGoal,
          dependencies: selectedDependencies,
          clear_dependencies: clearDependencies,
        },
      },
      {
        onSuccess: () => {
          toast("success", "Task updated", `“${title.trim()}” was updated.`);
          onClose();
        },
        onError: (err) => setError(getApiErrorMessage(err)),
      }
    );
  };

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }

    deleteTask.mutate(task.id, {
      onSuccess: () => {
        toast("info", "Task deleted", `“${task.title}” was removed.`);
        onClose();
      },
      onError: (err) => setError(getApiErrorMessage(err)),
    });
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Edit Task"
      description={`Update properties, deadline, goal alignment, or prerequisites for #${task.id}.`}
      footer={
        <div className="flex w-full items-center justify-between">
          <Button
            type="button"
            variant="danger"
            size="sm"
            onClick={handleDelete}
            isLoading={deleteTask.isPending}
            disabled={updateTask.isPending}
            leftIcon={<Trash2 className="size-3.5" />}
          >
            {confirmDelete ? "Confirm delete?" : "Delete"}
          </Button>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose} disabled={updateTask.isPending || deleteTask.isPending}>
              Cancel
            </Button>
            <Button type="submit" form="task-edit-form" isLoading={updateTask.isPending} disabled={deleteTask.isPending}>
              Save changes
            </Button>
          </div>
        </div>
      }
    >
      <form id="task-edit-form" onSubmit={submit} className="space-y-4 max-h-[75vh] overflow-y-auto pr-1" noValidate>
        <Field label="Title" htmlFor="edit-task-title">
          <Input
            id="edit-task-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={255}
            required
          />
        </Field>

        <Field label="Description / Context" htmlFor="edit-task-description" optional>
          <Textarea
            id="edit-task-description"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Add relevant context or notes..."
          />
        </Field>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Type" htmlFor="edit-task-type">
            <Input
              id="edit-task-type"
              list="edit-task-type-options"
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
              maxLength={100}
              required
            />
            <datalist id="edit-task-type-options">
              {TASK_TYPE_SUGGESTIONS.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
          </Field>

          <Field label="Associated Goal" htmlFor="edit-task-goal" optional>
            <Select
              id="edit-task-goal"
              value={goalId}
              onChange={(e) => setGoalId(e.target.value)}
            >
              <option value="">None (Independent task)</option>
              {activeGoals.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.title} (P{g.priority})
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Deadline" htmlFor="edit-task-deadline" optional hint="Earliest Deadline First (EDF)">
            <Input
              id="edit-task-deadline"
              type="datetime-local"
              value={deadlinestr}
              onChange={(e) => setDeadlinestr(e.target.value)}
            />
          </Field>

          <Field label="Estimated duration (minutes)" htmlFor="edit-task-duration">
            <Input
              id="edit-task-duration"
              type="number"
              min={1}
              step={5}
              inputMode="numeric"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              required
            />
          </Field>
        </div>

        <fieldset className="space-y-1.5">
          <legend className="text-[13px] font-medium text-content-secondary">Priority (1-5)</legend>
          <div className="grid grid-cols-5 gap-1.5">
            {[1, 2, 3, 4, 5].map((p) => (
              <button
                key={p}
                type="button"
                aria-pressed={priority === p}
                onClick={() => setPriority(p)}
                className={cn(
                  "flex flex-col items-center rounded-lg border py-2 text-xs transition-colors",
                  priority === p
                    ? "border-primary/50 bg-primary/10 text-content-primary"
                    : "border-border text-content-tertiary hover:bg-surface-2"
                )}
              >
                <span className="font-mono text-sm font-semibold">P{p}</span>
                <span className="mt-0.5 text-[10px]">{PRIORITY_META[p].label}</span>
              </button>
            ))}
          </div>
        </fieldset>

        {otherTasks.length > 0 && (
          <fieldset className="space-y-1.5">
            <legend className="text-[13px] font-medium text-content-secondary">
              Prerequisites / Dependencies
            </legend>
            <div className="max-h-36 overflow-y-auto space-y-1 rounded-lg border border-border p-2">
              {otherTasks.map((t) => (
                <label
                  key={t.id}
                  className={cn(
                    "flex items-center gap-2 rounded px-2 py-1 text-xs cursor-pointer transition-colors",
                    selectedDependencies.includes(t.id)
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-content-secondary hover:bg-surface-2"
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedDependencies.includes(t.id)}
                    onChange={() => toggleDependency(t.id)}
                    className="size-3.5 rounded border-border text-primary focus:ring-primary/20"
                  />
                  <span className="truncate flex-1">{t.title}</span>
                  <span className="text-[10px] text-content-muted font-mono">P{t.priority}</span>
                </label>
              ))}
            </div>
          </fieldset>
        )}

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-status-error/25 bg-status-error/[0.06] px-3 py-2 text-[13px] text-status-error"
          >
            {error}
          </p>
        )}
      </form>
    </Dialog>
  );
}
