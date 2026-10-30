import * as React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Search, Bell, User, Menu, Moon, Sun, Monitor } from "lucide-react";
import { IconButton } from "@/components/ui/IconButton";
import { useUIStore } from "@/stores/uiStore";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { api } from "@/api/endpoints";
import { CURRENT_USER_QUERY_KEY, useCurrentUser, useSystemHealth } from "@/api/hooks";
import { useQueryClient } from "@tanstack/react-query";
import { getApiErrorMessage } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import { useToastStore } from "@/stores/toastStore";
import { useJamStore } from "@/stores/jamStore";

const routeNames: Record<string, string> = {
  "/": "Home",
  "/assistant": "Ask JAM",
  "/tasks": "My Tasks",
  "/planning": "My Schedule",
  "/intelligence": "My Insights",
  "/optimization": "Optimization Lab",
  "/data-learning": "Data & Learning",
  "/quantum": "Quantum Workspace",
  "/settings": "Settings",
  "/status": "System Diagnostics",
};

export function TopBar() {
  const location = useLocation();
  const { toggleSidebar, theme, setTheme } = useUIStore();
  const { data: currentUser } = useCurrentUser();
  const systemHealth = useSystemHealth();
  const apiHealthy = systemHealth.data?.status === "operational" && systemHealth.data.database_connected === true;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const setUserId = useUserStore((state) => state.setUserId);
  const addToast = useToastStore((state) => state.addToast);
  const [loggingOut, setLoggingOut] = React.useState(false);
  const currentTitle = routeNames[location.pathname] || "HELIOX AI";

  const handleLogout = async () => {
    try {
      setLoggingOut(true);
      await api.auth.logout();
      setUserId(null);
      useJamStore.getState().clearMessages();
      queryClient.clear();
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
      await navigate("/login", { replace: true });
    } catch (error: unknown) {
      addToast({ type: "error", title: "Sign out failed", message: getApiErrorMessage(error) });
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full shrink-0 items-center justify-between gap-2 border-b border-border/60 bg-surface-1/70 px-2 backdrop-blur-xl sm:px-4 shadow-sm">
      <div className="flex min-w-0 items-center gap-2 sm:gap-4">
        {/* Mobile Sidebar Toggle */}
        <div className="md:hidden">
          <IconButton variant="ghost" onClick={toggleSidebar} aria-label="Open sidebar">
            <Menu className="h-5 w-5" />
          </IconButton>
        </div>

        {/* Page Title & Breadcrumbs */}
        <div className="flex flex-col">
          <div className="flex items-center space-x-2 text-xs text-content-tertiary">
            <span>HELIOX AI</span>
            <span>/</span>
            <span className="text-content-secondary">{currentTitle}</span>
          </div>
          <h1 className="text-lg font-semibold text-content-primary tracking-tight">{currentTitle}</h1>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1 sm:gap-3">
        {/* Command Palette Trigger */}
        <button
          type="button"
          aria-label="Open search and navigation"
          className="hidden md:flex items-center gap-4 rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm text-content-secondary transition-colors hover:bg-surface-3 hover:text-content-primary focus:outline-none focus:ring-2 focus:ring-primary"
          onClick={() => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }));
          }}
        >
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            <span>Search or jump to...</span>
          </div>
          <kbd className="inline-flex h-5 items-center gap-1 rounded border border-border bg-surface-1 px-1.5 font-mono text-[10px] font-medium opacity-100">
            <span className="text-xs">Ctrl</span>K
          </kbd>
        </button>

        {/* Mobile Search Trigger */}
        <div className="md:hidden">
          <IconButton variant="ghost" aria-label="Open search and navigation" onClick={() => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }));
          }}>
            <Search className="h-5 w-5" />
          </IconButton>
        </div>

        <div className="h-6 w-px bg-border mx-1"></div>

        {/* System Status Indicator */}
        <div className="flex items-center gap-2 px-2" title={systemHealth.isError ? "API health unavailable" : `API ${systemHealth.data?.status ?? "check pending"}; database ${systemHealth.data?.database_connected === true ? "connected" : systemHealth.data?.database_connected === false ? "disconnected" : "status unavailable"}`}>
          <StatusIndicator status={systemHealth.isError ? "offline" : systemHealth.isLoading ? "loading" : apiHealthy ? "online" : "warning"} pulse={apiHealthy} />
          <span className={`hidden sm:inline text-xs font-medium ${systemHealth.isError ? "text-status-error" : apiHealthy ? "text-status-success" : "text-status-warning"}`}>
            {systemHealth.isError ? "API unavailable" : systemHealth.isLoading ? "Checking API" : apiHealthy ? "Operational" : systemHealth.data?.database_connected === false ? "Database unavailable" : "Status incomplete"}
          </span>
        </div>

        <div className="h-6 w-px bg-border mx-1"></div>

        {/* Theme Switcher */}
        <div className="hidden sm:flex items-center rounded-md border border-border bg-surface-2 p-0.5">
          <button
            onClick={() => setTheme("system")}
            className={`p-1.5 rounded-sm transition-colors ${theme === "system" ? "bg-surface-3 text-content-primary" : "text-content-tertiary hover:text-content-secondary"}`}
            title="System Theme"
            aria-label="Use system theme"
            aria-pressed={theme === "system"}
          >
            <Monitor className="h-4 w-4" />
          </button>
          <button
            onClick={() => setTheme("aurora")}
            className={`p-1.5 rounded-sm transition-colors ${theme === "aurora" ? "bg-surface-3 text-content-primary" : "text-content-tertiary hover:text-content-secondary"}`}
            title="Aurora (Light)"
            aria-label="Use light theme"
            aria-pressed={theme === "aurora"}
          >
            <Sun className="h-4 w-4" />
          </button>
          <button
            onClick={() => setTheme("obsidian")}
            className={`p-1.5 rounded-sm transition-colors ${theme === "obsidian" ? "bg-surface-3 text-content-primary" : "text-content-tertiary hover:text-content-secondary"}`}
            title="Obsidian (Dark)"
            aria-label="Use dark theme"
            aria-pressed={theme === "obsidian"}
          >
            <Moon className="h-4 w-4" />
          </button>
        </div>

        <IconButton variant="ghost" aria-label="Notifications are not available yet" disabled>
          <Bell className="h-5 w-5" />
        </IconButton>

        {/* User Context */}
        <div className="flex items-center gap-2 ml-1 p-1 pl-2 rounded-full bg-surface-2 border border-border">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-primary">
            <User className="h-4 w-4" />
          </div>
          <span className="hidden max-w-40 truncate sm:inline text-sm font-medium text-content-primary">{currentUser?.email ?? "Signed in"}</span>
          <button type="button" onClick={handleLogout} disabled={loggingOut} className="rounded px-2 py-1 text-xs text-content-secondary hover:bg-surface-3 hover:text-content-primary disabled:opacity-50">{loggingOut ? "Signing out…" : "Sign out"}</button>
        </div>
      </div>
    </header>
  );
}
