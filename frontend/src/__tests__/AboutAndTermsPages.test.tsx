import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AboutPage } from "@/pages/AboutPage";
import { TermsPage } from "@/pages/TermsPage";

function createWrapper(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe("AboutPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders page header, Gemini 3.8 Flash badge, and core mission", () => {
    const { container } = render(<AboutPage />, { wrapper: createWrapper("/about") });

    // Page title and subtitle
    expect(screen.getByRole("heading", { name: "About Heliox AI" })).toBeInTheDocument();
    expect(screen.getByText(/Precision Intelligence for Complex Human Execution/i)).toBeInTheDocument();

    // Core AI Model badges and mentions
    const modelBadges = screen.getAllByText(/Gemini 3.8 Flash/i);
    expect(modelBadges.length).toBeGreaterThanOrEqual(1);

    // STRICT SECURITY VERIFICATION: No API keys or internal secrets in the rendered HTML
    const html = container.innerHTML;
    expect(html).not.toContain("AIzaSy");
    expect(html).not.toContain("sk-proj");
    expect(html).not.toMatch(/\bsk-[a-zA-Z0-9]{15,}\b/);
    expect(html).not.toContain("GEMINI_API_KEY");
    expect(html).not.toContain("generativelanguage.googleapis.com");
  });

  it("renders the 6 Core Capability Pillars with formulas", () => {
    render(<AboutPage />, { wrapper: createWrapper("/about") });

    // Check pillars
    expect(screen.getByText("Goals Intelligence & Feasibility Modeling")).toBeInTheDocument();
    expect(screen.getByText("DAG Dependency Topology & Downstream Slack")).toBeInTheDocument();
    expect(screen.getByText("Multi-Criteria Dynamic Prioritization (MCDA)")).toBeInTheDocument();
    expect(screen.getByText("Context-Aware Actionable Proposals")).toBeInTheDocument();
    expect(screen.getByText("Cognitive Energy Budgeting & Fatigue Risk")).toBeInTheDocument();
    expect(screen.getByText("Classical & Quantum-Inspired Optimization")).toBeInTheDocument();
  });

  it("navigates across tabs to inspect 13-Layer Architecture Walkthrough and Governance", () => {
    render(<AboutPage />, { wrapper: createWrapper("/about") });

    // Switch to Language Intelligence tab
    const aiTab = screen.getByRole("button", { name: /Language Intelligence/i });
    fireEvent.click(aiTab);
    expect(screen.getByText("The JAM Assistant Architecture")).toBeInTheDocument();
    expect(screen.getByText("Deterministic Fallback Matrix")).toBeInTheDocument();

    // Switch to Architecture Walkthrough tab
    const archTab = screen.getByRole("button", { name: /13-Layer Architecture Walkthrough/i });
    fireEvent.click(archTab);
    expect(screen.getByText("The 13 Architectural Layers of Heliox AI")).toBeInTheDocument();
    expect(screen.getByText("L1")).toBeInTheDocument();
    expect(screen.getByText("L13")).toBeInTheDocument();

    // Switch to Governance tab
    const govTab = screen.getByRole("button", { name: /Governance, Privacy & Stack/i });
    fireEvent.click(govTab);
    expect(screen.getByText("Storage, Isolation & Privacy Guarantees")).toBeInTheDocument();
    expect(screen.getByText(/Local SQLite Workspace Isolation/i)).toBeInTheDocument();
  });
});

describe("TermsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders terms header, last updated badge, and executive summary", () => {
    render(<TermsPage />, { wrapper: createWrapper("/terms") });

    expect(screen.getByRole("heading", { name: "Terms & Conditions" })).toBeInTheDocument();
    expect(screen.getByText(/Last Updated: November 2026/i)).toBeInTheDocument();
    expect(screen.getByText("Executive Legal Summary")).toBeInTheDocument();
  });

  it("verifies accurate Heliox AI clauses: password length, SQLite data, and Gemini 3.8 Flash advisory disclaimer", () => {
    render(<TermsPage />, { wrapper: createWrapper("/terms") });

    // 12 character password requirement
    expect(screen.getByText(/at least 12 characters/i)).toBeInTheDocument();

    // SQLite relational storage & no commercial selling
    expect(screen.getByText(/SQLite \/ behavior_engine\.db/i)).toBeInTheDocument();
    expect(screen.getByText(/No Commercial Monetization or Selling of Data/i)).toBeInTheDocument();

    // Advisory nature of Gemini 3.8 Flash
    expect(screen.getByText(/Advisory Nature of Recommendations/i)).toBeInTheDocument();
    expect(screen.getByText(/AI recommendations do NOT constitute professional/i)).toBeInTheDocument();
  });

  it("filters clauses using the in-page search", () => {
    render(<TermsPage />, { wrapper: createWrapper("/terms") });

    const searchInput = screen.getByPlaceholderText("Search clauses...");
    fireEvent.change(searchInput, { target: { value: "password" } });

    // Section 2.0 (Account Security) should remain visible
    expect(screen.getByRole("heading", { name: /Account Security/i })).toBeInTheDocument();

    // Non-matching section like 5.0 (Optimization Solvers) should be filtered out from the main content
    expect(screen.queryByRole("heading", { name: /Optimization Solvers/i })).toBeNull();
  });
});
