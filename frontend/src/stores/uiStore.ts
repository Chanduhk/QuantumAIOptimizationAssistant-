import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "system" | "obsidian" | "aurora";

interface UIStore {
  isSidebarExpanded: boolean;
  theme: Theme;
  toggleSidebar: () => void;
  setSidebarExpanded: (expanded: boolean) => void;
  setTheme: (theme: Theme) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      isSidebarExpanded: true,
      theme: "system",
      toggleSidebar: () => set((state) => ({ isSidebarExpanded: !state.isSidebarExpanded })),
      setSidebarExpanded: (expanded) => set({ isSidebarExpanded: expanded }),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "heliox-ui-storage",
    }
  )
);
