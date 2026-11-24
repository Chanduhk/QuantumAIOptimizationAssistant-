import type { Task } from "@/api/endpoints";
import type { BadgeTone } from "@/components/ui/Badge";
import { parseUtcDate } from "@/utils/formatters";

export type LifecycleState = "created" | "started" | "completed" | "unknown";

export function lifecycle(task: Task): LifecycleState {
  if (task.completed || task.lifecycle_state === "completed") return "completed";
  if (task.lifecycle_state === "started") return "started";
  if (task.lifecycle_state === "created") return "created";
  return "unknown";
}

export const LIFECYCLE_META: Record<LifecycleState, { label: string; tone: BadgeTone }> = {
  created: { label: "Planned", tone: "neutral" },
  started: { label: "In progress", tone: "primary" },
  completed: { label: "Completed", tone: "success" },
  unknown: { label: "Unknown state", tone: "warning" },
};

export const PRIORITY_META: Record<number, { label: string; tone: BadgeTone }> = {
  5: { label: "Critical", tone: "error" },
  4: { label: "High", tone: "warning" },
  3: { label: "Medium", tone: "primary" },
  2: { label: "Normal", tone: "neutral" },
  1: { label: "Low", tone: "outline" },
};

export function priorityMeta(priority: number) {
  return PRIORITY_META[priority] ?? PRIORITY_META[3];
}

export const TASK_TYPE_SUGGESTIONS = ["work", "coding", "writing", "research", "study", "meeting", "admin", "health", "personal"];

export function hasFeedback(task: Task): boolean {
  return task.focus_rating != null && task.energy_rating != null && task.productivity_rating != null;
}

/** Mirrors the backend executive-plan input contract (see F9.1B). */
export function isPlanningEligible(task: Task): boolean {
  return (
    Number.isInteger(task.id) &&
    task.id > 0 &&
    task.lifecycle_state === "created" &&
    task.completed === false &&
    task.estimated_duration_unit === "minutes" &&
    typeof task.estimated_duration_source === "string" &&
    task.estimated_duration_source.trim().length > 0 &&
    typeof task.estimated_duration === "number" &&
    Number.isFinite(task.estimated_duration) &&
    task.estimated_duration > 0 &&
    Number.isInteger(task.priority) &&
    task.priority >= 1 &&
    task.priority <= 5 &&
    Boolean(task.title.trim()) &&
    Boolean(task.task_type.trim())
  );
}

export function ineligibilityReason(task: Task): string {
  const state = lifecycle(task);
  if (state === "completed") return "Completed — historical record";
  if (state === "started") return "Already in progress";
  if (state !== "created") return "Lifecycle state unrecognized";
  if (task.estimated_duration === null || !Number.isFinite(task.estimated_duration) || task.estimated_duration <= 0) return "Needs a positive estimate";
  if (task.estimated_duration_unit !== "minutes") return "Estimate unit is not minutes";
  if (!task.estimated_duration_source?.trim()) return "Estimate provenance missing";
  return "Required fields incomplete";
}

/** Minutes elapsed since a started task's start_time. */
export function elapsedMinutes(task: Task, now = Date.now()): number | null {
  const start = parseUtcDate(task.start_time);
  if (!start) return null;
  return Math.max(0, (now - start.getTime()) / 60000);
}

/** Ratio of actual to estimated duration for completed tasks. */
export function durationRatio(task: Task): number | null {
  if (typeof task.actual_duration !== "number" || typeof task.estimated_duration !== "number" || task.estimated_duration <= 0) return null;
  return task.actual_duration / task.estimated_duration;
}

export function sortTasks(tasks: Task[], sort: "priority" | "recent" | "duration"): Task[] {
  const copy = [...tasks];
  if (sort === "priority") copy.sort((a, b) => b.priority - a.priority || (b.id - a.id));
  if (sort === "recent") copy.sort((a, b) => (parseUtcDate(b.created_at)?.getTime() ?? 0) - (parseUtcDate(a.created_at)?.getTime() ?? 0));
  if (sort === "duration") copy.sort((a, b) => (b.estimated_duration ?? 0) - (a.estimated_duration ?? 0));
  return copy;
}

export interface DeadlineCountdownResult {
  countdownText: string;
  isOverdue: boolean;
  minutesRemaining: number;
  formattedDeadline: string;
}

export function formatDeadlineCountdown(deadlinestr: string | null | undefined, nowMs = Date.now()): DeadlineCountdownResult | null {
  if (!deadlinestr) return null;
  const deadlineDate = parseUtcDate(deadlinestr);
  if (!deadlineDate || isNaN(deadlineDate.getTime())) return null;

  const diffMs = deadlineDate.getTime() - nowMs;
  const isOverdue = diffMs < 0;
  const absDiffSec = Math.floor(Math.abs(diffMs) / 1000);
  const minutes = Math.floor(absDiffSec / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  let countdownText = "";
  if (isOverdue) {
    if (days > 0) countdownText = `Overdue by ${days}d ${hours % 24}h`;
    else if (hours > 0) countdownText = `Overdue by ${hours}h ${minutes % 60}m`;
    else countdownText = `Overdue by ${minutes}m`;
  } else {
    if (days > 0) countdownText = `In ${days}d ${hours % 24}h`;
    else if (hours > 0) countdownText = `In ${hours}h ${minutes % 60}m`;
    else countdownText = `In ${minutes}m`;
  }

  const formattedDeadline = deadlineDate.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return {
    countdownText,
    isOverdue,
    minutesRemaining: Math.floor(diffMs / 60000),
    formattedDeadline,
  };
}

export function formatScheduledSlot(startStr?: string | null, endStr?: string | null): string | null {
  if (!startStr) return null;
  const start = parseUtcDate(startStr);
  if (!start || isNaN(start.getTime())) return null;
  const end = endStr ? parseUtcDate(endStr) : null;

  const sTime = start.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  if (end && !isNaN(end.getTime())) {
    const eTime = end.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return `${sTime} – ${eTime}`;
  }
  return `At ${sTime}`;
}

export interface RiskMeta {
  level: "overdue" | "high" | "moderate" | "low" | "scheduled" | "none";
  label: string;
  tone: BadgeTone;
  badgeClass: string;
}

export function getTaskRiskMeta(task: Task, isOverdueCalc = false): RiskMeta {
  if (task.completed || task.lifecycle_state === "completed") {
    return { level: "none", label: "Completed", tone: "success", badgeClass: "border-emerald-500/30 text-emerald-400 bg-emerald-500/10" };
  }

  const risk = task.deadline_risk;
  if (isOverdueCalc || risk?.is_overdue || risk?.risk_level === "overdue") {
    return { level: "overdue", label: "Overdue", tone: "error", badgeClass: "border-red-500/40 text-red-400 bg-red-500/15 animate-pulse" };
  }
  if (risk?.risk_level === "high") {
    return { level: "high", label: "High Risk", tone: "error", badgeClass: "border-red-500/30 text-red-400 bg-red-500/10" };
  }
  if (risk?.risk_level === "moderate") {
    return { level: "moderate", label: "Approaching", tone: "warning", badgeClass: "border-amber-500/30 text-amber-400 bg-amber-500/10" };
  }
  if (risk?.risk_level === "low") {
    return { level: "low", label: "On Track", tone: "success", badgeClass: "border-emerald-500/30 text-emerald-400 bg-emerald-500/10" };
  }
  if (task.scheduled_start_time) {
    return { level: "scheduled", label: "Scheduled", tone: "primary", badgeClass: "border-sky-500/30 text-sky-400 bg-sky-500/10" };
  }
  return { level: "none", label: "No Deadline", tone: "neutral", badgeClass: "border-neutral-500/30 text-neutral-400 bg-neutral-500/10" };
}
