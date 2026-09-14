import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from "lucide-react";
import { useToastStore, Toast as ToastType } from "@/stores/toastStore";

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  return (
    <div className="fixed bottom-0 right-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]">
      <AnimatePresence>
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onRemove={() => removeToast(toast.id)} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function ToastItem({ toast, onRemove }: { toast: ToastType; onRemove: () => void }) {
  const icons = {
    success: <CheckCircle className="h-5 w-5 text-status-success" />,
    error: <AlertCircle className="h-5 w-5 text-status-error" />,
    warning: <AlertTriangle className="h-5 w-5 text-status-warning" />,
    info: <Info className="h-5 w-5 text-status-info" />,
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 50, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.2 } }}
      className="pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-md border border-border bg-surface-2 p-4 pr-6 shadow-lg transition-all mb-2"
      role="alert"
    >
      <div className="flex gap-3">
        <div className="mt-0.5 shrink-0">{icons[toast.type]}</div>
        <div className="flex flex-col gap-1">
          <div className="text-sm font-semibold text-content-primary">{toast.title}</div>
          {toast.message && <div className="text-sm text-content-secondary">{toast.message}</div>}
        </div>
      </div>
      <button
        onClick={onRemove}
        className="absolute right-2 top-2 rounded-md p-1 text-content-secondary opacity-70 transition-opacity hover:text-content-primary hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}
