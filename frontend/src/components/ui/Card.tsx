import * as React from "react";
import { cn } from "@/lib/utils";

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { interactive?: boolean }>(
  ({ className, interactive, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "min-w-0 rounded-2xl border border-border-subtle bg-surface-1 shadow-card dark:border-border",
        interactive && "transition-colors hover:border-content-muted/40",
        className
      )}
      {...props}
    />
  )
);
Card.displayName = "Card";

interface CardHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  eyebrow?: React.ReactNode;
  className?: string;
}

export function CardHeader({ title, description, icon, action, eyebrow, className }: CardHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between gap-4 px-5 pt-5", className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon && (
          <div className="grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-surface-2 text-content-secondary [&_svg]:size-4">
            {icon}
          </div>
        )}
        <div className="min-w-0">
          {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
          <h3 className="text-[15px] font-semibold leading-tight tracking-tight text-content-primary">{title}</h3>
          {description && <p className="mt-1 text-[13px] leading-snug text-content-tertiary">{description}</p>}
        </div>
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  );
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}

export function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center gap-3 border-t border-border-subtle px-5 py-3.5 dark:border-border", className)} {...props} />;
}

/** Label/value pair used in dense detail grids. */
export function KeyValue({ label, value, mono, className }: { label: React.ReactNode; value: React.ReactNode; mono?: boolean; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="text-xs text-content-tertiary">{label}</dt>
      <dd className={cn("mt-0.5 truncate text-sm font-medium text-content-primary", mono && "font-mono text-[13px] tabular")}>{value}</dd>
    </div>
  );
}
