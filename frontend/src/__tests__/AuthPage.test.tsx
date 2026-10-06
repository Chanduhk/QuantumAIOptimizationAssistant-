import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { login, register, sessionState } = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  sessionState: { data: null as { id: number; email: string; created_at: string } | null, isLoading: false },
}));

vi.mock("@/api/endpoints", () => ({
  api: { auth: { login, register } },
}));

vi.mock("@/api/hooks", () => ({
  CURRENT_USER_QUERY_KEY: ["auth", "current-user"],
  useCurrentUser: () => sessionState,
}));

import { AuthPage } from "@/pages/AuthPage";
import { useUserStore } from "@/stores/userStore";

function renderAuth(path: "/login" | "/signup") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<AuthPage />} />
          <Route path="/signup" element={<AuthPage />} />
          <Route path="/" element={<p>Authenticated dashboard</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AuthPage", () => {
  beforeEach(() => {
    login.mockReset();
    register.mockReset();
    sessionState.data = null;
    sessionState.isLoading = false;
    useUserStore.getState().setUserId(null);
  });

  it("logs in, stores authenticated identity, and opens the protected dashboard", async () => {
    login.mockResolvedValue({ user: { id: 23, email: "user@example.com", created_at: "2026-01-01" } });
    renderAuth("/login");
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a long enough password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Authenticated dashboard")).toBeInTheDocument();
    expect(login).toHaveBeenCalledWith({ email: "user@example.com", password: "a long enough password" });
    expect(useUserStore.getState().userId).toBe(23);
  });

  it("registers a new account through the authenticated-session API", async () => {
    register.mockResolvedValue({ user: { id: 24, email: "new@example.com", created_at: "2026-01-01" } });
    renderAuth("/signup");
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a long enough password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Authenticated dashboard")).toBeInTheDocument();
    expect(register).toHaveBeenCalledWith({ email: "new@example.com", password: "a long enough password" });
    expect(useUserStore.getState().userId).toBe(24);
  });

  it("restores an existing session and redirects away from login", async () => {
    sessionState.data = { id: 25, email: "restored@example.com", created_at: "2026-01-01" };
    renderAuth("/login");
    expect(await screen.findByText("Authenticated dashboard")).toBeInTheDocument();
  });
});
