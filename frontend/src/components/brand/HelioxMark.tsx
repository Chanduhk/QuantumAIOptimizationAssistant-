import { cn } from "@/lib/utils";

/** HELIOX mark: a solar core with an inclined orbit and a single satellite. */
export function HelioxMark({ className, animated }: { className?: string; animated?: boolean }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} aria-hidden>
      <defs>
        <radialGradient id="hx-core" cx="45%" cy="40%" r="60%">
          <stop offset="0%" stopColor="#ffd88a" />
          <stop offset="55%" stopColor="#f5a524" />
          <stop offset="100%" stopColor="#d9780b" />
        </radialGradient>
      </defs>
      <circle cx="16" cy="16" r="5.2" fill="url(#hx-core)" />
      <g transform="rotate(-28 16 16)">
        <ellipse cx="16" cy="16" rx="12" ry="4.6" fill="none" stroke="hsl(var(--quantum))" strokeWidth="1.5" opacity="0.9" />
        <g className={animated ? "origin-center animate-orbit" : undefined} style={{ transformOrigin: "16px 16px" }}>
          <circle cx="28" cy="16" r="1.8" fill="hsl(var(--quantum))" />
        </g>
      </g>
    </svg>
  );
}

export function HelioxWordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <HelioxMark className="size-7" />
      <span className="text-[15px] font-semibold tracking-[0.14em] text-content-primary">
        HELIOX<span className="ml-1 font-medium tracking-normal text-content-tertiary">AI</span>
      </span>
    </span>
  );
}
