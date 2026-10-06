import { EmptyState } from "@/components/ui/EmptyState";
import { Atom } from "lucide-react";

export function QuantumWorkspacePage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Quantum Workspace</h2>
          <p className="text-content-secondary">Local software simulation configuration for research and development.</p>
        </div>
      </div>
      <EmptyState
        icon={Atom}
        title="Interface Pending"
        description="Standalone quantum execution is not available here. Optimization candidates are evaluated through the local simulator when backend readiness checks permit; no physical hardware or quantum advantage is claimed."
      />
    </div>
  );
}
