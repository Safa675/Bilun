"use client";

import type { HealthStatus } from "@/lib/api/health";
import { translateHealthMessage } from "@/lib/apiMessages";
import { Chip, Eyebrow, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

function statusVariant(status: HealthStatus["status"] | "unavailable"): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
    case "ready":
      return "success";
    case "degraded":
      return "warning";
    case "unavailable":
    default:
      return "danger";
  }
}

export default function SutHealthPanel({ healthStatus }: { healthStatus: HealthStatus | null }) {
  const t = useT();
  const resolvedStatus = healthStatus?.status ?? "unavailable";
  const statusLabel = t(`admin.statuses.${resolvedStatus}`);
  const empty = t("admin.empty");

  return (
    <Surface
      variant="soft"
      padding="md"
      className="flex flex-wrap items-center gap-4 text-xs text-[var(--text-secondary)]"
    >
      <Eyebrow>{t("admin.eyebrow")}</Eyebrow>
      <span className="inline-flex items-center gap-2">
        {t("admin.status")}
        <Chip variant={statusVariant(resolvedStatus)}>{statusLabel}</Chip>
      </span>
      <span>
        {t("admin.patients")}{" "}
        <strong className="font-semibold text-[var(--text-primary)] tabular-nums">
          {healthStatus?.patients ?? empty}
        </strong>
      </span>
      <span>
        {t("admin.build")}{" "}
        <code className="rounded bg-[var(--surface-base)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-primary)]">
          {healthStatus?.build_id ?? empty}
        </code>
      </span>
      {healthStatus?.message ? (
        <span className="text-[var(--text-muted)]">{translateHealthMessage(healthStatus.message)}</span>
      ) : null}
    </Surface>
  );
}
