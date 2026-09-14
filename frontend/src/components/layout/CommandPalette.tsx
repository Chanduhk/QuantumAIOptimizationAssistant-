import * as React from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Search, LayoutDashboard, MessageSquare, CheckSquare, Calendar, Zap, BrainCircuit, Database, Atom, Settings, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandItem {
  id: string;
  title: string;
  icon: React.ElementType;
  onSelect: () => void;
  section: string;
}

export function CommandPalette() {
  const [isOpen, setIsOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const navigate = useNavigate();
  const inputRef = React.useRef<HTMLInputElement>(null);

  const togglePalette = React.useCallback(() => {
    setIsOpen((prev) => !prev);
    setQuery("");
    setSelectedIndex(0);
  }, []);

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        togglePalette();
      }
      if (e.key === "Escape" && isOpen) {
        e.preventDefault();
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, togglePalette]);

  const commands: CommandItem[] = React.useMemo(() => [
    { id: "home", title: "Dashboard", icon: LayoutDashboard, section: "Navigation", onSelect: () => navigate("/") },
    { id: "assistant", title: "JAM Assistant", icon: MessageSquare, section: "Navigation", onSelect: () => navigate("/assistant") },
    { id: "tasks", title: "Tasks", icon: CheckSquare, section: "Navigation", onSelect: () => navigate("/tasks") },
    { id: "planning", title: "Planning", icon: Calendar, section: "Navigation", onSelect: () => navigate("/planning") },
    { id: "optimization", title: "Optimization", icon: Zap, section: "Navigation", onSelect: () => navigate("/optimization") },
    { id: "intelligence", title: "Intelligence", icon: BrainCircuit, section: "Navigation", onSelect: () => navigate("/intelligence") },
    { id: "data-learning", title: "Data & Learning", icon: Database, section: "Navigation", onSelect: () => navigate("/data-learning") },
    { id: "quantum", title: "Quantum Workspace", icon: Atom, section: "Navigation", onSelect: () => navigate("/quantum") },
    { id: "settings", title: "Settings", icon: Settings, section: "System", onSelect: () => navigate("/settings") },
    { id: "status", title: "System Status", icon: Activity, section: "System", onSelect: () => navigate("/status") },
  ], [navigate]);

  const filteredCommands = React.useMemo(() => {
    if (!query) return commands;
    return commands.filter((cmd) => cmd.title.toLowerCase().includes(query.toLowerCase()));
  }, [commands, query]);



  React.useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % filteredCommands.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        filteredCommands[selectedIndex].onSelect();
        setIsOpen(false);
      }
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 bg-background/50 backdrop-blur-md"
            onClick={() => setIsOpen(false)}
          />
          <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] sm:pt-[20vh] px-4 pointer-events-none">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              className="w-full max-w-xl overflow-hidden rounded-xl border border-border-subtle bg-surface-1 shadow-2xl pointer-events-auto"
            >
              <div className="flex items-center border-b border-border px-4 py-3">
                <Search className="h-5 w-5 text-content-tertiary mr-3" />
                <input
                  ref={inputRef}
                  type="text"
                  placeholder="Search commands, navigate..."
                  className="flex-1 bg-transparent text-content-primary placeholder:text-content-tertiary focus:outline-none"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setSelectedIndex(0);
                  }}
                  onKeyDown={handleKeyDown}
                />
                <kbd className="hidden sm:inline-flex h-5 items-center gap-1 rounded border border-border bg-surface-2 px-1.5 font-mono text-[10px] font-medium text-content-secondary">
                  ESC
                </kbd>
              </div>

              <div className="max-h-[60vh] overflow-y-auto p-2">
                {filteredCommands.length === 0 ? (
                  <div className="py-6 text-center text-sm text-content-secondary">
                    No results found for "{query}"
                  </div>
                ) : (
                  <div className="space-y-1">
                    {filteredCommands.map((cmd, index) => {
                      const isSelected = index === selectedIndex;
                      const Icon = cmd.icon;
                      return (
                        <button
                          key={cmd.id}
                          className={cn(
                            "flex w-full items-center rounded-md px-3 py-2 text-sm transition-colors focus:outline-none",
                            isSelected
                              ? "bg-primary/10 text-primary"
                              : "text-content-secondary hover:bg-surface-2 hover:text-content-primary"
                          )}
                          onClick={() => {
                            cmd.onSelect();
                            setIsOpen(false);
                          }}
                          onMouseEnter={() => setSelectedIndex(index)}
                        >
                          <Icon className="h-4 w-4 mr-3" />
                          <div className="flex flex-1 items-center justify-between">
                            <span>{cmd.title}</span>
                            <span className="text-xs text-content-tertiary">{cmd.section}</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
