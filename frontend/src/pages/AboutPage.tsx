import * as React from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  ArrowRight,
  Atom,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  Clock,
  Compass,
  Cpu,
  Database,
  ExternalLink,
  FileText,
  Flame,
  GitBranch,
  GraduationCap,
  Layers,
  ListChecks,
  Lock,
  Network,
  Scale,
  Shield,
  ShieldCheck,
  Sparkles,
  Target,
  Workflow,
  Zap,
} from "lucide-react";
import { Page, PageHeader, SectionTitle } from "@/components/layout/Page";
import { Card, CardBody, CardHeader, CardFooter, KeyValue } from "@/components/ui/Card";
import { Badge, StatusDot } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { HelioxMark, HelioxWordmark } from "@/components/brand/HelioxMark";
import { OrbitalSystem } from "@/components/brand/OrbitalSystem";
import { FadeIn, StaggerContainer, StaggerItem, AIActivityIndicator } from "@/components/motion";
import { LAYERS, type ArchitectureLayer } from "@/lib/architecture";
import { cn } from "@/lib/utils";

// Verified core AI model used by Heliox AI
const AI_MODEL_DISPLAY = "Gemini 3.8 Flash";

interface CapabilityPillar {
  id: string;
  title: string;
  eyebrow: string;
  icon: React.ElementType;
  summary: string;
  mechanics: string[];
  operationalFormula?: string;
  statusText: string;
  layerTag: string;
}

const CAPABILITY_PILLARS: CapabilityPillar[] = [
  {
    id: "goals",
    title: "Goals Intelligence & Feasibility Modeling",
    eyebrow: "Pillar 1 · Strategic Alignment",
    icon: Target,
    summary:
      "Replaces static task counters with duration- and priority-weighted progress rollups, paired with a 14-day rolling velocity tracker and dynamic health forecasting.",
    mechanics: [
      "Calculates progress weighted by Task Duration × Priority instead of flat unit counts.",
      "Models historical daily velocity over a rolling 14-day window against required completion velocity.",
      "Computes feasibility ratio to project completion dates and assign 4 dynamic health states: On Track, At Risk, Behind, and Critical.",
      "Surfaces blocked prerequisite counts and estimated remaining effort directly on goal metrics.",
    ],
    operationalFormula: "Progress = ∑(Duration_i × Priority_i) / ∑(Total_Work) × 100",
    statusText: "Fully Operational",
    layerTag: "L1 · L8",
  },
  {
    id: "dependencies",
    title: "DAG Dependency Topology & Downstream Slack",
    eyebrow: "Pillar 2 · Schedule Topology",
    icon: GitBranch,
    summary:
      "A real-time Directed Acyclic Graph (DAG) engine that validates task networks, prevents deadlocks, highlights bottlenecks, and computes backward-propagated downstream slack.",
    mechanics: [
      "Validates dependency chains upon task creation and updates to prevent circular dependency deadlocks.",
      "Identifies critical bottlenecks—tasks that directly gate multiple downstream items.",
      "Calculates downstream slack via backward pass from dependent deadlines, isolating zero-slack critical paths.",
      "Enforces blocker gating so pending prerequisites visibly flag downstream items as unexecutable.",
    ],
    operationalFormula: "Slack_u = min_{v ∈ Dependents} (Deadline_v - Duration_v) - Deadline_u",
    statusText: "Fully Operational",
    layerTag: "L1 · L4",
  },
  {
    id: "prioritization",
    title: "Multi-Criteria Dynamic Prioritization (MCDA)",
    eyebrow: "Pillar 3 · Algorithmic Ranking",
    icon: Scale,
    summary:
      "Scores and dynamically re-ranks all active work from 0 to 100 using a 6-pillar decision matrix, augmented with strict blocker gating penalties.",
    mechanics: [
      "Pillar 1: Urgency (30%) — exponential deadline proximity scoring with overdue penalty scaling.",
      "Pillar 2: Goal Alignment (20%) — prioritization boost derived from parent goal urgency and health deficit.",
      "Pillar 3: Dependency Leverage (20%) — high-leverage points awarded to tasks that unblock critical downstream chains.",
      "Pillar 4: User Priority (15%) — normalized baseline preference set by the user.",
      "Pillar 5: Energy Match (10%) — task cognitive load matched against the user's current focus window.",
      "Pillar 6: Starvation Prevention (5%) — age-based progression preventing low-priority tasks from idling indefinitely.",
      "Blocker Gating: Strict -50 point penalty applied if prerequisite tasks remain unfinished.",
    ],
    operationalFormula: "Score = ∑(w_k × S_k) - (50 if is_blocked else 0)",
    statusText: "Fully Operational",
    layerTag: "L8 · MCDA",
  },
  {
    id: "proposals",
    title: "Context-Aware Actionable Proposals",
    eyebrow: "Pillar 4 · Autonomous Execution",
    icon: Zap,
    summary:
      "Synthesizes structured, programmatic interventions from system bottlenecks that users or AI agents can execute with a single click via backend APIs.",
    mechanics: [
      "Dependency Unblocking: detects blocked high-priority tasks and targets immediate resolution of prerequisite bottlenecks.",
      "Goal Risk Mitigation: detects goals lagging behind schedule velocity and dispatches batch priority boosts.",
      "Workload Balancing: detects single-day workload saturation and calculates optimal shifting to subsequent focus windows.",
      "1-Click Execution: API endpoints execute structured mutation payloads with instantaneous state persistence.",
    ],
    operationalFormula: "POST /api/v1/ai/recommendations/apply { proposal_id, action_payload }",
    statusText: "Fully Operational",
    layerTag: "L8 · L9",
  },
  {
    id: "resources",
    title: "Cognitive Energy Budgeting & Fatigue Risk",
    eyebrow: "Pillar 5 · Human Constraints",
    icon: Flame,
    summary:
      "Protects human focus stamina by budgeting daily deep work against sustainable capacity limits and actively modeling cognitive fatigue risk.",
    mechanics: [
      "Distinguishes high-intensity deep work (coding, research, design) from administrative overhead (email, check-ins).",
      "Enforces a baseline 4.0-hour daily deep work limit to prevent mental exhaustion and burnout.",
      "Tracks real-time fatigue risk tiers: Low (≤4h), Moderate (4h–6h), and High (>6h deep work or >9h total day).",
      "Emits automated pacing suggestions when planned workload violates sustainable biological thresholds.",
    ],
    operationalFormula: "Fatigue = Low (≤4h Deep) | Moderate (4-6h) | High (>6h / >9h Total)",
    statusText: "Fully Operational",
    layerTag: "L1 · L4",
  },
  {
    id: "quantum",
    title: "Classical & Quantum-Inspired Optimization",
    eyebrow: "Pillar 6 · Hybrid Solvers",
    icon: Atom,
    summary:
      "A principled optimization stack that executes deterministic classical heuristics first, reserving quantum formulations (QUBO/QAOA) for genuine combinatorial benchmarks.",
    mechanics: [
      "Classical Scheduler: constraint satisfaction and multi-objective heuristics handle day-to-day schedule construction.",
      "Quantum Suitability Evaluator: inspects task conflict graphs and constraint densities to verify if quantum mapping is justified.",
      "QUBO / Ising Formulations: maps combinatorial conflict matrices onto binary quadratic optimization variables.",
      "Simulated QAOA & Exact Solver: benchmarks quantum approximate optimization against exact classical branch-and-bound solutions.",
    ],
    operationalFormula: "H = ∑ h_i σ_i^z + ∑ J_{ij} σ_i^z σ_j^z (Ising Hamiltonian)",
    statusText: "Fully Operational (Simulated)",
    layerTag: "L4 · L5 · L6 · L7",
  },
];

export function AboutPage() {
  const [activeTab, setActiveTab] = React.useState<"pillars" | "ai" | "architecture" | "governance">("pillars");
  const [selectedLayerStage, setSelectedLayerStage] = React.useState<string>("all");

  const filteredLayers = React.useMemo(() => {
    if (selectedLayerStage === "all") return LAYERS;
    return LAYERS.filter((l) => l.stage === selectedLayerStage);
  }, [selectedLayerStage]);

  return (
    <Page wide>
      {/* Page Header */}
      <PageHeader
        layers="L1 – L13 Full Spectrum"
        title="About Heliox AI"
        description="The quantum-aware personal optimization assistant engineered for cognitive energy management, mathematical scheduling, and disciplined execution."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="quantum" dot size="md">
              AI Core: {AI_MODEL_DISPLAY}
            </Badge>
            <Badge tone="success" dot size="md">
              Architecture: 13 Layers
            </Badge>
            <Link to="/terms">
              <Button variant="secondary" size="sm" leftIcon={<FileText className="size-4" />}>
                Terms & Conditions
              </Button>
            </Link>
          </div>
        }
      />

      {/* Hero Brand & Mission Section */}
      <FadeIn delay={0.05} className="mb-8">
        <div className="relative overflow-hidden rounded-3xl border border-border-subtle bg-gradient-to-br from-surface-1 via-surface-1/90 to-surface-2 p-6 shadow-card sm:p-10 dark:border-border dark:from-surface-1/60 dark:to-surface-2/40">
          <div className="bg-grid absolute inset-0 opacity-40 [mask-image:radial-gradient(ellipse_at_top_right,black_20%,transparent_70%)]" />

          <div className="relative z-10 grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                <Sparkles className="size-3.5" />
                <span>Next-Generation Cognitive Architecture</span>
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-content-primary sm:text-3xl lg:text-4xl">
                Precision Intelligence for Complex Human Execution
              </h2>
              <p className="mt-4 text-base leading-relaxed text-content-secondary">
                Modern high-performance work is rarely bottlenecked by lack of ambition—it is bottlenecked by fragmented
                priorities, unquantified dependencies, unrealistic deadline pacing, and cognitive exhaustion.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-content-tertiary">
                <strong>Heliox AI</strong> bridges the gap between natural human intent and mathematical optimization. By
                coupling the conversational reasoning of <strong>{AI_MODEL_DISPLAY}</strong> with multi-criteria decision
                analysis, directed acyclic graph topology, and quantum-inspired combinatorial algorithms, Heliox transforms
                chaotic schedules into coherent, self-healing execution pipelines.
              </p>

              {/* Core System Highlights */}
              <div className="mt-6 grid grid-cols-2 gap-4 border-t border-border-subtle pt-6 dark:border-border sm:grid-cols-4">
                <div>
                  <p className="font-mono text-xs text-content-muted">Primary LLM</p>
                  <p className="mt-1 font-semibold text-content-primary">{AI_MODEL_DISPLAY}</p>
                </div>
                <div>
                  <p className="font-mono text-xs text-content-muted">Prioritizer</p>
                  <p className="mt-1 font-semibold text-content-primary">6-Pillar MCDA</p>
                </div>
                <div>
                  <p className="font-mono text-xs text-content-muted">Optimization</p>
                  <p className="mt-1 font-semibold text-content-primary">Hybrid Classical + QAOA</p>
                </div>
                <div>
                  <p className="font-mono text-xs text-content-muted">Learning Loop</p>
                  <p className="mt-1 font-semibold text-content-primary">Autonomous & Governed</p>
                </div>
              </div>
            </div>

            {/* Orbital System Visual */}
            <div className="relative flex items-center justify-center py-4">
              <OrbitalSystem className="w-[min(340px,90%)]" />
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="rounded-2xl border border-primary/20 bg-background/80 p-4 text-center shadow-lg backdrop-blur-md">
                  <div className="mx-auto flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/80 to-quantum/80 text-white">
                    <HelioxMark className="size-6 text-white" />
                  </div>
                  <p className="mt-2 text-xs font-semibold tracking-wider text-content-primary">HELIOX AI</p>
                  <p className="text-[10px] text-content-muted">Cognitive Optimization Matrix</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </FadeIn>

      {/* Navigation Tabs */}
      <div className="mb-6 flex flex-wrap gap-2 border-b border-border-subtle pb-3 dark:border-border">
        <button
          type="button"
          onClick={() => setActiveTab("pillars")}
          className={cn(
            "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "pillars"
              ? "bg-surface-2 text-content-primary shadow-sm dark:bg-surface-3"
              : "text-content-tertiary hover:bg-surface-2/60 hover:text-content-secondary"
          )}
        >
          <Layers className="size-4 text-primary" />
          <span>Core Capabilities (6 Pillars)</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("ai")}
          className={cn(
            "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "ai"
              ? "bg-surface-2 text-content-primary shadow-sm dark:bg-surface-3"
              : "text-content-tertiary hover:bg-surface-2/60 hover:text-content-secondary"
          )}
        >
          <Sparkles className="size-4 text-quantum" />
          <span>Language Intelligence ({AI_MODEL_DISPLAY})</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("architecture")}
          className={cn(
            "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "architecture"
              ? "bg-surface-2 text-content-primary shadow-sm dark:bg-surface-3"
              : "text-content-tertiary hover:bg-surface-2/60 hover:text-content-secondary"
          )}
        >
          <Network className="size-4 text-status-success" />
          <span>13-Layer Architecture Walkthrough</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("governance")}
          className={cn(
            "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "governance"
              ? "bg-surface-2 text-content-primary shadow-sm dark:bg-surface-3"
              : "text-content-tertiary hover:bg-surface-2/60 hover:text-content-secondary"
          )}
        >
          <ShieldCheck className="size-4 text-content-secondary" />
          <span>Governance, Privacy & Stack</span>
        </button>
      </div>

      {/* TAB CONTENT 1: The 6 Pillars */}
      {activeTab === "pillars" && (
        <section aria-label="Core Capability Pillars">
          <SectionTitle
            title="Six Pillars of HelioX Intelligence"
            description="Every capability in Heliox AI is built on verifiable mathematical formulations and robust state management."
          />

          <StaggerContainer stagger={0.06} className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {CAPABILITY_PILLARS.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <StaggerItem key={pillar.id}>
                  <Card hoverLift className="flex h-full flex-col justify-between">
                    <CardHeader
                      icon={<Icon className="size-4 text-primary" />}
                      eyebrow={pillar.eyebrow}
                      title={pillar.title}
                      action={<Badge tone="outline" size="sm">{pillar.layerTag}</Badge>}
                    />
                    <CardBody className="space-y-4">
                      <p className="text-sm leading-relaxed text-content-secondary">{pillar.summary}</p>

                      <div className="space-y-2 border-t border-border-subtle pt-3 dark:border-border">
                        <p className="text-xs font-semibold uppercase tracking-wider text-content-muted">
                          Key Operational Capabilities
                        </p>
                        <ul className="space-y-1.5 text-xs text-content-tertiary">
                          {pillar.mechanics.map((mech, idx) => (
                            <li key={idx} className="flex items-start gap-2">
                              <span className="mt-1 size-1.5 shrink-0 rounded-full bg-primary/70" />
                              <span className="leading-snug">{mech}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {pillar.operationalFormula && (
                        <div className="rounded-xl border border-border-subtle bg-surface-2/50 p-2.5 font-mono text-[11px] text-content-secondary dark:border-border">
                          <p className="text-[10px] uppercase text-content-muted">Formula / Engine Contract</p>
                          <p className="mt-0.5 truncate text-primary">{pillar.operationalFormula}</p>
                        </div>
                      )}
                    </CardBody>
                    <CardFooter className="justify-between text-xs text-content-muted">
                      <span className="inline-flex items-center gap-1.5">
                        <StatusDot tone="success" pulse />
                        {pillar.statusText}
                      </span>
                      <span className="font-mono text-[11px]">{pillar.id}</span>
                    </CardFooter>
                  </Card>
                </StaggerItem>
              );
            })}
          </StaggerContainer>
        </section>
      )}

      {/* TAB CONTENT 2: Gemini 3.8 Flash & AI Intelligence */}
      {activeTab === "ai" && (
        <section aria-label="Language Intelligence with Gemini 3.8 Flash">
          <SectionTitle
            title={`Language Intelligence Powered by ${AI_MODEL_DISPLAY}`}
            description="How Heliox AI blends large language model reasoning with deterministic optimization engines."
          />

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                icon={<Bot className="size-4 text-primary" />}
                eyebrow="Conversational Planning Engine"
                title="The JAM Assistant Architecture"
                action={<Badge tone="quantum" dot size="md">{AI_MODEL_DISPLAY}</Badge>}
              />
              <CardBody className="space-y-4 text-sm leading-relaxed text-content-secondary">
                <p>
                  The conversational frontend of Heliox AI is driven by <strong>JAM</strong> (Joint Autonomous
                  Model), powered natively by <strong>{AI_MODEL_DISPLAY}</strong>. Unlike generic chat interfaces,
                  JAM is tightly coupled to the backend optimization services through structured JSON function calling
                  and deterministic intent classification.
                </p>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-xl border border-border-subtle bg-surface-2/40 p-4 dark:border-border">
                    <p className="flex items-center gap-2 text-xs font-semibold text-content-primary">
                      <Target className="size-4 text-primary" />
                      Intent-Aware Action Dispatch
                    </p>
                    <p className="mt-1.5 text-xs text-content-tertiary">
                      Commands like “prioritize my tasks”, “create a 2-hour coding task due tomorrow”, or “optimize my
                      afternoon” are translated into deterministic database operations and MCDA queries.
                    </p>
                  </div>

                  <div className="rounded-xl border border-border-subtle bg-surface-2/40 p-4 dark:border-border">
                    <p className="flex items-center gap-2 text-xs font-semibold text-content-primary">
                      <Sparkles className="size-4 text-quantum" />
                      Executable Plan Proposals
                    </p>
                    <p className="mt-1.5 text-xs text-content-tertiary">
                      When rescheduling or reallocating tasks, JAM generates structured proposals that the user can inspect,
                      accept, or reject before any database changes are finalized.
                    </p>
                  </div>
                </div>

                <div className="rounded-2xl border border-primary/20 bg-primary/[0.04] p-4 text-xs">
                  <p className="font-semibold text-content-primary">Architectural Privacy & Secret Isolation</p>
                  <p className="mt-1 text-content-tertiary">
                    All communication with Google AI services is mediated exclusively through secure server-side controllers.
                    API keys, authorization headers, and raw configuration parameters are strictly encapsulated on the
                    backend and never transmitted to the client browser or exposed in frontend bundles.
                  </p>
                </div>
              </CardBody>
            </Card>

            {/* Fallback Resilience */}
            <Card>
              <CardHeader
                icon={<Shield className="size-4 text-status-warning" />}
                eyebrow="High Availability"
                title="Deterministic Fallback Matrix"
              />
              <CardBody className="space-y-3 text-xs leading-relaxed text-content-secondary">
                <p>
                  Heliox AI is engineered with full offline and degraded-mode resilience. In the event of provider latency,
                  rate limits, or network disruption, the system maintains complete operability:
                </p>
                <div className="space-y-2 border-t border-border-subtle pt-3 dark:border-border">
                  <div className="rounded-lg bg-surface-2/70 p-2.5">
                    <p className="font-medium text-content-primary">Rule-Based Intent Classifier</p>
                    <p className="mt-0.5 text-[11px] text-content-muted">
                      Local regex and pattern parser handles core task creation, status queries, and scheduling commands.
                    </p>
                  </div>
                  <div className="rounded-lg bg-surface-2/70 p-2.5">
                    <p className="font-medium text-content-primary">Heuristic Classical Optimizer</p>
                    <p className="mt-0.5 text-[11px] text-content-muted">
                      Greedy interval scheduling and topological sort operate with zero external network dependencies.
                    </p>
                  </div>
                  <div className="rounded-lg bg-surface-2/70 p-2.5">
                    <p className="font-medium text-content-primary">6-Pillar MCDA Engine</p>
                    <p className="mt-0.5 text-[11px] text-content-muted">
                      All mathematical priority scores calculate locally inside SQLite and Python without third-party APIs.
                    </p>
                  </div>
                </div>
              </CardBody>
              <CardFooter className="text-[11px] text-content-muted">
                Fail-Safe Architecture: Zero Single Points of Failure
              </CardFooter>
            </Card>
          </div>
        </section>
      )}

      {/* TAB CONTENT 3: 13-Layer Architecture */}
      {activeTab === "architecture" && (
        <section aria-label="13-Layer Architecture Walkthrough">
          <SectionTitle
            title="The 13 Architectural Layers of Heliox AI"
            description="From raw task capture (Layer 1) to continuous autonomous learning (Layer 13)."
            action={
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                {(["all", "capture", "intelligence", "optimize", "decide", "learn"] as const).map((stage) => (
                  <button
                    key={stage}
                    type="button"
                    onClick={() => setSelectedLayerStage(stage)}
                    className={cn(
                      "rounded-lg px-2.5 py-1 capitalize transition-colors",
                      selectedLayerStage === stage
                        ? "bg-primary text-primary-foreground font-medium"
                        : "bg-surface-2 text-content-tertiary hover:text-content-primary"
                    )}
                  >
                    {stage}
                  </button>
                ))}
              </div>
            }
          />

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filteredLayers.map((layer) => (
              <Card key={layer.n} className="flex flex-col justify-between">
                <CardHeader
                  eyebrow={`Stage: ${layer.stage.toUpperCase()}`}
                  title={
                    <span className="flex items-center gap-2">
                      <span className="grid size-6 place-items-center rounded-md bg-surface-2 font-mono text-xs font-semibold text-primary">
                        L{layer.n}
                      </span>
                      <span>{layer.name}</span>
                    </span>
                  }
                  action={
                    <Link to={layer.route} title={`Open ${layer.name} view`}>
                      <ChevronRight className="size-4 text-content-muted hover:text-content-primary" />
                    </Link>
                  }
                />
                <CardBody className="space-y-3">
                  <p className="text-xs text-content-secondary leading-relaxed">{layer.summary}</p>
                  {layer.components.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-1">
                      {layer.components.map((comp) => (
                        <span key={comp} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-content-muted">
                          {comp}
                        </span>
                      ))}
                    </div>
                  )}
                </CardBody>
                <CardFooter className="justify-between text-[11px] text-content-muted">
                  <span>Route: {layer.route}</span>
                  <Link to={layer.route} className="inline-flex items-center gap-1 text-primary hover:underline">
                    View <ArrowRight className="size-3" />
                  </Link>
                </CardFooter>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* TAB CONTENT 4: Governance & Project Stack */}
      {activeTab === "governance" && (
        <section aria-label="Governance and Technical Stack">
          <SectionTitle
            title="System Governance, Security & Project Identity"
            description="Verified implementation details for academic evaluation and user transparency."
          />

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader
                icon={<Lock className="size-4 text-primary" />}
                eyebrow="Data Protection"
                title="Storage, Isolation & Privacy Guarantees"
              />
              <CardBody className="space-y-3 text-xs leading-relaxed text-content-secondary">
                <ul className="space-y-2.5">
                  <li className="flex items-start gap-2.5">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-status-success" />
                    <div>
                      <strong className="text-content-primary">Local SQLite Workspace Isolation:</strong> User tasks,
                      deadlines, durations, outcomes, and behavioral ratings are isolated to the user's relational
                      database tables. No shared multi-tenant bleed.
                    </div>
                  </li>
                  <li className="flex items-start gap-2.5">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-status-success" />
                    <div>
                      <strong className="text-content-primary">HttpOnly Cookie Authentication:</strong> Sessions are
                      managed via secure, HttpOnly, SameSite cookies paired with double-submit CSRF tokens.
                    </div>
                  </li>
                  <li className="flex items-start gap-2.5">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-status-success" />
                    <div>
                      <strong className="text-content-primary">Zero Commercial Data Monetization:</strong> Personal
                      productivity data is never sold, shared with ad networks, or used for third-party commercial profiling.
                    </div>
                  </li>
                  <li className="flex items-start gap-2.5">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-status-success" />
                    <div>
                      <strong className="text-content-primary">Governed Autonomous Learning:</strong> Personal models
                      train only on verified user task outcomes when explicit readiness criteria are met.
                    </div>
                  </li>
                </ul>
              </CardBody>
              <CardFooter>
                <Link to="/terms" className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline">
                  Read complete Terms & Conditions <ArrowRight className="size-3.5" />
                </Link>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader
                icon={<Cpu className="size-4 text-quantum" />}
                eyebrow="Demonstration Context"
                title="Project Attribution & Technical Stack"
              />
              <CardBody className="space-y-4 text-xs leading-relaxed text-content-secondary">
                <div>
                  <p className="font-semibold text-content-primary">Quantum AI Personal Optimization Assistant</p>
                  <p className="mt-1 text-content-tertiary">
                    An advanced AI/ML major engineering demonstration integrating cognitive modeling, quantum-inspired
                    combinatorial mathematics, and full-stack software architecture.
                  </p>
                </div>

                <dl className="grid grid-cols-2 gap-3 border-t border-border-subtle pt-3 dark:border-border">
                  <KeyValue label="Backend" value="Python 3.14 · FastAPI · SQLAlchemy" />
                  <KeyValue label="Database" value="SQLite (behavior_engine.db)" />
                  <KeyValue label="Frontend" value="React 19 · TypeScript · Vite" />
                  <KeyValue label="Styling & Motion" value="Tailwind CSS · Framer Motion" />
                  <KeyValue label="State & Query" value="Zustand · TanStack React Query" />
                  <KeyValue label="AI Provider" value="Google Gemini (gemini-3.8-flash)" />
                </dl>
              </CardBody>
              <CardFooter className="justify-between text-[11px] text-content-muted">
                <span>Repository: QuantumAIOptimizationAssistant-</span>
                <Link to="/system" className="text-primary hover:underline">
                  Inspect System Inventory
                </Link>
              </CardFooter>
            </Card>
          </div>
        </section>
      )}

      {/* Footer Call to Action */}
      <FadeIn delay={0.2} className="mt-10">
        <div className="flex flex-col items-center justify-between gap-4 rounded-2xl border border-border-subtle bg-surface-1 p-6 text-center sm:flex-row sm:text-left dark:border-border">
          <div>
            <p className="text-sm font-semibold text-content-primary">Ready to optimize your day with Heliox AI?</p>
            <p className="text-xs text-content-tertiary">
              Experience the 6-pillar prioritizer, cognitive energy budgeting, and the {AI_MODEL_DISPLAY}-powered JAM Assistant.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link to="/assistant">
              <Button size="sm" leftIcon={<Sparkles className="size-3.5" />}>
                Ask JAM
              </Button>
            </Link>
            <Link to="/tasks">
              <Button variant="secondary" size="sm" leftIcon={<ListChecks className="size-3.5" />}>
                View Tasks
              </Button>
            </Link>
          </div>
        </div>
      </FadeIn>
    </Page>
  );
}
