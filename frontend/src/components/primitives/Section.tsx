/**
 * Section — titled content block primitive.
 *
 * Replaces ad-hoc `<div className="frost-panel ...">` + h2 + total-pill
 * wrappers scattered across `billing/page.tsx`, `PatientSection`, etc.
 *
 * Surface variant is configurable so a Section can sit on white
 * (default) or on a cream/tint background. The title supports the
 * deck's italic-gold accent on a single word via `titleAccent`.
 */

import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import Surface, { type SurfaceVariant } from "./Surface";

export interface SectionProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  /** Section title (rendered in Fraunces). */
  title: ReactNode;
  /** Optional italic-gold accent word, appended after `title`. */
  titleAccent?: ReactNode;
  /** Short helper sentence under the title. */
  description?: ReactNode;
  /** Right-aligned content (total, action, toolbar). */
  trailing?: ReactNode;
  /** Surface variant applied to the wrapper. */
  variant?: SurfaceVariant;
  /** Padding passed to the wrapper Surface. */
  padding?: "none" | "sm" | "md" | "lg";
  children?: ReactNode;
}

export default function Section({
  title,
  titleAccent,
  description,
  trailing,
  variant = "base",
  padding = "lg",
  className,
  children,
  ...rest
}: SectionProps) {
  return (
    <Surface
      as="section"
      variant={variant}
      padding={padding}
      className={cn("space-y-4", className)}
      {...rest}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-[var(--font-display)] text-lg font-medium leading-tight text-[var(--text-primary)] tracking-tight">
            {title}
            {titleAccent ? (
              <>
                {" "}
                <em
                  className="not-italic font-[var(--font-display)] italic text-[var(--gold)]"
                >
                  {titleAccent}
                </em>
              </>
            ) : null}
          </h2>
          {description ? (
            <p className="mt-1 text-sm leading-snug text-[var(--text-secondary)]">
              {description}
            </p>
          ) : null}
        </div>
        {trailing ? <div className="shrink-0">{trailing}</div> : null}
      </header>
      <div>{children}</div>
    </Surface>
  );
}
