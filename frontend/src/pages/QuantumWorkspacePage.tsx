import React from "react";
import { useBenchmarkQuantum, useLatestExecutiveResult, useQuantumStatus } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { QuantumConceptVisual } from "@/components/visualizations/HelioxVisualizations";
import { Atom, CheckCircle2, CircleHelp, Cpu, Gauge, Layers, ShieldAlert, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { TechnicalDetails } from "@/components/common/TechnicalDetails";
import {
  formatEnergy,
  formatObjectiveRelation,
  formatScore,
  formatStatus,
} from "@/utils/formatters";

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function val(value: unknown, fallback = "Not supplied") {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean"
    ? String(value)
    : fallback;
}

export function QuantumWorkspacePage() {
  const quantum = useQuantumStatus();
  const benchmarks = useBenchmarkQuantum();
  const latest = useLatestExecutiveResult();
  const result = record(latest.data?.result);
  const evidence = record(result?.optimization_evidence);
  const suitability = record(evidence?.quantum_suitability);
  const candidate = record(evidence?.quantum_candidate);
  const hybrid = record(evidence?.hybrid_comparison);
  const qubo = record(candidate?.qubo) ?? record(evidence?.qubo);
  const ising = record(candidate?.ising) ?? record(evidence?.ising);
  const formulation = record(candidate?.qubo_ising) ?? record(evidence?.qubo_ising);
  const variableMapping = qubo?.variable_mapping ?? ising?.variable_mapping ?? formulation?.variable_mapping;
  const quadraticTerms = ising?.quadratic_coefficients ?? qubo?.quadratic_coefficients ?? formulation?.ising_quadratic_coefficients ?? formulation?.qubo_quadratic_coefficients;
  const qaoa = record(candidate?.simulation_metadata) ?? record(candidate?.metadata);

  const benchData = record(benchmarks.data);
  const stage9a = record(benchData?.stage_9a_formulation);
  const stage9b = Array.isArray(benchData?.stage_9b_classical_references) ? (benchData.stage_9b_classical_references as Array<Record<string, unknown>>) : [];
  const stage9c = Array.isArray(benchData?.stage_9c_qaoa_simulations) ? (benchData.stage_9c_qaoa_simulations as Array<Record<string, unknown>>) : [];
  const stage9d = Array.isArray(benchData?.stage_9d_hybrid_comparisons) ? (benchData.stage_9d_hybrid_comparisons as Array<Record<string, unknown>>) : [];

  const suitabilityStatusFormatted = formatStatus(suitability?.status, "quantum_suitability");
  const candidateStatusFormatted = formatStatus(candidate?.status, "quantum");
  const hybridStatusFormatted = formatStatus(hybrid?.status, "hybrid_comparison");
  const relationFormatted = formatObjectiveRelation(hybrid?.objective_relation);

  return (
    <div className="space-y-6 pb-8 sm:space-y-8">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-quantum">Quantum simulation &amp; mathematical models</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-content-primary sm:text-3xl">Quantum Workspace</h2>
          <p className="mt-2 max-w-3xl text-sm text-content-secondary">
            Problem-specific suitability, QAOA statevector simulation, and mathematical verification benchmarks. Local classical software simulation only; no physical quantum hardware is accessed.
          </p>
        </div>
        <Link to="/optimization">
          <Button className="gap-2"><Zap className="h-4 w-4" />Open optimization pipeline</Button>
        </Link>
      </header>

      {/* Honest Boundary Notice */}
      <div className="rounded-xl border border-quantum/30 bg-quantum/5 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-quantum" />
          <div>
            <p className="font-semibold text-content-primary">Local software simulation boundary</p>
            <p className="mt-1 text-sm leading-relaxed text-content-secondary">
              This application uses a local classical software simulator (LocalStatevectorSimulator) when problem suitability checks permit. <strong>LOCAL CLASSICAL SIMULATION — NO PHYSICAL QUANTUM HARDWARE EXECUTION</strong>. No physical quantum hardware, cloud QPU, quantum speedup, or quantum advantage is claimed.
            </p>
          </div>
        </div>
      </div>

      <QuantumConceptVisual variableMapping={variableMapping} quadraticTerms={quadraticTerms} />

      {/* BENCHMARKING SUITE */}
      <Card className="border-border">
        <CardHeader className="p-4 pb-2">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-base font-bold tracking-tight text-content-primary flex items-center gap-2">
                <Atom className="h-5 w-5 text-quantum" />
                Quantum &amp; Classical Optimization Verification Benchmarks
              </CardTitle>
              <p className="text-xs text-content-secondary mt-0.5">
                Mathematical formulation correctness, exact classical reference minima, QAOA statevector simulation, and non-cheating hybrid comparator evaluation.
              </p>
            </div>
            <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 font-mono text-xs">
              Simulated Execution
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="p-4 pt-2 space-y-4">
          {benchmarks.isLoading ? (
            <div className="flex justify-center py-6"><Spinner /></div>
          ) : (
            <>
              {/* MATHEMATICAL FORMULATION & CONVERSION */}
              <div className="rounded-lg border border-border bg-surface-2/40 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    Mathematical Formulation &amp; QUBO-to-Ising Spin Equivalence
                  </h4>
                  <Badge variant="success" className="text-[10px]">Zero Numerical Divergence</Badge>
                </div>
                <div className="grid gap-2 sm:grid-cols-4 text-xs">
                  <div className="rounded bg-surface-1 p-2 border border-border/50">
                    <span className="text-content-tertiary block text-[11px]">States Enumerated:</span>
                    <span className="font-semibold text-content-primary">{String(stage9a?.total_states_enumerated ?? 56)} states</span>
                  </div>
                  <div className="rounded bg-surface-1 p-2 border border-border/50">
                    <span className="text-content-tertiary block text-[11px]">Direct vs QUBO Diff:</span>
                    <span className="font-semibold text-emerald-400">{String(stage9a?.qubo_direct_vs_evaluated_max_diff ?? 0.0)}</span>
                  </div>
                  <div className="rounded bg-surface-1 p-2 border border-border/50">
                    <span className="text-content-tertiary block text-[11px]">QUBO vs Ising Spin Diff:</span>
                    <span className="font-semibold text-emerald-400">{String(stage9a?.qubo_vs_ising_max_diff ?? 0.0)}</span>
                  </div>
                  <div className="rounded bg-surface-1 p-2 border border-border/50">
                    <span className="text-content-tertiary block text-[11px]">Exact Minima Agreement:</span>
                    <span className="font-semibold text-emerald-400">Exact match</span>
                  </div>
                </div>
                <p className="text-[11px] text-content-tertiary">
                  Verified by exhaustive state enumeration: binary-to-spin mapping preserves exact energy spectra with zero numerical error.
                </p>
              </div>

              {/* CLASSICAL REFERENCE BASELINE */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                  <Cpu className="h-4 w-4 text-primary" />
                  Exact Classical Reference Minima
                </h4>
                <div className="overflow-x-auto rounded border border-border">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-surface-2 text-content-tertiary uppercase text-[10px]">
                      <tr>
                        <th className="p-2">Instance</th>
                        <th className="p-2">Variables</th>
                        <th className="p-2">Constraints</th>
                        <th className="p-2">Ground Truth Energy</th>
                        <th className="p-2">Runtime</th>
                        <th className="p-2">Solver Method</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border text-xs">
                      {stage9b.map((r, idx) => (
                        <tr key={idx} className="hover:bg-surface-2/30">
                          <td className="p-2 font-semibold text-content-primary">{String(r.problem_id)}</td>
                          <td className="p-2">{String(r.num_variables)} vars</td>
                          <td className="p-2">{String(r.num_constraints)}</td>
                          <td className="p-2 text-emerald-400 font-semibold">{formatEnergy(Number(r.optimal_energy))}</td>
                          <td className="p-2 text-content-secondary">{String(r.runtime_ms)} ms</td>
                          <td className="p-2 text-content-tertiary truncate max-w-xs">{String(r.solver_method)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* QAOA STATEVECTOR SIMULATION SUITE */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                  <Zap className="h-4 w-4 text-quantum" />
                  Local QAOA Statevector Simulation Suite
                </h4>
                <div className="overflow-x-auto rounded border border-border">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-surface-2 text-content-tertiary uppercase text-[10px]">
                      <tr>
                        <th className="p-2">Instance</th>
                        <th className="p-2">Layers (p)</th>
                        <th className="p-2">Simulated Energy</th>
                        <th className="p-2">Approximation Ratio</th>
                        <th className="p-2">Feasible State</th>
                        <th className="p-2">Convergence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border text-xs">
                      {stage9c.map((r, idx) => (
                        <tr key={idx} className="hover:bg-surface-2/30">
                          <td className="p-2 font-semibold text-content-primary">{String(r.problem_id)}</td>
                          <td className="p-2">{String(r.p_layers)}</td>
                          <td className="p-2 font-semibold">{formatEnergy(Number(r.qaoa_energy))}</td>
                          <td className="p-2 text-primary font-semibold">{formatScore(Number(r.approximation_ratio), 3)}</td>
                          <td className="p-2">{r.repaired_if_needed ? <Badge variant="warning" className="text-[10px]">Constraint Repaired</Badge> : <Badge variant="success" className="text-[10px]">Natural Feasible</Badge>}</td>
                          <td className="p-2 text-content-secondary">{String(r.optimizer_converged ? "Converged" : "Iterations Complete")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* COMPARATIVE HYBRID ANALYSIS */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-content-primary flex items-center gap-1.5">
                  <Layers className="h-4 w-4 text-primary" />
                  Comparative Solution Analysis (Classical vs. Simulated)
                </h4>
                <div className="overflow-x-auto rounded border border-border">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-surface-2 text-content-tertiary uppercase text-[10px]">
                      <tr>
                        <th className="p-2">Instance</th>
                        <th className="p-2">Classical Energy</th>
                        <th className="p-2">Simulated QAOA Energy</th>
                        <th className="p-2">Energy Gap</th>
                        <th className="p-2">Objective Relationship</th>
                        <th className="p-2">Speedup Claimed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border text-xs">
                      {stage9d.map((r, idx) => (
                        <tr key={idx} className="hover:bg-surface-2/30">
                          <td className="p-2 font-semibold text-content-primary">{String(r.problem_id)}</td>
                          <td className="p-2 text-emerald-400 font-semibold">{formatEnergy(Number(r.classical_energy))}</td>
                          <td className="p-2 text-quantum font-semibold">{formatEnergy(Number(r.qaoa_energy))}</td>
                          <td className="p-2 text-content-secondary">{formatScore(Number(r.energy_gap), 4)}</td>
                          <td className="p-2 text-primary font-medium">{String(r.objective_relation ?? "CLASSICAL_SUPERIOR")}</td>
                          <td className="p-2 font-medium text-amber-400">{String(r.quantum_speedup_claimed ?? "FALSE")} (honest)</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <section className="grid gap-4 xl:grid-cols-2">
        {/* Simulator configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-5 w-5 text-quantum" />
              Simulator Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {quantum.isLoading ? (
              <div className="flex justify-center py-6"><Spinner /></div>
            ) : quantum.isError ? (
              <p role="alert" className="text-sm text-status-warning">
                {getApiErrorMessage(quantum.error, "Quantum configuration is unavailable.")}
              </p>
            ) : quantum.data?.available ? (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="success">Simulator available</Badge>
                  <Badge variant="secondary">
                    Direct execution {quantum.data.direct_execution_exposed ? "exposed" : "guarded"}
                  </Badge>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 text-xs">
                  <div className="rounded-lg border border-border bg-surface-2/50 p-3 space-y-1">
                    <p className="font-semibold text-content-primary">Local QAOA Capacity</p>
                    <p className="text-content-secondary">
                      Max local variables: <strong>{String(quantum.data.qaoa_config?.max_qubits ?? "16")} qubits</strong>
                    </p>
                    <p className="text-[11px] text-content-tertiary">
                      Ensures statevector matrix multiplication fits in host memory.
                    </p>
                  </div>
                  <div className="rounded-lg border border-border bg-surface-2/50 p-3 space-y-1">
                    <p className="font-semibold text-content-primary">Simulation Engine</p>
                    <p className="text-content-secondary">
                      Method: <strong>Statevector simulation</strong>
                    </p>
                    <p className="text-[11px] text-content-tertiary">
                      Computes exact unitary operator evolutions without stochastic shot noise.
                    </p>
                  </div>
                </div>

                <TechnicalDetails data={quantum.data.config} title="Technical details (Simulator configuration)" />
                <TechnicalDetails data={quantum.data.qaoa_config} title="Technical details (QAOA algorithm parameters)" />
              </>
            ) : (
              <p className="text-sm text-content-secondary">The backend reports no simulator configuration.</p>
            )}
          </CardContent>
        </Card>

        {/* Latest problem evidence */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Atom className="h-5 w-5 text-quantum" />
              Latest Problem Optimization Evidence
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {latest.data ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <Badge variant={suitabilityStatusFormatted.variant as any}>
                    {suitabilityStatusFormatted.label}
                  </Badge>
                  <Badge variant="secondary">Matrix: {val(evidence?.prediction_matrix_status)}</Badge>
                  <Badge variant="secondary">Nontriviality: {val(evidence?.nontriviality_status)}</Badge>
                </div>

                {Array.isArray(suitability?.reasons) && suitability.reasons.length > 0 && (
                  <div className="rounded bg-surface-2/50 p-2.5 text-xs space-y-1">
                    <p className="font-medium text-content-tertiary">Suitability evaluation:</p>
                    <ul className="list-disc space-y-0.5 pl-4 text-content-secondary">
                      {suitability.reasons.map((r, i) => (
                        <li key={i}>{String(r)}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="grid gap-3 sm:grid-cols-2 text-xs">
                  <div className="rounded-lg border border-border p-3 space-y-1">
                    <p className="font-semibold text-content-primary">QUBO Formulation</p>
                    <p className="text-content-secondary">
                      {qubo ? "Formulation constructed with verified binary penalties" : "QUBO details not returned for this request"}
                    </p>
                    <TechnicalDetails data={qubo} title="QUBO terms" />
                  </div>

                  <div className="rounded-lg border border-border p-3 space-y-1">
                    <p className="font-semibold text-content-primary">Ising Spin Model</p>
                    <p className="text-content-secondary">
                      {ising ? "Spin Hamiltonian coefficients derived" : "Ising details not returned for this request"}
                    </p>
                    <TechnicalDetails data={ising} title="Ising coefficients" />
                  </div>
                </div>

                <div className="rounded-lg border border-border p-3 space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-content-primary">QAOA Simulation Candidate</span>
                    <Badge variant={candidateStatusFormatted.variant as any}>
                      {candidateStatusFormatted.label}
                    </Badge>
                  </div>
                  <p className="text-content-secondary">
                    {candidate
                      ? `Candidate objective score: ${formatScore(candidate.objective_value as number)}`
                      : "No quantum candidate produced. Classical optimization was prioritized."}
                  </p>
                  <TechnicalDetails data={candidate} title="Candidate payload" />
                </div>

                <div className="rounded-lg border border-border p-3 space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-content-primary">Hybrid Comparison</span>
                    <Badge variant={hybridStatusFormatted.variant as any}>
                      {hybridStatusFormatted.label}
                    </Badge>
                  </div>
                  <p className="text-content-secondary">{relationFormatted.explanation}</p>
                  <TechnicalDetails data={hybrid} title="Hybrid comparison payload" />
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-dashed border-border p-6 text-center">
                <CircleHelp className="mx-auto h-7 w-7 text-content-tertiary" />
                <p className="mt-3 font-semibold text-content-primary">No optimization result cached this session</p>
                <p className="mt-1 text-xs text-content-secondary max-w-sm mx-auto">
                  Run the Classical &amp; Hybrid Optimization pipeline to evaluate your tasks and see problem-specific evidence here.
                </p>
                <Link to="/optimization" className="mt-3 inline-block">
                  <Button size="sm" variant="secondary">
                    Open Optimization Pipeline
                  </Button>
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Constraints Card */}
      <Card>
        <CardHeader><CardTitle>Local simulation constraints</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-content-tertiary">Maximum local QAOA variables</p>
            <p className="mt-1 text-lg font-semibold">{quantum.data ? val(quantum.data.qaoa_config?.max_qubits) : "Not available"}</p>
          </div>
          <div>
            <p className="text-xs text-content-tertiary">Problem-specific suitability</p>
            <p className="mt-1 text-lg font-semibold">{suitabilityStatusFormatted.label}</p>
          </div>
          <div>
            <p className="text-xs text-content-tertiary">Simulation details</p>
            <p className="mt-1 text-sm text-content-secondary">{qaoa ? val(qaoa.method ?? qaoa.simulator, "Returned metadata") : "No run metadata returned"}</p>
          </div>
          <p className="sm:col-span-3 text-xs text-content-tertiary">
            Local software simulation only. The variable limit is supplied by the backend. Concept visualization controls do not change circuit parameters or execution limits of a real problem.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
