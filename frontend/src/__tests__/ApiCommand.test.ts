import { beforeEach, describe, expect, it, vi } from "vitest";

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("@/api/client", () => ({ apiClient: { post } }));

import { api } from "@/api/endpoints";

describe("JAM command request", () => {
  beforeEach(() => post.mockReset());

  it("uses the measured cold-start request budget", async () => {
    post.mockResolvedValueOnce({ data: { intent: "analyze_productivity", result: {} } });
    const payload = { user_id: 1, command: "analyze my productivity", days_back: 90 };

    await api.ai.command(payload);

    expect(post).toHaveBeenCalledWith("/api/v1/ai/command", payload, { timeout: 240_000 });
  });
});
