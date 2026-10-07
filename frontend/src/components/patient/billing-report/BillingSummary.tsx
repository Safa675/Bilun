"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { hasRecoverableBillingTotals, isExactOutput } from "@/lib/sutExactness";
import { copayExemptionGapTotal, copayShowsIlaveColumn } from "@/lib/billingReportFields";
import { Chip, ExactnessBlock as ExactnessNotice, Eyebrow, Stat, Surface } from "@/components/primitives";
import { fmtNum, fmtPriorityLabel, fmtTRY2 } from "@/components/tabs/sut/shared";
import { ACCENT, chipVariantFromColor } from "./shared";

const PRIORITY_COLORS: Record<BillingActionReport["priority"], string> = {
  high: "#B91C1C",
  medium: "#D97706",
  low: ACCENT,
};

export function BillingSummary({
  billingReport,
  omitPriority = false,
}: {
  billingReport: BillingActionReport;
  /** The page summary already displays this same report's priority. */
  omitPriority?: boolean;
}) {
  const t = useT();
  const isBillScope = billingReport.scope === "bill" && Boolean(billingReport.claim_id);
  const reportExact = isExactOutput(billingReport);
  const reportHasTotals = hasRecoverableBillingTotals(billingReport);
  const copayExact = isExactOutput(billingReport.copay);
  const exemptionGapTotal = copayExemptionGapTotal(billingReport.copay);
  const showExemptionGap = copayExact && billingReport.copay.is_exempt && exemptionGapTotal > 0;
  const showIlaveInfo = copayExact && copayShowsIlaveColumn(billingReport.copay);
  const ilaveTotal = billingReport.copay.ilave_ucret_total_try ?? 0;
  const copayOnlyDecomposition =
    billingReport.copay.line_decomposition_status === "copay_only";
  const sgkUplift =
    billingReport.sgk_uplift_try ?? billingReport.total_recoverable_try ?? 0;
  const complianceAdjustment = billingReport.compliance_adjustment_try ?? 0;
  const auditExposure = billingReport.audit_exposure_try ?? 0;
  const captureGap = billingReport.capture_gap_try ?? 0;
  const packageAdequacyReview = billingReport.package_adequacy_review_try ?? 0;
  const medulaPlaybookCount = billingReport.medula_playbook_entry_count ?? 0;
  const drugIndicationCount = billingReport.drug_indication_violation_count ?? 0;
  const showCompliance = reportHasTotals && complianceAdjustment > 0;
  const showAuditExposure = reportHasTotals && auditExposure > 0;
  const showCaptureGap = reportHasTotals && captureGap > 0;
  const showPackageAdequacy = reportHasTotals && packageAdequacyReview > 0;
  const showMedulaPlaybook = reportHasTotals && medulaPlaybookCount > 0;
  const showDrugIndication = drugIndicationCount > 0;
  const extraSummaryStats = [
    showCompliance,
    showAuditExposure,
    showCaptureGap,
    showPackageAdequacy,
    showMedulaPlaybook,
    showDrugIndication,
    showIlaveInfo,
  ].filter(Boolean).length;
  const priorityColor = reportHasTotals ? PRIORITY_COLORS[billingReport.priority] : "#71717A";
  const statusLabel = reportExact
    ? fmtPriorityLabel(billingReport.priority)
    : reportHasTotals
      ? t("billing.summary.partialExact")
      : t("common.unavailable");

  return (
    <Surface variant="base" padding="lg" className="space-y-5 [&_.tabular-nums]:whitespace-nowrap">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Eyebrow>
            {isBillScope ? t("billing.summary.billTitle") : t("billing.summary.title")}
          </Eyebrow>
          <p className="mt-1 font-mono text-base text-[var(--text-secondary)]">
            {isBillScope ? billingReport.claim_id : billingReport.patient_id}
          </p>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
            {isBillScope ? t("billing.summary.billDescription") : t("billing.summary.description")}
          </p>
        </div>
        <Chip variant={chipVariantFromColor(priorityColor)}>{statusLabel}</Chip>
      </div>

      <div
        className={`grid gap-6 md:grid-cols-2 ${
          extraSummaryStats >= 2 ? "xl:grid-cols-6" : extraSummaryStats >= 1 ? "xl:grid-cols-5" : "xl:grid-cols-4"
        }`}
      >
        <Stat
          label={t("billing.summary.ruleCalculatedOpportunity")}
          value={reportHasTotals ? fmtTRY2(sgkUplift) : t("common.unavailable")}
        />
        {showCompliance && (
          <Stat
            label={t("billing.summary.complianceAdjustment")}
            value={fmtTRY2(complianceAdjustment)}
          />
        )}
        {showAuditExposure && (
          <Stat
            label={t("billing.summary.auditExposure")}
            value={fmtTRY2(auditExposure)}
          />
        )}
        {showCaptureGap && (
          <Stat
            label={t("billing.summary.captureGap")}
            value={fmtTRY2(captureGap)}
          />
        )}
        {showPackageAdequacy && (
          <Stat
            label={t("billing.summary.packageAdequacyReview")}
            value={fmtTRY2(packageAdequacyReview)}
          />
        )}
        {showMedulaPlaybook && (
          <Stat
            label={t("billing.summary.medulaPlaybook")}
            value={String(medulaPlaybookCount)}
          />
        )}
        {showDrugIndication && (
          <Stat
            label={t("billing.summary.drugIndicationReview")}
            value={String(drugIndicationCount)}
          />
        )}
        <Stat
          label={t("billing.summary.exemptionGapCorrective")}
          value={
            showExemptionGap
              ? fmtTRY2(exemptionGapTotal)
              : copayExact
                ? fmtTRY2(0)
                : t("common.unavailable")
          }
        />
        {showIlaveInfo && (
          <Stat
            label={t("billing.summary.ilaveUcretInfo")}
            value={fmtTRY2(ilaveTotal)}
          />
        )}
        <Stat
          label={t("billing.summary.recommendedActions")}
          value={reportHasTotals ? fmtNum(billingReport.action_count) : t("billing.summary.reviewSections")}
        />
        {!omitPriority && <Stat
          label={t("billing.summary.priorityTier")}
          value={
            <span style={{ color: priorityColor }}>
              {reportHasTotals ? fmtPriorityLabel(billingReport.priority) : t("common.unavailable")}
            </span>
          }
        />}
      </div>
      {showExemptionGap && reportHasTotals && (
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.summary.dualTotalsFootnote")}
        </p>
      )}
      {showIlaveInfo && reportHasTotals && (
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.copay.ilaveUcretFootnote")}
        </p>
      )}
      {copayOnlyDecomposition && copayExact && reportHasTotals && (
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.copay.partialDecompositionNotice")}
        </p>
      )}
      {!reportExact && reportHasTotals && (
        <ExactnessNotice
          block={billingReport}
          fallback={t("billing.summary.partialTotalsNotice")}
        />
      )}
      {!reportHasTotals && (
        <ExactnessNotice
          block={billingReport}
          fallback={t("billing.summary.totalsUnavailableNotice")}
        />
      )}
    </Surface>
  );
}
