import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface TabItem<T extends string> {
  value: T;
  label: React.ReactNode;
  count?: number;
  icon?: React.ReactNode;
}

interface SegmentedProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  size?: "sm" | "md";
  ariaLabel?: string;
}

/** Pill-style segmented control with an animated active indicator. */
export function Segmented<T extends string>({ items, value, onChange, className, size = "md", ariaLabel }: SegmentedProps<T>) {
  const layoutId = React.useId();
  return (
    <div role="tablist" aria-label={ariaLabel} className={cn("scrollbar-none inline-flex max-w-full items-center gap-0.5 overflow-x-auto rounded-xl border border-border bg-surface-2/70 p-1", className)}>
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={cn(
              "relative inline-flex shrink-0 items-center gap-1.5 rounded-lg font-medium transition-colors [&_svg]:size-3.5",
              size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]",
              active ? "text-content-primary" : "text-content-tertiary hover:text-content-secondary"
            )}
          >
            {active && (
              <motion.span
                layoutId={layoutId}
                className="absolute inset-0 rounded-lg border border-border bg-surface-1 shadow-sm dark:bg-surface-3"
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            )}
            <span className="relative inline-flex items-center gap-1.5">
              {item.icon}
              {item.label}
              {item.count !== undefined && (
                <span className={cn("tabular rounded-md px-1.5 text-[11px]", active ? "bg-surface-2 text-content-secondary dark:bg-surface-1" : "text-content-muted")}>{item.count}</span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
