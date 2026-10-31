import { Link } from "react-router-dom";
import { Menu, Monitor, Moon, Search, Sparkles, Sun } from "lucide-react";
import { useProviderStatus, useSystemHealth } from "@/api/hooks";
import { useUIStore, type Theme } from "@/stores/uiStore";
import { providerState } from "@/lib/status";
import { Badge, Kbd, StatusDot } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { HelioxMark } from "@/components/brand/HelioxMark";

const themeOrder: Theme[] = ["system", "dark", "light"];
const themeIcon = { system: Monitor, dark: Moon, light: Sun } as const;

export function Topbar() {
  const { setMobileNavOpen, setCommandPaletteOpen, theme, setTheme } = useUIStore();
  const health = useSystemHealth();
  const provider = useProviderStatus();
  const providerInfo = providerState(provider.data);
  const ThemeIcon = themeIcon[theme];

  const healthy = health.data?.status === "operational" && health.data.database_connected;
  const healthTone = health.isError ? "error" : health.isLoading ? "neutral" : healthy ? "success" : "warning";
  const healthText = health.isError ? "API offline" : health.isLoading ? "Connecting" : healthy ? "Operational" : "Degraded";

  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border-subtle bg-background/80 px-4 backdrop-blur-xl dark:border-border sm:px-6">
      <button
        type="button"
        onClick={() => setMobileNavOpen(true)}
        className="-ml-1.5 grid size-9 place-items-center rounded-lg text-content-secondary hover:bg-surface-2 lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="size-5" />
      </button>
      <Link to="/" className="lg:hidden" aria-label="HELIOX AI home">
        <HelioxMark className="size-7" />
      </Link>

      <button
        type="button"
        onClick={() => setCommandPaletteOpen(true)}
        className="ml-1 flex h-9 min-w-0 flex-1 items-center gap-2.5 rounded-lg border border-border bg-surface-1 px-3 text-left text-[13px] text-content-muted transition-colors hover:border-content-muted/40 hover:text-content-tertiary dark:bg-surface-2/50 sm:max-w-sm lg:ml-0"
      >
        <Search className="size-4 shrink-0" />
        <span className="flex-1 truncate">Search pages or ask JAM…</span>
        <span className="hidden items-center gap-0.5 sm:flex">
          <Kbd>{isMac ? "⌘" : "Ctrl"}</Kbd>
          <Kbd>K</Kbd>
        </span>
      </button>

      <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
        <Link to="/system" className="hidden md:block" title={health.data ? `Database ${health.data.database_connected ? "connected" : "disconnected"}` : undefined}>
          <span className="inline-flex h-8 items-center gap-2 rounded-lg px-2.5 text-xs font-medium text-content-secondary hover:bg-surface-2">
            <StatusDot tone={healthTone} pulse={healthy} />
            {healthText}
          </span>
        </Link>
        <Link to="/settings" className="hidden md:block" title={providerInfo.detail}>
          <Badge tone={providerInfo.tone} dot size="md">{providerInfo.short}</Badge>
        </Link>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Theme: ${theme}. Switch theme`}
          title={`Theme: ${theme}`}
          onClick={() => setTheme(themeOrder[(themeOrder.indexOf(theme) + 1) % themeOrder.length])}
        >
          <ThemeIcon />
        </Button>
        <Link to="/assistant" className="hidden sm:block">
          <Button size="sm" leftIcon={<Sparkles />}>Ask JAM</Button>
        </Link>
      </div>
    </header>
  );
}
