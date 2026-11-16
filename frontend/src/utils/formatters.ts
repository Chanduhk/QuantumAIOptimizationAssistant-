import { getApiErrorMessage } from "@/api/client";

export type StatusVariant = "default" | "secondary" | "outline" | "success" | "warning" | "error" | "quantum";

export interface FormattedStatus {
  label: string;
  description: string;
  variant: StatusVariant;
}

/**
 * Maps raw backend status codes and enums to clear, human-readable labels and descriptions.
 * Uses context when available to give precise, actionable explanations rather than generic copy.
 */
export function formatStatus(rawStatus: unknown, context?: string): FormattedStatus {
  if (rawStatus === null || rawStatus === undefined) {
    return {
      label: "Status unavailable",
      description: "The system has not provided enough information to determine this component's status.",
      variant: "secondary",
    };
  }

  const status = String(rawStatus).trim().toUpperCase();

  // Context-specific handling
  if (context === "hybrid_comparison" || context === "comparison") {
    if (status === "NOT_READY" || status === "PENDING") {
      return {
        label: "Comparison pending",
        description: "A fair comparison is not available because both classical and simulation candidate results are required.",
        variant: "outline",
      };
    }
    if (status === "COMPARED") {
      return {
        label: "Evaluated side-by-side",
        description: "Both classical and simulation candidates were compared under identical constraints.",
        variant: "success",
      };
    }
  }

  if (context === "quantum_suitability" || context === "quantum") {
    if (status === "SUITABLE") {
      return {
        label: "Suitable for simulation",
        description: "The task set and objective constraints can be encoded into QUBO/Ising spin formulation for QAOA.",
        variant: "success",
      };
    }
    if (status === "NOT_SUITABLE") {
      return {
        label: "Not suitable for simulation",
        description: "The problem structure is solved more reliably and accurately by exact classical solvers.",
        variant: "secondary",
      };
    }
    if (status === "NOT_SUPPORTED") {
      return {
        label: "Constraints not supported",
        description: "The current problem size or constraint types exceed supported local simulation capacity.",
        variant: "warning",
      };
    }
    if (status === "NOT_READY") {
      return {
        label: "Suitability check pending",
        description: "Waiting for task input validation and prediction matrix verification.",
        variant: "warning",
      };
    }
  }

  if (context === "prediction_matrix") {
    if (status === "COMPLETE") {
      return {
        label: "Matrix computed",
        description: "Per-task hourly productivity and focus expectations calculated.",
        variant: "success",
      };
    }
    if (status === "NOT_READY") {
      return {
        label: "Matrix pending data",
        description: "Requires sufficient completed task history to calculate nontrivial predictions.",
        variant: "warning",
      };
    }
  }

  // Universal status codes
  switch (status) {
    case "NOT_READY_INSUFFICIENT_DATA":
      return {
        label: "Not enough personal data yet",
        description: "Complete more tasks and record genuine feedback to build a reliable personalized model.",
        variant: "warning",
      };

    case "NOT_PROVEN":
      return {
        label: "Not yet validated",
        description: "There isn't enough empirical evidence to confirm this capability's effectiveness.",
        variant: "outline",
      };

    case "NOT_SUITABLE":
      return {
        label: "Not suitable for this task",
        description: "This engine is not optimal for the current input structure; an appropriate alternative is selected.",
        variant: "secondary",
      };

    case "NOT_READY":
      return {
        label: "Waiting for required results",
        description: "Waiting for predecessor pipeline stages or required task inputs before proceeding.",
        variant: "warning",
      };

    case "UNINITIALIZED":
      return {
        label: "Model not yet initialized",
        description: "Initial model weights and baseline calibration have not yet been completed.",
        variant: "secondary",
      };

    case "UNKNOWN":
      return {
        label: "Status unavailable",
        description: "The system has not provided enough information to determine this component's status.",
        variant: "secondary",
      };

    case "READY":
    case "AVAILABLE":
      return {
        label: "Available",
        description: "Fully operational and verified by current backend evidence.",
        variant: "success",
      };

    case "OPERATIONAL":
      return {
        label: "Operational",
        description: "Service is active and responding normally.",
        variant: "success",
      };

    case "COMPLETE":
    case "COMPLETED":
      return {
        label: "Completed",
        description: "Execution finished successfully with verified results.",
        variant: "success",
      };

    case "TRAINED":
      return {
        label: "Personalized & trained",
        description: "Model has passed accuracy and generalization gates on your verified task history.",
        variant: "success",
      };

    case "PRETRAINED":
      return {
        label: "Pretrained baseline",
        description: "Standard pre-calibrated baseline model active prior to personal fine-tuning.",
        variant: "outline",
      };

    case "READY_FOR_TRAINING":
      return {
        label: "Ready for training",
        description: "Your dataset meets all sample count, quality, and diversity thresholds for training.",
        variant: "success",
      };

    case "AWAITING_REAL_DATA":
      return {
        label: "Awaiting real data",
        description: "Waiting for genuine completed tasks and post-task ratings.",
        variant: "warning",
      };

    case "CANDIDATE":
      return {
        label: "Candidate produced",
        description: "A candidate solution was generated and is ready for cognitive evaluation.",
        variant: "default",
      };

    case "DEGRADED":
      return {
        label: "Degraded performance",
        description: "Service is partially available with heuristic fallback mechanisms active.",
        variant: "warning",
      };

    case "API_UNAVAILABLE":
      return {
        label: "API unavailable",
        description: "The required backend service is currently unreachable.",
        variant: "error",
      };

    case "FAILED":
    case "ERROR":
      return {
        label: "Failed",
        description: "The component encountered an error during execution.",
        variant: "error",
      };

    case "UNREGISTERED":
      return {
        label: "Not registered",
        description: "Component is not currently loaded in the active runtime registry.",
        variant: "secondary",
      };

    default: {
      const formatted = String(rawStatus)
        .toLowerCase()
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
      return {
        label: formatted,
        description: `Component reported status: ${status}`,
        variant: "secondary",
      };
    }
  }
}

/**
 * Formats a duration in minutes into a clean, human-readable string.
 */
export function formatDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || !Number.isFinite(minutes)) {
    return "Not recorded";
  }
  if (minutes <= 0) {
    return "0 min";
  }
  if (minutes < 60) {
    return `${Math.round(minutes)} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = Math.round(minutes % 60);
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

/**
 * Formats a scalar score safely without fabricating precision.
 */
export function formatScore(score: number | null | undefined, precision = 2): string {
  if (score === null || score === undefined || !Number.isFinite(score)) {
    return "—";
  }
  return score.toFixed(precision);
}

/**
 * Formats a fraction/ratio (0.0 - 1.0) as a percentage string.
 */
export function formatPercentage(ratio: number | null | undefined, precision = 1): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) {
    return "—";
  }
  return `${(ratio * 100).toFixed(precision)}%`;
}

/**
 * Formats an optimization energy metric (e.g. Ising Hamiltonian energy).
 */
export function formatEnergy(energy: number | null | undefined): string {
  if (energy === null || energy === undefined || !Number.isFinite(energy)) {
    return "—";
  }
  return `${energy.toFixed(4)} (energy)`;
}

/**
 * Formats objective relation terms into clear human language.
 */
export function formatObjectiveRelation(relation: unknown): { label: string; explanation: string } {
  const rel = String(relation || "").toUpperCase();
  if (rel === "QUANTUM_HIGHER") {
    return {
      label: "Simulation objective higher",
      explanation: "The QAOA simulation candidate achieved a higher objective score than the classical reference.",
    };
  }
  if (rel === "CLASSICAL_HIGHER") {
    return {
      label: "Classical objective higher",
      explanation: "The exact classical solver achieved a higher objective score than the QAOA simulation candidate.",
    };
  }
  if (rel === "EQUAL" || rel === "TIE") {
    return {
      label: "Equivalent objective scores",
      explanation: "Both classical and simulation candidates achieved identical objective performance.",
    };
  }
  return {
    label: rel ? rel.replace(/_/g, " ") : "Not compared",
    explanation: "Candidate objective relation is evaluated when both solutions are available.",
  };
}

export interface NormalizedError {
  title: string;
  explanation: string;
  actionSuggestion?: string;
  isRetryable: boolean;
}

/**
 * Normalizes technical backend error codes and exceptions into actionable human explanations.
 */
export function normalizeErrorMessage(error: unknown, fallback = "An unexpected error occurred."): NormalizedError {
  let rawMessage = "";
  if (typeof error === "string") {
    rawMessage = error;
  } else if (error instanceof Error) {
    rawMessage = error.message;
  } else {
    rawMessage = getApiErrorMessage(error, fallback);
  }
  const lower = rawMessage.toLowerCase();

  if (lower.includes("depends_on") || lower.includes("depend") || lower.includes("prerequisite") || lower.includes("cycle")) {
    return {
      title: "Task Dependency Issue",
      explanation: rawMessage || "A selected task contains an invalid, missing, or circular dependency.",
      actionSuggestion: "Review your task prerequisites in Tasks and try running the pipeline again.",
      isRetryable: true,
    };
  }

  if (lower.includes("no completed tasks") || lower.includes("insufficient completed history")) {
    return {
      title: "Completed Task History Needed",
      explanation: "Personalized intelligence requires at least one completed task with duration feedback to discover your optimal work rhythm.",
      actionSuggestion: "Start and complete a task in the Tasks workspace to enable this feature.",
      isRetryable: false,
    };
  }

  if (lower.includes("no active tasks")) {
    return {
      title: "No Active Tasks Found",
      explanation: "There are currently no backlog or in-progress tasks to prioritize or schedule.",
      actionSuggestion: "Create a task in Tasks to generate recommendations and plans.",
      isRetryable: false,
    };
  }

  if (lower.includes("failed to fetch") || lower.includes("network error") || lower.includes("connection refused") || lower.includes("service unavailable")) {
    return {
      title: "Connection Unavailable",
      explanation: "The application could not reach the HELIOX backend API service.",
      actionSuggestion: "Check that the backend server is running and try again.",
      isRetryable: true,
    };
  }

  if (lower.includes("timeout") || lower.includes("timed out")) {
    return {
      title: "Request Timed Out",
      explanation: "The requested operation took longer than expected to compute.",
      actionSuggestion: "Please try again in a few moments.",
      isRetryable: true,
    };
  }

  if (lower.includes("unauthorized") || lower.includes("401") || lower.includes("session")) {
    return {
      title: "Session Expired",
      explanation: "Your session may have expired or is not authenticated.",
      actionSuggestion: "Please sign in again to continue.",
      isRetryable: false,
    };
  }

  return {
    title: "Request Notice",
    explanation: rawMessage,
    isRetryable: true,
  };
}

/**
 * Detects the user's local IANA timezone.
 */
export function getUserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/**
 * Parses an ISO timestamp safely, treating naive ISO strings without offset as UTC.
 */
export function parseUtcDate(value: string | number | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "number") {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const str = String(value).trim();
  if (!str) return null;
  // If no timezone offset (+HH:MM, -HH:MM, or Z) is present, append Z to parse as UTC
  const hasTz = /[Zz]|[+-]\d{2}(?::?\d{2})?$/.test(str);
  const normalized = hasTz ? str : `${str}Z`;
  const d = new Date(normalized);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * Formats a timestamp into the user's local clock time (e.g. "09:30 AM" or "14:15").
 */
export function formatLocalTime(
  value: string | number | Date | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = parseUtcDate(value);
  if (!d) return "—";
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    ...options,
  });
}

/**
 * Formats a timestamp into the user's local date (e.g. "Oct 19, 2026").
 */
export function formatLocalDate(
  value: string | number | Date | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = parseUtcDate(value);
  if (!d) return "—";
  return d.toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...options,
  });
}

/**
 * Formats a timestamp into the user's local date and time.
 */
export function formatLocalDateTime(
  value: string | number | Date | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = parseUtcDate(value);
  if (!d) return "—";
  return `${formatLocalDate(d, options)} ${formatLocalTime(d, options)}`;
}

/**
 * Formats a numeric hour slot (0-23) into the user's local time range (e.g. "09:00 AM – 10:30 AM").
 */
export function formatHourSlot(startHour: number, durationHours: number = 1.0): string {
  if (!Number.isFinite(startHour)) return "Time pending";
  const startMinutes = Math.round(startHour * 60);
  const endMinutes = Math.round((startHour + durationHours) * 60);

  const formatMin = (m: number) => {
    const h = Math.floor(m / 60) % 24;
    const min = m % 60;
    const period = h >= 12 ? "PM" : "AM";
    const displayH = h % 12 === 0 ? 12 : h % 12;
    const displayMin = min < 10 ? `0${min}` : String(min);
    return `${displayH}:${displayMin} ${period}`;
  };

  return `${formatMin(startMinutes)} – ${formatMin(endMinutes)}`;
}

