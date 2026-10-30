import type { NeuralCoreNode } from "./coreState";

const points = [
  { x: 50, y: 15 }, { x: 82, y: 33 }, { x: 82, y: 68 },
  { x: 50, y: 86 }, { x: 18, y: 68 }, { x: 18, y: 33 },
];

export function CoreFallback({ nodes }: { nodes: NeuralCoreNode[] }) {
  return (
    <div className="neural-core-fallback" role="img" aria-label="Static conceptual HELIOX neural core; WebGL rendering is unavailable">
      <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <radialGradient id="heliox-fallback-core"><stop stopColor="#f8fafc" /><stop offset=".22" stopColor="#22d3ee" /><stop offset=".65" stopColor="#8b5cf6" stopOpacity=".7" /><stop offset="1" stopColor="#0b1026" stopOpacity="0" /></radialGradient>
        </defs>
        {points.map((point, index) => <line key={index} x1="50" y1="50" x2={point.x} y2={point.y} stroke="#38bdf8" strokeOpacity=".55" strokeWidth=".35" />)}
        <circle cx="50" cy="50" r="34" fill="url(#heliox-fallback-core)" />
        <circle cx="50" cy="50" r="22" fill="none" stroke="#a78bfa" strokeOpacity=".65" strokeWidth=".5" />
        <circle cx="50" cy="50" r="12" fill="none" stroke="#22d3ee" strokeOpacity=".9" strokeWidth=".5" />
        <text x="50" y="51.5" fill="#f8fafc" textAnchor="middle" fontSize="3.3" fontWeight="700">HELIOX</text>
      </svg>
      <span className="absolute bottom-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full border border-white/10 bg-[#050816]/80 px-3 py-1 text-[10px] text-slate-300">2D fallback · backend state retained</span>
      <span className="sr-only">{nodes.map((node) => `${node.label}: ${node.state}`).join(". ")}</span>
    </div>
  );
}
