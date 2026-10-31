import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "system" | "dark" | "light";

interface UIStore {
  isSidebarExpanded: boolean;
  isMobileNavOpen: boolean;
  isCommandPaletteOpen: boolean;
  theme: Theme;
  toggleSidebar: () => void;
  setSidebarExpanded: (expanded: boolean) => void;
  setMobileNavOpen: (open: boolean) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setTheme: (theme: Theme) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      isSidebarExpanded: true,
      isMobileNavOpen: false,
      isCommandPaletteOpen: false,
      theme: "system",
      toggleSidebar: () => set((state) => ({ isSidebarExpanded: !state.isSidebarExpanded })),
      setSidebarExpanded: (expanded) => set({ isSidebarExpanded: expanded }),
      setMobileNavOpen: (open) => set({ isMobileNavOpen: open }),
      setCommandPaletteOpen: (open) => set({ isCommandPaletteOpen: open }),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "heliox-ui-storage",
      version: 2,
      // Earlier builds stored "obsidian"/"aurora" theme names.
      migrate: (persisted) => {
        const state = (persisted ?? {}) as { theme?: string; isSidebarExpanded?: boolean };
        const theme: Theme = state.theme === "obsidian" ? "dark" : state.theme === "aurora" ? "light" : state.theme === "dark" || state.theme === "light" ? state.theme : "system";
        return { isSidebarExpanded: state.isSidebarExpanded ?? true, theme } as UIStore;
      },
      partialize: (state) => ({ isSidebarExpanded: state.isSidebarExpanded, theme: state.theme }) as UIStore,
    }
  )
);
