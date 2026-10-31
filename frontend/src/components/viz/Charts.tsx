import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
  ZAxis,
} from "recharts";
import { useChartPalette } from "@/lib/theme";
import { cn } from "@/lib/utils";

interface TooltipEntry {
  name?: string | number;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
  payload?: Record<string, unknown>;
}

function ChartTooltip({ active, payload, label, format, labelKey }: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  format?: (v: number) => string;
  labelKey?: string;
}) {
  if (!active || !payload?.length) return null;
  const heading = labelKey ? String(payload[0]?.payload?.[labelKey] ?? label ?? "") : label;
  return (
    <div className="pointer-events-none min-w-[140px] rounded-lg border border-border bg-surface-1 px-3 py-2 text-xs shadow-lift">
      {heading !== undefined && heading !== "" && <p className="mb-1 font-medium text-content-primary">{heading}</p>}
      <ul className="space-y-0.5">
        {payload.map((entry, i) => (
          <li key={i} className="flex items-center justify-between gap-4 text-content-secondary">
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-sm" style={{ background: entry.color }} />
              {entry.name}
            </span>
            <span className="tabular font-mono text-content-primary">
              {typeof entry.value === "number" ? (format ? format(entry.value) : entry.value.toLocaleString(undefined, { maximumFractionDigits: 2 })) : entry.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface SeriesDef {
  key: string;
  name: string;
}

export function Legend({ series, className }: { series: SeriesDef[]; className?: string }) {
  const palette = useChartPalette();
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-content-secondary", className)}>
      {series.map((s, i) => (
        <span key={s.key} className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 rounded-sm" style={{ background: palette.series[i] }} />
          {s.name}
        </span>
      ))}
    </div>
  );
}

const axisProps = (palette: ReturnType<typeof useChartPalette>) => ({
  tick: { fill: palette.axis, fontSize: 11 },
  axisLine: false,
  tickLine: false,
});

interface BarsProps {
  data: Array<Record<string, unknown>>;
  xKey: string;
  series: SeriesDef[];
  height?: number;
  format?: (v: number) => string;
  domain?: [number | "auto", number | "auto"];
  highlightKey?: string;
  referenceY?: { value: number; label: string };
  layout?: "vertical" | "horizontal";
  className?: string;
}

/** Column or bar chart. One axis, ≤24px bars, 4px rounded data-end, 2px surface gap. */
export function Bars({ data, xKey, series, height = 220, format, domain, highlightKey, referenceY, layout = "horizontal", className }: BarsProps) {
  const palette = useChartPalette();
  const horizontalBars = layout === "vertical";
  return (
    <div className={cn("w-full", className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout={layout} margin={{ top: 8, right: 12, bottom: 0, left: horizontalBars ? 8 : -12 }} barGap={2} barCategoryGap="28%">
          <CartesianGrid stroke={palette.grid} vertical={horizontalBars} horizontal={!horizontalBars} />
          {horizontalBars ? (
            <>
              <XAxis type="number" {...axisProps(palette)} domain={domain ?? [0, "auto"]} tickFormatter={format} />
              <YAxis type="category" dataKey={xKey} {...axisProps(palette)} width={120} />
            </>
          ) : (
            <>
              <XAxis dataKey={xKey} {...axisProps(palette)} interval={data.length <= 8 ? 0 : "preserveStartEnd"} />
              <YAxis {...axisProps(palette)} domain={domain ?? [0, "auto"]} tickFormatter={format} width={44} />
            </>
          )}
          <Tooltip cursor={{ fill: palette.muted, opacity: 0.35 }} content={<ChartTooltip format={format} />} />
          {referenceY && <ReferenceLine y={referenceY.value} stroke={palette.axis} strokeDasharray="0" strokeOpacity={0.6} label={{ value: referenceY.label, fill: palette.axis, fontSize: 10, position: "insideTopRight" }} />}
          {series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={palette.series[i]}
              maxBarSize={24}
              radius={horizontalBars ? [0, 4, 4, 0] : [4, 4, 0, 0]}
              stroke={palette.surface}
              strokeWidth={series.length > 1 ? 1 : 0}
              isAnimationActive
              animationDuration={600}
            >
              {highlightKey &&
                data.map((row, idx) => (
                  <Cell key={idx} fill={palette.series[i]} fillOpacity={row[highlightKey] ? 1 : 0.45} />
                ))}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Single-series area/line over an ordered x axis (2px line, ~10% wash). */
export function AreaLine({ data, xKey, yKey, name, height = 220, format, domain, className }: {
  data: Array<Record<string, unknown>>;
  xKey: string;
  yKey: string;
  name: string;
  height?: number;
  format?: (v: number) => string;
  domain?: [number | "auto", number | "auto"];
  className?: string;
}) {
  const palette = useChartPalette();
  const id = React.useId().replace(/:/g, "");
  const color = palette.series[0];
  return (
    <div className={cn("w-full", className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
          <defs>
            <linearGradient id={`fill-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.18} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={palette.grid} vertical={false} />
          <XAxis dataKey={xKey} {...axisProps(palette)} />
          <YAxis {...axisProps(palette)} domain={domain ?? ["auto", "auto"]} tickFormatter={format} width={44} />
          <Tooltip cursor={{ stroke: palette.axis, strokeWidth: 1 }} content={<ChartTooltip format={format} />} />
          <Area
            type="monotone"
            dataKey={yKey}
            name={name}
            stroke={color}
            strokeWidth={2}
            fill={`url(#fill-${id})`}
            dot={{ r: 4, fill: color, stroke: palette.surface, strokeWidth: 2 }}
            activeDot={{ r: 5, fill: color, stroke: palette.surface, strokeWidth: 2 }}
            animationDuration={700}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Scatter of estimated vs actual minutes with a y = x reference. */
export function EstimateScatter({ data, height = 260, className }: { data: Array<{ estimated: number; actual: number; title: string }>; height?: number; className?: string }) {
  const palette = useChartPalette();
  const max = Math.max(30, ...data.map((d) => Math.max(d.estimated, d.actual))) * 1.1;
  return (
    <div className={cn("w-full", className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: -8 }}>
          <CartesianGrid stroke={palette.grid} />
          <XAxis type="number" dataKey="estimated" name="Estimated" unit="m" domain={[0, Math.ceil(max)]} {...axisProps(palette)} />
          <YAxis type="number" dataKey="actual" name="Actual" unit="m" domain={[0, Math.ceil(max)]} {...axisProps(palette)} width={48} />
          <ZAxis range={[80, 80]} />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: max, y: max }]} stroke={palette.axis} strokeOpacity={0.5} />
          <Tooltip cursor={{ strokeDasharray: "0", stroke: palette.grid }} content={<ChartTooltip labelKey="title" format={(v) => `${Math.round(v)} min`} />} />
          <Scatter name="Task" data={data} fill={palette.series[0]} stroke={palette.surface} strokeWidth={2} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
