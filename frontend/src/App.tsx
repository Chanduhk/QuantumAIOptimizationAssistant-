import { lazy, Suspense, useEffect } from "react";
import { createBrowserRouter, Navigate, Outlet, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ErrorBoundary, RouteErrorBoundary } from "@/components/common/ErrorBoundary";
import { AppShell } from "@/components/layout/AppShell";
import { AuthPage } from "@/pages/AuthPage";
import { CURRENT_USER_QUERY_KEY, useCurrentUser } from "@/api/hooks";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Feedback";
import { HelioxMark } from "@/components/brand/HelioxMark";
import { useUserStore } from "@/stores/userStore";
import { useJamStore } from "@/stores/jamStore";
import { useApplyTheme } from "@/lib/theme";

const named = <K extends string>(loader: () => Promise<Record<K, React.ComponentType>>, name: K) =>
  lazy(() => loader().then((module) => ({ default: module[name] })));

const OverviewPage = named(() => import("@/pages/OverviewPage"), "OverviewPage");
const AssistantPage = named(() => import("@/pages/AssistantPage"), "AssistantPage");
const TasksPage = named(() => import("@/pages/TasksPage"), "TasksPage");
const InsightsPage = named(() => import("@/pages/InsightsPage"), "InsightsPage");
const OptimizationStudioPage = named(() => import("@/pages/OptimizationStudioPage"), "OptimizationStudioPage");
const QuantumLabPage = named(() => import("@/pages/QuantumLabPage"), "QuantumLabPage");
const ExecutiveBrainPage = named(() => import("@/pages/ExecutiveBrainPage"), "ExecutiveBrainPage");
const OutcomesPage = named(() => import("@/pages/OutcomesPage"), "OutcomesPage");
const LearningPage = named(() => import("@/pages/LearningPage"), "LearningPage");
const SystemStatusPage = named(() => import("@/pages/SystemStatusPage"), "SystemStatusPage");
const SettingsPage = named(() => import("@/pages/SettingsPage"), "SettingsPage");

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function FullScreenLoader() {
  return (
    <div className="grid min-h-dvh place-items-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <HelioxMark className="size-10" animated />
        <Spinner size="sm" className="text-content-muted" />
      </div>
    </div>
  );
}

function RouteFallback() {
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <Spinner />
    </div>
  );
}

function RequireAuthentication() {
  const { data: user, isLoading, isError, refetch } = useCurrentUser();
  const setUserId = useUserStore((state) => state.setUserId);

  useEffect(() => setUserId(user?.id ?? null), [setUserId, user?.id]);

  if (isLoading) return <FullScreenLoader />;
  if (isError) {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-background p-6 text-center">
        <HelioxMark className="size-10" />
        <p role="alert" className="max-w-sm text-sm text-content-secondary">
          Could not verify your session. Check that the HELIOX API is running and reachable, then try again.
        </p>
        <Button variant="secondary" onClick={() => void refetch()}>Retry</Button>
      </main>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function ThemeController() {
  useApplyTheme();
  return null;
}

function AuthenticationExpiryHandler() {
  const setUserId = useUserStore((state) => state.setUserId);
  useEffect(() => {
    const clearExpiredSession = () => {
      setUserId(null);
      useJamStore.getState().clearMessages();
      queryClient.clear();
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
    };
    window.addEventListener("heliox:unauthorized", clearExpiredSession);
    return () => window.removeEventListener("heliox:unauthorized", clearExpiredSession);
  }, [setUserId]);
  return null;
}

const page = (Component: React.ComponentType) => (
  <Suspense fallback={<RouteFallback />}>
    <Component />
  </Suspense>
);

const router = createBrowserRouter([
  { path: "/login", element: <AuthPage /> },
  { path: "/signup", element: <AuthPage /> },
  { path: "/auth", element: <Navigate to="/login" replace /> },
  {
    path: "/",
    element: <RequireAuthentication />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: page(OverviewPage) },
          { path: "assistant", element: page(AssistantPage) },
          { path: "tasks", element: page(TasksPage) },
          { path: "insights", element: page(InsightsPage) },
          { path: "optimize", element: page(OptimizationStudioPage) },
          { path: "quantum", element: page(QuantumLabPage) },
          { path: "brain", element: page(ExecutiveBrainPage) },
          { path: "outcomes", element: page(OutcomesPage) },
          { path: "learning", element: page(LearningPage) },
          { path: "system", element: page(SystemStatusPage) },
          { path: "settings", element: page(SettingsPage) },
          // Routes from the previous frontend keep working.
          { path: "planning", element: <Navigate to="/optimize" replace /> },
          { path: "optimization", element: <Navigate to="/optimize" replace /> },
          { path: "intelligence", element: <Navigate to="/insights" replace /> },
          { path: "data-learning", element: <Navigate to="/learning" replace /> },
          { path: "status", element: <Navigate to="/system" replace /> },
          { path: "*", element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
]);

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeController />
        <AuthenticationExpiryHandler />
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
