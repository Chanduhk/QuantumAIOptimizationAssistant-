import { EmptyState } from "@/components/ui/EmptyState";
import { Calendar } from "lucide-react";

export function PlanningPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Strategic Planning</h2>
          <p className="text-content-secondary">Executive orchestration and goal breakdown planning interfaces.</p>
        </div>
      </div>
      <EmptyState
        icon={Calendar}
        title="Interface Pending"
        description="This component is planned for future iterations and will connect to the underlying backend services."
      />
    </div>
  );
}
