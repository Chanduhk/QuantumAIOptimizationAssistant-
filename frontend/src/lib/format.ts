import { parseUtcDate } from "@/utils/formatters";

/** "3 min ago", "2 h ago", "Yesterday", or a date. */
export function formatRelative(value: string | number | Date | null | undefined, now = Date.now()): string {
  const date = parseUtcDate(value);
  if (!date) return "—";
  const diff = (now - date.getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
  if (diff < 172800) return "yesterday";
  if (diff < 604800) return `${Math.round(diff / 86400)} days ago`;
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

/** Decimal hour (e.g. 13.5) to a clock string ("13:30"). */
export function formatClock(hour: unknown): string {
  if (typeof hour !== "number" || !Number.isFinite(hour)) return "--:--";
  const h = Math.floor(hour) % 24;
  const m = Math.round((hour % 1) * 60);
  return `${String(h).padStart(2, "0")}:${String(m === 60 ? 0 : m).padStart(2, "0")}`;
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function formatPct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function greeting(date = new Date()): string {
  const h = date.getHours();
  if (h < 5) return "Working late";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}
