import * as React from "react";
import type { Goal } from "@/api/endpoints";
import { useCreateGoal, useUpdateGoal, useDeleteGoal } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Dialog } from "@/components/ui/Dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Toaster";
import { cn } from "@/lib/utils";
import { Trash2 } from "lucide-react";

const GOAL_CATEGORIES = ["general", "academic", "career", "health", "finance", "project"];

export function GoalDialog({
  goal,
  isOpen,
  onClose,
}: {
  goal?: Goal | null;
  isOpen: boolean;
  onClose: () => void;
}) {
  const createGoal = useCreateGoal();
  const updateGoal = useUpdateGoal();
  const deleteGoal = useDeleteGoal();

  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [category, setCategory] = React.useState("general");
  const [priority, setPriority] = React.useState(3);
  const [targetDateStr, setTargetDateStr] = React.useState("");
  const [status, setStatus] = React.useState("active");
  const [progressPct, setProgressPct] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = React.useState(false);

  const isEditing = Boolean(goal);

  React.useEffect(() => {
    if (isOpen) {
      if (goal) {
        setTitle(goal.title || "");
        setDescription(goal.description || "");
        setCategory(goal.category || "general");
        setPriority(goal.priority || 3);
        setStatus(goal.status || "active");
        setProgressPct(Math.round((goal.progress || 0) * 100));

        if (goal.target_date) {
          try {
            const d = new Date(goal.target_date);
            setTargetDateStr(d.toISOString().slice(0, 10));
          } catch {
            setTargetDateStr("");
          }
        } else {
          setTargetDateStr("");
        }
      } else {
        setTitle("");
        setDescription("");
        setCategory("general");
        setPriority(3);
        setStatus("active");
        setProgressPct(0);
        setTargetDateStr("");
      }
      setError(null);
      setConfirmDelete(false);
      createGoal.reset();
      updateGoal.reset();
      deleteGoal.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goal, isOpen]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return setError("Please enter a goal title.");
    setError(null);

    let formattedTargetDate: string | undefined = undefined;
    const clearTargetDate = !targetDateStr.trim() && Boolean(goal?.target_date);
    if (targetDateStr.trim()) {
      try {
        const d = new Date(targetDateStr);
        if (isNaN(d.getTime())) return setError("Invalid target date.");
        formattedTargetDate = d.toISOString();
      } catch {
        return setError("Invalid target date format.");
      }
    }

    const progressRatio = Math.max(0, Math.min(1, progressPct / 100));

    if (isEditing && goal) {
      updateGoal.mutate(
        {
          goalId: goal.id,
          data: {
            title: title.trim(),
            description: description.trim() || undefined,
            category: category.trim().toLowerCase(),
            priority,
            target_date: formattedTargetDate,
            clear_target_date: clearTargetDate,
            status,
            progress: progressRatio,
          },
        },
        {
          onSuccess: () => {
            toast("success", "Goal updated", `“${title.trim()}” has been updated.`);
            onClose();
          },
          onError: (err) => setError(getApiErrorMessage(err)),
        }
      );
    } else {
      createGoal.mutate(
        {
          title: title.trim(),
          description: description.trim() || undefined,
          category: category.trim().toLowerCase(),
          priority,
          target_date: formattedTargetDate,
          status,
          progress: progressRatio,
        },
        {
          onSuccess: () => {
            toast("success", "Goal created", `“${title.trim()}” is ready.`);
            onClose();
          },
          onError: (err) => setError(getApiErrorMessage(err)),
        }
      );
    }
  };

  const handleDelete = () => {
    if (!goal) return;
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }

    deleteGoal.mutate(goal.id, {
      onSuccess: () => {
        toast("info", "Goal deleted", `“${goal.title}” was removed.`);
        onClose();
      },
      onError: (err) => setError(getApiErrorMessage(err)),
    });
  };

  const isPending = createGoal.isPending || updateGoal.isPending || deleteGoal.isPending;

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? "Edit Goal" : "New Goal"}
      description="Goals establish strategic anchors that prioritize and guide executive task scheduling."
      footer={
        <div className="flex w-full items-center justify-between">
          {isEditing ? (
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={handleDelete}
              isLoading={deleteGoal.isPending}
              disabled={isPending}
              leftIcon={<Trash2 className="size-3.5" />}
            >
              {confirmDelete ? "Confirm delete?" : "Delete"}
            </Button>
          ) : <div />}
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" form="goal-form" isLoading={createGoal.isPending || updateGoal.isPending}>
              {isEditing ? "Save changes" : "Create goal"}
            </Button>
          </div>
        </div>
      }
    >
      <form id="goal-form" onSubmit={submit} className="space-y-4 max-h-[75vh] overflow-y-auto pr-1" noValidate>
        <Field label="Goal Title" htmlFor="goal-title">
          <Input
            id="goal-title"
            autoFocus={!isEditing}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Master's Degree Graduation"
            maxLength={255}
            required
          />
        </Field>

        <Field label="Description / Success Criteria" htmlFor="goal-description" optional>
          <Textarea
            id="goal-description"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What does achieving this goal look like?"
          />
        </Field>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Category" htmlFor="goal-category">
            <Select
              id="goal-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {GOAL_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Target Date" htmlFor="goal-target-date" optional hint="Target completion horizon">
            <Input
              id="goal-target-date"
              type="date"
              value={targetDateStr}
              onChange={(e) => setTargetDateStr(e.target.value)}
            />
          </Field>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Status" htmlFor="goal-status">
            <Select
              id="goal-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="paused">Paused</option>
              <option value="archived">Archived</option>
            </Select>
          </Field>

          <Field label={`Progress (${progressPct}%)`} htmlFor="goal-progress" hint="Manual / estimated progress">
            <div className="flex items-center gap-3 pt-2">
              <input
                id="goal-progress"
                type="range"
                min={0}
                max={100}
                step={5}
                value={progressPct}
                onChange={(e) => setProgressPct(Number(e.target.value))}
                className="w-full h-2 rounded bg-surface-2 accent-primary cursor-pointer"
              />
              <span className="font-mono text-xs w-10 text-right">{progressPct}%</span>
            </div>
          </Field>
        </div>

        <fieldset className="space-y-1.5">
          <legend className="text-[13px] font-medium text-content-secondary">Goal Priority (1-5)</legend>
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
                <span className="mt-0.5 text-[10px]">
                  {p === 5 ? "Critical" : p === 4 ? "High" : p === 3 ? "Standard" : p === 2 ? "Moderate" : "Low"}
                </span>
              </button>
            ))}
          </div>
        </fieldset>

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
