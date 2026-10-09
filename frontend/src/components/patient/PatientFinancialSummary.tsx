"use client";

import type { CSSProperties } from "react";
import type {
  BillingActionReport,
  PatientClaimSummary,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import { fmtNum, fmtTRY2, fmtPriorityLabel } from "@/components/tabs/sut/shared";
import { chipVariantFromColor } from "@/components/patient/SutBillingReportSections";
import { Chip, Surface } from "@/components/primitives";
import { getExactnessDescription, hasRecoverableBillingTotals, isExactOutput } from "@/lib/sutExactness";
import { useT } from "@/lib/i18n/useTranslations";

const PRIORITY_COLORS: Record<BillingActionReport["priority"], string> = {
  high: "var(--danger)",
  medium: "var(--warning)",
  low: "var(--success)",
};

export interface PatientFinancialSummaryProps {
  outcome: SutPatientOutcomeData | null;
  billingReport: BillingActionReport | null;
  /** When set, KPI recoverable/priority reflect the selected bill only. */
  selectedClaimId?: string | null;
  /** Fallback when `sut_claim_totals.claim_count` is absent. */
  claimCount?: number;
  /** Per-bill summary for the selected claim. When present alongside a
   *  `selectedClaimId`, the Total billed / Expected payable tiles source
   *  from this bill instead of the patient-level `sut_claim_totals`. */
  selectedClaimSummary?: PatientClaimSummary | null;
}

export function PatientFinancialSummary({
  outcome,
  billingReport,
  selectedClaimId = null,
  claimCount,
  selectedClaimSummary = null,
}: PatientFinancialSummaryProps) {
  const t = useT();
  const isBillScoped = Boolean(selectedClaimId?.trim());
  const claimTotals = outcome?.sut_claim_totals;
  const claimTotalsExact = isExactOutput(claimTotals);
  // When bill-scoped, the Total billed / Expected payable tiles reflect the
  // selected bill's summary rather than the patient-level rollup.
  const billBilled = isBillScoped
    ? selectedClaimSummary?.expected_total_billed_try
    : undefined;
  const billPayable = isBillScoped
    ? selectedClaimSummary?.expected_total_payable_try
    : undefined;
  const reportHasTotals = hasRecoverableBillingTotals(billingReport);
  const recoverable =
    billingReport?.total_recoverable_try ?? billingReport?.sgk_uplift_try ?? null;
  const bills =
    claimTotals?.claim_count ??
    claimCount ??
    null;
  const priority = reportHasTotals ? billingReport?.priority : null;
  const priorityColor = priority ? PRIORITY_COLORS[priority] : "var(--text-muted)";
  const statusLabel = priority
    ? fmtPriorityLabel(priority)
    : reportHasTotals
      ? t("billing.summary.partialExact")
      : t("common.unavailable");

  if (!claimTotals && !billingReport) {
    return null;
  }

  const values = [
    {
      label: t("patient.financialSummary.totalBilled"),
      value: isBillScoped
        ? billBilled != null ? fmtTRY2(billBilled) : t("common.unavailable")
        : claimTotalsExact && claimTotals?.total_billed_try != null
          ? fmtTRY2(claimTotals.total_billed_try) : t("common.unavailable"),
    },
    {
      label: t("patient.financialSummary.expectedPayable"),
      value: isBillScoped
        ? billPayable != null ? fmtTRY2(billPayable) : t("common.unavailable")
        : claimTotalsExact && claimTotals?.total_expected_payable_try != null
          ? fmtTRY2(claimTotals.total_expected_payable_try) : t("common.unavailable"),
    },
    {
      label: t("patient.financialSummary.totalRecoverable"),
      explanation: t("billing.glossary.claimBacked"),
      value: reportHasTotals && recoverable != null ? fmtTRY2(recoverable) : t("common.unavailable"),
      gold: reportHasTotals && (recoverable ?? 0) > 0,
    },
    {
      label: t("patient.financialSummary.billCount"),
      value: isBillScoped ? fmtNum(1) : bills != null ? fmtNum(bills) : t("common.unavailable"),
    },
    {
      label: t("patient.financialSummary.overallPriority"),
      value: priority ? (
        <span style={{ color: priorityColor } as CSSProperties} className="font-medium">
          {fmtPriorityLabel(priority)}
        </span>
      ) : t("common.unavailable"),
    },
  ];

  return (
    <Surface variant="base" padding="sm" className="@container space-y-3 sm:p-4" data-patient-summary>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          {isBillScoped
            ? t("patient.financialSummary.titleBill", { claimId: selectedClaimId ?? "" })
            : t("patient.financialSummary.title")}
        </h2>
        {billingReport && !isExactOutput(billingReport) && (
          <Chip variant={chipVariantFromColor(priorityColor)} title={getExactnessDescription(billingReport, t)}>{statusLabel}</Chip>
        )}
      </div>
      <p className="sr-only">
        {isBillScoped
          ? t("patient.financialSummary.descriptionBill")
          : t("patient.financialSummary.description")}
      </p>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-3 @min-[360px]:grid-cols-2 @min-[800px]:grid-cols-[1.1fr_1.1fr_1.4fr_0.45fr_0.65fr]">
        {values.map(({ label, value, gold, explanation }) => (
          <div key={label} className="min-w-0 space-y-2">
            <dt title={explanation} className="min-h-8 text-xs leading-4 text-[var(--text-muted)]">{label}</dt>
            <dd title={value === t("common.unavailable") ? t("billing.glossary.unavailable") : undefined} className={`whitespace-nowrap tabular-nums text-xs leading-6 @min-[180px]:text-lg @min-[800px]:text-xl ${gold ? "font-display italic text-[var(--gold)]" : "font-semibold text-[var(--text-primary)]"}`}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </Surface>
  );
}
