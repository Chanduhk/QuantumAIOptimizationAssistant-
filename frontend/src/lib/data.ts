// Safe readers for the loosely-typed `result` payloads returned by the
// multi-engine endpoints. They never throw and never invent values.

export type Rec = Record<string, unknown>;

export function rec(value: unknown): Rec | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Rec) : null;
}

export function recs(value: unknown): Rec[] {
  return Array.isArray(value) ? value.filter((item): item is Rec => rec(item) !== null) : [];
}

export function strs(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0) : [];
}

export function num(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) return Number(value);
  return null;
}

export function str(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

/** Read a nested path such as `get(result, "risk_summary.risk_level")`. */
export function get(value: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, key) => rec(acc)?.[key], value);
}

/** "NOT_READY_INSUFFICIENT_DATA" -> "Not ready insufficient data" */
export function humanize(value: unknown): string {
  const raw = str(value).trim();
  if (!raw) return "—";
  const spaced = raw.replace(/[_-]+/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Fix UTF-8 em dashes that the backend occasionally returns double-encoded. */
export function cleanText(value: unknown): string {
  return str(value).replace(/â€”/g, "—").replace(/â€“/g, "–");
}

export function clamp(value: number, min = 0, max = 100): number {
  return Math.min(max, Math.max(min, value));
}

/** Backend scores arrive either as 0–1 ratios or 0–100 percentages. */
export function toPercent(value: unknown): number | null {
  const n = num(value);
  if (n === null) return null;
  return n <= 1 && n >= 0 ? n * 100 : n;
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}
