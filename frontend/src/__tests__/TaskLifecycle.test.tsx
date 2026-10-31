import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Task } from "@/api/endpoints";

const { startTask, completeTask, submitFeedback, createTask } = vi.hoisted(() => ({
  startTask: vi.fn(),
  completeTask: vi.fn(),
  submitFeedback: vi.fn(),
  createTask: vi.fn(),
}));

vi.mock("@/api/hooks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/hooks")>();
  return {
    ...actual,
    useStartTask: () => ({ mutate: startTask, isPending: false, reset: vi.fn() }),
    useCompleteTask: () => ({ mutate: completeTask, isPending: false, reset: vi.fn() }),
    useSubmitTaskFeedback: () => ({ mutate: submitFeedback, isPending: false }),
    useCreateTask: () => ({ mutate: createTask, isPending: false, reset: vi.fn() }),
  };
});

import { TaskRow } from "@/features/tasks/TaskRow";
import { FeedbackDialog } from "@/features/tasks/FeedbackDialog";
import { TaskCreateDialog } from "@/features/tasks/TaskCreateDialog";

const task: Task = {
  id: 33,
  user_id: 202,
  title: "Write a report",
  task_type: "work",
  priority: 3,
  estimated_duration: 40,
  estimated_duration_unit: "minutes",
  estimated_duration_source: "task_api",
  actual_duration: null,
  created_at: null,
  start_time: null,
  end_time: null,
  completed: false,
  lifecycle_state: "created",
  outcome_valid: null,
};

const renderRow = (t: Task, onRequestFeedback = vi.fn()) =>
  render(
    <ul>
      <TaskRow task={t} onRequestFeedback={onRequestFeedback} />
    </ul>
  );

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TaskRow lifecycle actions", () => {
  it("starts a planned task", () => {
    renderRow(task);
    fireEvent.click(screen.getByRole("button", { name: "Start Write a report" }));
    expect(startTask).toHaveBeenCalledWith({ taskId: 33, data: {} }, expect.any(Object));
  });

  it("completes a started task and requests feedback on success", () => {
    const onRequestFeedback = vi.fn();
    completeTask.mockImplementation((_vars, opts) => opts.onSuccess({ result: { task: { ...task, completed: true, lifecycle_state: "completed", actual_duration: 42 } } }));
    renderRow({ ...task, lifecycle_state: "started", start_time: new Date().toISOString() }, onRequestFeedback);
    fireEvent.click(screen.getByRole("button", { name: "Complete Write a report" }));
    expect(completeTask).toHaveBeenCalledWith({ taskId: 33, data: {} }, expect.any(Object));
    expect(onRequestFeedback).toHaveBeenCalledWith(expect.objectContaining({ id: 33, actual_duration: 42 }));
  });

  it("offers feedback for an unrated completed task and shows the duration ratio", () => {
    const onRequestFeedback = vi.fn();
    renderRow({ ...task, completed: true, lifecycle_state: "completed", actual_duration: 60 }, onRequestFeedback);
    expect(screen.getByText("×1.50")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add feedback for Write a report" }));
    expect(onRequestFeedback).toHaveBeenCalled();
  });
});

describe("FeedbackDialog", () => {
  const done: Task = { ...task, completed: true, lifecycle_state: "completed", actual_duration: 50 };

  it("requires all three ratings", () => {
    render(<FeedbackDialog task={done} isOpen onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Save feedback" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Rate focus, energy and productivity");
    expect(submitFeedback).not.toHaveBeenCalled();
  });

  it("submits ratings and notes", () => {
    render(<FeedbackDialog task={done} isOpen onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("radio", { name: "Focus 4 of 5" }));
    fireEvent.click(screen.getByRole("radio", { name: "Energy 2 of 5" }));
    fireEvent.click(screen.getByRole("radio", { name: "Productivity 5 of 5" }));
    fireEvent.change(screen.getByLabelText(/Notes/), { target: { value: "Interrupted twice" } });
    fireEvent.click(screen.getByRole("button", { name: "Save feedback" }));
    expect(submitFeedback).toHaveBeenCalledWith(
      { taskId: 33, data: { focus_rating: 4, energy_rating: 2, productivity_rating: 5, feedback_notes: "Interrupted twice" } },
      expect.any(Object)
    );
  });
});

describe("TaskCreateDialog", () => {
  it("creates a task with an explicit minute estimate", () => {
    render(<TaskCreateDialog isOpen onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Plan sprint" } });
    fireEvent.click(screen.getByRole("button", { name: /P5/ }));
    fireEvent.click(screen.getByRole("button", { name: "1.5h" }));
    fireEvent.click(screen.getByRole("button", { name: "Create task" }));
    expect(createTask).toHaveBeenCalledWith(
      { title: "Plan sprint", task_type: "work", priority: 5, estimated_duration: 90, estimated_duration_unit: "minutes" },
      expect.any(Object)
    );
  });

  it("rejects a missing title", () => {
    render(<TaskCreateDialog isOpen onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Create task" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Give the task a title");
    expect(createTask).not.toHaveBeenCalled();
  });
});
