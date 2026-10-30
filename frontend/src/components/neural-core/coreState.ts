export type CoreState = "READY" | "PROCESSING" | "NOT_READY" | "NOT_PROVEN" | "UNAVAILABLE" | "ERROR" | "UNKNOWN";

export interface NeuralCoreNode {
  id: string;
  label: string;
  state: CoreState;
  detail: string;
  route: string;
}

export function mapBackendState(value: unknown, requestError = false, loading = false): CoreState {
  if (requestError) return "ERROR";
  if (loading) return "UNKNOWN";
  if (typeof value !== "string") return "UNKNOWN";
  const normalized = value.trim().toUpperCase();
  if (normalized.includes("CONDITIONALLY") || normalized.includes("NOT_PROVEN") || normalized.includes("NOT_CHECKED")) return "NOT_PROVEN";
  if (["READY", "OPERATIONAL", "AVAILABLE", "COMPLETE", "SUITABLE", "PASS"].includes(normalized)) return "READY";
  if (["PROCESSING", "RUNNING", "PENDING"].includes(normalized)) return "PROCESSING";
  if (["NOT_READY", "UNINITIALIZED", "BLOCKED"].includes(normalized)) return "NOT_READY";
  if (["NOT_PROVEN", "NOT_PROVEN_YET", "NOT_CHECKED"].includes(normalized)) return "NOT_PROVEN";
  if (["UNAVAILABLE", "NOT_SUPPORTED", "NOT_SUITABLE"].includes(normalized)) return "UNAVAILABLE";
  if (["ERROR", "FAILED", "DEGRADED"].includes(normalized)) return "ERROR";
  return "UNKNOWN";
}

export const coreStateDescription: Record<CoreState, string> = {
  READY: "Backend reports ready",
  PROCESSING: "Backend reports processing",
  NOT_READY: "Backend readiness gate is closed",
  NOT_PROVEN: "Evidence is not established",
  UNAVAILABLE: "Backend reports unavailable or unsupported",
  ERROR: "Backend request failed",
  UNKNOWN: "No status evidence is available",
};
