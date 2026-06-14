"use client";

import type { CSSProperties } from "react";
import type { BillingActionReport, SutPatientOutcomeData } from "@/lib/domains/sut";
import { fmtNum, fmtTRY2, fmtPriorityLabel } from "@/components/tabs/sut/shared";
import { StatusChip } from "@/components/patient/SutBillingReportSections";
import { Eyebrow, Stat, Surface } from "@/components/primitives";
import { hasRecoverableBillingTotals, isExactOutput } from "@/lib/sutExactness";
import { theme } from "@/lib/theme";
import { useT } from "@/lib/i18n/useTranslations";

const PRIORITY_COLORS: Record<BillingActionReport["priority"], string> = {
  high: "#B91C1C",
  medium: "#D97706",
  low: theme.accent,
};

export interface PatientFinancialSummaryProps {
  outcome: SutPatientOutcomeData | null;
  billingReport: BillingActionReport | null;
  /** Fallback when `sut_claim_totals.claim_count` is absent. */
  claimCount?: number;
}

export function PatientFinancialSummary({
  outcome,
  billingReport,
  claimCount,
}: PatientFinancialSummaryProps) {
  const t = useT();
  const claimTotals = outcome?.sut_claim_totals;
  const claimTotalsExact = isExactOutput(claimTotals);
  const reportHasTotals = hasRecoverableBillingTotals(billingReport);
  const recoverable =
    billingReport?.total_recoverable_try ?? billingReport?.sgk_uplift_try ?? null;
  const bills =
    claimTotals?.claim_count ??
    claimCount ??
    null;
  const priority = reportHasTotals ? billingReport?.priority : null;
  const priorityColor = priority ? PRIORITY_COLORS[priority] : "#71717A";
  const statusLabel = priority
    ? fmtPriorityLabel(priority)
    : reportHasTotals
      ? t("billing.summary.partialExact")
      : t("common.unavailable");

  if (!claimTotals && !billingReport) {
    return null;
  }

  return (
    <Surface variant="base" padding="lg" className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Eyebrow>{t("patient.financialSummary.eyebrow")}</Eyebrow>
          <h2 className="mt-1 font-[var(--font-display)] text-xl font-medium tracking-tight text-[var(--text-primary)]">
            {t("patient.financialSummary.title")}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
            {t("patient.financialSummary.description")}
          </p>
        </div>
        {billingReport && (
          <StatusChip label={statusLabel} color={priorityColor} />
        )}
      </div>

      <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-5">
        <Stat
          label={t("patient.financialSummary.totalBilled")}
          value={
            claimTotalsExact && claimTotals?.total_billed_try != null
              ? fmtTRY2(claimTotals.total_billed_try)
              : t("common.unavailable")
          }
          display={claimTotalsExact ? "gold" : "default"}
        />
        <Stat
          label={t("patient.financialSummary.expectedPayable")}
          value={
            claimTotalsExact && claimTotals?.total_expected_payable_try != null
              ? fmtTRY2(claimTotals.total_expected_payable_try)
              : t("common.unavailable")
          }
        />
        <Stat
          label={t("patient.financialSummary.totalRecoverable")}
          value={
            reportHasTotals && recoverable != null
              ? fmtTRY2(recoverable)
              : t("common.unavailable")
          }
          display={reportHasTotals && (recoverable ?? 0) > 0 ? "gold" : "default"}
        />
        <Stat
          label={t("patient.financialSummary.billCount")}
          value={bills != null ? fmtNum(bills) : t("common.unavailable")}
        />
        <Stat
          label={t("patient.financialSummary.overallPriority")}
          value={
            priority ? (
              <span
                style={{ color: priorityColor } as CSSProperties}
                className="font-medium"
              >
                {fmtPriorityLabel(priority)}
              </span>
            ) : (
              t("common.unavailable")
            )
          }
        />
      </div>
    </Surface>
  );
}
