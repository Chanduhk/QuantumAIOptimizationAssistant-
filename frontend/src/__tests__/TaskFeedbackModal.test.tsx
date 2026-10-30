import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TaskFeedbackModal } from "../pages/tasks/TaskFeedbackModal";
import type { Task } from "@/api/endpoints";
import { useUserStore } from "@/stores/userStore";

const { submitFeedback } = vi.hoisted(() => ({
  submitFeedback: vi.fn(),
}));

vi.mock("@/api/endpoints", () => ({
  api: {
    tasks: { feedback: submitFeedback },
  },
}));

const mockTask: Task = {
  id: 42,
  user_id: 1,
  title: "Neural Architecture Review",
  task_type: "research",
  priority: 4,
  estimated_duration: 60,
  estimated_duration_unit: "minutes",
  actual_duration: 75,
  created_at: "2026-10-11T08:00:00Z",
  start_time: "2026-10-11T08:05:00Z",
  end_time: "2026-10-11T09:20:00Z",
  completed: true,
  lifecycle_state: "completed",
  outcome_valid: true,
  focus_rating: null,
  energy_rating: null,
  productivity_rating: null,
  feedback_notes: null,
  feedback_submitted_at: null,
};

describe("TaskFeedbackModal", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    submitFeedback.mockReset().mockResolvedValue({ result: { task: mockTask } });
    useUserStore.setState({ userId: 1 });
  });

  const renderComponent = (props: { isOpen: boolean; onClose: () => void; task?: Task }) => {
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    return render(
      <TaskFeedbackModal
        isOpen={props.isOpen}
        onClose={props.onClose}
        task={props.task ?? mockTask}
      />,
      { wrapper }
    );
  };

  it("renders outcome summary with verified duration metrics", () => {
    renderComponent({ isOpen: true, onClose: vi.fn() });

    expect(screen.getByText("Task Outcome & Feedback")).toBeInTheDocument();
    expect(screen.getByText("Outcome Summary")).toBeInTheDocument();
    expect(screen.getByText("1h")).toBeInTheDocument(); // Estimated (60m -> 1h)
    expect(screen.getByText("1h 15m")).toBeInTheDocument(); // Actual (75m -> 1h 15m)
    expect(screen.getByText("+15 min")).toBeInTheDocument(); // Difference
    expect(screen.getByText("1.25×")).toBeInTheDocument(); // Ratio
    expect(screen.getByText("Not provided")).toBeInTheDocument(); // Feedback Status
  });

  it("shows validation error when user attempts to save without rating all 3 categories", async () => {
    renderComponent({ isOpen: true, onClose: vi.fn() });

    const saveButton = screen.getByRole("button", { name: "Save feedback" });
    fireEvent.click(saveButton);

    expect(await screen.findByText(/Please provide a rating \(1 to 5\) for Focus, Energy, and Productivity/i)).toBeInTheDocument();
    expect(submitFeedback).not.toHaveBeenCalled();
  });

  it("submits genuine ratings when all categories are rated", async () => {
    const onClose = vi.fn();
    renderComponent({ isOpen: true, onClose });

    // Click 4 stars for Focus
    const focusStar4 = screen.getByRole("button", { name: "Focus: 4 stars" });
    fireEvent.click(focusStar4);

    // Click 5 stars for Energy
    const energyStar5 = screen.getByRole("button", { name: "Energy: 5 stars" });
    fireEvent.click(energyStar5);

    // Click 4 stars for Productivity
    const prodStar4 = screen.getByRole("button", { name: "Productivity: 4 stars" });
    fireEvent.click(prodStar4);

    // Enter optional notes
    const notesInput = screen.getByPlaceholderText(/Any notes on your flow/i);
    fireEvent.change(notesInput, { target: { value: "Smooth session" } });

    const saveButton = screen.getByRole("button", { name: "Save feedback" });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(submitFeedback).toHaveBeenCalledWith(
        42,
        expect.objectContaining({
          focus_rating: 4,
          energy_rating: 5,
          productivity_rating: 4,
          feedback_notes: "Smooth session",
          user_id: 1,
        }),
      );
    });

    expect(await screen.findByText(/Feedback successfully recorded/i)).toBeInTheDocument();
  });

  it("skips feedback without submitting when user clicks Skip for now", () => {
    const onClose = vi.fn();
    renderComponent({ isOpen: true, onClose });

    const skipButton = screen.getByRole("button", { name: "Skip for now" });
    fireEvent.click(skipButton);

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(submitFeedback).not.toHaveBeenCalled();
  });

  it("renders existing ratings if the task already has feedback recorded", () => {
    const ratedTask: Task = {
      ...mockTask,
      focus_rating: 5,
      energy_rating: 4,
      productivity_rating: 5,
      feedback_notes: "Deep focus state",
    };

    renderComponent({ isOpen: true, onClose: vi.fn(), task: ratedTask });

    expect(screen.getByText("Recorded")).toBeInTheDocument();
    expect(screen.getByText("Close")).toBeInTheDocument(); // button changes to Close
    expect(screen.getByDisplayValue("Deep focus state")).toBeInTheDocument();
  });
});
