"use client";

import { type ReactNode } from "react";
import { theme } from "@/lib/theme";
import { EkAnnexChips } from "@/components/sut/RegulatorySourceChips";
import { resolveBillingEkAnnexLabels } from "@/lib/sutRegulatorySources";
import { DataTable, Section } from "@/components/primitives";

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
}: {
  id?: string;
  title: string;
  total?: string;
  children: ReactNode;
}) {
  return (
    <Section
      id={id}
      title={title}
      trailing={
        total ? (
          <span className="font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]">
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
