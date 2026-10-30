import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { createTask, startTask, completeTask, submitFeedback, mockState } = vi.hoisted(() => ({
  createTask: vi.fn(),
  startTask: vi.fn(),
  completeTask: vi.fn(),
  submitFeedback: vi.fn(),
  mockState: {
    startError: null as unknown,
    completeError: null as unknown,
    startPending: false,
    completePending: false,
    startReset: vi.fn(),
    completeReset: vi.fn(),
  },
}));

vi.mock("@/api/hooks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/hooks")>();
  return {
    ...actual,
    useCreateTask: () => ({ mutate: createTask, isPending: false }),
    useStartTask: () => ({
      mutate: startTask,
      isPending: mockState.startPending,
      error: mockState.startError,
      reset: mockState.startReset,
    }),
    useCompleteTask: () => ({
      mutate: completeTask,
      isPending: mockState.completePending,
      error: mockState.completeError,
      reset: mockState.completeReset,
    }),
    useSubmitTaskFeedback: () => ({
      mutate: submitFeedback,
      isPending: false,
      error: null,
    }),
  };
});

import { TaskCreateDialog } from "@/pages/tasks/TaskCreateDialog";
import { TaskRow } from "@/pages/tasks/TaskRow";
import { isAlreadyStartedError, isAlreadyCompletedError } from "@/api/hooks";
import { ApiRequestError } from "@/api/client";

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
    submitFeedback.mockReset();
    mockState.startError = null;
    mockState.completeError = null;
    mockState.startPending = false;
    mockState.completePending = false;
    mockState.startReset.mockReset();
    mockState.completeReset.mockReset();
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
    expect(startTask).toHaveBeenCalledWith({ taskId: 33, data: {} }, expect.anything());

    rerender(<TaskRow task={{ ...task, lifecycle_state: "started", start_time: "2026-10-19T09:00:00" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Complete" }));
    expect(completeTask).toHaveBeenCalledWith(
      { taskId: 33, data: {} },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("transitions cleanly through pending -> started -> completed with correct actions", () => {
    // 1. Pending state
    const { rerender } = render(<TaskRow task={task} />);
    expect(screen.getByText("○ Pending")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Start" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Complete" })).toBeNull();
    expect(screen.queryByText("✓ Completed")).toBeNull();

    // 2. Started state
    rerender(<TaskRow task={{ ...task, lifecycle_state: "started", start_time: "2026-10-19T09:00:00" }} />);
    expect(screen.getByText("● In progress")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Complete" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Start" })).toBeNull();
    expect(screen.queryByText("✓ Completed")).toBeNull();

    // 3. Completed state
    rerender(<TaskRow task={{
      ...task,
      completed: true,
      lifecycle_state: "completed",
      start_time: "2026-10-19T09:00:00",
      end_time: "2026-10-19T09:40:00",
      actual_duration: 40,
      outcome_valid: true,
    }} />);
    expect(screen.getByText("✓ Completed")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Start" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Complete" })).toBeNull();
    expect(screen.getByRole("button", { name: "Add Feedback" })).toBeTruthy();
  });

  it("recovers from stale frontend state where start_time is set but lifecycle_state is created", () => {
    render(<TaskRow task={{
      ...task,
      lifecycle_state: "created",
      start_time: "2026-10-19T09:00:00",
    }} />);

    // Even though lifecycle_state is "created", start_time !== null means it is in progress!
    expect(screen.getByText("● In progress")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Complete" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Start" })).toBeNull();
  });

  it("treats completed: true as authoritative completed state even with stale lifecycle_state", () => {
    render(<TaskRow task={{
      ...task,
      completed: true,
      lifecycle_state: "created",
    }} />);

    expect(screen.getByText("✓ Completed")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Start" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Complete" })).toBeNull();
  });

  it("handles duplicate start gracefully by resetting mutation error when backend returns already started", () => {
    startTask.mockImplementation((_args, options) => {
      options?.onError?.(new Error("task has already been started."));
    });

    render(<TaskRow task={task} />);
    fireEvent.click(screen.getByRole("button", { name: "Start" }));

    expect(startTask).toHaveBeenCalled();
    expect(mockState.startReset).toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("displays genuine unrelated mutation errors when start fails", () => {
    mockState.startError = new Error("Database connection lost.");
    render(<TaskRow task={task} />);

    const alert = screen.getByRole("alert");
    expect(alert).toBeTruthy();
    expect(alert.textContent).toContain("Database connection lost.");
  });

  it("does not label legacy actual duration values as minutes without lifecycle evidence", () => {
    render(<TaskRow task={{ ...task, actual_duration: 75, completed: true, lifecycle_state: "completed", start_time: null, end_time: null }} />);
    expect(screen.getByText("Actual: 75 (unverified)")).toBeTruthy();
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
    expect(screen.getByText(/Diff:\s+\+35 min/)).toBeTruthy();
  });

  it("rounds short runtime outcomes and estimate differences for display", () => {
    render(<TaskRow task={{
      ...task,
      actual_duration: 5 / 60,
      completed: true,
      lifecycle_state: "completed",
      outcome_valid: true,
      start_time: "2026-09-01T09:00:00",
      end_time: "2026-09-01T09:00:05",
    }} />);
    expect(screen.getByText("Actual: 0.1 min")).toBeTruthy();
    expect(screen.getByText(/Diff:\s+-39\.9 min/)).toBeTruthy();
  });

  it("correctly identifies already started and already completed error strings and responses", () => {
    expect(isAlreadyStartedError(new Error("task has already been started."))).toBe(true);
    expect(isAlreadyStartedError(new ApiRequestError("task has already been started.", "validation", 400))).toBe(true);
    expect(isAlreadyStartedError(new ApiRequestError("Task has already started", "http", 409))).toBe(true);
    expect(isAlreadyStartedError(new Error("Network Error"))).toBe(false);
    expect(isAlreadyStartedError(null)).toBe(false);

    expect(isAlreadyCompletedError(new Error("task has already been completed."))).toBe(true);
    expect(isAlreadyCompletedError(new ApiRequestError("Task has already been completed", "http", 409))).toBe(true);
    expect(isAlreadyCompletedError(new Error("Network Error"))).toBe(false);
    expect(isAlreadyCompletedError(undefined)).toBe(false);
  });
});

