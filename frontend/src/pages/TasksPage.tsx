import * as React from "react";
import { Plus, ListTodo, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { useTasks } from "@/api/hooks";
import { TaskRow } from "./tasks/TaskRow";
import { TaskCreateDialog } from "./tasks/TaskCreateDialog";
import { Tabs } from "@/components/ui/Tabs";
import { getApiErrorMessage } from "@/api/client";
import { Task } from "@/api/endpoints";

export function TasksPage() {
  const { data: tasksResponse, isLoading, error, refetch } = useTasks();
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const [activeTab, setActiveTab] = React.useState("pending");

  const tasks = tasksResponse?.tasks || [];

  const normalizedSearch = search.trim().toLocaleLowerCase();
  const visibleTasks = tasks.filter((task) => !normalizedSearch || `${task.title} ${task.task_type}`.toLocaleLowerCase().includes(normalizedSearch));
  const isTaskCompleted = (t: Task) => Boolean(t.completed) || t.lifecycle_state === "completed";
  const pendingTasks = visibleTasks.filter((t) => !isTaskCompleted(t));
  const completedTasks = visibleTasks.filter((t) => isTaskCompleted(t));

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
        label: `All (${visibleTasks.length})`,
        content: (
          <div className="space-y-3 pt-4">
            {visibleTasks.map(task => (
              <TaskRow key={task.id} task={task} />
            ))}
            {visibleTasks.length === 0 && <p className="text-content-secondary py-8 text-center">No tasks match this search.</p>}
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

    return <Tabs tabs={tabData} activeTab={activeTab} onTabChange={setActiveTab} className="w-full" />;
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-content-primary">My Tasks</h2>
          <p className="text-content-secondary">Track, start, and complete your personal tasks with verified feedback.</p>
        </div>
        <Button
          variant="primary"
          onClick={() => setIsCreateOpen(true)}
        >
          <Plus className="mr-2 h-4 w-4" />
          Create Task
        </Button>
      </div>

      {!isLoading && !error && tasks.length > 0 && (
        <label className="flex max-w-lg items-center gap-2 rounded-lg border border-border/70 bg-surface-1/90 backdrop-blur-md px-3.5 py-2 text-content-secondary shadow-glass focus-within:ring-2 focus-within:ring-primary focus-within:border-primary/50">
          <Search aria-hidden="true" className="h-4 w-4 shrink-0" />
          <span className="sr-only">Search tasks</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search title or task type" className="min-w-0 flex-1 bg-transparent text-sm text-content-primary outline-none placeholder:text-content-tertiary" />
        </label>
      )}

      {renderContent()}

      <TaskCreateDialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreated={() => setActiveTab("pending")}
      />
    </div>
  );
}
