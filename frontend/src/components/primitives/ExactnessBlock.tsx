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
    <div className={cn("sut-exactness-notice", className)} role="status">
      {getUnavailableMessage(block, fallback)}
    </div>
  );
}
