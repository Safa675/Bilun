/**
 * Button — the single action primitive.
 *
 * Replaces the legacy primary / secondary / icon / section button
 * classes (and their compact / active modifiers) with one variant-driven
 * component.
 *
 * Variants map to brand tokens:
 * - `primary`   — filled gold, the affirmative action on a surface
 * - `secondary` — bordered subtle, the quiet / default action
 * - `ghost`     — transparent, only a hover wash
 * - `icon`      — square, for icon-only controls (dock / minimize / chevrons)
 *
 * Sizes:
 * - `default` — page-level actions
 * - `compact` — inline subsection / filter controls
 *
 * `asChild` merges the composed classes onto a single child element
 * (e.g. `<Button asChild><Link …/></Button>`) so anchors can carry the
 * button look without losing their native hit area — mirroring Radix's
 * Slot contract without the dependency.
 *
 * For the legacy "selected toggle" emphasis, spread
 * {@link buttonActiveClass} via `className` (conditional on selection
 * state) — twMerge resolves it over the variant base.
 */

import { Children, cloneElement } from "react";
import type {
  ButtonHTMLAttributes,
  ComponentProps,
  ReactElement,
  ReactNode,
} from "react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "icon";
export type ButtonSize = "default" | "compact";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  /** Merge button classes onto a single child (e.g. `<Link>`). */
  asChild?: boolean;
}

/**
 * Shared "selected / active toggle" emphasis — maps the legacy section
 * button "active" modifier. Apply via `className` so the variant base
 * stays declarative:
 *
 *     <Button variant="secondary" className={cn(selected && buttonActiveClass)} />
 */
export const buttonActiveClass =
  "border-[var(--gold)] bg-[var(--gold-subtle)] text-[var(--gold-hover)]";

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: cn(
    "rounded-[var(--r-md)] border border-[var(--gold)] bg-[var(--gold)]",
    "px-5 py-2 text-sm font-semibold text-[var(--text-inverse)]",
    "whitespace-nowrap transition-[background-color,border-color] duration-[var(--dur)] ease-[var(--ease)]",
    "hover:bg-[var(--gold-hover)] hover:border-[var(--gold-hover)]",
    "disabled:opacity-55 disabled:cursor-not-allowed",
  ),
  secondary: cn(
    "inline-flex items-center gap-2 rounded-[var(--r-md)] border border-[var(--border-subtle)]",
    "bg-[var(--surface-base)] px-4 py-2 text-sm font-semibold text-[var(--text-secondary)]",
    "whitespace-nowrap transition-[background-color,border-color,color] duration-[var(--dur)] ease-[var(--ease)]",
    "hover:border-[var(--gold-light)] hover:bg-[var(--gold-subtle)] hover:text-[var(--gold-hover)]",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ),
  ghost: cn(
    "inline-flex items-center gap-2 rounded-[var(--r-md)] border border-transparent",
    "bg-transparent px-3 py-2 text-sm font-medium text-[var(--text-secondary)]",
    "whitespace-nowrap transition-[background-color,color] duration-[var(--dur)] ease-[var(--ease)]",
    "hover:bg-[var(--surface-soft)] hover:text-[var(--text-primary)]",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ),
  icon: cn(
    "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--r-md)]",
    "border border-[var(--border-subtle)] bg-transparent text-sm text-[var(--text-secondary)]",
    "transition-[background-color,border-color,color] duration-[var(--dur)] ease-[var(--ease)]",
    "hover:bg-[var(--surface-soft)] hover:text-[var(--text-primary)]",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ),
};

const SIZE_CLASS: Record<ButtonSize, string> = {
  default: "",
  compact: "px-3.5 py-1.5 text-xs",
};

export default function Button({
  variant = "secondary",
  size = "default",
  loading = false,
  asChild = false,
  type = "button",
  className,
  children,
  disabled,
  onClick,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;
  const composed = cn(
    VARIANT_CLASS[variant],
    // `icon` owns its square sizing — don't let compact padding clobber it.
    variant === "icon" ? undefined : SIZE_CLASS[size],
    loading && "opacity-60 cursor-not-allowed",
    className,
  );

  if (asChild) {
    const child = Children.only(children) as ReactElement<ComponentProps<"a">>;
    // The anchor onClick differs from the button onClick only by currentTarget
    // type; treat them as interchangeable here (cloneElement is structural).
    const mergedProps = {
      ...rest,
      className: cn(composed, child.props.className),
      onClick,
      "aria-disabled": isDisabled ? true : undefined,
    } as Partial<ComponentProps<"a">>;
    return cloneElement(child, mergedProps);
  }

  return (
    <button
      type={type}
      disabled={isDisabled}
      onClick={onClick}
      className={composed}
      {...rest}
    >
      {children as ReactNode}
    </button>
  );
}
