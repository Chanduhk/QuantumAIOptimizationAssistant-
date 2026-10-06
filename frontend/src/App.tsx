import { createBrowserRouter, Navigate, Outlet, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { AuthPage } from "@/pages/AuthPage";
import { CURRENT_USER_QUERY_KEY, useCurrentUser } from "@/api/hooks";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { useUserStore } from "@/stores/userStore";
import { useJamStore } from "@/stores/jamStore";

// Pages
import { DashboardPage } from "@/pages/DashboardPage";
import { AssistantPage } from "@/pages/AssistantPage";
import { TasksPage } from "@/pages/TasksPage";
import { PlanningPage } from "@/pages/PlanningPage";
import { OptimizationPage } from "@/pages/OptimizationPage";
import { IntelligencePage } from "@/pages/IntelligencePage";
import { DataLearningPage } from "@/pages/DataLearningPage";
import { QuantumWorkspacePage } from "@/pages/QuantumWorkspacePage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SystemStatusPage } from "@/pages/SystemStatusPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function RequireAuthentication() {
  const { data: user, isLoading, isError, refetch } = useCurrentUser();
  const setUserId = useUserStore((state) => state.setUserId);

  useEffect(() => setUserId(user?.id ?? null), [setUserId, user?.id]);

  if (isLoading) return <div className="flex min-h-screen items-center justify-center"><Spinner size="lg" /></div>;
  if (isError) {
    return <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background p-6">
      <p role="alert" className="text-status-error">Could not verify your session. Check the API connection and try again.</p>
      <Button variant="secondary" onClick={() => void refetch()}>Retry</Button>
    </main>;
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
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

const router = createBrowserRouter([
  { path: "/login", element: <AuthPage /> },
  { path: "/signup", element: <AuthPage /> },
  {
    path: "/",
    element: <RequireAuthentication />,
    errorElement: (
      <ErrorBoundary>
        <div />
      </ErrorBoundary>
    ),
    children: [
      { element: <MainLayout />, children: [
        { index: true, element: <DashboardPage /> },
        { path: "assistant", element: <AssistantPage /> },
        { path: "tasks", element: <TasksPage /> },
        { path: "planning", element: <PlanningPage /> },
        { path: "optimization", element: <OptimizationPage /> },
        { path: "intelligence", element: <IntelligencePage /> },
        { path: "data-learning", element: <DataLearningPage /> },
        { path: "quantum", element: <QuantumWorkspacePage /> },
        { path: "settings", element: <SettingsPage /> },
        { path: "status", element: <SystemStatusPage /> },
      ]},
    ],
  },
]);

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthenticationExpiryHandler />
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
