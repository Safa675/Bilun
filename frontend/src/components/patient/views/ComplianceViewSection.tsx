"use client";

import type {
  BillingActionReport,
  RecommendedActionItem,
} from "@/lib/domains/sut";
import type { ReactNode } from "react";
import {
  BillingStrategySection,
  DrugIndicationReviewSection,
  LabOptimizationSection,
  MaterialsPreCheckSection,
  OptionalOverrideSection,
} from "@/components/patient/SutBillingReportSections";
import { fmtNum, fmtTRY2 } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import { complianceBilledAtRiskSummary } from "@/lib/workspaceViews";
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
  selectedSection,
  detailsPrelude,
}: {
  billingReport: BillingActionReport;
  patientId?: string;
  unifiedRows?: UnifiedComplianceFindingRow[];
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  onOpenClause?: (sectionId: string) => void;
  selectedFindingId?: string | null;
  selectedClaimId?: string | null;
  selectedSection?: string | null;
  detailsPrelude?: ReactNode;
}) {
  const t = useT();
  const rows = unifiedRows ?? buildUnifiedComplianceFindings(billingReport, t);
  // A missing billed amount is unknown, never zero: show the sum only when every
  // counted action has one; otherwise a dash (none) or a labelled partial sum.
  const billed = complianceBilledAtRiskSummary(billingReport);
  const billedComplete = billed.known === billed.count;
  const billedNone = billed.known === 0;
  const auditExposure = billingReport.audit_exposure_try ?? null;
  const effectivePatientId = patientId || billingReport.patient_id;
  const coverage = buildComplianceCoverage(billingReport, t);

  return (
    <div className="space-y-4">
      <p className="text-sm leading-snug text-[var(--text-secondary)]">
        {t("billing.views.compliance.description")}
      </p>

      <dl data-compliance-metrics className="@container space-y-3">
        <div data-compliance-metric="risk" className="grid min-w-0 grid-cols-1 items-start gap-x-6 gap-y-1 @min-[480px]:grid-cols-[minmax(0,1fr)_auto] @min-[480px]:items-center">
          <dt className="text-xs font-medium text-[var(--text-muted)]">{t("billing.views.compliance.kpiRisk")}</dt>
          <dd className="min-w-0 whitespace-nowrap text-2xl font-semibold tabular-nums lining-nums leading-tight" style={{ color: RISK_COLOR }}>
            {auditExposure == null ? "—" : fmtTRY2(auditExposure)}
          </dd>
        </div>
        <div data-compliance-metric="findings" className="grid min-w-0 grid-cols-1 items-start gap-x-6 gap-y-1 @min-[480px]:grid-cols-[minmax(0,1fr)_auto] @min-[480px]:items-center">
          <dt className="text-xs font-medium text-[var(--text-muted)]">{t("billing.views.compliance.kpiFindings")}</dt>
          <dd className="min-w-0 whitespace-nowrap text-2xl font-semibold tabular-nums lining-nums leading-tight text-[var(--text-primary)]">{fmtNum(rows.length)}</dd>
        </div>
        <div data-compliance-metric="billed-at-risk" className="grid min-w-0 grid-cols-1 items-start gap-x-6 gap-y-1 @min-[480px]:grid-cols-[minmax(0,1fr)_auto] @min-[480px]:items-center">
          <dt className="text-xs font-medium text-[var(--text-muted)]">{t("billing.views.compliance.kpiBilledAtRisk")}</dt>
          <dd className="min-w-0 whitespace-nowrap text-2xl font-semibold tabular-nums lining-nums leading-tight text-[var(--text-primary)]">{billedNone ? "—" : fmtTRY2(billed.total)}</dd>
          {!billedComplete && (
            <dd className="text-xs leading-snug text-[var(--text-secondary)] @min-[480px]:col-span-2">
              {billedNone
                ? t("billing.views.compliance.kpiBilledAtRiskNone", {
                    count: billed.count,
                  })
                : t("billing.views.compliance.kpiBilledAtRiskPartial", {
                    known: billed.known,
                    count: billed.count,
                  })}
            </dd>
          )}
        </div>
      </dl>

      <section id="claim-compliance" className="space-y-3 scroll-mt-24">
        <UnifiedComplianceFindingsTable
          rows={rows}
          patientId={effectivePatientId}
          selectedActionId={selectedActionId}
          onSelectAction={onSelectAction}
          onOpenClause={onOpenClause}
          selectedFindingId={selectedFindingId}
        />
      </section>

      {detailsPrelude}

      <details id="claim-coverage" open={selectedSection === "claim-coverage" || undefined} className="scroll-mt-24 rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-3">
        <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">
          {t("billing.wavea.coverageDetails")} · {coverage
            ? t("billing.wavea.missingDataCount", { count: coverage.nonEvaluatedTotal })
            : t("billing.wavea.countUnavailable")}
          <span className="mt-1 block text-xs font-normal tabular-nums text-[var(--text-secondary)]">
            {coverage ? coverage.summaryText : t("optimizer.claimCompliance.unavailable")}
          </span>
        </summary>
        {!coverage ? (
          <p className="text-sm text-[var(--text-muted)]">
            {t("optimizer.claimCompliance.unavailable")}
          </p>
        ) : (
          <div className="space-y-2 text-xs text-[var(--text-secondary)]">
            <p className="mt-2">
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
      </details>

      <PatientWaveAEvidenceSection
        patientId={effectivePatientId}
        kind="reviews"
        block={billingReport.claim_reviews}
        onOpenClause={onOpenClause}
        selectedFindingId={selectedFindingId}
        selectedClaimId={selectedClaimId}
        selectedSection={selectedSection}
      />

      <PatientWaveAEvidenceSection
        patientId={effectivePatientId}
        kind="advisories"
        block={billingReport.claim_advisories}
        onOpenClause={onOpenClause}
        selectedFindingId={selectedFindingId}
        selectedClaimId={selectedClaimId}
        selectedSection={selectedSection}
      />

      <WaveACoverageSummary coverage={billingReport.wavea_coverage} selectedSection={selectedSection} />

      <LabOptimizationSection labData={billingReport.lab} />
      <BillingStrategySection strategyData={billingReport.billing_strategy} collapsed />
      <OptionalOverrideSection strategyData={billingReport.billing_strategy} collapsed />
      <MaterialsPreCheckSection materialsData={billingReport.materials} collapsed />
      {billingReport.drug_indication && (
        <DrugIndicationReviewSection
          reviewData={billingReport.drug_indication}
          selectedFindingId={selectedFindingId}
          selectedSection={selectedSection}
        />
      )}
    </div>
  );
}
