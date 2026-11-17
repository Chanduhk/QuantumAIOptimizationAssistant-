import * as React from "react";
import { cn } from "@/lib/utils";
import { Skeleton } from "./Feedback";
import { AnimatedNumber } from "@/components/motion/AnimatedNumber";

interface StatProps {
  label: React.ReactNode;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon?: React.ReactNode;
  loading?: boolean;
  className?: string;
  accent?: "primary" | "quantum" | "success" | "warning" | "error" | "neutral";
}

const accentIcon = {
  primary: "text-primary bg-primary/10",
  quantum: "text-quantum bg-quantum/10",
  success: "text-status-success bg-status-success/10",
  warning: "text-status-warning bg-status-warning/10",
  error: "text-status-error bg-status-error/10",
  neutral: "text-content-tertiary bg-surface-2",
};

/** Stat tile: label, value, optional supporting line. */
export function Stat({ label, value, sub, icon, loading, className, accent = "neutral" }: StatProps) {
  return (
    <div className={cn("group rounded-2xl border border-border-subtle bg-surface-1 p-4 shadow-card transition-all duration-300 hover:-translate-y-0.5 hover:border-content-muted/30 hover:shadow-lift dark:border-border", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[13px] text-content-tertiary">{label}</p>
        {icon && <span className={cn("grid size-7 place-items-center rounded-lg transition-transform duration-300 group-hover:scale-110 [&_svg]:size-3.5", accentIcon[accent])}>{icon}</span>}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-7 w-20" />
      ) : (
        <p className="tabular mt-2 text-[26px] font-semibold leading-none tracking-tight text-content-primary">
          {typeof value === "number" ? <AnimatedNumber value={value} /> : value}
        </p>
      )}
      {sub && <div className="mt-2 text-xs text-content-tertiary">{sub}</div>}
    </div>
  );
}
