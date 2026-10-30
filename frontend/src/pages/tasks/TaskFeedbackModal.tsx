import * as React from "react";
import { Star, CheckCircle2, AlertCircle } from "lucide-react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Task } from "@/api/endpoints";
import { useSubmitTaskFeedback } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";

interface TaskFeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  task: Task;
}

interface StarRatingInputProps {
  label: string;
  value: number | null;
  onChange: (rating: number) => void;
  disabled?: boolean;
}

function StarRatingInput({ label, value, onChange, disabled }: StarRatingInputProps) {
  const [hovered, setHovered] = React.useState<number | null>(null);

  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-content-primary">{label}</span>
        {value !== null && (
          <span className="text-xs font-mono font-medium text-primary">
            {value} / 5
          </span>
        )}
      </div>
      <div
        className="flex items-center gap-1"
        role="group"
        aria-label={`${label} rating: ${value ? `${value} of 5 stars` : "unrated"}`}
      >
        {[1, 2, 3, 4, 5].map((star) => {
          const isFilled = hovered !== null ? star <= hovered : value !== null && star <= value;
          return (
            <button
              key={star}
              type="button"
              disabled={disabled}
              onClick={() => onChange(star)}
              onMouseEnter={() => setHovered(star)}
              onMouseLeave={() => setHovered(null)}
              className="group p-1 text-content-tertiary transition-transform hover:scale-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
              aria-label={`${label}: ${star} star${star > 1 ? "s" : ""}`}
            >
              <Star
                className={`h-6 w-6 transition-colors ${
                  isFilled
                    ? "fill-amber-400 text-amber-400 drop-shadow-[0_0_4px_rgba(251,191,36,0.3)]"
                    : "fill-transparent text-content-tertiary group-hover:text-amber-300"
                }`}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function TaskFeedbackModal({ isOpen, onClose, task }: TaskFeedbackModalProps) {
  const feedbackMutation = useSubmitTaskFeedback();
  const [focusRating, setFocusRating] = React.useState<number | null>(task.focus_rating ?? null);
  const [energyRating, setEnergyRating] = React.useState<number | null>(task.energy_rating ?? null);
  const [productivityRating, setProductivityRating] = React.useState<number | null>(task.productivity_rating ?? null);
  const [feedbackNotes, setFeedbackNotes] = React.useState<string>(task.feedback_notes ?? "");
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const [successMessage, setSuccessMessage] = React.useState<string | null>(null);

  // Reset ratings when task changes or modal opens
  React.useEffect(() => {
    if (isOpen) {
      setFocusRating(task.focus_rating ?? null);
      setEnergyRating(task.energy_rating ?? null);
      setProductivityRating(task.productivity_rating ?? null);
      setFeedbackNotes(task.feedback_notes ?? "");
      setValidationError(null);
      setSuccessMessage(null);
    }
  }, [isOpen, task]);

  const formatDuration = (minutes: number | null | undefined): string => {
    if (minutes === null || minutes === undefined) return "N/A";
    if (!Number.isFinite(minutes)) return "Unavailable";
    const mag = Math.round(Math.abs(minutes) * 10) / 10;
    const sign = minutes < 0 ? "-" : "";
    if (mag < 60) {
      return `${sign}${Number.isInteger(mag) ? mag : mag.toFixed(1)} min`;
    }
    const h = Math.floor(mag / 60);
    const m = Math.round((mag % 60) * 10) / 10;
    return m > 0 ? `${sign}${h}h ${Number.isInteger(m) ? m : m.toFixed(1)}m` : `${sign}${h}h`;
  };

  // Duration metrics verification
  const isEstimateVerified =
    task.estimated_duration !== null &&
    task.estimated_duration > 0 &&
    task.estimated_duration_unit === "minutes";

  const isActualVerified =
    task.actual_duration !== null &&
    task.actual_duration > 0 &&
    task.outcome_valid === true &&
    task.lifecycle_state === "completed";

  const durationDiff =
    isEstimateVerified && isActualVerified && task.actual_duration !== null && task.estimated_duration !== null
      ? task.actual_duration - task.estimated_duration
      : null;

  const durationRatio =
    isEstimateVerified && isActualVerified && task.actual_duration !== null && task.estimated_duration !== null
      ? task.actual_duration / task.estimated_duration
      : null;

  const hasExistingFeedback =
    task.focus_rating !== null &&
    task.focus_rating !== undefined &&
    task.productivity_rating !== null &&
    task.productivity_rating !== undefined;

  const handleSave = () => {
    setValidationError(null);
    setSuccessMessage(null);

    if (focusRating === null || energyRating === null || productivityRating === null) {
      setValidationError("Please provide a rating (1 to 5) for Focus, Energy, and Productivity.");
      return;
    }

    if (
      focusRating < 1 || focusRating > 5 ||
      energyRating < 1 || energyRating > 5 ||
      productivityRating < 1 || productivityRating > 5
    ) {
      setValidationError("Ratings must be between 1 and 5.");
      return;
    }

    feedbackMutation.mutate(
      {
        taskId: task.id,
        data: {
          focus_rating: focusRating,
          energy_rating: energyRating,
          productivity_rating: productivityRating,
          feedback_notes: feedbackNotes.trim() ? feedbackNotes.trim() : undefined,
        },
      },
      {
        onSuccess: () => {
          setSuccessMessage("Feedback successfully recorded! Helping HELIOX learn your genuine patterns.");
          setTimeout(() => {
            onClose();
          }, 1200);
        },
      }
    );
  };

  const handleSkip = () => {
    // Explicitly do not send or store any ratings
    onClose();
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Task Outcome & Feedback"
      description={`Task: "${task.title}" (${task.task_type})`}
      footer={
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Button
            type="button"
            variant="ghost"
            onClick={handleSkip}
            disabled={feedbackMutation.isPending}
            className="w-full sm:w-auto"
          >
            {hasExistingFeedback ? "Close" : "Skip for now"}
          </Button>

          <Button
            type="button"
            variant="primary"
            onClick={handleSave}
            isLoading={feedbackMutation.isPending}
            disabled={feedbackMutation.isPending || !!successMessage}
            className="w-full sm:w-auto"
          >
            Save feedback
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        {/* Outcome Presentation Grid */}
        <div className="rounded-lg border border-border bg-surface-2/60 p-4">
          <div className="mb-3 flex items-center justify-between border-b border-border/60 pb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-content-secondary">
              Outcome Summary
            </span>
            <Badge variant="success" className="gap-1">
              <CheckCircle2 className="h-3 w-3" />
              Completed
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <p className="text-xs text-content-tertiary">Estimated</p>
              <p className="mt-1 font-mono font-medium text-content-primary">
                {isEstimateVerified
                  ? formatDuration(task.estimated_duration)
                  : task.estimated_duration !== null
                  ? `${task.estimated_duration} (${task.estimated_duration_unit ?? "unverified"})`
                  : "N/A"}
              </p>
            </div>

            <div>
              <p className="text-xs text-content-tertiary">Actual</p>
              <p className="mt-1 font-mono font-medium text-content-primary">
                {isActualVerified ? formatDuration(task.actual_duration) : "N/A"}
              </p>
            </div>

            <div>
              <p className="text-xs text-content-tertiary">Difference</p>
              <p className="mt-1 font-mono font-medium">
                {durationDiff !== null ? (
                  <span className={durationDiff > 0 ? "text-amber-400" : "text-emerald-400"}>
                    {durationDiff > 0 ? "+" : ""}
                    {formatDuration(durationDiff)}
                  </span>
                ) : (
                  <span className="text-content-tertiary">—</span>
                )}
              </p>
            </div>

            <div>
              <p className="text-xs text-content-tertiary">Duration Ratio</p>
              <p className="mt-1 font-mono font-medium">
                {durationRatio !== null ? (
                  <span className="text-primary">{durationRatio.toFixed(2)}×</span>
                ) : (
                  <span className="text-content-tertiary">—</span>
                )}
              </p>
            </div>
          </div>

          <div className="mt-3 flex items-center justify-between border-t border-border/40 pt-2 text-xs text-content-secondary">
            <span>Feedback Status:</span>
            <Badge variant={hasExistingFeedback ? "default" : "outline"} className="text-xs">
              {hasExistingFeedback ? "Recorded" : "Not provided"}
            </Badge>
          </div>
        </div>

        {/* Feedback Rating Form */}
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-primary">
              How did this task go?
            </h3>
            <p className="mt-1 text-xs text-content-secondary">
              Rate your genuine experience. HELIOX uses your ratings to train personalized ML models once enough real data is collected.
            </p>
          </div>

          <div className="space-y-3 rounded-lg border border-border bg-surface-1/70 p-4">
            <StarRatingInput
              label="Focus"
              value={focusRating}
              onChange={(r) => {
                setFocusRating(r);
                setValidationError(null);
              }}
              disabled={feedbackMutation.isPending}
            />

            <div className="border-t border-border/50" />

            <StarRatingInput
              label="Energy"
              value={energyRating}
              onChange={(r) => {
                setEnergyRating(r);
                setValidationError(null);
              }}
              disabled={feedbackMutation.isPending}
            />

            <div className="border-t border-border/50" />

            <StarRatingInput
              label="Productivity"
              value={productivityRating}
              onChange={(r) => {
                setProductivityRating(r);
                setValidationError(null);
              }}
              disabled={feedbackMutation.isPending}
            />

            {productivityRating !== null && (
              <div className="mt-2 rounded-md border border-primary/20 bg-primary/5 p-2.5 text-xs">
                <span className="font-semibold text-primary">
                  Calibrated Score: {Math.round((productivityRating - 1) * 25)} / 100
                </span>
                <p className="mt-0.5 text-[11px] text-content-secondary leading-relaxed">
                  Transformed self-reported score via ((rating - 1) × 25). Note: this is a subjective self-reported rating, not objectively measured productivity.
                </p>
              </div>
            )}
          </div>

          <div>
            <label htmlFor="feedback-notes" className="text-xs font-medium text-content-secondary">
              Notes (Optional)
            </label>
            <textarea
              id="feedback-notes"
              value={feedbackNotes}
              onChange={(e) => setFeedbackNotes(e.target.value)}
              placeholder="Any notes on your flow, blockers, or mental context..."
              disabled={feedbackMutation.isPending}
              maxLength={1000}
              rows={2}
              className="mt-1.5 w-full rounded-md border border-border bg-surface-2 p-2.5 text-xs text-content-primary placeholder-content-tertiary focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {validationError && (
            <div role="alert" className="flex items-center gap-2 rounded-md border border-status-warning/40 bg-status-warning/10 p-2.5 text-xs text-status-warning">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          {feedbackMutation.error && (
            <div role="alert" className="flex items-center gap-2 rounded-md border border-status-error/40 bg-status-error/10 p-2.5 text-xs text-status-error">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{getApiErrorMessage(feedbackMutation.error, "Failed to submit feedback.")}</span>
            </div>
          )}

          {successMessage && (
            <div role="status" className="flex items-center gap-2 rounded-md border border-status-success/40 bg-status-success/10 p-2.5 text-xs text-status-success">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}
        </div>
      </div>
    </Dialog>
  );
}
