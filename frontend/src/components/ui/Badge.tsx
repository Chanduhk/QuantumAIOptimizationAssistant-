import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "outline" | "success" | "warning" | "error" | "quantum";
}

export const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = "default", ...props }, ref) => {
    const variants = {
      default: "bg-primary/10 text-primary border-primary/20",
      secondary: "bg-surface-3 text-content-secondary border-transparent",
      outline: "text-content-primary border-border",
      success: "bg-status-success/10 text-status-success border-status-success/20",
      warning: "bg-status-warning/10 text-status-warning border-status-warning/20",
      error: "bg-status-error/10 text-status-error border-status-error/20",
      quantum: "bg-quantum/10 text-quantum border-quantum/20",
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
