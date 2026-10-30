import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "outline" | "success" | "warning" | "error" | "quantum";
}

export const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = "default", ...props }, ref) => {
    const variants = {
      default: "bg-primary/12 text-primary border-primary/25",
      secondary: "bg-surface-2 text-content-secondary border-border/60",
      outline: "text-content-primary border-border/70 bg-transparent",
      success: "bg-status-success/12 text-status-success border-status-success/25",
      warning: "bg-status-warning/12 text-status-warning border-status-warning/25",
      error: "bg-status-error/12 text-status-error border-status-error/25",
      quantum: "bg-quantum/12 text-quantum border-quantum/25",
    };

    return (
      <div
        ref={ref}
        className={cn(
          "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
          variants[variant],
          className
        )}
        {...props}
      />
    );
  }
);
Badge.displayName = "Badge";
