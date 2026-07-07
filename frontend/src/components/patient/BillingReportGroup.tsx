import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Eyebrow } from "@/components/primitives";

export interface BillingReportGroupProps {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

/** Visual grouping for long patient billing reports — extra vertical rhythm between regions. */
export function BillingReportGroup({
  title,
  description,
  children,
  className,
}: BillingReportGroupProps) {
  return (
    <div className={cn("mt-10 space-y-4 first:mt-0", className)}>
      <div className="border-b border-[var(--border-subtle)] pb-3">
        <Eyebrow tone="primary">{title}</Eyebrow>
        {description ? (
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{description}</p>
        ) : null}
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
}
