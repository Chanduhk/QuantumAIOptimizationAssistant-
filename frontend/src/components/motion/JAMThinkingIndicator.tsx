import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useReducedMotion } from "./useReducedMotion";
import { Cpu, Sparkles, Binary, Brain, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

const STAGES = [
  { icon: Sparkles, text: "Understanding your request & extracting constraints…", color: "text-primary" },
  { icon: Layers, text: "Synthesizing tasks & classical constraint scheduling…", color: "text-primary" },
  { icon: Binary, text: "Evaluating quantum suitability & QAOA optimization…", color: "text-quantum" },
  { icon: Brain, text: "Executive Brain validating feasibility & trade-offs…", color: "text-primary" },
  { icon: Cpu, text: "Assembling explainable schedule & recommendations…", color: "text-status-success" },
];

/**
 * Premium HELIOX AI thinking indicator.
 * Displays orbital neural motion and progressively cycles through real
 * pipeline stages so the user understands the exact optimization journey.
 */
export function JAMThinkingIndicator({ className }: { className?: string }) {
  const skip = useReducedMotion();
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    if (skip) return;
    const interval = setInterval(() => {
      setStageIndex((prev) => (prev + 1) % STAGES.length);
    }, 2800);
    return () => clearInterval(interval);
  }, [skip]);

  const currentStage = STAGES[stageIndex];
  const Icon = currentStage.icon;

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border bg-surface-1/90 p-4 shadow-card backdrop-blur-sm",
        className
      )}
    >
      {/* Soft progressive scanline at top border */}
      <div className="absolute inset-x-0 top-0 h-[2px] overflow-hidden bg-surface-3">
        {!skip && (
          <motion.div
            className="h-full w-1/3 bg-gradient-to-r from-transparent via-primary to-transparent"
            animate={{ x: ["-100%", "350%"] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
      </div>

      <div className="flex items-center gap-3.5">
        {/* Orbital node core */}
        <div className="relative grid size-8 shrink-0 place-items-center rounded-xl border border-primary/20 bg-primary/10">
          {!skip && (
            <>
              {/* Outer orbit ring */}
              <motion.div
                className="absolute inset-[-4px] rounded-xl border border-primary/25"
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
              />
              {/* Orbital satellite dot */}
              <motion.div
                className="absolute size-1.5 rounded-full bg-quantum shadow-[0_0_8px_hsl(var(--quantum))]"
                animate={{
                  x: [12 * Math.cos(0), 12 * Math.cos(Math.PI), 12 * Math.cos(2 * Math.PI)],
                  y: [12 * Math.sin(0), 12 * Math.sin(Math.PI), 12 * Math.sin(2 * Math.PI)],
                }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
              />
            </>
          )}
          <Icon className={cn("size-4 transition-colors duration-300", currentStage.color)} />
        </div>

        {/* Dynamic stage narrative */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="eyebrow text-[10px] text-content-tertiary">Optimization Pipeline</span>
            <span className="inline-flex items-center gap-1">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="size-1 rounded-full bg-primary"
                  animate={skip ? {} : { opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }}
                  transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                />
              ))}
            </span>
          </div>

          <AnimatePresence mode="wait">
            <motion.p
              key={stageIndex}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.28, ease: "easeOut" }}
              className="mt-0.5 truncate text-[13px] font-medium text-content-secondary"
            >
              {currentStage.text}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
