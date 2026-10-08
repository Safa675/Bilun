"use client";

import { type ReactNode } from "react";
import { theme } from "@/lib/theme";
import { EkAnnexChips } from "@/components/sut/RegulatorySourceChips";
import { resolveBillingEkAnnexLabels } from "@/lib/sutRegulatorySources";
import { DataTable, Section } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { getExactnessDescription, type ExactnessLike } from "@/lib/sutExactness";

export const ACCENT = theme.accent;

export const WRAPPED_HEADER_STYLE = {
  whiteSpace: "normal",
  minWidth: 120,
} as const;

/**
 * Map legacy StatusChip hex colors to `Chip` variants. The design system
 * reserves the `gold` Chip for actionable emphasis (not status), so legacy
 * gold-status chips (priority "low", copay "exempt", strategy "package")
 * collapse to `success`. Informational blue maps to `outline`.
 */
export function chipVariantFromColor(color: string) {
  if (color === "#B91C1C") return "danger" as const;
  if (color === "#B45309" || color === "#D97706") return "warning" as const;
  if (color === "#2F6E4E" || color === ACCENT) return "success" as const;
  if (color === "#2563EB") return "outline" as const;
  return "neutral" as const;
}

export function BillingRegulatorySourceCell({
  ruleSource,
  rowCatalog,
}: {
  ruleSource?: string | null;
  rowCatalog?: string | null;
}) {
  const labels = resolveBillingEkAnnexLabels(ruleSource, rowCatalog);
  if (labels.length === 0) {
    return <span className="text-[var(--text-muted)]">—</span>;
  }
  return <EkAnnexChips labels={labels} />;
}

export function BillingSectionShell({
  id,
  title,
  total,
  children,
  collapsed = false,
  count,
  exactness,
  status,
}: {
  id?: string;
  title: string;
  total?: string;
  children: ReactNode;
  collapsed?: boolean;
  count?: number;
  exactness?: ExactnessLike;
  status?: ReactNode;
}) {
  const t = useT();
  if (collapsed) {
    const exactnessStatus = exactness?.exactness_status ?? exactness?.pricing_status;
    return (
      <details id={id} className="scroll-mt-24 rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-3">
        <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">
          {title}{count != null && <span className="tabular-nums"> · {count}</span>}
          {total && <> <span className="ml-3 whitespace-nowrap tabular-nums">{total}</span></>}
          <span title={getExactnessDescription(exactness, t)} className="mt-1 block text-xs font-normal text-[var(--text-secondary)]">
            {exactnessStatus ? t(`billing.recommendedActions.exactness.${exactnessStatus}`) : t("common.unavailable")}
            {status && <> · {status}</>}
          </span>
        </summary>
        <div className="mt-3 space-y-3 [&_.num-col]:whitespace-nowrap">{children}</div>
      </details>
    );
  }
  return (
    <Section
      id={id}
      title={title}
      trailing={
        total ? (
          <span className="whitespace-nowrap font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]">
            {total}
          </span>
        ) : null
      }
    >
      {children}
    </Section>
  );
}

export function TableWrap({
  minWidth,
  children,
}: {
  minWidth: number;
  children: ReactNode;
}) {
  return (
    <DataTable minWidth={minWidth} className="text-[0.82rem]">
      {children}
    </DataTable>
  );
}
