import * as React from "react";
import { AlertTriangle, CheckCircle2, Info, OctagonAlert, RotateCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { normalizeErrorMessage } from "@/utils/formatters";

export function Spinner({ size = "md", className }: { size?: "sm" | "md" | "lg"; className?: string }) {
  const dims = { sm: "size-3.5 border-[1.5px]", md: "size-5 border-2", lg: "size-8 border-2" }[size];
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn("inline-block shrink-0 animate-spin rounded-full border-current border-r-transparent text-primary", dims, className)}
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton rounded-md", className)} />;
}

export function SkeletonRows({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2.5", className)} aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-xl" />
      ))}
    </div>
  );
}

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  compact?: boolean;
}

export function EmptyState({ icon, title, description, action, className, compact }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center text-center", compact ? "px-4 py-8" : "px-6 py-14", className)}>
      {icon && (
        <div className="mb-4 grid size-11 place-items-center rounded-xl border border-border bg-surface-2 text-content-tertiary [&_svg]:size-5">
          {icon}
        </div>
      )}
      <p className="text-sm font-semibold text-content-primary">{title}</p>
      {description && <div className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-content-tertiary">{description}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title, className }: { error: unknown; onRetry?: () => void; title?: string; className?: string }) {
  const normalized = normalizeErrorMessage(error);
  return (
    <div role="alert" className={cn("flex items-start gap-3 rounded-xl border border-status-error/25 bg-status-error/[0.06] p-4", className)}>
      <OctagonAlert className="mt-0.5 size-4 shrink-0 text-status-error" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-content-primary">{title ?? normalized.title}</p>
        <p className="mt-0.5 text-[13px] text-content-secondary">{normalized.explanation}</p>
        {normalized.actionSuggestion && <p className="mt-1 text-xs text-content-tertiary">{normalized.actionSuggestion}</p>}
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-content-secondary hover:bg-surface-2 hover:text-content-primary"
        >
          <RotateCw className="size-3.5" /> Retry
        </button>
      )}
    </div>
  );
}

type Tone = "info" | "success" | "warning" | "error" | "neutral";

const toneStyles: Record<Tone, { box: string; icon: React.ReactNode }> = {
  info: { box: "border-quantum/25 bg-quantum/[0.06]", icon: <Info className="size-4 text-quantum" /> },
  success: { box: "border-status-success/25 bg-status-success/[0.06]", icon: <CheckCircle2 className="size-4 text-status-success" /> },
  warning: { box: "border-status-warning/25 bg-status-warning/[0.07]", icon: <AlertTriangle className="size-4 text-status-warning" /> },
  error: { box: "border-status-error/25 bg-status-error/[0.06]", icon: <OctagonAlert className="size-4 text-status-error" /> },
  neutral: { box: "border-border bg-surface-2/60", icon: <Info className="size-4 text-content-tertiary" /> },
};

export function Callout({ tone = "info", title, children, action, className, icon }: {
  tone?: Tone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}) {
  const style = toneStyles[tone];
  return (
    <div className={cn("flex items-start gap-3 rounded-xl border px-4 py-3", style.box, className)}>
      <span className="mt-0.5 shrink-0">{icon ?? style.icon}</span>
      <div className="min-w-0 flex-1 text-[13px] leading-relaxed text-content-secondary">
        {title && <p className="font-medium text-content-primary">{title}</p>}
        {children}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  );
}
