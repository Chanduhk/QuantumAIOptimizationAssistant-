import { useRef, useState, type PointerEvent } from "react";
import { motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";

const coreNodes = [
  { label: "Memory", x: 92, y: 42 },
  { label: "Behavior", x: 210, y: 22 },
  { label: "Prediction", x: 328, y: 45 },
  { label: "Planning", x: 350, y: 136 },
  { label: "Optimization", x: 210, y: 157 },
  { label: "Decision", x: 70, y: 132 },
];

export function IntelligenceCoreVisual() {
  const edges = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0], [1, 4], [0, 4], [2, 4]];
  return (
    <div className="relative overflow-hidden rounded-xl border border-border/70 bg-surface-1/90 backdrop-blur-md p-4 sm:p-6 shadow-sm">
      <div className="absolute inset-0 opacity-20" aria-hidden="true" style={{ backgroundImage: "radial-gradient(circle at 50% 50%, hsl(var(--primary) / .08), transparent 60%)" }} />
      <div className="relative flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">HELIOX Intelligence Core</p>
          <p className="mt-1 text-xs text-content-secondary">Conceptual information flow · decorative visualization</p>
        </div>
        <span className="w-fit rounded-full border border-border/60 bg-surface-2/80 px-2.5 py-1 text-[11px] text-content-tertiary">Not a live execution trace</span>
      </div>
      <motion.svg
        viewBox="0 0 420 185"
        role="img"
        aria-label="Conceptual information flow among memory, behavior, prediction, planning, optimization, and decision"
        className="relative mt-3 h-40 w-full sm:h-48"
        style={{ transform: "perspective(900px) rotateX(8deg)" }}
        animate={{ rotateY: [0, 1.5, 0, -1.5, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      >
        <defs>
          <linearGradient id="core-line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity=".15" />
            <stop offset="50%" stopColor="hsl(var(--quantum))" stopOpacity=".5" />
            <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity=".15" />
          </linearGradient>
        </defs>
        {edges.map(([a, b]) => (
          <line key={`${a}-${b}`} x1={coreNodes[a].x} y1={coreNodes[a].y} x2={coreNodes[b].x} y2={coreNodes[b].y} stroke="url(#core-line)" strokeWidth="1.2" strokeDasharray="4 6" opacity="0.75" />
        ))}
        <circle cx="210" cy="91" r="28" fill="hsl(var(--primary) / .06)" stroke="hsl(var(--primary) / .25)" />
        <circle cx="210" cy="91" r="17" fill="hsl(var(--surface-2))" stroke="hsl(var(--quantum) / .4)" />
        <text x="210" y="95" fill="currentColor" textAnchor="middle" fontSize="8" fontWeight="700">HELIOX</text>
        {coreNodes.map((node, index) => (
          <g key={node.label}>
            <circle cx={node.x} cy={node.y} r="12" fill="hsl(var(--surface-1))" stroke={index === 4 ? "hsl(var(--quantum) / .6)" : "hsl(var(--primary) / .5)"} strokeWidth="1.5" />
            <circle cx={node.x} cy={node.y} r="3" fill={index === 4 ? "hsl(var(--quantum))" : "hsl(var(--primary))"} />
            <text x={node.x} y={node.y + 25} fill="currentColor" textAnchor="middle" fontSize="8" className="fill-content-secondary">{node.label}</text>
          </g>
        ))}
      </motion.svg>
      <div className="relative flex flex-wrap gap-2 text-[11px] text-content-tertiary">
        <span>Memory & knowledge</span><span aria-hidden="true">→</span><span>Behavior</span><span aria-hidden="true">→</span><span>Prediction</span><span aria-hidden="true">→</span><span>Planning & decision</span>
      </div>
    </div>
  );
}

export type PipelineStageState = "complete" | "active" | "blocked" | "pending";

export interface PipelineStage {
  label: string;
  state: PipelineStageState;
  detail?: string;
}

export function OptimizationPipelineVisual({ stages }: { stages: PipelineStage[] }) {
  const styles: Record<PipelineStageState, string> = {
    complete: "border-status-success/40 bg-status-success/10 text-status-success",
    active: "border-primary/50 bg-primary/10 text-primary",
    blocked: "border-status-warning/40 bg-status-warning/10 text-status-warning",
    pending: "border-border bg-surface-2 text-content-tertiary",
  };
  return (
    <div className="rounded-xl border border-border bg-surface-1 p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div><h3 className="font-semibold text-content-primary">Optimization Pipeline</h3><p className="mt-1 text-xs text-content-secondary">Stage indicators reflect returned backend evidence.</p></div>
        <span className="text-[11px] text-content-tertiary">Animation illustrates flow; it is not a circuit run.</span>
      </div>
      <ol className="flex gap-2 overflow-x-auto pb-2" aria-label="Optimization pipeline stages">
        {stages.map((stage, index) => (
          <li key={`${stage.label}-${index}`} className="flex min-w-[132px] flex-1 items-center gap-2">
            <div className={`heliox-pipeline-stage min-w-0 flex-1 rounded-lg border p-3 ${styles[stage.state]}`}>
              <div className="flex items-center gap-2"><span className="text-[10px] font-semibold opacity-70">{String(index + 1).padStart(2, "0")}</span><span className="truncate text-xs font-semibold">{stage.label}</span></div>
              <p className="mt-1 truncate text-[10px] opacity-80">{stage.detail ?? stage.state.replace("_", " ")}</p>
            </div>
            {index < stages.length - 1 && <span className="shrink-0 text-content-tertiary" aria-hidden="true">→</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

interface QuantumVisualizationVariable {
  id: string;
  taskId?: string;
  candidateHour?: number;
}

interface QuantumVisualizationTerm {
  left: string;
  right: string;
  coefficient: number;
}

function parseVariables(input: unknown): QuantumVisualizationVariable[] {
  if (!Array.isArray(input)) return [];
  const variables = input.flatMap((item): QuantumVisualizationVariable[] => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const row = item as Record<string, unknown>;
    const id = row.variable_id ?? row.variable ?? row.id;
    if (typeof id !== "string" || !id.trim()) return [];
    const taskId = row.task_id;
    const candidateHour = row.candidate_hour ?? row.hour;
    return [{ id, ...(typeof taskId === "string" ? { taskId } : {}), ...(typeof candidateHour === "number" && Number.isFinite(candidateHour) ? { candidateHour } : {}) }];
  });
  return new Set(variables.map((variable) => variable.id)).size === variables.length ? variables : [];
}

function parseTerms(input: unknown): QuantumVisualizationTerm[] {
  if (!Array.isArray(input)) return [];
  return input.flatMap((item): QuantumVisualizationTerm[] => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const row = item as Record<string, unknown>;
    const pair = row.variables;
    const left = row.left ?? (Array.isArray(pair) ? pair[0] : undefined);
    const right = row.right ?? (Array.isArray(pair) ? pair[1] : undefined);
    const coefficient = row.coefficient;
    if (typeof left !== "string" || typeof right !== "string" || typeof coefficient !== "number" || !Number.isFinite(coefficient)) return [];
    return [{ left, right, coefficient }];
  });
}

export function QuantumConceptVisual({ variableMapping, quadraticTerms }: { variableMapping: unknown; quadraticTerms: unknown }) {
  const [rotation, setRotation] = useState({ x: 8, y: -18 });
  const [zoom, setZoom] = useState(1);
  const drag = useRef<{ x: number; y: number; rotationX: number; rotationY: number } | null>(null);
  const variables = parseVariables(variableMapping);
  const terms = parseTerms(quadraticTerms).filter((term) => variables.some((variable) => variable.id === term.left) && variables.some((variable) => variable.id === term.right));
  const points = variables.map((variable, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(variables.length, 1) - Math.PI / 2;
    return { ...variable, x: 50 + Math.cos(angle) * 38, y: 50 + Math.sin(angle) * 38 };
  });
  const pointById = new Map(points.map((point) => [point.id, point]));
  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    drag.current = { x: event.clientX, y: event.clientY, rotationX: rotation.x, rotationY: rotation.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    setRotation({ x: drag.current.rotationX - (event.clientY - drag.current.y) * 0.35, y: drag.current.rotationY + (event.clientX - drag.current.x) * 0.35 });
  };
  const reset = () => { setRotation({ x: 8, y: -18 }); setZoom(1); };
  return (
    <section className="rounded-xl border border-border/70 bg-surface-1/90 backdrop-blur-md p-4 sm:p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-quantum">Quantum Optimization Visualization</p><p className="mt-1 text-sm text-content-secondary">Backend-provided variables and pairwise terms · local software simulation only</p></div>
        {points.length > 0 && <Button type="button" variant="secondary" size="sm" onClick={reset} aria-label="Reset visualization"><RotateCcw className="mr-2 h-3.5 w-3.5" />Reset view</Button>}
      </div>
      {points.length === 0 ? <div className="mt-5 flex min-h-48 items-center justify-center rounded-lg border border-dashed border-border bg-background/50 p-6 text-center"><div><p className="font-medium text-content-primary">Quantum problem data unavailable</p><p className="mt-2 max-w-xl text-sm text-content-secondary">No backend-provided variable mapping is present in the latest result. A conceptual sample graph is intentionally not shown.</p></div></div> : <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(220px,.75fr)]">
        <div
          className="relative flex min-h-64 select-none items-center justify-center overflow-hidden rounded-lg border border-border/70 bg-background/60 touch-none"
          role="application"
          aria-label="Interactive graph of backend-provided optimization variables. Drag to rotate."
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={() => { drag.current = null; }}
          onPointerCancel={() => { drag.current = null; }}
        >
          <div className="relative aspect-square w-56 sm:w-64" style={{ transform: `perspective(700px) rotateX(${rotation.x}deg) rotateY(${rotation.y}deg) scale(${zoom})`, transformStyle: "preserve-3d", transition: "transform 180ms ease-out" }}>
            <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full overflow-visible" aria-hidden="true">
            {terms.map((term, index) => {
              const left = pointById.get(term.left);
              const right = pointById.get(term.right);
              if (!left || !right) return null;
              return <line key={`${term.left}-${term.right}-${index}`} x1={left.x} y1={left.y} x2={right.x} y2={right.y} stroke={term.coefficient < 0 ? "hsl(var(--quantum) / .65)" : "hsl(var(--primary) / .55)"} strokeWidth="1.2"><title>{`${term.left} ↔ ${term.right}; coefficient ${term.coefficient}`}</title></line>;
            })}
            </svg>
            {points.map((variable, index) => <div key={variable.id} title={variable.taskId && variable.candidateHour !== undefined ? `Task ${variable.taskId} at ${variable.candidateHour}:00` : variable.id} className="absolute flex h-11 min-w-11 max-w-28 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-quantum/50 bg-surface-1 px-2 text-[10px] font-semibold text-quantum shadow-sm sm:text-xs" style={{ left: `${variable.x}%`, top: `${variable.y}%`, transform: `translate(-50%, -50%) translateZ(${index % 2 ? 22 : 42}px)` }}>{variable.taskId && variable.candidateHour !== undefined ? `${variable.taskId} · ${variable.candidateHour}:00` : variable.id}</div>)}
          </div>
          <span className="absolute bottom-3 left-3 rounded bg-surface-1/80 px-2 py-1 text-[10px] text-content-tertiary">Backend formulation visualization · no hardware represented</span>
        </div>
        <div className="flex flex-col justify-center gap-4">
          <label className="text-xs font-medium text-content-secondary" htmlFor="quantum-visual-zoom">Visualization zoom
            <input id="quantum-visual-zoom" className="mt-2 w-full accent-[hsl(var(--quantum))]" type="range" min="0.75" max="1.25" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} />
          </label>
          <div className="rounded-lg border border-border bg-surface-1/70 p-3 text-xs leading-relaxed text-content-secondary">
            Each node is taken from the returned variable mapping. Lines are shown only for quadratic coefficients present in the returned formulation. No physical qubits or hardware are represented.
          </div>
          {terms.length > 0 && <details className="rounded-lg border border-border bg-surface-1/70 p-3 text-xs text-content-secondary"><summary className="cursor-pointer font-medium text-content-primary">Returned coupling coefficients</summary><ul className="mt-2 max-h-32 space-y-1 overflow-auto">{terms.map((term, index) => <li key={`${term.left}-${term.right}-${index}`} className="break-all"><code>{term.left} × {term.right}</code>: {term.coefficient}</li>)}</ul></details>}
          <p className="text-[11px] text-content-tertiary">Drag to rotate. Zoom is a visual control only and does not alter an optimization problem or simulator configuration. {terms.length === 0 ? "No quadratic terms were returned." : `${terms.length} returned quadratic terms.`}</p>
        </div>
      </div>}
    </section>
  );
}
