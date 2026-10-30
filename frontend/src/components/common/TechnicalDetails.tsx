import React, { useState } from "react";
import { ChevronDown, ChevronRight, Terminal } from "lucide-react";

interface TechnicalDetailsProps {
  title?: string;
  data?: unknown;
  children?: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
}

/**
 * Recursively masks sensitive fields such as tokens, passwords, secrets, or internal keys.
 */
function maskSensitiveFields(obj: unknown, depth = 0): unknown {
  if (depth > 8) return "[Truncated: max depth]";
  if (obj === null || obj === undefined) return obj;

  if (typeof obj === "string") {
    // Mask JWT or long hex tokens
    if (/bearer\s+[a-zA-Z0-9._-]+/i.test(obj)) {
      return "[MASKED_BEARER_TOKEN]";
    }
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => maskSensitiveFields(item, depth + 1));
  }

  if (typeof obj === "object") {
    const sanitized: Record<string, unknown> = {};
    const sensitiveKeyPattern = /(password|secret|token|api[_-]?key|authorization|bearer|cookie|credential)/i;

    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      if (sensitiveKeyPattern.test(key)) {
        sanitized[key] = "[PROTECTED_CREDENTIAL]";
      } else {
        sanitized[key] = maskSensitiveFields(value, depth + 1);
      }
    }
    return sanitized;
  }

  return obj;
}

/**
 * Collapsible section for advanced diagnostic data and developer information.
 * Hidden by default to keep the primary interface clean, friendly, and non-technical.
 */
export function TechnicalDetails({
  title = "Technical details (Advanced diagnostics)",
  data,
  children,
  defaultOpen = false,
  className = "",
}: TechnicalDetailsProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const hasData = data !== undefined && data !== null;
  const hasContent = hasData || children !== undefined;

  if (!hasContent) {
    return null;
  }

  const sanitizedData = hasData ? maskSensitiveFields(data) : null;
  const jsonString = sanitizedData ? JSON.stringify(sanitizedData, null, 2) : "";

  return (
    <div
      className={`rounded-lg border border-border/70 bg-surface-2/40 transition-colors ${className}`}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-3.5 py-2.5 text-left text-xs font-medium text-content-secondary hover:text-content-primary focus:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        aria-expanded={isOpen}
      >
        <span className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-content-tertiary" />
          <span>{title}</span>
        </span>
        <span className="text-content-tertiary">
          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>

      {isOpen && (
        <div className="border-t border-border/50 px-3.5 py-3">
          {children}
          {hasData && (
            <pre className="max-h-72 overflow-auto rounded bg-surface-1 p-3 text-[11px] font-mono leading-relaxed text-content-secondary">
              <code>{jsonString}</code>
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
