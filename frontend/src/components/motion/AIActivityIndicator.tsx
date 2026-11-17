import { motion } from "framer-motion";
import { useReducedMotion } from "./useReducedMotion";
import { cn } from "@/lib/utils";

interface AIActivityIndicatorProps {
  /** Whether JAM or the system is actively processing. */
  active?: boolean;
  className?: string;
}

/**
 * Orbital AI activity indicator: three concentric dots orbit
 * when `active`, and settle into a gentle pulse when idle.
 * Reflects actual system state — never purely decorative.
 */
export function AIActivityIndicator({ active, className }: AIActivityIndicatorProps) {
  const skip = useReducedMotion();

  return (
    <div className={cn("relative flex items-center justify-center", className)} aria-label={active ? "Processing" : "Idle"}>
      {/* Core */}
      <motion.div
        className="absolute size-2.5 rounded-full bg-primary"
        animate={
          skip
            ? {}
            : active
              ? { scale: [1, 1.25, 1], opacity: [1, 0.7, 1] }
              : { scale: 1, opacity: [0.6, 1, 0.6] }
        }
        transition={{
          duration: active ? 1.2 : 2.5,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      {/* Orbital dots */}
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute size-1 rounded-full bg-quantum"
          animate={
            skip
              ? {}
              : active
                ? {
                    x: [
                      8 * Math.cos((2 * Math.PI * i) / 3),
                      8 * Math.cos((2 * Math.PI * i) / 3 + Math.PI),
                      8 * Math.cos((2 * Math.PI * i) / 3 + 2 * Math.PI),
                    ],
                    y: [
                      8 * Math.sin((2 * Math.PI * i) / 3),
                      8 * Math.sin((2 * Math.PI * i) / 3 + Math.PI),
                      8 * Math.sin((2 * Math.PI * i) / 3 + 2 * Math.PI),
                    ],
                    opacity: 1,
                  }
                : {
                    x: 6 * Math.cos((2 * Math.PI * i) / 3),
                    y: 6 * Math.sin((2 * Math.PI * i) / 3),
                    opacity: [0.3, 0.7, 0.3],
                  }
          }
          transition={{
            duration: active ? 2 : 3,
            repeat: Infinity,
            ease: "linear",
            delay: i * 0.15,
          }}
        />
      ))}
    </div>
  );
}
