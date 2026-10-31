import * as React from "react";
import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import type { ScheduleBlock } from "@/features/optimization/parse";
import { formatClock } from "@/lib/format";
import { cn } from "@/lib/utils";

const priorityFill: Record<number, string> = {
  5: "bg-primary/90 text-primary-foreground",
  4: "bg-primary/70 text-primary-foreground",
  3: "bg-quantum/75 text-quantum-foreground",
  2: "bg-quantum/50 text-content-primary",
  1: "bg-content-muted/40 text-content-primary",
};

interface ScheduleTimelineProps {
  blocks: ScheduleBlock[];
  focusHours?: number[];
  className?: string;
  /** Optional working window; otherwise derived from the blocks. */
  window?: [number, number];
}

/**
 * Gantt-style day timeline: one row per task so overlapping recommendations
 * stay readable. Focus hours are shaded behind the rows.
 */
export function ScheduleTimeline({ blocks, focusHours = [], className, window: fixed }: ScheduleTimelineProps) {
  const [hovered, setHovered] = React.useState<string | null>(null);
  if (blocks.length === 0) return null;

  const minStart = Math.floor(Math.min(...blocks.map((b) => b.start), ...(fixed ? [fixed[0]] : [])));
  const maxEnd = Math.ceil(Math.max(...blocks.map((b) => b.end), ...(fixed ? [fixed[1]] : [])));
  const from = Math.max(0, Math.min(minStart, maxEnd - 4));
  const to = Math.min(24, Math.max(maxEnd, from + 4));
  const span = to - from;
  const hours = Array.from({ length: span + 1 }, (_, i) => from + i);
  const pct = (h: number) => ((h - from) / span) * 100;
  const sorted = [...blocks].sort((a, b) => a.start - b.start);

  return (
    <div className={cn("w-full", className)}>
      <div className="relative ml-0 sm:ml-[180px]">
        {/* Hour axis */}
        <div className="relative h-5">
          {hours.map((h) => (
            <span key={h} className="tabular absolute -translate-x-1/2 font-mono text-[10px] text-content-muted" style={{ left: `${pct(h)}%` }}>
              {String(h % 24).padStart(2, "0")}
            </span>
          ))}
        </div>
      </div>

      <div className="relative">
        {/* Grid + focus shading behind the rows */}
        <div className="pointer-events-none absolute inset-y-0 left-0 right-0 sm:left-[180px]">
          {focusHours.filter((h) => h >= from && h < to).map((h) => (
            <div key={`f${h}`} className="absolute inset-y-0 bg-primary/[0.10]" style={{ left: `${pct(h)}%`, width: `${100 / span}%` }} />
          ))}
          {hours.map((h) => (
            <div key={h} className="absolute inset-y-0 w-px bg-border-subtle dark:bg-border/70" style={{ left: `${pct(h)}%` }} />
          ))}
        </div>

        <ul className="relative space-y-1.5 py-1.5">
          {sorted.map((block, i) => {
            const fill = priorityFill[block.priority ?? 3] ?? priorityFill[3];
            const isHover = hovered === block.key;
            return (
              <li key={block.key} className="flex flex-col gap-1 sm:flex-row sm:items-center" onMouseEnter={() => setHovered(block.key)} onMouseLeave={() => setHovered(null)}>
                <div className="flex min-w-0 items-center gap-2 sm:w-[180px] sm:shrink-0 sm:pr-3">
                  <span className="truncate text-[13px] font-medium text-content-primary" title={block.title}>{block.title}</span>
                  {block.warning && <AlertTriangle className="size-3.5 shrink-0 text-status-warning" aria-label={block.warning} />}
                </div>
                <div className="relative h-8 w-full sm:flex-1">
                  <motion.div
                    initial={{ opacity: 0, scaleX: 0.6 }}
                    animate={{ opacity: 1, scaleX: 1 }}
                    transition={{ delay: i * 0.05, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                    style={{ left: `${pct(Math.max(from, block.start))}%`, width: `${Math.max(2.5, pct(Math.min(to, block.end)) - pct(Math.max(from, block.start)))}%`, transformOrigin: "left" }}
                    className={cn(
                      "absolute inset-y-0 flex items-center overflow-hidden rounded-md px-2 text-[11px] font-medium shadow-sm ring-2 ring-transparent transition-shadow",
                      fill,
                      isHover && "ring-content-primary/20"
                    )}
                    title={`${block.title} · ${formatClock(block.start)}–${formatClock(block.end)}${block.rationale ? `\n${block.rationale}` : ""}`}
                  >
                    <span className="tabular truncate font-mono">{pct(Math.min(to, block.end)) - pct(Math.max(from, block.start)) >= 22 ? `${formatClock(block.start)}–${formatClock(block.end)}` : formatClock(block.start)}</span>
                  </motion.div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      {hovered && (() => {
        const block = sorted.find((b) => b.key === hovered);
        if (!block || (!block.rationale && !block.meta && !block.warning)) return null;
        return (
          <div className="mt-2 rounded-lg bg-surface-2 px-3 py-2 text-xs text-content-secondary sm:ml-[180px]">
            <span className="font-medium text-content-primary">{block.title}</span>
            {block.meta && <> · {block.meta}</>}
            {block.rationale && <p className="mt-0.5 text-content-tertiary">{block.rationale}</p>}
            {block.warning && <p className="mt-0.5 text-status-warning">{block.warning}</p>}
          </div>
        );
      })()}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-content-tertiary sm:ml-[180px]">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-primary/90" />P5–P4</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-quantum/75" />P3–P2</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-content-muted/40" />P1</span>
        {focusHours.length > 0 && <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-primary/15" />Focus hours</span>}
      </div>
    </div>
  );
}
