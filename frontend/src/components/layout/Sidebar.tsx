import * as React from "react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import {
  LayoutDashboard,
  MessageSquare,
  CheckSquare,
  Calendar,
  Zap,
  BrainCircuit,
  Database,
  Atom,
  Settings,
  Activity,
  Menu,
  X
} from "lucide-react";
import { IconButton } from "@/components/ui/IconButton";
import { motion, AnimatePresence } from "framer-motion";

const primaryNavItems = [
  { path: "/", label: "Home", icon: LayoutDashboard },
  { path: "/assistant", label: "Ask JAM", icon: MessageSquare },
  { path: "/tasks", label: "My Tasks", icon: CheckSquare },
  { path: "/planning", label: "My Schedule", icon: Calendar },
  { path: "/intelligence", label: "My Insights", icon: BrainCircuit },
];

const advancedNavItems = [
  { path: "/optimization", label: "Optimization Lab", icon: Zap },
  { path: "/quantum", label: "Quantum Workspace", icon: Atom },
  { path: "/data-learning", label: "Data & Learning", icon: Database },
  { path: "/status", label: "System Diagnostics", icon: Activity },
];

const bottomNavItems = [
  { path: "/settings", label: "Settings", icon: Settings },
];

function SidebarContent({ isMobile }: { isMobile: boolean }) {
  const { isSidebarExpanded, toggleSidebar, setSidebarExpanded } = useUIStore();
  const location = useLocation();

  return (
    <div className="flex h-full flex-col justify-between bg-surface-1/90 backdrop-blur-xl border-r border-border/70 shadow-lg">
      <div className="flex flex-col py-4 overflow-y-auto">
        <div className="flex items-center justify-between px-4 mb-5">
          <div className={cn("flex items-center overflow-hidden transition-all duration-300", isSidebarExpanded ? "w-auto opacity-100" : "w-0 opacity-0")}>
            <div className="flex flex-col whitespace-nowrap">
              <span className="text-sm font-bold tracking-wider text-primary uppercase">HELIOX AI</span>
              <span className="text-[10px] text-content-tertiary">Personal AI Assistant</span>
            </div>
          </div>
          {!isMobile && (
            <IconButton variant="ghost" onClick={toggleSidebar} aria-label="Toggle sidebar" className="ml-auto shrink-0">
              <Menu className="h-5 w-5" />
            </IconButton>
          )}
          {isMobile && (
            <IconButton variant="ghost" onClick={toggleSidebar} aria-label="Close sidebar" className="ml-auto shrink-0">
              <X className="h-5 w-5" />
            </IconButton>
          )}
        </div>

        {/* Primary Navigation */}
        <nav className="space-y-1 px-3">
          {primaryNavItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors group relative",
                  isActive
                    ? "bg-primary/12 text-primary shadow-sm"
                    : "text-content-secondary hover:bg-surface-2/80 hover:text-content-primary"
                )}
                title={!isSidebarExpanded && !isMobile ? item.label : undefined}
                aria-current={isActive ? "page" : undefined}
                onClick={() => isMobile && setSidebarExpanded(false)}
              >
                <Icon className={cn("h-5 w-5 shrink-0 transition-colors", isActive ? "text-primary" : "text-content-secondary group-hover:text-content-primary")} />
                <AnimatePresence>
                  {(isSidebarExpanded || isMobile) && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.18 }}
                      className="ml-3 truncate font-medium"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active-indicator"
                    className="absolute left-0 top-1/2 h-1/2 w-1 -translate-y-1/2 rounded-r-md bg-primary"
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Advanced Labs Section */}
        <div className="mt-6 px-3">
          <AnimatePresence>
            {(isSidebarExpanded || isMobile) && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-content-tertiary"
              >
                Labs & Diagnostics
              </motion.div>
            )}
          </AnimatePresence>
          <nav className="space-y-1">
            {advancedNavItems.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "flex items-center rounded-lg px-3 py-1.5 text-xs font-medium transition-colors group relative",
                    isActive
                      ? "bg-quantum/12 text-quantum shadow-sm"
                      : "text-content-tertiary hover:bg-surface-2/70 hover:text-content-primary"
                  )}
                  title={!isSidebarExpanded && !isMobile ? item.label : undefined}
                  aria-current={isActive ? "page" : undefined}
                  onClick={() => isMobile && setSidebarExpanded(false)}
                >
                  <Icon className={cn("h-4 w-4 shrink-0 transition-colors", isActive ? "text-quantum" : "text-content-tertiary group-hover:text-content-primary")} />
                  <AnimatePresence>
                    {(isSidebarExpanded || isMobile) && (
                      <motion.span
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: "auto" }}
                        exit={{ opacity: 0, width: 0 }}
                        transition={{ duration: 0.18 }}
                        className="ml-3 truncate"
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-advanced-indicator"
                      className="absolute left-0 top-1/2 h-1/2 w-1 -translate-y-1/2 rounded-r-md bg-quantum"
                    />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      <div className="p-3 border-t border-border/50">
        <nav className="space-y-1">
          {bottomNavItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors group relative",
                  isActive
                    ? "bg-primary/12 text-primary"
                    : "text-content-secondary hover:bg-surface-2/80 hover:text-content-primary"
                )}
                title={!isSidebarExpanded && !isMobile ? item.label : undefined}
                aria-current={isActive ? "page" : undefined}
                onClick={() => isMobile && setSidebarExpanded(false)}
              >
                <Icon className={cn("h-5 w-5 shrink-0", isActive ? "text-primary" : "text-content-secondary group-hover:text-content-primary")} />
                <AnimatePresence>
                  {(isSidebarExpanded || isMobile) && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.18 }}
                      className="ml-3 truncate"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

export function Sidebar() {
  const { isSidebarExpanded, setSidebarExpanded } = useUIStore();
  const mobileDrawerRef = React.useRef<HTMLElement>(null);
  
  // Handle mobile drawer responsive logic
  const [isMobile, setIsMobile] = React.useState(false);

  React.useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) {
        setSidebarExpanded(false);
      } else {
        // Desktop default to expanded if previously set
        setSidebarExpanded(true);
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [setSidebarExpanded]);

  React.useEffect(() => {
    if (!isMobile || !isSidebarExpanded) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const drawer = mobileDrawerRef.current;
    drawer?.querySelector<HTMLElement>("button, a")?.focus();
    const onDrawerKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSidebarExpanded(false);
        return;
      }
      if (event.key !== "Tab" || !drawer) return;
      const focusable = Array.from(drawer.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)'));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    drawer?.addEventListener("keydown", onDrawerKeyDown);
    return () => {
      drawer?.removeEventListener("keydown", onDrawerKeyDown);
      previousFocus?.focus();
    };
  }, [isMobile, isSidebarExpanded, setSidebarExpanded]);

  return (
    <>
      {/* Desktop Sidebar */}
      <motion.aside
        className="hidden h-dvh shrink-0 flex-col sticky top-0 md:flex"
        initial={false}
        animate={{ width: isSidebarExpanded ? 240 : 72 }}
        transition={{ duration: 0.3, ease: "easeInOut" }}
      >
        <SidebarContent isMobile={isMobile} />
      </motion.aside>

      {/* Mobile Sidebar (Drawer) */}
      <AnimatePresence>
        {isMobile && isSidebarExpanded && (
          <>
            <motion.button
              type="button"
              aria-label="Close navigation menu"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-40 bg-background/50 backdrop-blur-md md:hidden"
              onClick={() => setSidebarExpanded(false)}
            />
            <motion.aside
              ref={mobileDrawerRef}
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="fixed inset-y-0 left-0 z-50 w-64 md:hidden"
              role="dialog"
              aria-modal="true"
              aria-label="Main navigation"
            >
              <SidebarContent isMobile={isMobile} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
