import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MainLayout } from "@/components/layout/MainLayout";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";

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

const router = createBrowserRouter([
  {
    path: "/",
    element: <MainLayout />,
    errorElement: (
      <ErrorBoundary>
        <div />
      </ErrorBoundary>
    ),
    children: [
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
    ],
  },
]);

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
