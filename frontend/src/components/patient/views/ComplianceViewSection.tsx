"use client";

import type {
  BillingActionReport,
  ClaimComplianceCohortSummary,
  ComplianceIndexRow,
  RecommendedActionItem,
} from "@/lib/domains/sut";
import {
  BillingStrategySection,
  DrugIndicationReviewSection,
  LabOptimizationSection,
  MaterialsPreCheckSection,
  OptionalOverrideSection,
  RecommendedActionsPanel,
} from "@/components/patient/SutBillingReportSections";
import { fmtNum, fmtTRY2, KpiCard } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import { ComplianceFindingTable } from "@/components/tabs/sut/compliance/modules/ComplianceFindingTable";
import { complianceBilledAtRisk, scopedClaimComplianceFindings, viewActions } from "@/lib/workspaceViews";

const RISK_COLOR = "#B91C1C";

/**
 * View 1 — Mevzuat Uyumluluk & Red Önleme (Denial Prevention).
 *
 * Groups the surfaces `getFindingType` classifies as `compliance`
 * (lab, billing_strategy, materials, drug_indication) with their KPIs.
 */
export default function ComplianceViewSection({
  billingReport,
  selectedActionId,
  onSelectAction,
  onOpenClause,
  selectedFindingId,
}: {
  billingReport: BillingActionReport;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  onOpenClause?: (sectionId: string) => void;
  selectedFindingId?: string | null;
}) {
  const t = useT();
  const viewActionsList = viewActions(billingReport, "compliance");
  const billedAtRisk = complianceBilledAtRisk(billingReport);
  const auditExposure = billingReport.audit_exposure_try ?? 0;
  const projection = billingReport.claim_compliance;
  const inScope = (row: { patient_id: string; claim_id?: string | null }) =>
    row.patient_id === billingReport.patient_id &&
    (!billingReport.claim_id || row.claim_id === billingReport.claim_id || row.claim_id == null);
  const projectionRows: ComplianceIndexRow[] = scopedClaimComplianceFindings(billingReport).map((row) => ({
    ...row,
    surface: "claim_compliance" as const,
    source_surface: "claim_compliance",
  }));
  const evaluations = projection?.evaluations.filter(inScope) ?? [];
  const claimComplianceSummary: ClaimComplianceCohortSummary | null = projection
    ? (() => {
        const counts = evaluations.reduce(
          (acc, evaluation) => ({ ...acc, [evaluation.status]: acc[evaluation.status] + 1 }),
          { evaluated: 0, missing_inputs: 0, unavailable: 0 },
        );
        const nonEvaluated = evaluations.filter((evaluation) => evaluation.status !== "evaluated");
        return {
          counts,
          non_evaluated_total: nonEvaluated.length,
          details: nonEvaluated.slice(0, 20),
          details_truncated: nonEvaluated.length > 20,
        };
      })()
    : null;

  return (
    <div className="space-y-4">
      <p className="text-sm leading-snug text-[var(--text-secondary)]">
        {t("billing.views.compliance.description")}
      </p>

      <div className="grid gap-6 sm:grid-cols-3">
        <KpiCard
          label={t("billing.views.compliance.kpiRisk")}
          value={fmtTRY2(auditExposure)}
          valueColor={RISK_COLOR}
        />
        <KpiCard
          label={t("billing.views.compliance.kpiFindings")}
          value={fmtNum(viewActionsList.length + projectionRows.length)}
        />
        <KpiCard
          label={t("billing.views.compliance.kpiBilledAtRisk")}
          value={fmtTRY2(billedAtRisk)}
        />
      </div>

      {viewActionsList.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.views.noItems")}</p>
      ) : (
        <RecommendedActionsPanel
          billingReport={billingReport}
          findingFilter="compliance"
          selectedActionId={selectedActionId}
          onSelectAction={onSelectAction}
          onOpenClause={onOpenClause}
        />
      )}

      <section id="claim-compliance" className="space-y-3 scroll-mt-24">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t("optimizer.tabs.claim_compliance")}</h3>
        <ComplianceFindingTable
          rows={projectionRows}
          claimComplianceSummary={claimComplianceSummary}
          loading={false}
          unavailable={!projection}
          claimCompliance
          selectedFindingId={selectedFindingId}
        />
      </section>

      <LabOptimizationSection labData={billingReport.lab} />
      <BillingStrategySection strategyData={billingReport.billing_strategy} />
      <OptionalOverrideSection strategyData={billingReport.billing_strategy} />
      <MaterialsPreCheckSection materialsData={billingReport.materials} />
      {billingReport.drug_indication && (
        <DrugIndicationReviewSection reviewData={billingReport.drug_indication} />
      )}
    </div>
  );
}
