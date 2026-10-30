import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  contentClassName?: string;
}

export function Dialog({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  className,
  contentClassName,
}: DialogProps) {
  // Prevent scrolling when dialog is open
  React.useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  // Handle escape key
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/65 backdrop-blur-md"
            onClick={onClose}
            aria-hidden="true"
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="dialog-title"
              aria-describedby={description ? "dialog-description" : undefined}
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ type: "spring", damping: 26, stiffness: 320 }}
              className={cn(
                "pointer-events-auto flex w-full max-w-lg flex-col overflow-hidden rounded-xl border border-border/70 bg-surface-1/95 shadow-2xl backdrop-blur-xl modal-viewport-height",
                "max-h-[calc(100vh-2rem)] max-h-[calc(100dvh-2rem)]",
                className
              )}
            >
              <div className="flex shrink-0 items-center justify-between border-b border-border p-4 sm:p-6">
                <div>
                  <h2 id="dialog-title" className="text-lg font-semibold text-content-primary">
                    {title}
                  </h2>
                  {description && (
                    <p id="dialog-description" className="mt-1 text-sm text-content-secondary">
                      {description}
                    </p>
                  )}
                </div>
                <button
                  onClick={onClose}
                  className="rounded-full p-1.5 text-content-secondary hover:bg-surface-2 hover:text-content-primary focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
                  aria-label="Close dialog"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div
                className={cn(
                  "min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-6",
                  contentClassName
                )}
              >
                {children}
              </div>
              {footer && (
                <div className="shrink-0 border-t border-border bg-surface-2 p-4 sm:p-6">
                  {footer}
                </div>
              )}
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}

