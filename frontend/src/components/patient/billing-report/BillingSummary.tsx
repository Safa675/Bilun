"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import type { ReactNode } from "react";
import { useT } from "@/lib/i18n/useTranslations";
import { hasRecoverableBillingTotals, isExactOutput } from "@/lib/sutExactness";
import { copayExemptionGapTotal, copayShowsIlaveColumn } from "@/lib/billingReportFields";
import { Chip, ExactnessBlock as ExactnessNotice, Eyebrow, Surface } from "@/components/primitives";
import { fmtNum, fmtPriorityLabel, fmtTRY2 } from "@/components/tabs/sut/shared";
import { ACCENT, chipVariantFromColor } from "./shared";

const PRIORITY_COLORS: Record<BillingActionReport["priority"], string> = {
  high: "#B91C1C",
  medium: "#D97706",
  low: ACCENT,
};

function SummaryMetric({ name, label, value }: { name: string; label: string; value: ReactNode }) {
  return (
    <div data-billing-metric={name} className="min-w-0 basis-full space-y-1 @min-[400px]/billing-summary:min-w-min @min-[400px]/billing-summary:flex-1 @min-[400px]/billing-summary:basis-[calc(50%-0.75rem)]">
      <dt className="text-[0.68rem] font-semibold uppercase tracking-normal text-[var(--text-muted)]">{label}</dt>
      <dd className="min-w-0 font-sans text-2xl leading-none font-semibold tracking-normal tabular-nums lining-nums text-[var(--text-primary)]">{value}</dd>
    </div>
  );
}

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
  const showExemptionGap = copayExact && billingReport.copay.is_exempt && exemptionGapTotal != null && exemptionGapTotal > 0;
  const showIlaveInfo = copayExact && copayShowsIlaveColumn(billingReport.copay);
  const ilaveTotal = billingReport.copay.ilave_ucret_total_try ?? null;
  const copayOnlyDecomposition =
    billingReport.copay.line_decomposition_status === "copay_only";
  const sgkUplift =
    billingReport.sgk_uplift_try ?? billingReport.total_recoverable_try ?? null;
  const complianceAdjustment = billingReport.compliance_adjustment_try;
  const auditExposure = billingReport.audit_exposure_try;
  const captureGap = billingReport.capture_gap_try;
  const packageAdequacyReview = billingReport.package_adequacy_review_try;
  const medulaPlaybookCount = billingReport.medula_playbook_entry_count ?? 0;
  const drugIndicationCount = billingReport.drug_indication_violation_count ?? 0;
  const showCompliance = reportHasTotals && complianceAdjustment != null && complianceAdjustment > 0;
  const showAuditExposure = reportHasTotals && auditExposure != null && auditExposure > 0;
  const showCaptureGap = reportHasTotals && captureGap != null && captureGap > 0;
  const showPackageAdequacy = reportHasTotals && packageAdequacyReview != null && packageAdequacyReview > 0;
  const showMedulaPlaybook = reportHasTotals && medulaPlaybookCount > 0;
  const showDrugIndication = drugIndicationCount > 0;
  const priorityColor = reportHasTotals ? PRIORITY_COLORS[billingReport.priority] : "#71717A";
  const statusLabel = reportExact
    ? fmtPriorityLabel(billingReport.priority)
    : reportHasTotals
      ? t("billing.summary.partialExact")
      : t("common.unavailable");

  return (
    <Surface
      variant="base"
      padding="lg"
      className="@container/billing-summary space-y-5 max-sm:p-3 [&_.tabular-nums]:whitespace-nowrap [&_.tabular-nums]:text-xs @min-[180px]:[&_.tabular-nums]:text-sm @min-[220px]:[&_.tabular-nums]:text-2xl"
      data-billing-summary
    >
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

      <dl className="flex flex-wrap gap-x-6 gap-y-3">
        <SummaryMetric
          name="sgk-uplift"
          label={t("billing.summary.ruleCalculatedOpportunity")}
          value={reportHasTotals ? sgkUplift == null ? "—" : fmtTRY2(sgkUplift) : t("common.unavailable")}
        />
        {showCompliance && (
          <SummaryMetric
            name="compliance-adjustment"
            label={t("billing.summary.complianceAdjustment")}
            value={fmtTRY2(complianceAdjustment)}
          />
        )}
        {showAuditExposure && (
          <SummaryMetric
            name="audit-exposure"
            label={t("billing.summary.auditExposure")}
            value={fmtTRY2(auditExposure)}
          />
        )}
        {showCaptureGap && (
          <SummaryMetric
            name="capture-gap"
            label={t("billing.summary.captureGap")}
            value={fmtTRY2(captureGap)}
          />
        )}
        {showPackageAdequacy && (
          <SummaryMetric
            name="package-adequacy"
            label={t("billing.summary.packageAdequacyReview")}
            value={fmtTRY2(packageAdequacyReview)}
          />
        )}
        {showMedulaPlaybook && (
          <SummaryMetric
            name="medula-playbook"
            label={t("billing.summary.medulaPlaybook")}
            value={String(medulaPlaybookCount)}
          />
        )}
        {showDrugIndication && (
          <SummaryMetric
            name="drug-indication"
            label={t("billing.summary.drugIndicationReview")}
            value={String(drugIndicationCount)}
          />
        )}
        <SummaryMetric
          name="exemption-gap"
          label={t("billing.summary.exemptionGapCorrective")}
          value={
            showExemptionGap
              ? fmtTRY2(exemptionGapTotal)
              : copayExact
                ? exemptionGapTotal == null ? "—" : fmtTRY2(exemptionGapTotal)
                : t("common.unavailable")
          }
        />
        {showIlaveInfo && (
          <SummaryMetric
            name="ilave-ucret"
            label={t("billing.summary.ilaveUcretInfo")}
            value={ilaveTotal == null ? "—" : fmtTRY2(ilaveTotal)}
          />
        )}
        <SummaryMetric
          name="recommended-actions"
          label={t("billing.summary.recommendedActions")}
          value={reportHasTotals ? fmtNum(billingReport.action_count) : t("billing.summary.reviewSections")}
        />
        {!omitPriority && <SummaryMetric
          name="priority"
          label={t("billing.summary.priorityTier")}
          value={
            <span style={{ color: priorityColor }}>
              {reportHasTotals ? fmtPriorityLabel(billingReport.priority) : t("common.unavailable")}
            </span>
          }
        />}
      </dl>
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
