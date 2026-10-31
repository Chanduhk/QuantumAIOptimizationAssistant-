import * as React from "react";
import type { Task } from "@/api/endpoints";
import { useSubmitTaskFeedback } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Dialog } from "@/components/ui/Dialog";
import { Field, Textarea } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Toaster";
import { formatDuration } from "@/utils/formatters";
import { cn } from "@/lib/utils";

const SCALE_HINT = ["", "Very low", "Low", "Moderate", "High", "Excellent"];

function RatingScale({ label, description, value, onChange }: { label: string; description: string; value: number | null; onChange: (v: number) => void }) {
  return (
    <fieldset>
      <div className="mb-2 flex items-baseline justify-between">
        <legend className="text-[13px] font-medium text-content-primary">{label}</legend>
        <span className="text-xs text-content-tertiary">{value ? `${value}/5 · ${SCALE_HINT[value]}` : description}</span>
      </div>
      <div className="grid grid-cols-5 gap-1.5" role="radiogroup" aria-label={`${label} rating`}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            aria-label={`${label} ${n} of 5`}
            onClick={() => onChange(n)}
            className={cn(
              "h-10 rounded-lg border font-mono text-sm font-medium transition-all",
              value !== null && n <= value ? "border-primary/50 bg-primary/15 text-content-primary" : "border-border text-content-tertiary hover:bg-surface-2",
              value === n && "ring-2 ring-primary/30"
            )}
          >
            {n}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function FeedbackDialog({ task, isOpen, onClose }: { task: Task | null; isOpen: boolean; onClose: () => void }) {
  const submit = useSubmitTaskFeedback();
  const [focus, setFocus] = React.useState<number | null>(null);
  const [energy, setEnergy] = React.useState<number | null>(null);
  const [productivity, setProductivity] = React.useState<number | null>(null);
  const [notes, setNotes] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (isOpen && task) {
      setFocus(task.focus_rating ?? null);
      setEnergy(task.energy_rating ?? null);
      setProductivity(task.productivity_rating ?? null);
      setNotes(task.feedback_notes ?? "");
      setError(null);
    }
  }, [isOpen, task]);

  if (!task) return null;

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!focus || !energy || !productivity) return setError("Rate focus, energy and productivity from 1 to 5.");
    setError(null);
    submit.mutate(
      { taskId: task.id, data: { focus_rating: focus, energy_rating: energy, productivity_rating: productivity, feedback_notes: notes.trim() || undefined } },
      {
        onSuccess: () => {
          toast("success", "Feedback recorded", "This outcome now counts toward personal model readiness.");
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
      title="How did it go?"
      description={
        <>
          <span className="font-medium text-content-secondary">{task.title}</span>
          {typeof task.actual_duration === "number" && <> · took {formatDuration(task.actual_duration)}{task.estimated_duration ? ` of ${formatDuration(task.estimated_duration)} planned` : ""}</>}
        </>
      }
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submit.isPending}>Later</Button>
          <Button type="submit" form="feedback-form" isLoading={submit.isPending}>Save feedback</Button>
        </>
      }
    >
      <form id="feedback-form" onSubmit={onSubmit} className="space-y-5">
        <RatingScale label="Focus" description="How deep was your concentration?" value={focus} onChange={setFocus} />
        <RatingScale label="Energy" description="How energized did you feel?" value={energy} onChange={setEnergy} />
        <RatingScale label="Productivity" description="How much did you get done?" value={productivity} onChange={setProductivity} />
        <Field label="Notes" htmlFor="feedback-notes" optional>
          <Textarea id="feedback-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Interruptions, context, anything worth remembering" rows={3} />
        </Field>
        <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs leading-relaxed text-content-tertiary">
          Ratings are genuine ground-truth labels. The productivity model needs at least 10 before personal training is unlocked (Layer 12 → 13).
        </p>
        {error && <p role="alert" className="text-[13px] text-status-error">{error}</p>}
      </form>
    </Dialog>
  );
}
