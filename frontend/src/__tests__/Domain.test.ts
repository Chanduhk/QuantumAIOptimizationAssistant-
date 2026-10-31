import { describe, expect, it } from "vitest";
import type { ProviderStatusResponse, Task } from "@/api/endpoints";
import { cleanText, humanize, num, toPercent } from "@/lib/data";
import { providerState, readinessTone } from "@/lib/status";
import { durationRatio, ineligibilityReason, isPlanningEligible, lifecycle } from "@/features/tasks/taskUtils";
import { formatClock } from "@/lib/format";

const baseTask: Task = {
  id: 7,
  user_id: 1,
  title: "Draft memo",
  task_type: "writing",
  priority: 4,
  estimated_duration: 45,
  estimated_duration_unit: "minutes",
  estimated_duration_source: "task_api",
  actual_duration: null,
  created_at: "2026-10-30T06:03:45+00:00",
  start_time: null,
  end_time: null,
  completed: false,
  lifecycle_state: "created",
  outcome_valid: null,
};

const provider = (overrides: Partial<ProviderStatusResponse>): ProviderStatusResponse => ({
  provider: "openai",
  model: "gpt-4o-mini",
  is_configured: true,
  has_api_key: true,
  masked_key: "sk-...x",
  endpoint: "https://api.openai.com/v1/chat/completions",
  status: "openai_configured",
  status_label: "Openai Configured (gpt-4o-mini)",
  fallback_active: false,
  timeout_seconds: 10,
  supported_models: [],
  ...overrides,
});

describe("data helpers", () => {
  it("humanizes backend enums", () => {
    expect(humanize("NOT_READY_INSUFFICIENT_DATA")).toBe("Not ready insufficient data");
    expect(humanize("")).toBe("—");
  });

  it("repairs double-encoded em dashes", () => {
    expect(cleanText("LOCAL_CLASSICAL_SIMULATION â€” NO HARDWARE")).toBe("LOCAL_CLASSICAL_SIMULATION — NO HARDWARE");
  });

  it("normalizes ratios and percentages without inventing values", () => {
    expect(toPercent(0.7325)).toBeCloseTo(73.25);
    expect(toPercent(86.71)).toBe(86.71);
    expect(toPercent(null)).toBeNull();
    expect(num("12.5")).toBe(12.5);
    expect(num("abc")).toBeNull();
  });

  it("formats decimal hours as clock time", () => {
    expect(formatClock(13.5)).toBe("13:30");
    expect(formatClock(undefined)).toBe("--:--");
  });
});

describe("providerState", () => {
  it("does not claim a live LLM when only a key is configured", () => {
    const state = providerState(provider({}));
    expect(state.live).toBe(false);
    expect(state.short).toBe("OpenAI key set");
  });

  it("reports live only after verified availability", () => {
    expect(providerState(provider({ status: "openai_configured_and_available" })).live).toBe(true);
  });

  it("reports the deterministic fallback", () => {
    expect(providerState(provider({ fallback_active: true, status: "openai_rate_limited" })).tone).toBe("warning");
    expect(providerState(provider({ is_configured: false, has_api_key: false })).short).toBe("Rule-based parser");
  });
});

describe("readinessTone", () => {
  it("maps statuses to severity", () => {
    expect(readinessTone("NOT_READY_INSUFFICIENT_DATA")).toBe("warning");
    expect(readinessTone("READY_FOR_TRAINING")).toBe("success");
    expect(readinessTone("INVALID_INPUT")).toBe("error");
  });
});

describe("task planning eligibility", () => {
  it("accepts planned tasks with explicit minute estimates", () => {
    expect(isPlanningEligible(baseTask)).toBe(true);
  });

  it("rejects started, completed and unit-less tasks with a reason", () => {
    const started = { ...baseTask, lifecycle_state: "started" };
    expect(isPlanningEligible(started)).toBe(false);
    expect(ineligibilityReason(started)).toBe("Already in progress");

    const noUnit = { ...baseTask, estimated_duration_unit: null };
    expect(isPlanningEligible(noUnit)).toBe(false);
    expect(ineligibilityReason(noUnit)).toBe("Estimate unit is not minutes");

    const done = { ...baseTask, completed: true, lifecycle_state: "completed" };
    expect(lifecycle(done)).toBe("completed");
    expect(isPlanningEligible(done)).toBe(false);
  });

  it("computes actual/estimate ratio only when both exist", () => {
    expect(durationRatio(baseTask)).toBeNull();
    expect(durationRatio({ ...baseTask, actual_duration: 90 })).toBe(2);
  });
});
