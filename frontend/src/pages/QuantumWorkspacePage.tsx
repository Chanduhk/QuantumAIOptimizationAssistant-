import { EmptyState } from "@/components/ui/EmptyState";
import { Atom } from "lucide-react";

export function QuantumWorkspacePage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Quantum Workspace</h2>
          <p className="text-content-secondary">Quantum annealer and gate-model hardware status and job execution.</p>
        </div>
      </div>
      <EmptyState
        icon={Atom}
        title="Interface Pending"
        description="This component is planned for future iterations and will connect to the underlying backend services."
      />
    </div>
  );
}
