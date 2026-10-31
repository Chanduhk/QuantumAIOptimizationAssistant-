import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, OctagonAlert, X } from "lucide-react";
import { useToastStore, type ToastType } from "@/stores/toastStore";
import { cn } from "@/lib/utils";

const icons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 className="size-4 text-status-success" />,
  error: <OctagonAlert className="size-4 text-status-error" />,
  warning: <AlertTriangle className="size-4 text-status-warning" />,
  info: <Info className="size-4 text-quantum" />,
};

export function Toaster() {
  const { toasts, removeToast } = useToastStore();
  return (
    <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2 sm:bottom-6 sm:right-6">
      <AnimatePresence initial={false}>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            layout
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 24 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            className={cn("pointer-events-auto flex items-start gap-3 rounded-xl border border-border bg-surface-1 p-3.5 shadow-lift")}
            role={toast.type === "error" ? "alert" : "status"}
          >
            <span className="mt-0.5">{icons[toast.type]}</span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-content-primary">{toast.title}</p>
              {toast.message && <p className="mt-0.5 text-[13px] text-content-tertiary">{toast.message}</p>}
            </div>
            <button
              type="button"
              aria-label="Dismiss notification"
              onClick={() => removeToast(toast.id)}
              className="grid size-6 place-items-center rounded-md text-content-muted hover:bg-surface-2 hover:text-content-primary"
            >
              <X className="size-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export function toast(type: ToastType, title: string, message?: string) {
  useToastStore.getState().addToast({ type, title, message });
}
