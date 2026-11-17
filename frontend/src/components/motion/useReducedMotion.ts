import { useReducedMotion as useFMReducedMotion } from "framer-motion";

/**
 * Returns `true` when the user has `prefers-reduced-motion: reduce` set.
 * Wraps Framer Motion's hook so every animation primitive uses one source of truth.
 */
export function useReducedMotion(): boolean {
  return useFMReducedMotion() ?? false;
}
