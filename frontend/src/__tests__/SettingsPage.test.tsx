import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type ProviderStatusResponse } from "@/api/endpoints";
import { useUserStore } from "@/stores/userStore";
import { SettingsPage } from "@/pages/SettingsPage";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/settings"]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe("SettingsPage - Language Provider Section", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUserStore.setState({ userId: 1 });

    vi.spyOn(api.auth, "currentUser").mockResolvedValue({
      id: 1,
      email: "engineer@heliox.ai",
      created_at: "2026-01-01T00:00:00Z",
    });

    vi.spyOn(api.system, "getHealth").mockResolvedValue({
      status: "healthy",
      database_connected: true,
      timestamp: "2026-11-03T00:00:00Z",
    });
  });

  it("renders minimal Language Provider card with model and status", async () => {
    const mockProviderStatus: ProviderStatusResponse = {
      provider: "gemini",
      model: "gemini-3.8-flash",
      display_model: "Gemini 3.8 Flash",
      is_configured: true,
      status: "gemini_configured",
      status_label: "Configured",
      fallback_active: false,
    };
    vi.spyOn(api.ai, "providerStatus").mockResolvedValue(mockProviderStatus);

    const { container } = render(<SettingsPage />, { wrapper: createWrapper() });

    // Verify Card Title
    expect(await screen.findByRole("heading", { name: "Language Provider" })).toBeInTheDocument();

    // Wait for provider data to resolve and verify AI Model label and friendly name
    expect(await screen.findByText("AI Model")).toBeInTheDocument();
    expect(screen.getByText("Gemini 3.8 Flash")).toBeInTheDocument();

    // Verify Status label and configured value
    expect(screen.getByText("Status")).toBeInTheDocument();
    const configuredElements = screen.getAllByText("Configured");
    expect(configuredElements.length).toBeGreaterThanOrEqual(1);

    // Verify Test connection button exists and is enabled
    const testButton = await screen.findByRole("button", { name: "Test connection" }, { timeout: 5000 });
    expect(testButton).toBeInTheDocument();
    expect(testButton).not.toBeDisabled();

    // STRICT SECURITY VERIFICATION: No sensitive configuration details exposed
    expect(screen.queryByText(/api key/i)).toBeNull();
    expect(screen.queryByText(/masked/i)).toBeNull();
    expect(screen.queryByText(/endpoint/i)).toBeNull();
    expect(screen.queryByText(/timeout/i)).toBeNull();
    expect(screen.queryByText(/supported models/i)).toBeNull();

    // Verify raw secret keys or URLs are not in the DOM
    const html = container.innerHTML;
    expect(html).not.toContain("AIzaSy");
    expect(html).not.toContain("sk-");
    expect(html).not.toContain("https://generativelanguage.googleapis.com");
    expect(html).not.toContain("GEMINI_API_KEY");
  });

  it("transitions to Verified when test connection succeeds", async () => {
    const mockProviderStatus: ProviderStatusResponse = {
      provider: "gemini",
      model: "gemini-3.8-flash",
      display_model: "Gemini 3.8 Flash",
      is_configured: true,
      status: "gemini_configured",
      status_label: "Configured",
      fallback_active: false,
    };
    vi.spyOn(api.ai, "providerStatus").mockResolvedValue(mockProviderStatus);
    const testSpy = vi.spyOn(api.ai, "testProvider").mockResolvedValue({
      success: true,
      message: "Connection to Gemini 3.8 Flash succeeded.",
      status: "gemini_configured_and_available",
    });

    render(<SettingsPage />, { wrapper: createWrapper() });

    const testButton = await screen.findByRole("button", { name: "Test connection" }, { timeout: 5000 });
    fireEvent.click(testButton);

    await waitFor(() => {
      expect(testSpy).toHaveBeenCalledTimes(1);
    });

    // Should update status to Verified
    await waitFor(() => {
      expect(screen.getAllByText("Verified").length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText("Connection verified")).toBeInTheDocument();
    expect(screen.getByText("Connection to Gemini 3.8 Flash succeeded.")).toBeInTheDocument();
  });

  it("transitions to Connection failed when test connection fails", async () => {
    const mockProviderStatus: ProviderStatusResponse = {
      provider: "gemini",
      model: "gemini-3.8-flash",
      display_model: "Gemini 3.8 Flash",
      is_configured: true,
      status: "gemini_configured",
      status_label: "Configured",
      fallback_active: false,
    };
    vi.spyOn(api.ai, "providerStatus").mockResolvedValue(mockProviderStatus);
    vi.spyOn(api.ai, "testProvider").mockResolvedValue({
      success: false,
      message: "Provider credentials missing or invalid.",
      status: "gemini_unconfigured",
    });

    render(<SettingsPage />, { wrapper: createWrapper() });

    const testButton = await screen.findByRole("button", { name: "Test connection" }, { timeout: 5000 });
    fireEvent.click(testButton);

    await waitFor(() => {
      expect(screen.getAllByText("Connection failed").length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText("Provider credentials missing or invalid.")).toBeInTheDocument();
  });

  it("disables test connection when provider is not configured", async () => {
    const mockProviderStatus: ProviderStatusResponse = {
      provider: "gemini",
      model: "gemini-3.8-flash",
      display_model: "Gemini 3.8 Flash",
      is_configured: false,
      status: "gemini_unconfigured",
      status_label: "Deterministic Parser Active (Gemini Unconfigured)",
      fallback_active: true,
    };
    vi.spyOn(api.ai, "providerStatus").mockResolvedValue(mockProviderStatus);

    render(<SettingsPage />, { wrapper: createWrapper() });

    expect(await screen.findByRole("heading", { name: "Language Provider" })).toBeInTheDocument();
    expect(await screen.findByText("AI Model")).toBeInTheDocument();
    expect(screen.getAllByText("Not configured").length).toBeGreaterThanOrEqual(1);

    const testButton = await screen.findByRole("button", { name: "Test connection" }, { timeout: 5000 });
    expect(testButton).toBeDisabled();
  });
});
