import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RouteErrorBoundary } from "@/components/common/ErrorBoundary";

const mockUseRouteError = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useRouteError: () => mockUseRouteError(),
  };
});

describe("RouteErrorBoundary", () => {
  it("renders recovery UI with error message when an Error is thrown", () => {
    mockUseRouteError.mockReturnValue(new Error("Component crashed while rendering"));
    render(<RouteErrorBoundary />);

    expect(screen.getByRole("heading", { name: "System Error" })).toBeInTheDocument();
    expect(screen.getByText("Component crashed while rendering")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload Interface" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Go Back" })).toBeInTheDocument();
  });

  it("renders fallback recovery message when error is an object with statusText", () => {
    mockUseRouteError.mockReturnValue({ statusText: "Gateway Timeout" });
    render(<RouteErrorBoundary />);

    expect(screen.getByRole("heading", { name: "System Error" })).toBeInTheDocument();
    expect(screen.getByText("Gateway Timeout")).toBeInTheDocument();
  });

  it("renders generic recovery message when error is unknown or primitive", () => {
    mockUseRouteError.mockReturnValue("some strange failure");
    render(<RouteErrorBoundary />);

    expect(screen.getByRole("heading", { name: "System Error" })).toBeInTheDocument();
    expect(screen.getByText("The interface encountered an unexpected routing exception.")).toBeInTheDocument();
  });
});
