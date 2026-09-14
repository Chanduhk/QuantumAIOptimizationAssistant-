import { EmptyState } from "@/components/ui/EmptyState";
import { CheckSquare } from "lucide-react";

export function TasksPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Tasks Management</h2>
          <p className="text-content-secondary">Manage, monitor, and coordinate background operations.</p>
        </div>
      </div>
      <EmptyState
        icon={CheckSquare}
        title="Interface Pending"
        description="This component is planned for future iterations and will connect to the underlying backend services."
      />
    </div>
  );
}
