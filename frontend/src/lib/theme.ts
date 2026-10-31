import { useEffect, useState } from "react";
import { useUIStore } from "@/stores/uiStore";

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : true;
}

/** Applies the chosen theme to <html> and returns the resolved mode. */
export function useApplyTheme(): "dark" | "light" {
  const theme = useUIStore((state) => state.theme);
  const [systemDark, setSystemDark] = useState(systemPrefersDark);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const resolved = theme === "system" ? (systemDark ? "dark" : "light") : theme;

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", resolved === "dark");
    root.style.colorScheme = resolved;
  }, [resolved]);

  return resolved;
}

export function useResolvedTheme(): "dark" | "light" {
  const theme = useUIStore((state) => state.theme);
  const [systemDark, setSystemDark] = useState(systemPrefersDark);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  return theme === "system" ? (systemDark ? "dark" : "light") : theme;
}

/**
 * Chart colors. Categorical slots follow the validated reference order
 * (blue, orange, aqua) with separate steps per mode; the first three slots pass
 * all-pairs CVD checks, so no chart uses more than three series.
 */
export interface ChartPalette {
  series: [string, string, string];
  grid: string;
  axis: string;
  text: string;
  surface: string;
  primary: string;
  muted: string;
}

const PALETTES: Record<"dark" | "light", ChartPalette> = {
  dark: {
    series: ["#3987e5", "#d95926", "#199e70"],
    grid: "#1f2430",
    axis: "#7d8597",
    text: "#c4c9d4",
    surface: "#0f121a",
    primary: "#f5a524",
    muted: "#2a3040",
  },
  light: {
    series: ["#2a78d6", "#eb6834", "#1baf7a"],
    grid: "#e7e4dd",
    axis: "#6d7280",
    text: "#3f4554",
    surface: "#ffffff",
    primary: "#c97a08",
    muted: "#e3dfd6",
  },
};

export function useChartPalette(): ChartPalette {
  return PALETTES[useResolvedTheme()];
}
