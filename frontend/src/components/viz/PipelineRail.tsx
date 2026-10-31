import { motion } from "framer-motion";
import { Check, CircleDashed, Minus, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

export type StageState = "done" | "skipped" | "blocked" | "pending" | "running";

export interface PipelineStage {
  id: string;
  layer: string;
  label: string;
  state: StageState;
  value?: string;
}

const stateStyle: Record<StageState, { ring: string; icon: React.ReactNode; text: string }> = {
  done: { ring: "border-status-success/40 bg-status-success/10 text-status-success", icon: <Check className="size-3.5" />, text: "text-content-primary" },
  skipped: { ring: "border-border bg-surface-2 text-content-tertiary", icon: <Minus className="size-3.5" />, text: "text-content-secondary" },
  blocked: { ring: "border-status-warning/40 bg-status-warning/10 text-status-warning", icon: <TriangleAlert className="size-3.5" />, text: "text-content-primary" },
  pending: { ring: "border-border bg-surface-1 text-content-muted", icon: <CircleDashed className="size-3.5" />, text: "text-content-tertiary" },
  running: { ring: "border-primary/50 bg-primary/10 text-primary", icon: <span className="size-2 animate-pulse rounded-full bg-primary" />, text: "text-content-primary" },
};

/** Horizontal stage rail for the L4→L9 optimization pipeline. */
export function PipelineRail({ stages, className }: { stages: PipelineStage[]; className?: string }) {
  return (
    <ol className={cn("scrollbar-none -mx-1 flex snap-x items-stretch overflow-x-auto px-1", className)}>
      {stages.map((stage, i) => {
        const style = stateStyle[stage.state];
        return (
          <li key={stage.id} className="flex min-w-[150px] flex-1 snap-start items-start">
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="flex w-full flex-col"
            >
              <div className="flex items-center">
                <span className={cn("grid size-7 shrink-0 place-items-center rounded-full border", style.ring)}>{style.icon}</span>
                {i < stages.length - 1 && (
                  <span className="relative mx-2 h-px flex-1 overflow-hidden bg-border">
                    {stage.state === "running" && <span className="absolute inset-y-0 w-1/3 animate-slide bg-primary/70" />}
                  </span>
                )}
              </div>
              <div className="mt-2.5 pr-3">
                <p className="font-mono text-[10px] uppercase tracking-wider text-content-muted">{stage.layer}</p>
                <p className={cn("text-[13px] font-medium leading-tight", style.text)}>{stage.label}</p>
                {stage.value && <p className="mt-0.5 truncate text-xs text-content-tertiary" title={stage.value}>{stage.value}</p>}
              </div>
            </motion.div>
          </li>
        );
      })}
    </ol>
  );
}
