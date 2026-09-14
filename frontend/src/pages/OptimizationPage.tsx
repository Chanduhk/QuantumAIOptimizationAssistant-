import { EmptyState } from "@/components/ui/EmptyState";
import { Zap } from "lucide-react";

export function OptimizationPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Quantum & Classical Optimization</h2>
          <p className="text-content-secondary">Formulate and solve complex optimization problems.</p>
        </div>
      </div>
      <EmptyState
        icon={Zap}
        title="Interface Pending"
        description="This component is planned for future iterations and will connect to the underlying backend services."
      />
    </div>
  );
}
