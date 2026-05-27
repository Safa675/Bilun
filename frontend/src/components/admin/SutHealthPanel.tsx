"use client";

import type { HealthStatus } from "@/lib/api/health";
import { Chip, Eyebrow, Surface } from "@/components/primitives";

function statusVariant(status: HealthStatus["status"] | "unavailable"): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
    case "ready":
      return "success";
    case "building":
      return "warning";
    case "error":
    case "not_started":
    case "unavailable":
    default:
      return "danger";
  }
}

export default function SutHealthPanel({ healthStatus }: { healthStatus: HealthStatus | null }) {
  const resolvedStatus = healthStatus?.status ?? "unavailable";

  return (
    <Surface
      variant="soft"
      padding="md"
      className="flex flex-wrap items-center gap-4 text-xs text-[var(--text-secondary)]"
    >
      <Eyebrow>Admin</Eyebrow>
      <span className="inline-flex items-center gap-2">
        Status
        <Chip variant={statusVariant(resolvedStatus)}>{resolvedStatus}</Chip>
      </span>
      <span>
        Patients:{" "}
        <strong className="font-semibold text-[var(--text-primary)] tabular-nums">
          {healthStatus?.patients ?? "—"}
        </strong>
      </span>
      <span>
        Build:{" "}
        <code className="rounded bg-[var(--surface-base)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-primary)]">
          {healthStatus?.build_id ?? "—"}
        </code>
      </span>
      {healthStatus?.message ? (
        <span className="text-[var(--text-muted)]">{healthStatus.message}</span>
      ) : null}
    </Surface>
  );
}
