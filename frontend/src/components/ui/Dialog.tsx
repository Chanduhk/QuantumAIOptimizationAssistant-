import * as React from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  /** "center" for modals, "right" for a side sheet. */
  placement?: "center" | "right";
  dismissible?: boolean;
}

export function Dialog({ isOpen, onClose, title, description, children, footer, className, placement = "center", dismissible = true }: DialogProps) {
  const titleId = React.useId();
  const panelRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && dismissible) onClose();
    };
    window.addEventListener("keydown", onKey);
    // Move focus into the dialog for keyboard and screen-reader users.
    requestAnimationFrame(() => {
      const focusable = panelRef.current?.querySelector<HTMLElement>("[autofocus], input, textarea, select, button:not([data-close])");
      (focusable ?? panelRef.current)?.focus();
    });
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [isOpen, onClose, dismissible]);

  const isSheet = placement === "right";

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className={cn("fixed inset-0 z-50 flex", isSheet ? "justify-end" : "items-end justify-center sm:items-center sm:p-6")}>
          <motion.div
            className="absolute inset-0 bg-black/50 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={dismissible ? onClose : undefined}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            initial={isSheet ? { x: 32, opacity: 0 } : { y: 16, opacity: 0, scale: 0.98 }}
            animate={isSheet ? { x: 0, opacity: 1 } : { y: 0, opacity: 1, scale: 1 }}
            exit={isSheet ? { x: 32, opacity: 0 } : { y: 12, opacity: 0, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 420, damping: 34 }}
            className={cn(
              "relative flex max-h-[92dvh] w-full flex-col border border-border bg-surface-1 shadow-lift outline-none",
              isSheet ? "h-full max-h-none max-w-md border-y-0 border-r-0" : "rounded-t-2xl sm:max-w-lg sm:rounded-2xl",
              className
            )}
          >
            <div className="flex items-start justify-between gap-4 border-b border-border-subtle px-5 py-4 dark:border-border">
              <div className="min-w-0">
                <h2 id={titleId} className="text-base font-semibold tracking-tight text-content-primary">{title}</h2>
                {description && <p className="mt-1 text-[13px] text-content-tertiary">{description}</p>}
              </div>
              {dismissible && (
                <button
                  type="button"
                  data-close
                  onClick={onClose}
                  aria-label="Close"
                  className="-mr-1.5 -mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg text-content-tertiary hover:bg-surface-2 hover:text-content-primary"
                >
                  <X className="size-4" />
                </button>
              )}
            </div>
            <div className="scrollbar-thin flex-1 overflow-y-auto px-5 py-4">{children}</div>
            {footer && <div className="flex items-center justify-end gap-2 border-t border-border-subtle px-5 py-3.5 dark:border-border">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}
