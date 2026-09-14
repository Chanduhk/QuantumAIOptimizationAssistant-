import { EmptyState } from "@/components/ui/EmptyState";
import { Database } from "lucide-react";

export function DataLearningPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Data & Learning</h2>
          <p className="text-content-secondary">Data ingestion, embeddings, and RAG configuration.</p>
        </div>
      </div>
      <EmptyState
        icon={Database}
        title="Interface Pending"
        description="This component is planned for future iterations and will connect to the underlying backend services."
      />
    </div>
  );
}
