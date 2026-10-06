import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { createTask, startTask, completeTask } = vi.hoisted(() => ({
  createTask: vi.fn(),
  startTask: vi.fn(),
  completeTask: vi.fn(),
}));

vi.mock("@/api/hooks", () => ({
  useCreateTask: () => ({ mutate: createTask, isPending: false }),
  useStartTask: () => ({ mutate: startTask, isPending: false, error: null }),
  useCompleteTask: () => ({ mutate: completeTask, isPending: false, error: null }),
}));

import { TaskCreateDialog } from "@/pages/tasks/TaskCreateDialog";
import { TaskRow } from "@/pages/tasks/TaskRow";

const task = {
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
} as const;

describe("task frontend lifecycle", () => {
  beforeEach(() => {
    createTask.mockReset();
    startTask.mockReset();
    completeTask.mockReset();
  });

  it("validates task input and sends new estimates explicitly in minutes", () => {
    render(<TaskCreateDialog isOpen onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Write report" } });
    fireEvent.change(screen.getByLabelText("Task Type"), { target: { value: "work" } });
    const durationInput = screen.getByLabelText("Estimated Duration (minutes)") as HTMLInputElement;
    fireEvent.change(durationInput, { target: { value: "0" } });
    expect(durationInput.validity.rangeUnderflow).toBe(true);
    expect(createTask).not.toHaveBeenCalled();

    fireEvent.change(durationInput, { target: { value: "40" } });
    fireEvent.submit(screen.getByRole("button", { name: "Create Task" }).closest("form")!);
    expect(createTask).toHaveBeenCalledWith(
      expect.objectContaining({ estimated_duration: 40, estimated_duration_unit: "minutes", task_type: "work" }),
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );
  });

  it("starts and completes tasks only through the lifecycle mutations", () => {
    const { rerender } = render(<TaskRow task={task} />);
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(startTask).toHaveBeenCalledWith({ taskId: 33, data: {} });

    rerender(<TaskRow task={{ ...task, lifecycle_state: "started" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Complete" }));
    expect(completeTask).toHaveBeenCalledWith({ taskId: 33, data: {} });
  });

  it("does not label legacy actual duration values as minutes without lifecycle evidence", () => {
    render(<TaskRow task={{ ...task, actual_duration: 75 }} />);
    expect(screen.getByText("Actual duration recorded; unit unverified: 75")).toBeTruthy();
  });

  it("formats lifecycle-verified actual duration as minutes", () => {
    render(<TaskRow task={{
      ...task,
      actual_duration: 75,
      completed: true,
      lifecycle_state: "completed",
      outcome_valid: true,
      start_time: "2026-09-01T09:00:00",
      end_time: "2026-09-01T10:15:00",
    }} />);
    expect(screen.getByText("Actual: 1h 15m")).toBeTruthy();
  });
});
