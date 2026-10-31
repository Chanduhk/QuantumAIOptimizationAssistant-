import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useUserStore } from "@/stores/userStore";
import { AuthPage } from "@/pages/AuthPage";
import { ProposalCard } from "@/features/assistant/ProposalCard";

function wrapper(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/" element={<p>Home</p>} />
            <Route path="*" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
  useUserStore.setState({ userId: 5 });
});

describe("AuthPage", () => {
  beforeEach(() => {
    vi.spyOn(api.auth, "currentUser").mockRejectedValue(new ApiRequestError("Unauthorized", "authentication", 401));
  });

  it("enforces the 12 character password minimum on sign-up", async () => {
    const register = vi.spyOn(api.auth, "register");
    render(<AuthPage />, { wrapper: wrapper("/signup") });
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 12 characters");
    expect(register).not.toHaveBeenCalled();
  });

  it("signs in and navigates home", async () => {
    const login = vi.spyOn(api.auth, "login").mockResolvedValue({ user: { id: 9, email: "a@b.co", created_at: "2026-01-01" }, expires_at: "2026-02-01" });
    render(<AuthPage />, { wrapper: wrapper("/login") });
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: " a@b.co " } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Home")).toBeInTheDocument();
    expect(login).toHaveBeenCalledWith({ email: "a@b.co", password: "correct horse battery" });
    expect(useUserStore.getState().userId).toBe(9);
  });

  it("shows the API error on failed sign-in", async () => {
    vi.spyOn(api.auth, "login").mockRejectedValue(new ApiRequestError("Invalid email or password.", "authentication", 401));
    render(<AuthPage />, { wrapper: wrapper("/login") });
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong password!!" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  });
});

const proposal = {
  proposal_id: "1a5c6585-2a9c-48b3-bbc7-1bc3455d5a90",
  proposal_version: 2,
  feasibility_status: "FEASIBLE",
  total_demanded_hours: 2,
  available_hours: 8,
  parser_provenance: "deterministic_fallback",
  executive_summary: "Proposed feasible plan for 2 task(s).",
  schedule: [
    { task_id: "proposed:call", title: "Call the bank", priority: 3, scheduled_hour: 9, scheduled_end_hour: 10 },
    { task_id: "21", title: "Write report", priority: 5, scheduled_hour: 10, scheduled_end_hour: 11.5 },
  ],
};

describe("ProposalCard", () => {
  it("accepts the active proposal with its id and version", async () => {
    vi.spyOn(api.ai, "activePlan").mockResolvedValue({ id: proposal.proposal_id, version: 2, user_id: 5, status: "PROPOSED", schedule: proposal.schedule });
    const accept = vi.spyOn(api.ai, "acceptPlan").mockResolvedValue({ result: { persisted_count: 2 } });
    render(<ProposalCard result={proposal} onRefine={vi.fn()} />, { wrapper: wrapper("/assistant") });
    expect(screen.getByText("Rule-based parse")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Accept plan" }));
    await waitFor(() => expect(accept).toHaveBeenCalledWith({ user_id: 5, schedule: proposal.schedule, proposal_id: proposal.proposal_id, version: 2 }));
    expect(await screen.findByText(/Accepted — intervals were written/)).toBeInTheDocument();
  });

  it("closes a proposal that is no longer the active version", async () => {
    vi.spyOn(api.ai, "activePlan").mockResolvedValue({ id: proposal.proposal_id, version: 3, user_id: 5, status: "PROPOSED", schedule: [] });
    render(<ProposalCard result={proposal} fromHistory />, { wrapper: wrapper("/assistant") });
    expect(await screen.findByText("Closed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept plan" })).not.toBeInTheDocument();
  });

  it("sends refinement requests to the conversation", () => {
    vi.spyOn(api.ai, "activePlan").mockResolvedValue(null);
    const onRefine = vi.fn();
    render(<ProposalCard result={{ ...proposal, proposal_id: "" }} onRefine={onRefine} />, { wrapper: wrapper("/assistant") });
    fireEvent.change(screen.getByLabelText("Refine this plan"), { target: { value: "Move the report first" } });
    fireEvent.click(screen.getByRole("button", { name: "Refine" }));
    expect(onRefine).toHaveBeenCalledWith("Move the report first");
  });
});
