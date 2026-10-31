import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { clamp } from "@/lib/data";

export type MeterTone = "primary" | "quantum" | "success" | "warning" | "error" | "neutral";

const fillTone: Record<MeterTone, string> = {
  primary: "bg-primary",
  quantum: "bg-quantum",
  success: "bg-status-success",
  warning: "bg-status-warning",
  error: "bg-status-error",
  neutral: "bg-content-tertiary",
};

const trackTone: Record<MeterTone, string> = {
  primary: "bg-primary/15",
  quantum: "bg-quantum/15",
  success: "bg-status-success/15",
  warning: "bg-status-warning/15",
  error: "bg-status-error/15",
  neutral: "bg-surface-3",
};

const strokeTone: Record<MeterTone, string> = {
  primary: "stroke-primary",
  quantum: "stroke-quantum",
  success: "stroke-status-success",
  warning: "stroke-status-warning",
  error: "stroke-status-error",
  neutral: "stroke-content-tertiary",
};

/** Horizontal meter. The track is a lighter step of the fill's hue. */
export function Meter({ value, max = 100, tone = "primary", className, label }: { value: number; max?: number; tone?: MeterTone; className?: string; label?: string }) {
  const pct = max > 0 ? clamp((value / max) * 100) : 0;
  return (
    <div
      role="meter"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
      className={cn("h-1.5 w-full overflow-hidden rounded-full", trackTone[tone], className)}
    >
      <motion.div
        className={cn("h-full rounded-full", fillTone[tone])}
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      />
    </div>
  );
}

/** Circular progress ring with a centered label. */
export function Ring({ value, max = 100, size = 64, stroke = 6, tone = "primary", children, className, label }: {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  tone?: MeterTone;
  children?: React.ReactNode;
  className?: string;
  label?: string;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = max > 0 ? clamp(value / max, 0, 1) : 0;
  return (
    <div className={cn("relative inline-grid shrink-0 place-items-center", className)} style={{ width: size, height: size }} role="meter" aria-valuenow={Math.round(value)} aria-valuemax={max} aria-label={label}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} className={cn(strokeTone[tone], "opacity-15")} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className={strokeTone[tone]}
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - pct) }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}

/** Maps a 0–100 "higher is better" score to a severity tone. */
export function scoreTone(score: number | null | undefined, invert = false): MeterTone {
  if (score === null || score === undefined || !Number.isFinite(score)) return "neutral";
  const s = invert ? 100 - score : score;
  if (s >= 70) return "success";
  if (s >= 45) return "primary";
  if (s >= 25) return "warning";
  return "error";
}
