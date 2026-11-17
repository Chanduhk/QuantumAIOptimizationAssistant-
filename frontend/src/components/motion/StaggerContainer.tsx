import { motion, type HTMLMotionProps, type Variants } from "framer-motion";
import type { ReactNode } from "react";
import { useReducedMotion } from "./useReducedMotion";
import { cn } from "@/lib/utils";

interface StaggerContainerProps extends HTMLMotionProps<"div"> {
  children: ReactNode;
  /** Stagger delay between children in seconds. Default `0.06`. */
  stagger?: number;
  /** Initial delay before the first child. */
  delay?: number;
  className?: string;
  /** HTML tag override — stays a `div` by default. */
  as?: "div" | "ul" | "ol" | "section";
}

const containerVariants = (stagger: number, delay: number, skip: boolean): Variants => ({
  hidden: {},
  visible: {
    transition: {
      staggerChildren: skip ? 0 : stagger,
      delayChildren: skip ? 0 : delay,
    },
  },
});

/** Item variant — children must spread `variants={staggerItem}` or be wrapped in StaggerItem. */
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

export function StaggerContainer({ children, stagger = 0.06, delay = 0, className, as = "div", ...rest }: StaggerContainerProps) {
  const skip = useReducedMotion();
  const MotionTag = motion[as] as typeof motion.div;

  return (
    <MotionTag
      variants={containerVariants(stagger, delay, skip)}
      initial="hidden"
      animate="visible"
      className={cn(className)}
      {...rest}
    >
      {children}
    </MotionTag>
  );
}

/** Convenience wrapper for a single stagger child. */
export function StaggerItem({ children, className, ...rest }: { children: ReactNode; className?: string } & HTMLMotionProps<"div">) {
  const skip = useReducedMotion();
  return (
    <motion.div
      variants={skip ? { hidden: { opacity: 1 }, visible: { opacity: 1 } } : staggerItem}
      className={cn(className)}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
