import { motion, type HTMLMotionProps, type Variants } from "framer-motion";
import type { ReactNode } from "react";
import { useReducedMotion } from "./useReducedMotion";
import { cn } from "@/lib/utils";

type Direction = "up" | "down" | "left" | "right" | "none";

const offsets: Record<Direction, { x: number; y: number }> = {
  up: { x: 0, y: 12 },
  down: { x: 0, y: -12 },
  left: { x: 12, y: 0 },
  right: { x: -12, y: 0 },
  none: { x: 0, y: 0 },
};

interface FadeInProps extends HTMLMotionProps<"div"> {
  children: ReactNode;
  /** Direction the element slides from. Default `"up"`. */
  direction?: Direction;
  /** Delay in seconds. */
  delay?: number;
  /** Duration in seconds. Default `0.45`. */
  duration?: number;
  className?: string;
}

/** Fades-and-translates a single element on mount. GPU-friendly (opacity + translate). */
export function FadeIn({ children, direction = "up", delay = 0, duration = 0.45, className, ...rest }: FadeInProps) {
  const skip = useReducedMotion();
  const { x, y } = offsets[direction];

  const variants: Variants = {
    hidden: skip ? { opacity: 1 } : { opacity: 0, x, y },
    visible: { opacity: 1, x: 0, y: 0 },
  };

  return (
    <motion.div
      variants={variants}
      initial="hidden"
      animate="visible"
      transition={{ duration: skip ? 0 : duration, delay: skip ? 0 : delay, ease: [0.22, 1, 0.36, 1] }}
      className={cn(className)}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
