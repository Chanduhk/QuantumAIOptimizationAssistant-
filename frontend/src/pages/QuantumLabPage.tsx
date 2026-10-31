import * as React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Atom, Binary, Check, Cpu, FlaskConical, Gauge, Microscope, Sigma, X } from "lucide-react";
import { useBenchmarkQuantum, useQuantumStatus } from "@/api/hooks";
import { Page, PageHeader } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, KeyValue } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Callout, ErrorState, Skeleton, SkeletonRows } from "@/components/ui/Feedback";
import { Meter } from "@/components/ui/Meter";
import { Stat } from "@/components/ui/Stat";
import { Bars, Legend } from "@/components/viz/Charts";
import { useChartPalette } from "@/lib/theme";
import { useOptimization } from "@/features/optimization/useOptimization";
import { parseExecutive } from "@/features/optimization/parse";
import { cleanText, humanize, num, rec, recs, str, strs, type Rec } from "@/lib/data";
import { readinessTone } from "@/lib/status";
import { cn } from "@/lib/utils";

const shortId = (id: string) => id.replace(/^bench_/, "").replace(/_/g, " ");

/** Energy landscape per instance: optimum → worst, with QAOA expectation and best sample marked. */
function EnergyLandscape({ rows }: { rows: Rec[] }) {
  const palette = useChartPalette();
  return (
    <div>
      <ul className="space-y-4">
        {rows.map((row) => {
          const exact = num(row.exact_optimal_energy) ?? 0;
          const worst = num(row.worst_energy) ?? 0;
          const expectation = num(row.expectation_energy);
          const best = num(row.best_sampled_energy);
          const span = worst - exact || 1;
          const pos = (v: number) => ((v - exact) / span) * 100;
          return (
            <li key={str(row.problem_id)} className="grid items-center gap-2 sm:grid-cols-[140px_1fr]">
              <div>
                <p className="text-[13px] font-medium capitalize text-content-primary">{shortId(str(row.problem_id))}</p>
                <p className="font-mono text-[11px] text-content-muted">{str(row.num_qubits)} qubits · p={str(row.circuit_depth_p)}</p>
              </div>
              <div className="relative h-9">
                <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-gradient-to-r from-status-success/40 via-surface-3 to-status-error/30" />
                {expectation !== null && (
                  <motion.span
                    initial={{ left: "100%", opacity: 0 }}
                    animate={{ left: `${pos(expectation)}%`, opacity: 1 }}
                    transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                    className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2"
                    style={{ background: palette.series[0], ["--tw-ring-color" as string]: palette.surface }}
                    title={`Expectation ⟨H⟩ = ${expectation}`}
                  />
                )}
                {best !== null && (
                  <span
                    className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-[2px] ring-2"
                    style={{ left: `${pos(best)}%`, background: palette.series[1], ["--tw-ring-color" as string]: palette.surface }}
                    title={`Best sampled = ${best}`}
                  />
                )}
                <span className="tabular absolute -bottom-0.5 left-0 font-mono text-[10px] text-content-muted">{exact}</span>
                <span className="tabular absolute -bottom-0.5 right-0 font-mono text-[10px] text-content-muted">{worst}</span>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 flex flex-wrap gap-4 text-[11px] text-content-secondary sm:ml-[148px]">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rotate-45 rounded-[2px]" style={{ background: palette.series[1] }} />Best sampled energy</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: palette.series[0] }} />Expectation ⟨H⟩</span>
        <span className="text-content-muted">Track runs from exact optimum (left) to worst state (right).</span>
      </div>
    </div>
  );
}

/** Interactive sizing model: how many qubits would a scheduling QUBO need? */
function ProblemSizer({ maxQubits }: { maxQubits: number }) {
  const [tasks, setTasks] = React.useState(2);
  const [hours, setHours] = React.useState(3);
  const variables = tasks * hours;
  const fits = variables <= maxQubits;
  const states = 2 ** Math.min(variables, 60);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { label: "Tasks", value: tasks, set: setTasks, max: 8 },
          { label: "Candidate hours", value: hours, set: setHours, max: 17 },
        ].map((c) => (
          <label key={c.label} className="block">
            <span className="mb-1.5 flex justify-between text-xs text-content-secondary">
              {c.label}
              <span className="tabular font-mono text-content-primary">{c.value}</span>
            </span>
            <input type="range" min={1} max={c.max} value={c.value} onChange={(e) => c.set(Number(e.target.value))} className="w-full accent-[hsl(var(--quantum))]" aria-label={c.label} />
          </label>
        ))}
      </div>
      <div className={cn("rounded-xl border p-4 transition-colors", fits ? "border-quantum/30 bg-quantum/[0.06]" : "border-status-warning/30 bg-status-warning/[0.06]")}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="tabular font-mono text-2xl font-semibold">{variables} <span className="text-sm font-normal text-content-tertiary">binary variables → qubits</span></p>
          <Badge tone={fits ? "quantum" : "warning"} dot>{fits ? "Fits local QAOA" : "Classical only"}</Badge>
        </div>
        <Meter className="mt-3" value={Math.min(variables, maxQubits)} max={maxQubits} tone={fits ? "quantum" : "warning"} label="Qubits used" />
        <p className="mt-2 text-xs text-content-tertiary">
          State space 2<sup>{variables}</sup> = {variables > 60 ? "astronomically large" : states.toLocaleString()} configurations. The simulator limit is {maxQubits} qubits ({(2 ** maxQubits).toLocaleString()} states).
        </p>
      </div>
      <p className="text-xs text-content-muted">Illustrative sizing using the one-hot task×hour encoding the backend reports (variables = tasks × candidate hours).</p>
    </div>
  );
}

export function QuantumLabPage() {
  const status = useQuantumStatus();
  const bench = useBenchmarkQuantum();
  const { result } = useOptimization();
  const view = React.useMemo(() => (result ? parseExecutive(result) : null), [result]);

  const config = rec(status.data?.config) ?? {};
  const qaoa = rec(status.data?.qaoa_config) ?? {};
  const maxQubits = num(qaoa.max_qubits) ?? num(config.max_variables_for_quantum) ?? 8;

  const b = (bench.data ?? {}) as Rec;
  const formulation = rec(b.stage_9a_formulation) ?? {};
  const classicalRefs = recs(b.stage_9b_classical_references);
  const qaoaRuns = recs(b.stage_9c_qaoa_simulations);
  const hybrid = recs(b.stage_9d_hybrid_comparisons);
  const multi = rec(b.stage_9e_multi_objective) ?? {};

  const runtimeData = qaoaRuns.map((q) => {
    const ref = classicalRefs.find((c) => c.problem_id === q.problem_id);
    return { name: shortId(str(q.problem_id)), exact: num(ref?.runtime_ms) ?? 0, qaoa: num(q.runtime_ms) ?? 0 };
  });

  const suitability = view?.optimization.suitability;

  return (
    <Page wide>
      <PageHeader
        layers="L5 · L6 · L7"
        title="Quantum Lab"
        description="How HELIOX decides whether quantum optimization is appropriate, how scheduling problems become QUBO and Ising Hamiltonians, and how QAOA compares with exact classical solutions."
      />

      <Callout tone="info" className="mb-6" icon={<Microscope className="size-4 text-quantum" />} title={cleanText(b.provenance) || "Local classical simulation — no quantum hardware execution"}>
        QAOA runs on a NumPy statevector simulator on your CPU (≤ {maxQubits} qubits). No cloud QPU is connected and no quantum advantage is claimed — the exact classical solver remains the ground truth.
      </Callout>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Quantum engine" value={status.isLoading ? "…" : status.data?.available ? "Available" : "Unavailable"} loading={status.isLoading} icon={<Atom />} accent={status.data?.available ? "quantum" : "warning"} />
        <Stat label="Max qubits" value={maxQubits} loading={status.isLoading} icon={<Cpu />} sub="Local statevector" />
        <Stat label="Shots per run" value={num(qaoa.shots)?.toLocaleString() ?? "—"} loading={status.isLoading} icon={<FlaskConical />} sub={`Seed ${str(qaoa.seed, "—")}`} />
        <Stat label="Suitability state cap" value={num(config.max_states_for_suitability)?.toLocaleString() ?? "—"} loading={status.isLoading} icon={<Gauge />} sub="States enumerable" />
        <Stat label="Classical fallback" value={config.allow_classical_fallback ? "On" : "Off"} loading={status.isLoading} icon={<Binary />} accent={config.allow_classical_fallback ? "success" : "neutral"} sub="Always authoritative" />
      </div>

      <div className="mb-5 grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader icon={<Sigma />} eyebrow="Layer 5" title="Suitability for your last plan" description="Evaluated during your most recent Optimization Studio run." />
          <CardBody>
            {suitability && str(suitability.status) ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={readinessTone(str(suitability.status))} dot size="md">{humanize(str(suitability.status))}</Badge>
                  <Badge tone="outline">Mode {humanize(str(suitability.mode))}</Badge>
                </div>
                <dl className="grid grid-cols-3 gap-3">
                  <KeyValue label="Variables" value={str(suitability.variable_count, "—")} mono />
                  <KeyValue label="Constraints" value={str(suitability.constraint_count, "—")} mono />
                  <KeyValue label="Qubit limit" value={maxQubits} mono />
                </dl>
                {strs(suitability.reasons).map((r) => <p key={r} className="rounded-lg bg-surface-2 px-3 py-2 text-[13px] text-content-secondary">{r}</p>)}
                <p className="text-xs text-content-tertiary">
                  Real daily schedules usually span many candidate hours, so they exceed the simulator and are solved classically. That is the expected, honest outcome.
                </p>
              </div>
            ) : (
              <div className="py-6 text-center">
                <p className="text-[13px] text-content-tertiary">No pipeline run in this session yet.</p>
                <Link to="/optimize" className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-primary hover:underline">Run the pipeline <ArrowRight className="size-3.5" /></Link>
              </div>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader icon={<Binary />} title="Problem sizer" description="See when a scheduling problem crosses from quantum-eligible to classical-only." />
          <CardBody>
            <ProblemSizer maxQubits={maxQubits} />
          </CardBody>
        </Card>
      </div>

      {bench.isLoading ? (
        <div className="grid gap-5 xl:grid-cols-2"><Skeleton className="h-80 rounded-2xl" /><Skeleton className="h-80 rounded-2xl" /></div>
      ) : bench.isError ? (
        <ErrorState error={bench.error} title="Couldn't load quantum benchmarks" onRetry={() => void bench.refetch()} />
      ) : (
        <div className="space-y-5">
          <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr] [&>*]:min-w-0">
            <Card>
              <CardHeader icon={<Atom />} eyebrow="Layer 6 · QAOA" title="Energy landscape per benchmark" description={`QAOA approximation ratio ${qaoaRuns.every((q) => num(q.approximation_ratio) === 1) ? "is 1.0 on every instance" : "varies by instance"} — the best sample matched the exact optimum.`} />
              <CardBody>
                <EnergyLandscape rows={qaoaRuns} />
              </CardBody>
            </Card>
            <Card>
              <CardHeader icon={<Cpu />} title="Runtime: exact solver vs QAOA simulation" description="Milliseconds per instance (y-axis in ms). Simulation cost grows with 2ⁿ." />
              <CardBody>
                <Legend className="mb-2" series={[{ key: "exact", name: "Exact classical" }, { key: "qaoa", name: "QAOA (simulated)" }]} />
                <Bars data={runtimeData} xKey="name" series={[{ key: "exact", name: "Exact classical" }, { key: "qaoa", name: "QAOA (simulated)" }]} format={(v) => (v < 10 ? v.toFixed(1) : v.toFixed(0))} height={240} />
              </CardBody>
            </Card>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1fr_1.4fr] [&>*]:min-w-0">
            <Card>
              <CardHeader icon={<Sigma />} eyebrow="QUBO ↔ Ising" title="Formulation verification" description={str(formulation.notes)} />
              <CardBody className="space-y-4">
                <div className="rounded-xl bg-surface-2 px-4 py-3 text-center font-mono text-[13px] text-content-primary">{str(formulation.transformation_convention, "x = (1 + s) / 2")}</div>
                <ul className="space-y-2 text-[13px]">
                  {[
                    ["Constraints verified", formulation.constraints_verified],
                    ["Slack encoding verified", formulation.slack_encoding_verified],
                    ["All states match exactly", formulation.all_exact_matches],
                  ].map(([label, ok]) => (
                    <li key={String(label)} className="flex items-center justify-between">
                      <span className="text-content-secondary">{String(label)}</span>
                      {ok ? <Check className="size-4 text-status-success" aria-label="Verified" /> : <X className="size-4 text-status-error" aria-label="Not verified" />}
                    </li>
                  ))}
                </ul>
                <dl className="grid grid-cols-2 gap-3">
                  <KeyValue label="Instances tested" value={str(formulation.total_instances_tested, "—")} mono />
                  <KeyValue label="States enumerated" value={str(formulation.total_states_enumerated, "—")} mono />
                  <KeyValue label="QUBO vs Ising max Δ" value={str(formulation.qubo_vs_ising_max_diff, "—")} mono />
                  <KeyValue label="Direct vs evaluated Δ" value={str(formulation.qubo_direct_vs_evaluated_max_diff, "—")} mono />
                </dl>
              </CardBody>
            </Card>

            <Card>
              <CardHeader icon={<FlaskConical />} eyebrow="Layer 7 · Hybrid" title="Hybrid selection per instance" description="The hybrid engine keeps whichever candidate reaches the lower energy." />
              <CardBody className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-[13px]">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-content-tertiary">
                      <th className="pb-2 font-medium">Instance</th>
                      <th className="pb-2 text-right font-medium">Classical E</th>
                      <th className="pb-2 text-right font-medium">QAOA E</th>
                      <th className="pb-2 text-right font-medium">Feasible</th>
                      <th className="pb-2 text-right font-medium">Runtime</th>
                      <th className="pb-2 pl-4 font-medium">Selected</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle dark:divide-border">
                    {hybrid.map((h) => (
                      <tr key={str(h.problem_id)}>
                        <td className="py-2.5 capitalize text-content-primary">{shortId(str(h.problem_id))}</td>
                        <td className="tabular py-2.5 text-right font-mono">{str(h.classical_energy)}</td>
                        <td className="tabular py-2.5 text-right font-mono">{str(h.qaoa_energy)}</td>
                        <td className="tabular py-2.5 text-right font-mono">{str(h.feasibility_rate_pct)}%</td>
                        <td className="tabular py-2.5 text-right font-mono text-content-tertiary">{num(h.runtime_ms)?.toFixed(1)}ms</td>
                        <td className="py-2.5 pl-4"><Badge tone={str(h.selected_source).includes("quantum") ? "quantum" : "neutral"}>{str(h.selected_source).includes("qaoa") ? "QAOA" : humanize(str(h.selected_source))}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-3 text-xs text-content-tertiary">When energies tie, either source is equally optimal; ties here do not indicate a quantum advantage.</p>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader icon={<Gauge />} eyebrow="Multi-objective" title="Pareto scenario optimization" description="Benchmark of the multi-objective scenario optimizer used for future simulation." />
            <CardBody>
              {Object.keys(multi).length ? (
                <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                  <KeyValue label="Scenarios" value={str(multi.num_scenarios_evaluated)} mono />
                  <KeyValue label="Pareto frontier" value={str(multi.pareto_frontier_size)} mono />
                  <KeyValue label="Non-dominated" value={multi.non_dominated_verified ? "Verified" : "Unverified"} />
                  <KeyValue label="Hypervolume" value={num(multi.hypervolume_estimate)?.toLocaleString()} mono />
                  <KeyValue label="Spread" value={str(multi.spread_metric)} mono />
                  <KeyValue label="Selected" value={`${humanize(str(multi.selected_scenario_id).replace(/^S\d+_/, ""))} · ${str(multi.selected_overall_score)}`} />
                </dl>
              ) : (
                <SkeletonRows rows={1} />
              )}
              <p className="mt-4 text-xs text-content-muted">Benchmarks executed {str(b.execution_timestamp_utc, "—")} · hardware access: {humanize(str(b.quantum_hardware_access))} · advantage observed: {b.quantum_advantage_observed ? "yes" : "no"}</p>
            </CardBody>
          </Card>
        </div>
      )}
    </Page>
  );
}
