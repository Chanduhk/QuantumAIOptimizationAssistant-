import * as React from "react";
import { useCreateTask } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Dialog } from "@/components/ui/Dialog";
import { Field, Input } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Toaster";
import { cn } from "@/lib/utils";
import { PRIORITY_META, TASK_TYPE_SUGGESTIONS } from "./taskUtils";

const DURATION_PRESETS = [15, 30, 45, 60, 90, 120];

export function TaskCreateDialog({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const createTask = useCreateTask();
  const [title, setTitle] = React.useState("");
  const [taskType, setTaskType] = React.useState("work");
  const [priority, setPriority] = React.useState(3);
  const [duration, setDuration] = React.useState("60");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (isOpen) {
      setTitle("");
      setTaskType("work");
      setPriority(3);
      setDuration("60");
      setError(null);
      createTask.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const minutes = Number(duration);
    if (!title.trim()) return setError("Give the task a title.");
    if (!taskType.trim()) return setError("Choose or type a task type.");
    if (!Number.isFinite(minutes) || minutes <= 0) return setError("Estimated duration must be a positive number of minutes.");
    setError(null);
    createTask.mutate(
      { title: title.trim(), task_type: taskType.trim().toLowerCase(), priority, estimated_duration: minutes, estimated_duration_unit: "minutes" },
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
      description="Captured tasks feed Layer 1 and become candidates for optimization."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={createTask.isPending}>Cancel</Button>
          <Button type="submit" form="task-create-form" isLoading={createTask.isPending}>Create task</Button>
        </>
      }
    >
      <form id="task-create-form" onSubmit={submit} className="space-y-5" noValidate>
        <Field label="Title" htmlFor="task-title">
          <Input id="task-title" autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Draft the Q4 planning memo" maxLength={255} required />
        </Field>

        <Field label="Type" htmlFor="task-type" hint="Used by the behaviour and productivity models.">
          <Input id="task-type" list="task-type-options" value={taskType} onChange={(e) => setTaskType(e.target.value)} maxLength={100} required />
          <datalist id="task-type-options">
            {TASK_TYPE_SUGGESTIONS.map((t) => <option key={t} value={t} />)}
          </datalist>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {TASK_TYPE_SUGGESTIONS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTaskType(t)}
                className={cn(
                  "rounded-md border px-2 py-0.5 text-xs capitalize transition-colors",
                  taskType === t ? "border-primary/40 bg-primary/10 text-primary" : "border-border text-content-tertiary hover:text-content-primary"
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </Field>

        <fieldset className="space-y-1.5">
          <legend className="text-[13px] font-medium text-content-secondary">Priority</legend>
          <div className="grid grid-cols-5 gap-1.5">
            {[1, 2, 3, 4, 5].map((p) => (
              <button
                key={p}
                type="button"
                aria-pressed={priority === p}
                onClick={() => setPriority(p)}
                className={cn(
                  "flex flex-col items-center rounded-lg border py-2 text-xs transition-colors",
                  priority === p ? "border-primary/50 bg-primary/10 text-content-primary" : "border-border text-content-tertiary hover:bg-surface-2"
                )}
              >
                <span className="font-mono text-sm font-semibold">P{p}</span>
                <span className="mt-0.5 text-[10px]">{PRIORITY_META[p].label}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <Field label="Estimated duration (minutes)" htmlFor="task-duration" hint="Explicit minute estimates make the task eligible for quantum-aware optimization.">
          <Input id="task-duration" type="number" min={1} step={5} inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} required />
          <div className="flex flex-wrap gap-1.5 pt-1">
            {DURATION_PRESETS.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setDuration(String(m))}
                className={cn(
                  "tabular rounded-md border px-2 py-0.5 text-xs transition-colors",
                  Number(duration) === m ? "border-primary/40 bg-primary/10 text-primary" : "border-border text-content-tertiary hover:text-content-primary"
                )}
              >
                {m < 60 ? `${m}m` : `${m / 60}h`}
              </button>
            ))}
          </div>
        </Field>

        {error && <p role="alert" className="rounded-lg border border-status-error/25 bg-status-error/[0.06] px-3 py-2 text-[13px] text-status-error">{error}</p>}
      </form>
    </Dialog>
  );
}
