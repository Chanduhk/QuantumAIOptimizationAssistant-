import { EmptyState } from "@/components/ui/EmptyState";
import { Settings } from "lucide-react";

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">System Settings</h2>
          <p className="text-content-secondary">Configuration for API keys, backend connections, and preferences.</p>
        </div>
      </div>
      <EmptyState
        icon={Settings}
        title="Interface Pending"
        description="This component is planned for future iterations and will connect to the underlying backend services."
      />
    </div>
  );
}
