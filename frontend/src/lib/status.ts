import type { BadgeTone } from "@/components/ui/Badge";
import type { ProviderStatusResponse } from "@/api/endpoints";
import { humanize } from "./data";

export interface ProviderState {
  short: string;
  detail: string;
  tone: BadgeTone;
  live: boolean;
}

/**
 * Describes the language provider honestly: a configured key is not the same
 * as a verified, working connection.
 */
export function providerState(provider: ProviderStatusResponse | undefined | null): ProviderState {
  if (!provider) return { short: "Checking parser…", detail: "", tone: "neutral", live: false };
  const known: Record<string, string> = { openai: "OpenAI", anthropic: "Anthropic", gemini: "Gemini", groq: "Groq", ollama: "Ollama" };
  const name = known[provider.provider?.toLowerCase()] ?? (provider.provider ? provider.provider.charAt(0).toUpperCase() + provider.provider.slice(1) : "LLM");
  const modelName = provider.display_model || provider.model || "Gemini 3.8 Flash";
  if (provider.status?.endsWith("_configured_and_available")) {
    return { short: `${name} live`, detail: `${modelName} verified and answering requests.`, tone: "success", live: true };
  }
  if (!provider.is_configured) {
    return { short: "Rule-based parser", detail: "No LLM configured. JAM uses its deterministic planning parser.", tone: "neutral", live: false };
  }
  if (provider.fallback_active) {
    return { short: `${name} fallback`, detail: `${provider.status_label}. Requests use the deterministic parser.`, tone: "warning", live: false };
  }
  return {
    short: `${name} key set`,
    detail: `${modelName} is configured but has not been verified live in this session. Requests fall back to the deterministic parser if the call fails.`,
    tone: "quantum",
    live: false,
  };
}

/** Tone for component operational_state values from the inventory. */
export function componentTone(state: string | null | undefined): BadgeTone {
  switch (state) {
    case "AVAILABLE":
    case "TRAINED":
    case "PRETRAINED":
      return "success";
    case "READY_FOR_TRAINING":
      return "quantum";
    case "NOT_READY_INSUFFICIENT_DATA":
    case "UNINITIALIZED":
    case "DEGRADED":
      return "warning";
    case "API_UNAVAILABLE":
    case "FAILED":
    case "UNREGISTERED":
      return "error";
    default:
      return "neutral";
  }
}

/** Tone for readiness statuses such as NOT_READY_INSUFFICIENT_DATA or READY_FOR_TRAINING. */
export function readinessTone(status: string | null | undefined): BadgeTone {
  const s = (status ?? "").toUpperCase();
  if (!s) return "neutral";
  if (s.startsWith("NOT_READY") || s.includes("INSUFFICIENT") || s.includes("GATED")) return "warning";
  if (s.includes("FAIL") || s.includes("ERROR") || s.includes("INVALID")) return "error";
  if (s.includes("READY") || s.includes("COMPLETE") || s.includes("PRODUCTION") || s.includes("TRAINED") || s === "SUITABLE") return "success";
  if (s.includes("NOT_SUPPORTED") || s.includes("CLASSICAL_ONLY")) return "neutral";
  return "neutral";
}

export function statusLabel(status: string | null | undefined): string {
  return humanize(status ?? "");
}
