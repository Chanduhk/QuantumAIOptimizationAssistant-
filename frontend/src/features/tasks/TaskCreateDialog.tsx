import * as React from "react";
import { useCreateTask, useGoals, useTasks } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Dialog } from "@/components/ui/Dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Toaster";
import { cn } from "@/lib/utils";
import { PRIORITY_META, TASK_TYPE_SUGGESTIONS } from "./taskUtils";

const DURATION_PRESETS = [15, 30, 45, 60, 90, 120];

export function TaskCreateDialog({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const createTask = useCreateTask();
  const goalsQuery = useGoals("active");
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

  const activeGoals = React.useMemo(() => goalsQuery.data?.goals ?? [], [goalsQuery.data]);
  const availableTasks = React.useMemo(
    () => (tasksQuery.data?.tasks ?? []).filter((t) => !t.completed),
    [tasksQuery.data]
  );

  React.useEffect(() => {
    if (isOpen) {
      setTitle("");
      setDescription("");
      setTaskType("work");
      setPriority(3);
      setDuration("60");
      setDeadlinestr("");
      setGoalId("");
      setSelectedDependencies([]);
      setError(null);
      createTask.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

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
    if (deadlinestr.trim()) {
      try {
        const d = new Date(deadlinestr);
        if (isNaN(d.getTime())) return setError("Invalid deadline date/time.");
        formattedDeadline = d.toISOString();
      } catch {
        return setError("Invalid deadline format.");
      }
    }

    const payload: {
      title: string;
      task_type: string;
      priority: number;
      estimated_duration: number;
      estimated_duration_unit: "minutes";
      description?: string;
      deadline?: string;
      goal_id?: number;
      dependencies?: number[];
    } = {
      title: title.trim(),
      task_type: taskType.trim().toLowerCase(),
      priority,
      estimated_duration: minutes,
      estimated_duration_unit: "minutes",
    };
    if (description.trim()) payload.description = description.trim();
    if (formattedDeadline) payload.deadline = formattedDeadline;
    if (goalId) payload.goal_id = Number(goalId);
    if (selectedDependencies.length) payload.dependencies = selectedDependencies;

    createTask.mutate(
      payload,
      {
        onSuccess: () => {
          toast("success", "Task created", `“${title.trim()}” is ready for planning.`);
          onClose();
        },
        onError: (err) => setError(getApiErrorMessage(err)),
      }
    );
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="New task"
      description="Captured tasks feed Layer 1 and become candidates for quantum-aware optimization."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={createTask.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="task-create-form" isLoading={createTask.isPending}>
            Create task
          </Button>
        </>
      }
    >
      <form id="task-create-form" onSubmit={submit} className="space-y-4 max-h-[75vh] overflow-y-auto pr-1" noValidate>
        <Field label="Title" htmlFor="task-title">
          <Input
            id="task-title"
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Complete thesis literature review"
            maxLength={255}
            required
          />
        </Field>

        <Field label="Description / Context" htmlFor="task-description" optional hint="Relevant details or instructions for this task.">
          <Textarea
            id="task-description"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Add relevant context or notes..."
          />
        </Field>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Type" htmlFor="task-type" hint="Behaviour model category">
            <Input
              id="task-type"
              list="task-type-options"
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
              maxLength={100}
              required
            />
            <datalist id="task-type-options">
              {TASK_TYPE_SUGGESTIONS.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
          </Field>

          <Field label="Associated Goal" htmlFor="task-goal" optional hint="Align task with a core goal">
            <Select
              id="task-goal"
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
          <Field label="Deadline" htmlFor="task-deadline" optional hint="Earliest Deadline First (EDF) order">
            <Input
              id="task-deadline"
              type="datetime-local"
              value={deadlinestr}
              onChange={(e) => setDeadlinestr(e.target.value)}
            />
          </Field>

          <Field label="Estimated duration (minutes)" htmlFor="task-duration" hint="Positive minute estimate">
            <Input
              id="task-duration"
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

        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {DURATION_PRESETS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setDuration(String(m))}
              className={cn(
                "tabular rounded-md border px-2 py-0.5 text-xs transition-colors",
                Number(duration) === m
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border text-content-tertiary hover:text-content-primary"
              )}
            >
              {m < 60 ? `${m}m` : `${m / 60}h`}
            </button>
          ))}
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

        {availableTasks.length > 0 && (
          <fieldset className="space-y-1.5">
            <legend className="text-[13px] font-medium text-content-secondary">
              Prerequisites / Dependencies (Optional)
            </legend>
            <p className="text-xs text-content-muted">
              Select tasks that must be completed before this task can start.
            </p>
            <div className="max-h-36 overflow-y-auto space-y-1 rounded-lg border border-border p-2">
              {availableTasks.map((t) => (
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
