/**
 * Surface — the single card primitive for the BILUN design system.
 *
 * Replaces the legacy `.frost-panel`, `.glass-panel`, `.sut-premium-panel`,
 * and `.sut-panel-card` class trees (full deletion in Phase 2).
 *
 * Variants:
 * - `base`    — white background, subtle border  (the default)
 * - `soft`    — cream `--surface-soft` background, no border
 * - `tint`    — light cream `--surface-tint` background, no border
 * - `inset`   — transparent, no border (for nested compositions)
 * - `raised`  — white background + `--shadow-2` (use sparingly)
 */

import type { ElementType, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export type SurfaceVariant = "base" | "soft" | "tint" | "inset" | "raised";

export interface SurfaceProps extends HTMLAttributes<HTMLElement> {
  variant?: SurfaceVariant;
  as?: ElementType;
  /** Internal padding. Defaults to `md` (1rem). */
  padding?: "none" | "sm" | "md" | "lg";
  /** Subtle border emphasis on hover (interactive cards). */
  interactive?: boolean;
  children?: ReactNode;
}

const VARIANT_CLASS: Record<SurfaceVariant, string> = {
  base: "bg-[var(--surface-base)] border border-[var(--border-subtle)]",
  soft: "bg-[var(--surface-soft)] border border-transparent",
  tint: "bg-[var(--surface-tint)] border border-transparent",
  inset: "bg-transparent border border-transparent",
  raised:
    "bg-[var(--surface-base)] border border-[var(--border-subtle)] shadow-[var(--shadow-2)]",
};

const PADDING_CLASS = {
  none: "p-0",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
} as const;

export default function Surface({
  variant = "base",
  as,
  padding = "md",
  interactive = false,
  className,
  children,
  ...rest
}: SurfaceProps) {
  const Component = (as ?? "div") as ElementType;
  return (
    <Component
      className={cn(
        "rounded-[var(--r-lg)]",
        VARIANT_CLASS[variant],
        PADDING_CLASS[padding],
        interactive &&
          (variant === "base" || variant === "raised") &&
          "transition-[border-color,box-shadow] duration-[var(--dur)] ease-[var(--ease)] hover:border-[var(--border-strong)]",
        className,
      )}
      {...rest}
    >
      {children}
    </Component>
  );
}
