import React from "react";
import { Badge } from "@/components/ui/Badge";
import { formatStatus, type StatusVariant } from "@/utils/formatters";

interface HumanStatusBadgeProps {
  status: unknown;
  context?: string;
  showDescription?: boolean;
  className?: string;
}

export function HumanStatusBadge({
  status,
  context,
  showDescription = false,
  className = "",
}: HumanStatusBadgeProps) {
  const { label, description, variant } = formatStatus(status, context);

  return (
    <div className={`inline-flex flex-col gap-1 ${className}`}>
      <Badge variant={variant as any} title={description}>
        {label}
      </Badge>
      {showDescription && (
        <span className="text-[11px] text-content-secondary leading-tight max-w-sm">
          {description}
        </span>
      )}
    </div>
  );
}
