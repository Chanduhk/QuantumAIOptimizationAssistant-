import * as React from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { useCreateTask } from "@/api/hooks";
import { getApiErrorMessage } from "@/api/client";

interface TaskCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function TaskCreateDialog({ isOpen, onClose }: TaskCreateDialogProps) {
  const { mutate: createTask, isPending } = useCreateTask();

  const [title, setTitle] = React.useState("");
  const [taskType, setTaskType] = React.useState("");
  const [priority, setPriority] = React.useState("3");
  const [estimatedDuration, setEstimatedDuration] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    if (!taskType.trim()) {
      setError("Task type is required.");
      return;
    }

    const duration = Number(estimatedDuration);
    if (!Number.isFinite(duration) || duration <= 0) {
      setError("Estimated duration must be a positive number (minutes).");
      return;
    }

    const priorityNum = parseInt(priority, 10);
    if (!Number.isInteger(priorityNum) || priorityNum < 1 || priorityNum > 5) {
      setError("Priority must be between 1 and 5.");
      return;
    }

    createTask(
      {
        title,
        task_type: taskType,
        priority: priorityNum,
        estimated_duration: duration,
        estimated_duration_unit: "minutes",
      },
      {
        onSuccess: () => {
          setTitle("");
          setTaskType("");
          setPriority("3");
          setEstimatedDuration("");
          onClose();
        },
        onError: (err: unknown) => {
          setError(getApiErrorMessage(err, "Failed to create task."));
        },
      }
    );
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Create New Task"
      description="Define a new task to be tracked and optimized by the system."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-md border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="task-title" className="mb-1.5 block text-sm font-medium text-content-primary">Title</label>
          <Input
            id="task-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="E.g., Review weekly reports"
            required
            disabled={isPending}
          />
        </div>

        <div>
          <label htmlFor="task-type" className="mb-1.5 block text-sm font-medium text-content-primary">Task Type</label>
          <Input
            id="task-type"
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            placeholder="E.g., focus, meeting, administrative"
            required
            disabled={isPending}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="task-priority" className="mb-1.5 block text-sm font-medium text-content-primary">Priority</label>
            <Select
              id="task-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              options={[
                { value: "1", label: "1 - Low" },
                { value: "2", label: "2 - Normal" },
                { value: "3", label: "3 - Medium" },
                { value: "4", label: "4 - High" },
                { value: "5", label: "5 - Critical" },
              ]}
              disabled={isPending}
            />
          </div>
          <div>
          <label htmlFor="task-estimated-duration" className="mb-1.5 block text-sm font-medium text-content-primary">Estimated Duration (minutes)</label>
            <Input
              id="task-estimated-duration"
              type="number"
              step="any"
              value={estimatedDuration}
              onChange={(e) => setEstimatedDuration(e.target.value)}
              placeholder="E.g., 60"
              min="1"
              required
              disabled={isPending}
            />
          </div>
        </div>

        <div className="mt-6 flex justify-end space-x-3">
          <Button variant="secondary" onClick={onClose} disabled={isPending} type="button">
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={isPending} isLoading={isPending}>
            Create Task
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
