"use client";

import { cn } from "@/lib/cn";
import { getUnavailableMessage } from "@/lib/sutExactness";

export interface ExactnessBlockProps {
  block: Parameters<typeof getUnavailableMessage>[0];
  fallback: string;
  className?: string;
}

/**
 * Unified exactness / missing-input notice — same affordance in hero and billing sections.
 */
export default function ExactnessBlock({ block, fallback, className }: ExactnessBlockProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--r-lg)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-4 py-3 text-[0.86rem] leading-[1.55] text-[var(--text-secondary)]",
        className,
      )}
      role="status"
    >
      {getUnavailableMessage(block, fallback)}
    </div>
  );
}
