import { EmptyState } from "@/components/ui/EmptyState";
import { Activity } from "lucide-react";

export function SystemStatusPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">System Status</h2>
          <p className="text-content-secondary">Health metrics and diagnostic information for all engines.</p>
        </div>
      </div>
      <EmptyState
        icon={Activity}
        title="Interface Pending"
        description="This component is planned for future iterations and will connect to the underlying backend services."
      />
    </div>
  );
}
