"use client";

import type {
  BillingActionReport,
  RecommendedActionItem,
} from "@/lib/domains/sut";
import {
  BillingStrategySection,
  DrugIndicationReviewSection,
  LabOptimizationSection,
  MaterialsPreCheckSection,
  OptionalOverrideSection,
} from "@/components/patient/SutBillingReportSections";
import { fmtNum, fmtTRY2, KpiCard } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import { complianceBilledAtRisk } from "@/lib/workspaceViews";
import {
  buildUnifiedComplianceFindings,
  type UnifiedComplianceFindingRow,
} from "@/lib/complianceFindings";
import { buildComplianceCoverage } from "@/lib/complianceCoverage";
import UnifiedComplianceFindingsTable from "@/components/patient/UnifiedComplianceFindingsTable";
import { PatientWaveAEvidenceSection, WaveACoverageSummary } from "@/components/patient/WaveAEvidenceSection";

const RISK_COLOR = "#B91C1C";

function ruleLabel(t: ReturnType<typeof useT>, ruleId: string | null | undefined): string {
  if (!ruleId) return "—";
  const key = `optimizer.claimCompliance.${ruleId}`;
  const translated = t(key);
  return translated === key ? ruleId : translated;
}

function evaluationLabel(
  t: ReturnType<typeof useT>,
  status: string | null | undefined,
): string | null {
  if (!status) return null;
  const key = `optimizer.claimCompliance.${status}`;
  const translated = t(key);
  return translated === key ? status : translated;
}

/**
 * View 1 — Mevzuat Uyumluluk & Red Önleme (Denial Prevention).
 *
 * Displays a single unified compliance findings table combining compliance
 * recommended actions and canonical claim compliance findings, with compact
 * structural coverage summary below.
 */
export default function ComplianceViewSection({
  billingReport,
  patientId,
  unifiedRows,
  selectedActionId,
  onSelectAction,
  onOpenClause,
  selectedFindingId,
  selectedClaimId,
}: {
  billingReport: BillingActionReport;
  patientId?: string;
  unifiedRows?: UnifiedComplianceFindingRow[];
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  onOpenClause?: (sectionId: string) => void;
  selectedFindingId?: string | null;
  selectedClaimId?: string | null;
}) {
  const t = useT();
  const rows = unifiedRows ?? buildUnifiedComplianceFindings(billingReport, t);
  const billedAtRisk = complianceBilledAtRisk(billingReport);
  const auditExposure = billingReport.audit_exposure_try ?? 0;
  const effectivePatientId = patientId || billingReport.patient_id;
  const coverage = buildComplianceCoverage(billingReport, t);

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
          value={fmtNum(rows.length)}
        />
        <KpiCard
          label={t("billing.views.compliance.kpiBilledAtRisk")}
          value={fmtTRY2(billedAtRisk)}
        />
      </div>

      <section id="claim-compliance" className="space-y-3 scroll-mt-24">
        <UnifiedComplianceFindingsTable
          rows={rows}
          patientId={effectivePatientId}
          selectedActionId={selectedActionId}
          onSelectAction={onSelectAction}
          onOpenClause={onOpenClause}
          selectedFindingId={selectedFindingId}
        />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          {t("optimizer.tabs.claim_compliance")}
        </h3>
        {!coverage ? (
          <p className="text-sm text-[var(--text-muted)]">
            {t("optimizer.claimCompliance.unavailable")}
          </p>
        ) : (
          <div className="space-y-2 text-xs text-[var(--text-secondary)]">
            <p className="tabular-nums">
              {coverage.summaryText}
              {" · "}
              <span className="text-[var(--text-muted)]">
                {t("billing.views.compliance.coverageNotice")}
              </span>
            </p>
            {coverage.nonEvaluatedTotal > 0 && (
              <details className="text-xs text-[var(--text-secondary)]">
                <summary className="cursor-pointer font-medium hover:text-[var(--text-primary)]">
                  {t("optimizer.claimCompliance.evaluationDetails", {
                    count: coverage.details.length,
                    total: coverage.nonEvaluatedTotal,
                  })}
                </summary>
                <ul className="mt-2 space-y-1 pl-3 border-l border-[var(--border-subtle)]">
                  {coverage.details.map((evaluation) => (
                    <li
                      key={`${evaluation.patient_id}:${evaluation.claim_id}:${evaluation.rule_id}`}
                    >
                      <span className="font-mono">{evaluation.claim_id || "—"}</span>
                      {" · "}
                      <span>{ruleLabel(t, evaluation.rule_id)}</span>:{" "}
                      <span>
                        {evaluationLabel(
                          t,
                          evaluation.evaluation_status ?? evaluation.status,
                        )}
                      </span>
                      {evaluation.missing_inputs.length > 0
                        ? ` (${evaluation.missing_inputs.join(", ")})`
                        : ""}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </section>

      <PatientWaveAEvidenceSection
        patientId={effectivePatientId}
        kind="reviews"
        block={billingReport.claim_reviews}
        onOpenClause={onOpenClause}
        selectedFindingId={selectedFindingId}
        selectedClaimId={selectedClaimId}
      />

      <PatientWaveAEvidenceSection
        patientId={effectivePatientId}
        kind="advisories"
        block={billingReport.claim_advisories}
        onOpenClause={onOpenClause}
        selectedFindingId={selectedFindingId}
        selectedClaimId={selectedClaimId}
      />

      <WaveACoverageSummary coverage={billingReport.wavea_coverage} />

      <LabOptimizationSection labData={billingReport.lab} />
      <BillingStrategySection strategyData={billingReport.billing_strategy} />
      <OptionalOverrideSection strategyData={billingReport.billing_strategy} />
      <MaterialsPreCheckSection materialsData={billingReport.materials} />
      {billingReport.drug_indication && (
        <DrugIndicationReviewSection
          reviewData={billingReport.drug_indication}
          selectedFindingId={selectedFindingId}
        />
      )}
    </div>
  );
}
