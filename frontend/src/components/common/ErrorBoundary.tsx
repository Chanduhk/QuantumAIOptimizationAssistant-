import React, { Component, ErrorInfo, ReactNode } from "react";
import { useRouteError } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen w-full flex-col items-center justify-center bg-background p-6">
          <div className="flex w-full max-w-md flex-col items-center text-center">
            <div className="mb-6 rounded-full bg-status-error/10 p-4">
              <AlertCircle className="h-10 w-10 text-status-error" />
            </div>
            <h1 className="mb-2 text-2xl font-bold text-content-primary">System Error</h1>
            <p className="mb-6 text-content-secondary">
              The interface encountered an unexpected exception. Our systems have logged the issue.
            </p>
            <div className="flex gap-4">
              <Button onClick={() => window.location.reload()} variant="primary">
                Reload Interface
              </Button>
              <Button onClick={() => window.history.back()} variant="secondary">
                Go Back
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export function RouteErrorBoundary() {
  const error = useRouteError();
  console.error("Router error caught:", error);
  const errorMessage =
    error instanceof Error
      ? error.message
      : typeof error === "object" && error !== null && "statusText" in error
        ? String((error as { statusText: unknown }).statusText)
        : "The interface encountered an unexpected routing exception.";

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-background p-6">
      <div className="flex w-full max-w-md flex-col items-center text-center">
        <div className="mb-6 rounded-full bg-status-error/10 p-4">
          <AlertCircle className="h-10 w-10 text-status-error" />
        </div>
        <h1 className="mb-2 text-2xl font-bold text-content-primary">System Error</h1>
        <p className="mb-6 text-content-secondary">
          {errorMessage}
        </p>
        <div className="flex gap-4">
          <Button onClick={() => window.location.reload()} variant="primary">
            Reload Interface
          </Button>
          <Button onClick={() => window.history.back()} variant="secondary">
            Go Back
          </Button>
        </div>
      </div>
    </div>
  );
}
