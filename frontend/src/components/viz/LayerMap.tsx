import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { ComponentInventoryItem } from "@/api/endpoints";
import { LAYERS, type ArchitectureLayer } from "@/lib/architecture";
import { StatusDot, type BadgeTone } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

export interface LayerSignal {
  value: string;
  tone?: BadgeTone;
}

const stageLabel: Record<ArchitectureLayer["stage"], string> = {
  capture: "Capture",
  intelligence: "Understand",
  optimize: "Optimize",
  decide: "Decide",
  learn: "Act & learn",
};

const stageAccent: Record<ArchitectureLayer["stage"], string> = {
  capture: "before:bg-content-tertiary/60",
  intelligence: "before:bg-quantum/70",
  optimize: "before:bg-quantum",
  decide: "before:bg-primary",
  learn: "before:bg-status-success/80",
};

function layerTone(layer: ArchitectureLayer, components: Map<string, ComponentInventoryItem>, loading: boolean): { tone: BadgeTone; label: string } {
  if (!layer.components.length) return { tone: "success", label: "Live data" };
  if (loading) return { tone: "neutral", label: "Checking" };
  const items = layer.components.map((id) => components.get(id)).filter(Boolean) as ComponentInventoryItem[];
  if (!items.length) return { tone: "neutral", label: "Not reported" };
  if (items.some((c) => !c.can_execute_now || c.operational_state === "FAILED")) return { tone: "error", label: "Unavailable" };
  if (items.some((c) => c.fallback_active)) return { tone: "warning", label: "Fallback active" };
  return { tone: "success", label: "Operational" };
}

const STAGES: ArchitectureLayer["stage"][] = ["capture", "intelligence", "optimize", "decide", "learn"];

/** The 13 architecture layers in five stage columns, left to right in pipeline order. */
export function LayerMap({ components, loading, signals }: { components: ComponentInventoryItem[]; loading: boolean; signals: Partial<Record<number, LayerSignal>> }) {
  const byId = new Map(components.map((c) => [c.canonical_id || c.component_id, c]));
  let index = 0;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5 lg:gap-3">
      {STAGES.map((stage, si) => (
        <section key={stage} aria-label={stageLabel[stage]} className="min-w-0">
          <div className="mb-2 flex items-center gap-2">
            <span className="font-mono text-[10px] text-content-muted">0{si + 1}</span>
            <span className="eyebrow">{stageLabel[stage]}</span>
            {si < STAGES.length - 1 && <span className="hidden h-px flex-1 bg-gradient-to-r from-border to-transparent lg:block" />}
          </div>
          <ol className="space-y-2">
            {LAYERS.filter((l) => l.stage === stage).map((layer) => {
              const state = layerTone(layer, byId, loading);
              const signal = signals[layer.n];
              const delay = index++ * 0.025;
              return (
                <motion.li key={layer.n} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay }}>
                  <Link
                    to={layer.route}
                    className={cn(
                      "group relative flex flex-col overflow-hidden rounded-xl border border-border-subtle bg-surface-1 p-3 pl-4 transition-all hover:-translate-y-0.5 hover:border-border hover:shadow-card dark:border-border dark:hover:border-content-muted/40",
                      "before:absolute before:inset-y-0 before:left-0 before:w-[3px]",
                      stageAccent[layer.stage]
                    )}
                    title={`${layer.name}: ${layer.summary} · ${state.label}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] uppercase tracking-wider text-content-muted">Layer {layer.n}</span>
                      <StatusDot tone={state.tone} />
                    </div>
                    <p className="mt-1 text-[13px] font-medium leading-tight text-content-primary">{layer.name}</p>
                    <p className="mt-0.5 line-clamp-1 text-[11px] text-content-tertiary">{layer.summary}</p>
                    <p className={cn("tabular mt-2 truncate font-mono text-xs", signal?.tone === "warning" ? "text-status-warning" : "text-content-secondary")}>{signal?.value ?? state.label}</p>
                  </Link>
                </motion.li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
