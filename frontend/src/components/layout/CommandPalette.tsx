import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CornerDownLeft, Plus, Search, Sparkles, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { NAV_ITEMS } from "@/lib/architecture";
import { useUIStore } from "@/stores/uiStore";
import { Kbd } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

interface PaletteAction {
  id: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  run: () => void;
}

export function CommandPalette() {
  const { isCommandPaletteOpen: open, setCommandPaletteOpen: setOpen } = useUIStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(!useUIStore.getState().isCommandPaletteOpen);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const actions = useMemo<PaletteAction[]>(() => {
    const go = (to: string) => () => {
      navigate(to);
      setOpen(false);
    };
    const q = query.trim().toLowerCase();
    const base: PaletteAction[] = [
      { id: "new-task", label: "Create a task", hint: "Tasks", icon: Plus, run: go("/tasks?new=1") },
      { id: "run-opt", label: "Run optimization pipeline", hint: "Optimization Studio", icon: Workflow, run: go("/optimize") },
      ...NAV_ITEMS.map((item) => ({ id: item.to, label: item.label, hint: item.description, icon: item.icon, run: go(item.to) })),
    ];
    // Label matches rank ahead of matches found only in the description.
    const filtered = q
      ? [...base.filter((a) => a.label.toLowerCase().includes(q)), ...base.filter((a) => !a.label.toLowerCase().includes(q) && a.hint.toLowerCase().includes(q))]
      : base;
    if (q) {
      filtered.push({
        id: "ask",
        label: `Ask JAM: “${query.trim()}”`,
        hint: "Send to the assistant",
        icon: Sparkles,
        run: () => {
          navigate(`/assistant?q=${encodeURIComponent(query.trim())}`);
          setOpen(false);
        },
      });
    }
    return filtered;
  }, [query, navigate, setOpen]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(actions.length - 1, i + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      actions[active]?.run();
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[55] flex items-start justify-center px-4 pt-[12vh]">
          <motion.div className="absolute inset-0 bg-black/45 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-surface-1 shadow-lift"
          >
            <div className="flex items-center gap-3 border-b border-border px-4">
              <Search className="size-4 text-content-muted" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={onKeyDown}
                placeholder="Jump to a page, or type a request for JAM…"
                className="h-12 flex-1 bg-transparent text-sm text-content-primary placeholder:text-content-muted focus:outline-none"
                aria-label="Search commands"
              />
              <Kbd>Esc</Kbd>
            </div>
            <ul className="scrollbar-thin max-h-[52vh] overflow-y-auto p-2" role="listbox">
              {actions.map((action, index) => (
                <li key={action.id} role="option" aria-selected={index === active}>
                  <button
                    type="button"
                    onMouseEnter={() => setActive(index)}
                    onClick={action.run}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left",
                      index === active ? "bg-surface-2 dark:bg-surface-3" : "hover:bg-surface-2"
                    )}
                  >
                    <action.icon className={cn("size-4 shrink-0", action.id === "ask" ? "text-primary" : "text-content-tertiary")} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-content-primary">{action.label}</span>
                      <span className="block truncate text-xs text-content-muted">{action.hint}</span>
                    </span>
                    {index === active && <CornerDownLeft className="size-3.5 text-content-muted" />}
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}
