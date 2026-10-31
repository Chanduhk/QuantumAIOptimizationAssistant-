import { cn } from "@/lib/utils";

/**
 * Decorative orbital diagram: a solar core (the user's goals) with three orbits
 * standing for intelligence, optimization and learning. Purely visual.
 */
export function OrbitalSystem({ className }: { className?: string }) {
  const orbits = [
    { r: 70, dur: "animate-orbit", dots: [0, 140], tone: "hsl(var(--quantum))" },
    { r: 112, dur: "animate-orbit-slow", dots: [60, 210, 300], tone: "hsl(var(--primary))" },
    { r: 154, dur: "animate-orbit", dots: [30, 180], tone: "hsl(var(--content-tertiary))" },
  ];
  return (
    <svg viewBox="-170 -170 340 340" className={cn("overflow-visible", className)} aria-hidden>
      <defs>
        <radialGradient id="orb-core" cx="40%" cy="38%" r="65%">
          <stop offset="0%" stopColor="#ffe3a3" />
          <stop offset="50%" stopColor="#f5a524" />
          <stop offset="100%" stopColor="#c76a06" />
        </radialGradient>
        <radialGradient id="orb-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#f5a524" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#f5a524" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle r="90" fill="url(#orb-glow)" />
      {orbits.map((orbit, i) => (
        <g key={orbit.r}>
          <circle r={orbit.r} fill="none" stroke="hsl(var(--content-primary))" strokeOpacity={0.09} strokeDasharray={i === 2 ? "2 6" : undefined} />
          <g className={orbit.dur} style={{ transformOrigin: "0 0", animationDirection: i === 1 ? "reverse" : undefined }}>
            {orbit.dots.map((deg) => {
              const rad = (deg * Math.PI) / 180;
              return <circle key={deg} cx={orbit.r * Math.cos(rad)} cy={orbit.r * Math.sin(rad)} r={i === 1 ? 4 : 3} fill={orbit.tone} />;
            })}
          </g>
        </g>
      ))}
      <circle r="30" fill="url(#orb-core)" />
    </svg>
  );
}
