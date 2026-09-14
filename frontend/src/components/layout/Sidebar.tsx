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

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/assistant", label: "JAM Assistant", icon: MessageSquare },
  { path: "/tasks", label: "Tasks", icon: CheckSquare },
  { path: "/planning", label: "Planning", icon: Calendar },
  { path: "/optimization", label: "Optimization", icon: Zap },
  { path: "/intelligence", label: "Intelligence", icon: BrainCircuit },
  { path: "/data-learning", label: "Data & Learning", icon: Database },
  { path: "/quantum", label: "Quantum Workspace", icon: Atom },
];

const bottomNavItems = [
  { path: "/settings", label: "Settings", icon: Settings },
  { path: "/status", label: "System Status", icon: Activity },
];



function SidebarContent({ isMobile }: { isMobile: boolean }) {
  const { isSidebarExpanded, toggleSidebar, setSidebarExpanded } = useUIStore();
  const location = useLocation();

  return (
    <div className="flex h-full flex-col justify-between bg-surface-1 border-r border-border">
      <div className="flex flex-col py-4">
        <div className="flex items-center justify-between px-4 mb-6">
          <div className={cn("flex items-center overflow-hidden transition-all duration-300", isSidebarExpanded ? "w-auto opacity-100" : "w-0 opacity-0")}>
            <div className="flex flex-col whitespace-nowrap">
              <span className="text-sm font-bold tracking-wider text-primary uppercase">HELIOX AI</span>
              <span className="text-[10px] text-content-tertiary">Think. Predict. Optimize.</span>
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

        <nav className="flex-1 space-y-1 px-3">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors group relative",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-content-secondary hover:bg-surface-2 hover:text-content-primary"
                )}
                title={!isSidebarExpanded && !isMobile ? item.label : undefined}
                onClick={() => isMobile && setSidebarExpanded(false)}
              >
                <Icon className={cn("h-5 w-5 shrink-0", isActive ? "text-primary" : "text-content-secondary group-hover:text-content-primary")} />
                <AnimatePresence>
                  {(isSidebarExpanded || isMobile) && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.2 }}
                      className="ml-3 truncate"
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
      </div>

      <div className="p-3">
        <nav className="space-y-1">
          {bottomNavItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors group",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-content-secondary hover:bg-surface-2 hover:text-content-primary"
                )}
                title={!isSidebarExpanded && !isMobile ? item.label : undefined}
                onClick={() => isMobile && setSidebarExpanded(false)}
              >
                <Icon className={cn("h-5 w-5 shrink-0", isActive ? "text-primary" : "text-content-secondary group-hover:text-content-primary")} />
                <AnimatePresence>
                  {(isSidebarExpanded || isMobile) && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.2 }}
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
  const { isSidebarExpanded, toggleSidebar, setSidebarExpanded } = useUIStore();
  
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

  return (
    <>
      {/* Desktop Sidebar */}
      <motion.aside
        className="hidden md:flex flex-col shrink-0 h-screen sticky top-0"
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
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-40 bg-background/50 backdrop-blur-md md:hidden"
              onClick={toggleSidebar}
            />
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="fixed inset-y-0 left-0 z-50 w-64 md:hidden"
            >
              <SidebarContent isMobile={isMobile} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
