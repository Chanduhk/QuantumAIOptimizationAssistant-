import * as React from "react";
import { cn } from "@/lib/utils";

export type BadgeTone = "neutral" | "primary" | "quantum" | "success" | "warning" | "error" | "outline";

const tones: Record<BadgeTone, string> = {
  neutral: "bg-surface-2 text-content-secondary border-border",
  primary: "bg-primary/10 text-primary border-primary/25",
  quantum: "bg-quantum/10 text-quantum border-quantum/25",
  success: "bg-status-success/10 text-status-success border-status-success/25",
  warning: "bg-status-warning/10 text-status-warning border-status-warning/25",
  error: "bg-status-error/10 text-status-error border-status-error/25",
  outline: "bg-transparent text-content-tertiary border-border",
};

const dotTones: Record<BadgeTone, string> = {
  neutral: "bg-content-tertiary",
  primary: "bg-primary",
  quantum: "bg-quantum",
  success: "bg-status-success",
  warning: "bg-status-warning",
  error: "bg-status-error",
  outline: "bg-content-muted",
};

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  dot?: boolean;
  pulse?: boolean;
  size?: "sm" | "md";
}

export function Badge({ tone = "neutral", dot, pulse, size = "sm", className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 whitespace-nowrap rounded-full border font-medium",
        size === "sm" ? "h-[22px] px-2 text-[11px]" : "h-6 px-2.5 text-xs",
        tones[tone],
        className
      )}
      {...props}
    >
      {dot && <span className={cn("size-1.5 shrink-0 rounded-full", dotTones[tone], pulse && "animate-pulse-soft")} />}
      <span className="truncate">{children}</span>
    </span>
  );
}

export function StatusDot({ tone = "success", pulse, className }: { tone?: BadgeTone; pulse?: boolean; className?: string }) {
  return (
    <span className={cn("relative inline-flex size-2 shrink-0", className)}>
      {pulse && <span className={cn("absolute inset-0 animate-ping rounded-full opacity-50", dotTones[tone])} />}
      <span className={cn("relative inline-flex size-2 rounded-full", dotTones[tone])} />
    </span>
  );
}

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd className={cn("inline-flex h-5 min-w-5 items-center justify-center rounded border border-border bg-surface-2 px-1 font-mono text-[10px] font-medium text-content-tertiary", className)}>
      {children}
    </kbd>
  );
}
