/**
 * Eyebrow — single uppercase microcopy primitive.
 *
 * Replaces the legacy `.sut-muted-label`, `.sut-premium-eyebrow`,
 * `.metric-label`, `.tab-intro-subtitle`, `.app-filter-label`, and other
 * one-off "small caps label" rules scattered across `globals.css`.
 *
 * Tones:
 * - `muted` (default) — text-muted (`#8590A4`)
 * - `gold`           — gold accent (`--gold`)
 * - `primary`        — text-primary navy
 */

import type { ElementType, HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type EyebrowTone = "muted" | "gold" | "primary";

export interface EyebrowProps extends HTMLAttributes<HTMLElement> {
  tone?: EyebrowTone;
  as?: ElementType;
}

const TONE_CLASS: Record<EyebrowTone, string> = {
  muted: "text-[var(--text-muted)]",
  gold: "text-[var(--gold)]",
  primary: "text-[var(--text-primary)]",
};

export default function Eyebrow({
  tone = "muted",
  as,
  className,
  children,
  ...rest
}: EyebrowProps) {
  const Component = (as ?? "p") as ElementType;
  return (
    <Component
      className={cn(
        "text-[0.68rem] font-semibold uppercase tracking-[0.14em]",
        TONE_CLASS[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </Component>
  );
}
