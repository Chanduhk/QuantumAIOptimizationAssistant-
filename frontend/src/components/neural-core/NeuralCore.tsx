import { useCallback, useRef, useState, type PointerEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Activity, Network } from "lucide-react";
import { NeuralCoreCanvas, type NeuralCoreView } from "./NeuralCoreCanvas";
import { CoreFallback } from "./CoreFallback";
import { type CoreState, type NeuralCoreNode } from "./coreState";

const stateClass: Record<CoreState, string> = {
  READY: "border-primary/35 bg-primary/10 text-primary",
  PROCESSING: "border-quantum/40 bg-quantum/12 text-quantum",
  NOT_READY: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  NOT_PROVEN: "border-slate-400/25 bg-slate-400/10 text-slate-300",
  UNAVAILABLE: "border-slate-500/20 bg-slate-500/10 text-slate-400",
  ERROR: "border-rose-400/35 bg-rose-400/10 text-rose-200",
  UNKNOWN: "border-white/15 bg-white/5 text-slate-300",
};

const nodePosition: Record<string, string> = {
  memory: "left-[3%] top-[44%]",
  behavior: "left-[17%] top-[8%]",
  prediction: "right-[17%] top-[8%]",
  planning: "right-[3%] top-[44%]",
  optimization: "right-[9%] bottom-[9%]",
  quantum: "left-[44%] bottom-[3%]",
  executive: "left-[9%] bottom-[9%]",
};

export interface CoreActivityStatus {
  state: "idle" | "processing" | "active_task" | "completed";
  label: string;
  detail?: string;
}

export function NeuralCore({ nodes, activity }: { nodes: NeuralCoreNode[]; activity?: CoreActivityStatus }) {
  const [fallback, setFallback] = useState(false);
  const viewRef = useRef<NeuralCoreView>({ rotationX: 0, rotationY: 0, zoom: 1 });
  const dragRef = useRef<{ x: number; y: number } | null>(null);
  const showFallback = useCallback(() => setFallback(true), []);
  const active = activity?.state === "processing" || activity?.state === "active_task" || nodes.some((node) => node.state === "PROCESSING");
  const overall = nodes.find((node) => node.id === "executive")?.state ?? "UNKNOWN";
  const topNodes = nodes.filter((node) => ["memory", "behavior", "prediction", "planning", "optimization", "quantum", "executive"].includes(node.id));
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (!(event.target instanceof HTMLCanvasElement)) return;
    dragRef.current = { x: event.clientX, y: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragRef.current) return;
    viewRef.current.rotationY += (event.clientX - dragRef.current.x) * 0.008;
    viewRef.current.rotationX = Math.max(-0.8, Math.min(0.8, viewRef.current.rotationX + (event.clientY - dragRef.current.y) * 0.006));
    dragRef.current = { x: event.clientX, y: event.clientY };
  };
  const resetView = () => { viewRef.current = { rotationX: 0, rotationY: 0, zoom: 1 }; };
  const setZoom = (value: number) => { viewRef.current.zoom = value; };

  const activityBadgeClass = {
    idle: "border-border/70 bg-surface-2/60 text-content-secondary",
    processing: "border-quantum/40 bg-quantum/15 text-quantum",
    active_task: "border-primary/40 bg-primary/15 text-primary",
    completed: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  }[activity?.state ?? "idle"];

  return (
    <section className="overflow-hidden rounded-2xl border border-border/70 bg-surface-1/90 backdrop-blur-xl text-content-primary shadow-celestial" aria-labelledby="neural-core-title">
      <div className="flex flex-col gap-4 border-b border-border/60 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-7">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[.22em] text-primary">HELIOX · Intelligence visualization</p>
          <h2 id="neural-core-title" className="mt-1 text-xl font-semibold tracking-tight sm:text-2xl text-content-primary">HELIOX Neural Core</h2>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-content-secondary sm:text-sm">
            A live visualization of your authenticated workspace activity and intelligence readiness. Subtle cosmic motion is aesthetic; real states reflect verified database records.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Live Genuine Activity Badge */}
          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${activityBadgeClass}`}>
            <span className={`h-2 w-2 rounded-full ${
              activity?.state === "processing" ? "bg-quantum animate-ping" :
              activity?.state === "active_task" ? "bg-primary animate-pulse" :
              activity?.state === "completed" ? "bg-emerald-400" : "bg-slate-400"
            }`} />
            {activity?.label ?? "Workspace Idle · Ready"}
          </span>

          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${stateClass[overall]}`}>
            <Activity className="h-3.5 w-3.5" />
            Executive evidence: {overall.replaceAll("_", " ")}
          </span>
          {!fallback && <button type="button" onClick={resetView} className="rounded-full border border-border/60 bg-surface-2/40 px-3 py-1.5 text-xs text-content-secondary hover:border-primary/40 hover:text-content-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">Reset view</button>}
        </div>
      </div>

      <div className="relative min-h-[390px] overflow-hidden sm:min-h-[450px] xl:min-h-[520px]" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={() => { dragRef.current = null; }} onPointerCancel={() => { dragRef.current = null; }} onWheel={(event) => { if (!fallback) { event.preventDefault(); setZoom(Math.max(0.78, Math.min(1.32, viewRef.current.zoom - event.deltaY * 0.001))); } }}>
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_48%,rgba(98,138,202,.12),transparent_35%),radial-gradient(ellipse_at_52%_51%,rgba(88,76,148,.10),transparent_55%),linear-gradient(135deg,hsl(var(--background)),hsl(var(--surface-1))_55%,hsl(var(--surface-2)))]" aria-hidden="true" />
        <div className="absolute inset-0 opacity-25" aria-hidden="true" style={{ backgroundImage: "radial-gradient(rgba(148,163,184,.45) .6px,transparent .6px)", backgroundSize: "29px 29px" }} />
        {fallback ? <div className="absolute left-1/2 top-[42%] h-[min(78vw,320px)] w-[min(78vw,320px)] -translate-x-1/2 -translate-y-1/2"><CoreFallback nodes={nodes} /></div> : <NeuralCoreCanvas active={active} onUnavailable={showFallback} viewRef={viewRef} />}
        <div className="pointer-events-none absolute left-1/2 top-1/2 hidden h-[68%] w-[68%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary/10 xl:block" aria-hidden="true" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 hidden h-[84%] w-[84%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-quantum/10 xl:block" aria-hidden="true" />

        <svg className="pointer-events-none absolute inset-0 hidden h-full w-full xl:block" viewBox="0 0 1000 510" preserveAspectRatio="none" aria-hidden="true">
          <g fill="none" stroke="hsl(var(--primary))" strokeOpacity=".18" strokeWidth="1">
            <path d="M500 230 C390 165 290 110 190 100" /><path d="M500 230 C420 130 370 75 320 52" />
            <path d="M500 230 C580 130 640 75 690 52" /><path d="M500 230 C610 165 710 110 810 100" />
            <path d="M500 230 C610 280 690 335 770 385" /><path d="M500 230 C470 315 455 375 440 420" />
            <path d="M500 230 C370 280 300 335 230 385" />
          </g>
        </svg>

        <div className="absolute inset-3 hidden xl:block">
          {topNodes.map((node) => (
            <Link key={node.id} to={node.route} title={`${node.label}: ${node.detail}`} aria-label={`${node.label}. ${node.detail}. Open ${node.route === "/planning" ? "Planning" : node.route === "/optimization" ? "Optimization" : node.route === "/quantum" ? "Quantum Workspace" : "Intelligence"}.`} className={`group absolute ${nodePosition[node.id]} flex max-w-40 items-center gap-2 rounded-xl border px-3 py-2 text-left shadow-lg backdrop-blur-md transition hover:scale-[1.04] hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${stateClass[node.state]}`}>
              <span className="min-w-0"><span className="block truncate text-xs font-semibold">{node.label}</span><span className="mt-0.5 block truncate text-[9px] opacity-75">{node.state.replaceAll("_", " ")}</span></span>
              <ArrowUpRight className="h-3 w-3 shrink-0 opacity-60 group-hover:opacity-100" />
            </Link>
          ))}
        </div>
        <div className="pointer-events-none absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 text-center xl:block">
          <p className="text-[10px] font-semibold uppercase tracking-[.3em] text-content-primary/80">
            {activity?.state === "active_task" ? "Active Task" : activity?.state === "processing" ? "Processing" : "Neural Core"}
          </p>
          <p className="mt-0.5 text-xs font-semibold text-primary truncate max-w-[180px]">
            {activity?.label ?? "System Idle · Ready"}
          </p>
          <p className="mt-0.5 text-[9px] text-content-tertiary">Conceptual starlight field</p>
        </div>
        {!fallback && <label className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded-full border border-border/60 bg-surface-1/80 px-3 py-2 text-[10px] text-content-secondary backdrop-blur" htmlFor="neural-core-zoom">Zoom <input id="neural-core-zoom" aria-label="Neural Core visualization zoom" type="range" min="0.78" max="1.32" step="0.02" defaultValue="1" className="w-20 accent-primary" onChange={(event) => setZoom(Number(event.target.value))} /></label>}
      </div>
      <div className="grid gap-2 border-t border-border/60 bg-surface-1/95 p-4 sm:grid-cols-2 xl:hidden" aria-label="Module readiness details">
        {topNodes.map((node) => <Link key={node.id} to={node.route} className={`flex min-w-0 items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-xs ${stateClass[node.state]}`} aria-label={`${node.label}: ${node.state}. ${node.detail}`}><span className="truncate font-medium">{node.label}</span><span className="shrink-0 text-[10px]">{node.state.replaceAll("_", " ")}</span></Link>)}
      </div>
    </section>
  );
}
