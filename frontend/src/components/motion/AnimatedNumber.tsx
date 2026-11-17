import { useEffect, useRef, useState } from "react";
import { motion, useSpring, useTransform, type MotionValue } from "framer-motion";
import { useReducedMotion } from "./useReducedMotion";
import { cn } from "@/lib/utils";

interface AnimatedNumberProps {
  /** Target number to animate towards. */
  value: number;
  /** Animation duration in seconds. Default `0.8`. */
  duration?: number;
  /** Fixed decimal places. Default `0`. */
  decimals?: number;
  className?: string;
  /** Prefix string (e.g. "$"). */
  prefix?: string;
  /** Suffix string (e.g. "%"). */
  suffix?: string;
}

function AnimatedDigits({ motionValue, decimals }: { motionValue: MotionValue<number>; decimals: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const display = useTransform(motionValue, (v) => v.toFixed(decimals));

  useEffect(() => display.on("change", (v) => { if (ref.current) ref.current.textContent = v; }), [display]);
  return <span ref={ref} />;
}

/**
 * Smoothly animates a numeric value from 0 (or its previous value) to the target.
 * GPU-friendly: uses `useSpring` for buttery 60 fps interpolation.
 */
export function AnimatedNumber({ value, duration = 0.8, decimals = 0, className, prefix, suffix }: AnimatedNumberProps) {
  const skip = useReducedMotion();
  const [hasAppeared, setHasAppeared] = useState(false);
  const spring = useSpring(0, { duration: skip ? 0 : duration * 1000, bounce: 0 });

  useEffect(() => {
    if (!hasAppeared) {
      spring.set(value);
      setHasAppeared(true);
    } else {
      spring.set(value);
    }
  }, [value, spring, hasAppeared]);

  if (skip) {
    return <span className={cn(className)}>{prefix}{value.toFixed(decimals)}{suffix}</span>;
  }

  return (
    <motion.span className={cn(className)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      {prefix}
      <AnimatedDigits motionValue={spring} decimals={decimals} />
      {suffix}
    </motion.span>
  );
}
