import { EmptyState } from "@/components/ui/EmptyState";
import { BrainCircuit } from "lucide-react";

export function IntelligencePage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Intelligence & ML</h2>
          <p className="text-content-secondary">Model inference, prediction interfaces, and anomaly detection.</p>
        </div>
      </div>
      <EmptyState
        icon={BrainCircuit}
        title="Interface Pending"
        description="This component is planned for future iterations and will connect to the underlying backend services."
      />
    </div>
  );
}
