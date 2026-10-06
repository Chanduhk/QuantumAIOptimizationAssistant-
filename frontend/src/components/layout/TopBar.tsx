import * as React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Search, Bell, User, Menu, Moon, Sun, Monitor } from "lucide-react";
import { IconButton } from "@/components/ui/IconButton";
import { useUIStore } from "@/stores/uiStore";
import { StatusIndicator } from "@/components/ui/StatusIndicator";
import { api } from "@/api/endpoints";
import { CURRENT_USER_QUERY_KEY, useCurrentUser } from "@/api/hooks";
import { useQueryClient } from "@tanstack/react-query";
import { getApiErrorMessage } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import { useToastStore } from "@/stores/toastStore";
import { useJamStore } from "@/stores/jamStore";

const routeNames: Record<string, string> = {
  "/": "Dashboard",
  "/assistant": "JAM Assistant",
  "/tasks": "Tasks",
  "/planning": "Planning",
  "/optimization": "Optimization",
  "/intelligence": "Intelligence",
  "/data-learning": "Data & Learning",
  "/quantum": "Quantum Workspace",
  "/settings": "Settings",
  "/status": "System Status",
};

export function TopBar() {
  const location = useLocation();
  const { toggleSidebar, theme, setTheme } = useUIStore();
  const { data: currentUser } = useCurrentUser();
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
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-md">
      <div className="flex items-center gap-4">
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

      <div className="flex items-center gap-3">
        {/* Command Palette Trigger */}
        <button
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
          <IconButton variant="ghost" onClick={() => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }));
          }}>
            <Search className="h-5 w-5" />
          </IconButton>
        </div>

        <div className="h-6 w-px bg-border mx-1"></div>

        {/* System Status Indicator */}
        <div className="flex items-center gap-2 px-2" title="System Operational">
          <StatusIndicator status="online" pulse />
          <span className="hidden sm:inline text-xs font-medium text-status-success">Online</span>
        </div>

        <div className="h-6 w-px bg-border mx-1"></div>

        {/* Theme Switcher */}
        <div className="hidden sm:flex items-center rounded-md border border-border bg-surface-2 p-0.5">
          <button
            onClick={() => setTheme("system")}
            className={`p-1.5 rounded-sm transition-colors ${theme === "system" ? "bg-surface-3 text-content-primary" : "text-content-tertiary hover:text-content-secondary"}`}
            title="System Theme"
          >
            <Monitor className="h-4 w-4" />
          </button>
          <button
            onClick={() => setTheme("aurora")}
            className={`p-1.5 rounded-sm transition-colors ${theme === "aurora" ? "bg-surface-3 text-content-primary" : "text-content-tertiary hover:text-content-secondary"}`}
            title="Aurora (Light)"
          >
            <Sun className="h-4 w-4" />
          </button>
          <button
            onClick={() => setTheme("obsidian")}
            className={`p-1.5 rounded-sm transition-colors ${theme === "obsidian" ? "bg-surface-3 text-content-primary" : "text-content-tertiary hover:text-content-secondary"}`}
            title="Obsidian (Dark)"
          >
            <Moon className="h-4 w-4" />
          </button>
        </div>

        <IconButton variant="ghost" aria-label="Notifications">
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
