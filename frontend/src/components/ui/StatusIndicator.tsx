import { cn } from "@/lib/utils";

interface StatusIndicatorProps extends React.HTMLAttributes<HTMLDivElement> {
  status: "online" | "offline" | "warning" | "loading" | "unknown";
  pulse?: boolean;
}

export function StatusIndicator({ status, pulse = false, className, ...props }: StatusIndicatorProps) {
  const statusColors = {
    online: "bg-status-success",
    offline: "bg-status-error",
    warning: "bg-status-warning",
    loading: "bg-primary",
    unknown: "bg-content-tertiary",
  };

  return (
    <div className={cn("relative flex h-3 w-3", className)} {...props}>
      {pulse && status === "online" && (
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-success opacity-75"></span>
      )}
      {pulse && status === "loading" && (
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"></span>
      )}
      <span className={cn("relative inline-flex h-3 w-3 rounded-full", statusColors[status])}></span>
    </div>
  );
}
