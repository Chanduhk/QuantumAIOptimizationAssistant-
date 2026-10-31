import * as React from "react";
import { cn } from "@/lib/utils";

/** Standard page container with consistent gutters and max width. */
export function Page({ children, className, wide }: { children: React.ReactNode; className?: string; wide?: boolean }) {
  return <div className={cn("mx-auto w-full px-4 pb-16 pt-6 sm:px-6 lg:px-8 lg:pt-8", wide ? "max-w-[1600px]" : "max-w-[1360px]", className)}>{children}</div>;
}

interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  layers?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, description, layers, actions, className }: PageHeaderProps) {
  return (
    <header className={cn("mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        {layers && (
          <p className="mb-2 inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.1em] text-content-muted">
            <span className="h-px w-5 bg-primary/60" />
            Architecture {layers}
          </p>
        )}
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-content-primary sm:text-[30px]">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-content-tertiary">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Section heading inside a page. */
export function SectionTitle({ title, description, action, className }: { title: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("mb-3 flex items-end justify-between gap-4", className)}>
      <div>
        <h2 className="text-[15px] font-semibold tracking-tight text-content-primary">{title}</h2>
        {description && <p className="mt-0.5 text-[13px] text-content-tertiary">{description}</p>}
      </div>
      {action}
    </div>
  );
}
