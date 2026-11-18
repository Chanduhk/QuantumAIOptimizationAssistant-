import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Atom,
  BrainCircuit,
  Gauge,
  GraduationCap,
  LayoutDashboard,
  ListChecks,
  Network,
  Settings,
  Sparkles,
  Workflow,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  layers?: string;
  description: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Command",
    items: [
      { to: "/", label: "Overview", icon: LayoutDashboard, description: "Mission control for your day and the system" },
      { to: "/assistant", label: "JAM Assistant", icon: Sparkles, description: "Plan in natural language and review proposals" },
    ],
  },
  {
    label: "Capture & understand",
    items: [
      { to: "/tasks", label: "Tasks", icon: ListChecks, layers: "L1 · L10", description: "Tasks, priorities, estimates and lifecycle" },
      { to: "/insights", label: "Intelligence", icon: BrainCircuit, layers: "L2 · L3", description: "Memory, behaviour patterns and predictions" },
    ],
  },
  {
    label: "Optimize & decide",
    items: [
      { to: "/optimize", label: "Optimization Studio", icon: Workflow, layers: "L4 – L9", description: "Run the full classical → quantum → executive pipeline" },
      { to: "/quantum", label: "Quantum Lab", icon: Atom, layers: "L5 · L6 · L7", description: "QUBO, Ising, QAOA simulation and hybrid benchmarks" },
      { to: "/brain", label: "Executive Brain", icon: Network, layers: "L8", description: "Evidence, conflicts, risk, trade-offs and governance" },
    ],
  },
  {
    label: "Act & learn",
    items: [
      { to: "/outcomes", label: "Outcomes", icon: Activity, layers: "L10 – L13", description: "Execution, actual outcomes and feedback" },
    ],
  },
  {
    label: "System",
    items: [
      { to: "/system", label: "System Status", icon: Gauge, description: "Component inventory and service health" },
      { to: "/settings", label: "Settings", icon: Settings, description: "Account, AI provider and appearance" },
    ],
  },
];

export const NAV_ITEMS = NAV_GROUPS.flatMap((group) => group.items);

export interface ArchitectureLayer {
  n: number;
  name: string;
  summary: string;
  route: string;
  /** Canonical component ids from /system/component-inventory. */
  components: string[];
  stage: "capture" | "intelligence" | "optimize" | "decide" | "learn";
}

export const LAYERS: ArchitectureLayer[] = [
  { n: 1, name: "User Information", summary: "Tasks, deadlines, priorities, dependencies", route: "/tasks", components: [], stage: "capture" },
  { n: 2, name: "Memory & Knowledge", summary: "Profile, history, behaviour patterns", route: "/insights", components: ["vector_memory_embedding"], stage: "capture" },
  { n: 3, name: "AI Intelligence", summary: "Predictions, analysis, planning", route: "/insights", components: ["prediction_engine", "duration_ratio_model", "productivity_model", "conversational_intelligence"], stage: "intelligence" },
  { n: 4, name: "Classical Optimization", summary: "Scheduling, constraints, resources", route: "/optimize", components: ["classical_optimizer", "multi_objective_optimizer", "rl_scheduler"], stage: "optimize" },
  { n: 5, name: "Quantum Suitability", summary: "Is quantum appropriate here?", route: "/quantum", components: ["qubo_formulator"], stage: "optimize" },
  { n: 6, name: "Quantum Optimization", summary: "QUBO, Ising, QAOA", route: "/quantum", components: ["qaoa_simulator", "exact_classical_solver"], stage: "optimize" },
  { n: 7, name: "Hybrid Optimization", summary: "Classical vs quantum candidates", route: "/optimize", components: ["hybrid_optimizer"], stage: "optimize" },
  { n: 8, name: "Executive Brain", summary: "Evidence, risk, trade-offs, decision", route: "/brain", components: ["decision_pipeline"], stage: "decide" },
  { n: 9, name: "Recommendations", summary: "Schedules, priorities, action plans", route: "/optimize", components: ["autonomous_planning_engine"], stage: "decide" },
  { n: 10, name: "Execution", summary: "Tasks started and in flight", route: "/tasks", components: [], stage: "learn" },
  { n: 11, name: "Actual Outcomes", summary: "Completed work vs estimates", route: "/outcomes", components: [], stage: "learn" },
  { n: 12, name: "Feedback", summary: "Focus, energy, productivity ratings", route: "/outcomes", components: [], stage: "learn" },
  { n: 13, name: "Continuous Learning", summary: "Automatic readiness, training, promotion", route: "/system", components: ["training_controller", "public_dataset_manager"], stage: "learn" },
];
