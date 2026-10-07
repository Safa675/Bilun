"use client";

import type { BillingActionReport, RecommendedActionItem } from "@/lib/domains/sut";
import type { ReactNode } from "react";
import {
  BloodComponentUpliftSection,
  CareSettingReviewSection,
  CopayOptimizationSection,
  DrgPackageAdequacyReviewSection,
  DrgUpliftSection,
  MaterialUpliftSection,
  ProcedureAddonUpliftSection,
  ProcedureCaptureGapSection,
  RecommendedActionsPanel,
  SessionUpliftSection,
} from "@/components/patient/SutBillingReportSections";
import { fmtNum, fmtTRY2, KpiCard } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import { recoverableUplift, viewActions } from "@/lib/workspaceViews";
import { PatientWaveAEvidenceSection } from "@/components/patient/WaveAEvidenceSection";

const UPLIFT_COLOR = "var(--success)";

/**
 * View 2 — Gelir Optimizasyonu & Hak Kazanım (Revenue Recovery).
 *
 * Groups the surfaces `getFindingType` classifies as `opportunity`
 * (copay + all uplift/care-setting detectors) with their KPIs.
 */
export default function RevenueViewSection({
  billingReport,
  selectedActionId,
  onSelectAction,
  onOpenClause,
  selectedFindingId,
  selectedClaimId,
  detailsPrelude,
}: {
  billingReport: BillingActionReport;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  onOpenClause?: (sectionId: string) => void;
  selectedFindingId?: string | null;
  selectedClaimId?: string | null;
  detailsPrelude?: ReactNode;
}) {
  const t = useT();
  const viewActionsList = viewActions(billingReport, "revenue");
  const recoverable = recoverableUplift(billingReport);

  return (
    <div className="space-y-4">
      <p className="text-sm leading-snug text-[var(--text-secondary)]">
        {t("billing.views.revenue.description")}
      </p>

      <div className="grid gap-6 sm:grid-cols-2">
        <KpiCard
          label={t("billing.views.revenue.kpiRecoverable")}
          value={recoverable == null ? "—" : fmtTRY2(recoverable)}
          valueColor={UPLIFT_COLOR}
        />
        <KpiCard
          label={t("billing.views.revenue.kpiOpportunities")}
          value={fmtNum(viewActionsList.length)}
        />
      </div>

      {viewActionsList.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.views.noItems")}</p>
      ) : (
        <RecommendedActionsPanel
          billingReport={billingReport}
          findingFilter="opportunity"
          selectedActionId={selectedActionId}
          onSelectAction={onSelectAction}
          onOpenClause={onOpenClause}
        />
      )}

      {detailsPrelude}

      <PatientWaveAEvidenceSection
        patientId={billingReport.patient_id}
        kind="financial_rows"
        block={billingReport.financial_findings}
        onOpenClause={onOpenClause}
        selectedFindingId={selectedFindingId}
        selectedClaimId={selectedClaimId}
      />

      <CopayOptimizationSection copayData={billingReport.copay} onOpenClause={onOpenClause} />
      {billingReport.session_uplift && (
        <SessionUpliftSection sessionData={billingReport.session_uplift} />
      )}
      {billingReport.blood_uplift && (
        <BloodComponentUpliftSection bloodData={billingReport.blood_uplift} />
      )}
      {billingReport.material_uplift && (
        <MaterialUpliftSection materialData={billingReport.material_uplift} />
      )}
      {billingReport.procedure_addon_uplift && (
        <ProcedureAddonUpliftSection addonData={billingReport.procedure_addon_uplift} />
      )}
      {billingReport.procedure_capture_gap && (
        <ProcedureCaptureGapSection captureData={billingReport.procedure_capture_gap} />
      )}
      {billingReport.drg_package_adequacy && (
        <DrgPackageAdequacyReviewSection reviewData={billingReport.drg_package_adequacy} />
      )}
      {billingReport.drg_uplift && <DrgUpliftSection drgData={billingReport.drg_uplift} />}
      {billingReport.care_setting_review && (
        <CareSettingReviewSection reviewData={billingReport.care_setting_review} />
      )}
    </div>
  );
}
