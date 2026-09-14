import * as React from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { ToastContainer } from "@/components/ui/Toast";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { useUIStore } from "@/stores/uiStore";

export function MainLayout() {
  const theme = useUIStore((state) => state.theme);

  React.useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove("light", "dark");
    if (theme === "system") {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
        .matches
        ? "dark"
        : "light";
      root.classList.add(systemTheme);
      return;
    }
    const themeClass = theme === "obsidian" ? "dark" : "light";
    root.classList.add(themeClass);
  }, [theme]);
  return (
    <div className="flex min-h-screen w-full bg-background font-sans text-content-primary">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <div className="mx-auto w-full max-w-7xl animate-in fade-in slide-in-from-bottom-4 duration-500 ease-out fill-mode-both">
            <Outlet />
          </div>
        </main>
      </div>
      <ToastContainer />
      <CommandPalette />
    </div>
  );
}
