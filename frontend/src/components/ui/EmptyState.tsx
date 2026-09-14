import * as React from "react";
import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action, className, ...props }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex min-h-[400px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface-1/50 p-8 text-center animate-in fade-in-50",
        className
      )}
      {...props}
    >
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-surface-2 mb-6">
        <Icon className="h-10 w-10 text-content-secondary" />
      </div>
      <h3 className="mb-2 text-xl font-semibold text-content-primary">{title}</h3>
      <p className="mb-6 max-w-md text-sm text-content-tertiary">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
