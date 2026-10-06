import * as React from "react";
import { Plus, ListTodo } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { useTasks } from "@/api/hooks";
import { TaskRow } from "./tasks/TaskRow";
import { TaskCreateDialog } from "./tasks/TaskCreateDialog";
import { Tabs } from "@/components/ui/Tabs";
import { getApiErrorMessage } from "@/api/client";

export function TasksPage() {
  const { data: tasksResponse, isLoading, error, refetch } = useTasks();
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);

  const tasks = tasksResponse?.tasks || [];

  const pendingTasks = tasks.filter(t => t.lifecycle_state === "created" || t.lifecycle_state === "started");
  const completedTasks = tasks.filter(t => t.lifecycle_state === "completed");

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="flex h-64 items-center justify-center">
          <Spinner size="lg" />
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex h-64 flex-col items-center justify-center space-y-4 rounded-xl border border-status-error/20 bg-status-error/10 p-8 text-center">
          <div className="text-status-error font-medium">Failed to load tasks</div>
          <p className="text-sm text-status-error/80">{getApiErrorMessage(error, "An unexpected error occurred.")}</p>
          <Button variant="secondary" onClick={() => refetch()}>Try Again</Button>
        </div>
      );
    }

    if (tasks.length === 0) {
      return (
        <EmptyState
          icon={ListTodo}
          title="No tasks yet"
          description="Create your first task to start organizing your work."
          action={
            <Button variant="primary" onClick={() => setIsCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Task
            </Button>
          }
        />
      );
    }

    const tabData = [
      {
        id: "all",
        label: `All (${tasks.length})`,
        content: (
          <div className="space-y-3 pt-4">
            {tasks.map(task => (
              <TaskRow key={task.id} task={task} />
            ))}
            {tasks.length === 0 && <p className="text-content-secondary py-8 text-center">No tasks found.</p>}
          </div>
        )
      },
      {
        id: "pending",
        label: `Pending (${pendingTasks.length})`,
        content: (
          <div className="space-y-3 pt-4">
            {pendingTasks.map(task => (
              <TaskRow key={task.id} task={task} />
            ))}
            {pendingTasks.length === 0 && <p className="text-content-secondary py-8 text-center">No pending tasks.</p>}
          </div>
        )
      },
      {
        id: "completed",
        label: `Completed (${completedTasks.length})`,
        content: (
          <div className="space-y-3 pt-4">
            {completedTasks.map(task => (
              <TaskRow key={task.id} task={task} />
            ))}
            {completedTasks.length === 0 && <p className="text-content-secondary py-8 text-center">No completed tasks.</p>}
          </div>
        )
      }
    ];

    return <Tabs tabs={tabData} defaultTab="pending" className="w-full" />;
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">Tasks Management</h2>
          <p className="text-content-secondary">Manage, monitor, and coordinate your tasks.</p>
        </div>
        <Button
          variant="primary"
          onClick={() => setIsCreateOpen(true)}
        >
          <Plus className="mr-2 h-4 w-4" />
          Create Task
        </Button>
      </div>

      {renderContent()}

      <TaskCreateDialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
      />
    </div>
  );
}
