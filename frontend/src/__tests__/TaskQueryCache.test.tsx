import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { listTasks, createExecutivePlan } = vi.hoisted(() => ({
  listTasks: vi.fn(),
  createExecutivePlan: vi.fn(),
}));

vi.mock("@/api/endpoints", () => ({
  api: {
    tasks: { list: listTasks },
    ai: { createExecutivePlan },
  },
}));

import { useCreateExecutivePlan, useTasks } from "@/api/hooks";
import { useUserStore } from "@/stores/userStore";

describe("task query cache", () => {
  beforeEach(() => {
    listTasks.mockReset().mockResolvedValue({ tasks: [] });
    createExecutivePlan.mockReset().mockResolvedValue({ result: {} });
    useUserStore.getState().setUserId(123);
  });

  it("shares the task list across readers and keeps it fresh after executive planning", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const firstReader = renderHook(() => useTasks(), { wrapper });
    await waitFor(() => expect(firstReader.result.current.data).toEqual({ tasks: [] }));

    const secondReader = renderHook(() => useTasks(), { wrapper });
    await waitFor(() => expect(secondReader.result.current.data).toEqual({ tasks: [] }));
    expect(listTasks).toHaveBeenCalledTimes(1);

    const planMutation = renderHook(() => useCreateExecutivePlan(), { wrapper });
    await act(async () => {
      planMutation.result.current.mutate({ user_id: 123, tasks: [] } as never);
    });
    await waitFor(() => expect(createExecutivePlan).toHaveBeenCalledTimes(1));
    expect(listTasks).toHaveBeenCalledTimes(1);

    firstReader.unmount();
    secondReader.unmount();
    planMutation.unmount();
    client.clear();
  });
});
