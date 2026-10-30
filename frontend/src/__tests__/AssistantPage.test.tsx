import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

const { sendCommand } = vi.hoisted(() => ({ sendCommand: vi.fn() }));

vi.mock("@/api/hooks", () => ({
  useAICommand: () => ({ mutateAsync: sendCommand }),
  useProviderStatus: () => ({ data: undefined }),
}));

import { AssistantPage } from "@/pages/AssistantPage";
import { useJamStore } from "@/stores/jamStore";
import { useUserStore } from "@/stores/userStore";

function renderAssistant() {
  return render(<MemoryRouter><AssistantPage /></MemoryRouter>);
}

describe("JAM assistant session", () => {
  beforeEach(() => {
    sendCommand.mockReset();
    useJamStore.getState().clearMessages();
    useUserStore.getState().setUserId(101);
  });

  it("shows an immediate message, blocks duplicate sends, and renders the response", async () => {
    let resolveRequest!: (value: { intent: string; result: Record<string, unknown> }) => void;
    sendCommand.mockReturnValueOnce(new Promise((resolve) => { resolveRequest = resolve; }));
    renderAssistant();

    fireEvent.change(screen.getByRole("textbox", { name: "Message JAM" }), {
      target: { value: "get recommendations" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send command" }));

    expect(screen.getAllByText("get recommendations")).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent("JAM is processing");
    expect(screen.getByText(/local memory model may initialize on the first command/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send command" })).toBeDisabled();
    expect(sendCommand).toHaveBeenCalledTimes(1);

    await act(async () => resolveRequest({ intent: "get_recommendations", result: { answer: "Ready" } }));
    expect(await screen.findByText("Ready")).toBeInTheDocument();
  });

  it("retries a failed request without duplicating its user message", async () => {
    sendCommand
      .mockRejectedValueOnce(new Error("Temporary service error"))
      .mockResolvedValueOnce({ intent: "get_recommendations", result: { answer: "Recovered" } });
    renderAssistant();

    fireEvent.change(screen.getByRole("textbox", { name: "Message JAM" }), {
      target: { value: "get recommendations" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send command" }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));

    expect(sendCommand).toHaveBeenCalledTimes(2);
    expect(screen.getAllByText("get recommendations")).toHaveLength(1);
    expect(await screen.findByText("Recovered")).toBeInTheDocument();
  });

  it("clears conversation on account change and ignores a stale response", async () => {
    let resolveRequest!: (value: { intent: string; result: Record<string, unknown> }) => void;
    sendCommand.mockReturnValueOnce(new Promise((resolve) => { resolveRequest = resolve; }));
    renderAssistant();

    fireEvent.change(screen.getByRole("textbox", { name: "Message JAM" }), {
      target: { value: "get recommendations" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send command" }));
    act(() => useUserStore.getState().setUserId(202));

    await waitFor(() => expect(useJamStore.getState().messages).toHaveLength(0));
    await act(async () => resolveRequest({ intent: "get_recommendations", result: { answer: "Old account" } }));
    expect(screen.queryByText("Old account")).not.toBeInTheDocument();
    expect(useJamStore.getState().messages).toHaveLength(0);
  });
});
