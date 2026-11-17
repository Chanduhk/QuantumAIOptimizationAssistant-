import * as React from "react";
import { cn } from "@/lib/utils";
import { Spinner } from "./Feedback";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "outline" | "danger" | "quantum";
export type ButtonSize = "xs" | "sm" | "md" | "lg" | "icon" | "icon-sm";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-primary-foreground hover:bg-primary-hover shadow-[0_1px_0_0_hsl(var(--highlight)/0.25)_inset,0_1px_2px_0_rgb(0_0_0/0.2)] hover:shadow-[0_2px_8px_-2px_hsl(var(--primary)/0.5)] hover:-translate-y-0.5",
  secondary: "bg-surface-2 text-content-primary border border-border hover:bg-surface-3 hover:-translate-y-0.5",
  outline: "border border-border text-content-secondary hover:text-content-primary hover:bg-surface-2 hover:-translate-y-0.5",
  ghost: "text-content-secondary hover:text-content-primary hover:bg-surface-2",
  danger: "bg-status-error/10 text-status-error border border-status-error/25 hover:bg-status-error/15 hover:-translate-y-0.5",
  quantum: "bg-quantum text-quantum-foreground hover:bg-quantum/90 hover:shadow-[0_2px_8px_-2px_hsl(var(--quantum)/0.5)] hover:-translate-y-0.5",
};

const sizes: Record<ButtonSize, string> = {
  xs: "h-7 px-2.5 text-xs gap-1.5 rounded-md",
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-lg",
  md: "h-9 px-4 text-sm gap-2 rounded-lg",
  lg: "h-11 px-5 text-[15px] gap-2 rounded-xl",
  icon: "h-9 w-9 rounded-lg",
  "icon-sm": "h-7 w-7 rounded-md",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", isLoading, leftIcon, rightIcon, children, disabled, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex select-none items-center justify-center whitespace-nowrap font-medium transition-[background-color,color,border-color,transform,box-shadow] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      {...props}
    >
      {isLoading ? <Spinner size="sm" className="text-current" /> : leftIcon}
      {children}
      {!isLoading && rightIcon}
    </button>
  )
);
Button.displayName = "Button";
