import { NavLink, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { LogIn, LogOut, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NAV_GROUPS } from "@/lib/architecture";
import { useUIStore } from "@/stores/uiStore";
import { useCurrentUser, CURRENT_USER_QUERY_KEY } from "@/api/hooks";
import { api } from "@/api/endpoints";
import { useUserStore } from "@/stores/userStore";
import { useJamStore } from "@/stores/jamStore";
import { HelioxMark } from "@/components/brand/HelioxMark";
import { cn } from "@/lib/utils";

function NavContent({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  return (
    <nav aria-label="Primary" className="scrollbar-thin flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          {!collapsed && <p className="eyebrow mb-1.5 px-2.5">{group.label}</p>}
          {collapsed && <div className="mx-auto mb-2 h-px w-6 bg-border" />}
          <ul className="space-y-0.5">
            {group.items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === "/"}
                  onClick={onNavigate}
                  title={collapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    cn(
                      "group relative flex h-9 items-center gap-3 rounded-lg px-2.5 text-[13px] font-medium transition-colors",
                      collapsed && "justify-center px-0",
                      isActive
                        ? "bg-surface-2 text-content-primary dark:bg-surface-3/70"
                        : "text-content-tertiary hover:bg-surface-2/70 hover:text-content-primary"
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <motion.span
                          layoutId="nav-indicator"
                          className="absolute -left-3 top-2 h-5 w-[3px] rounded-r-full bg-primary"
                          transition={{ type: "spring", stiffness: 500, damping: 40 }}
                        />
                      )}
                      <item.icon className={cn("size-[17px] shrink-0", isActive ? "text-primary" : "text-content-muted group-hover:text-content-secondary")} />
                      {!collapsed && (
                        <>
                          <span className="flex-1 truncate">{item.label}</span>
                          {item.layers && <span className="font-mono text-[10px] text-content-muted">{item.layers}</span>}
                        </>
                      )}
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function UserFooter({ collapsed }: { collapsed: boolean }) {
  const { data: user } = useCurrentUser();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setUserId = useUserStore((s) => s.setUserId);

  const signOut = async () => {
    try {
      await api.auth.logout();
    } catch {
      // Session may already be invalid; clear local state regardless.
    }
    setUserId(null);
    useJamStore.getState().clearMessages();
    queryClient.clear();
    queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null);
    navigate("/login", { replace: true });
  };

  if (!user) {
    return (
      <div className={cn("border-t border-border-subtle p-3 dark:border-border", collapsed && "px-2")}>
        <NavLink
          to="/login"
          className={cn(
            "flex items-center gap-2.5 rounded-xl border border-primary/25 bg-primary/10 p-2 text-[13px] font-medium text-primary hover:bg-primary/20 transition-colors",
            collapsed ? "justify-center px-0" : "px-3"
          )}
          title={collapsed ? "Sign In" : undefined}
        >
          <LogIn className="size-4 shrink-0" />
          {!collapsed && <span>Sign In</span>}
        </NavLink>
      </div>
    );
  }

  const initial = user?.email?.charAt(0).toUpperCase() ?? "?";
  return (
    <div className={cn("border-t border-border-subtle p-3 dark:border-border", collapsed && "px-2")}>
      <div className={cn("flex items-center gap-2.5 rounded-xl p-1.5", collapsed && "flex-col")}>
        <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-primary/80 to-primary/40 text-[13px] font-semibold text-primary-foreground">
          {initial}
        </div>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-content-primary">{user?.email ?? "Signed in"}</p>
            <p className="text-[11px] text-content-muted">Personal workspace</p>
          </div>
        )}
        <button
          type="button"
          onClick={() => void signOut()}
          aria-label="Sign out"
          title="Sign out"
          className="grid size-8 shrink-0 place-items-center rounded-lg text-content-tertiary hover:bg-surface-2 hover:text-status-error"
        >
          <LogOut className="size-4" />
        </button>
      </div>
    </div>
  );
}

export function Sidebar() {
  const { isSidebarExpanded, toggleSidebar, isMobileNavOpen, setMobileNavOpen } = useUIStore();
  const collapsed = !isSidebarExpanded;

  return (
    <>
      {/* Desktop */}
      <aside
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border-subtle bg-surface-1/60 backdrop-blur-xl transition-[width] duration-200 dark:border-border dark:bg-surface-1/40 lg:flex",
          collapsed ? "w-[68px]" : "w-[248px]"
        )}
      >
        <div className={cn("flex h-14 items-center gap-2 px-4", collapsed && "justify-center px-0")}>
          <NavLink to="/" className="flex items-center gap-2.5" aria-label="HELIOX AI home">
            <HelioxMark className="size-7" animated />
            {!collapsed && (
              <span className="text-[14px] font-semibold tracking-[0.16em]">
                HELIOX<span className="ml-1 font-medium tracking-normal text-content-tertiary">AI</span>
              </span>
            )}
          </NavLink>
        </div>
        <NavContent collapsed={collapsed} />
        <div className={cn("px-3 pb-1", collapsed && "flex justify-center")}>
          <button
            type="button"
            onClick={toggleSidebar}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex h-8 items-center gap-2 rounded-lg px-2.5 text-xs text-content-muted hover:bg-surface-2 hover:text-content-secondary"
          >
            {collapsed ? <PanelLeftOpen className="size-4" /> : <><PanelLeftClose className="size-4" /> Collapse</>}
          </button>
        </div>
        <UserFooter collapsed={collapsed} />
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {isMobileNavOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <motion.div className="absolute inset-0 bg-black/50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMobileNavOpen(false)} />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 420, damping: 40 }}
              className="absolute inset-y-0 left-0 flex w-[272px] flex-col border-r border-border bg-surface-1"
            >
              <div className="flex h-14 items-center gap-2.5 px-4">
                <HelioxMark className="size-7" />
                <span className="text-[14px] font-semibold tracking-[0.16em]">HELIOX<span className="ml-1 font-medium tracking-normal text-content-tertiary">AI</span></span>
              </div>
              <NavContent collapsed={false} onNavigate={() => setMobileNavOpen(false)} />
              <UserFooter collapsed={false} />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
