"use client";

import { useState, type ReactNode } from "react";
import type { BillingActionReport, ClaimSubmissionChecklist, PatientOptimization } from "@/lib/domains/sut";
import { getSutAlertBadgeLabel, getSutSeverityLabel, getPaymentMethodKindLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import { fmtDate } from "@/lib/i18n/formatters";
import { translateApiText, translateStructuredApiMessage } from "@/lib/apiMessages";
import {
  hasRecoverableBillingTotals,
  isExactOutput,
  isOptionalIngestPending,
} from "@/lib/sutExactness";
import {
  copayClaimScopedAnnexLabels,
  copayCorrectionBilledTry,
  copayCorrectionGroundKey,
  copayCorrectionPayableTry,
  copayCorrectionProcedureLabel,
  copayCorrectionSavingsTry,
  copayCorrectedPayableTry,
  resolveCopayIlaveStatus,
  copayExemptionGapTotal,
  copayShowsIlaveColumn,
  formatSutSectionLabel,
  isClaimLevelStrategyRow,
  isComplianceViolationRow,
  mergeClaimStrategyTableRows,
  strategyBadgeColor,
  strategyItemizedTotalTry,
  strategyModeLabel,
  strategyPackageTotalTry,
  strategyPaymentMethodKindMessageKey,
  strategyPrimaryLabel,
  strategyRecommendationKindMessageKey,
  strategyCatalogAsOfFootnote,
  strategyRowStatus,
  strategyRowStatusChipVariant,
  strategyRowStatusMessageKey,
  strategySavingsHeaderKey,
  strategySavingsTryDisplay,
  strategySecondaryLabel,
  usesClaimCopayCorrectionShape,
  usesHeuristicStrategyReviewShape,
  usesInsightOnlyCopayCorrectionShape,
} from "@/lib/billingReportFields";
import {
  findingTypeChipVariant,
  findingTypeLabelKey,
  getFindingType,
  getRecommendedActions,
  recommendedActionSectionId,
  recommendedActionAmountParts,
  recommendedActionSurfaceLabel,
  recommendedActionTitle,
  type RecommendedActionItem,
} from "@/lib/recommendedActions";
import { theme } from "@/lib/theme";
import { cn } from "@/lib/cn";
import { ExemptionBasisChips } from "@/components/sut/ExemptionBasisChips";
import { EkAnnexChips, RuleSourceAttribution } from "@/components/sut/RegulatorySourceChips";
import { SutClauseDrawer } from "@/components/sut/SutClauseDrawer";
import { resolveBillingEkAnnexLabels } from "@/lib/sutRegulatorySources";
import { MaterialBundlingScopeNotice } from "@/components/sut/MaterialBundlingScopeNotice";
import { SpecialtyProseScopeNotice } from "@/components/sut/SpecialtyProseScopeNotice";
import { Chip, DataTable, ExactnessBlock as ExactnessNotice, Eyebrow, Section, Stat, Surface } from "@/components/primitives";
import { getExemptionCategories } from "@/lib/copayExemption";
import {
  fmtLabel,
  fmtNum,
  fmtPriorityLabel,
  fmtRiskLabel,
  fmtTRY2,
  fmtTRY2OrUnavailable,
  KpiCard,
} from "@/components/tabs/sut/shared";

const ACCENT = theme.accent;
const PRIORITY_COLORS: Record<BillingActionReport["priority"], string> = {
  high: "#B91C1C",
  medium: "#D97706",
  low: ACCENT,
};

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

function BillingRegulatorySourceCell({
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

export function RecommendedActionsPanel({
  billingReport,
  selectedActionId,
  onSelectAction,
}: {
  billingReport: BillingActionReport;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
}) {
  const t = useT();
  const actions = getRecommendedActions(billingReport);

  if (actions.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 border-t border-[var(--border-subtle)] pt-5">
      <Eyebrow>{t("billing.recommendedActions.listTitle")}</Eyebrow>
      <TableWrap minWidth={920}>
        <thead>
          <tr>
            <th>{t("billing.recommendedActions.surface")}</th>
            <th>{t("billing.summary.recommendedActions")}</th>
            {!billingReport.scope && (
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.recommendedActions.claim")}</th>
            )}
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.recommendedActions.section")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.recommendedActions.amountBilledOrUplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.recommendedActions.detail")}</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((action) => {
            const amount = recommendedActionAmountParts(t, action);
            const sectionId = recommendedActionSectionId(action.surface);
            const isActive = action.action_id === selectedActionId;
            const findingType = getFindingType(action);
            // Selection drives invoice-line highlighting (independent of scroll),
            // so every row is clickable; scroll is a bonus when an anchor exists.
            const handleSelect = () => {
              onSelectAction?.(action);
              if (sectionId) {
                document.getElementById(sectionId)?.scrollIntoView({
                  behavior: "smooth",
                  block: "start",
                });
              }
            };
            return (
              <tr
                key={action.action_id}
                className={cn(
                  "cursor-pointer",
                  isActive && "bg-[var(--gold-subtle)]",
                )}
                onClick={handleSelect}
                onKeyDown={
                  (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      handleSelect();
                    }
                  }
                }
                tabIndex={0}
              >
                <td>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Chip variant="neutral">
                      {recommendedActionSurfaceLabel(t, action.surface)}
                    </Chip>
                    <Chip variant={findingTypeChipVariant(findingType)}>
                      {t(findingTypeLabelKey(findingType))}
                    </Chip>
                  </div>
                </td>
                <td className="font-medium text-[var(--text-primary)]">
                  {recommendedActionTitle(t, action)}
                </td>
                {!billingReport.scope && (
                  <td className="font-mono text-xs text-[var(--text-secondary)]">
                    {action.claim_id ?? "—"}
                  </td>
                )}
                <td className="text-sm text-[var(--text-secondary)]">
                  {action.sut_section_id ? formatSutSectionLabel(action.sut_section_id) : "—"}
                </td>
                <td className="num-col tabular-nums text-right text-sm text-[var(--text-primary)]">
                  {amount ? (
                    <span>
                      {amount.value != null ? fmtTRY2(amount.value) : amount.label}
                      {amount.value != null ? (
                        <span className="block text-xs text-[var(--text-secondary)]">
                          {amount.label}
                        </span>
                      ) : null}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="text-sm text-[var(--text-secondary)]">
                  {action.detail || action.message_code
                    ? translateStructuredApiMessage(t, action)
                    : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </TableWrap>
    </div>
  );
}

export function BillingSummary({
  billingReport,
  selectedActionId,
  onSelectAction,
}: {
  billingReport: BillingActionReport;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
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
  const gazetteRepricing = billingReport.gazette_repricing_try ?? 0;
  const medulaPlaybookCount = billingReport.medula_playbook_entry_count ?? 0;
  const drugIndicationCount = billingReport.drug_indication_violation_count ?? 0;
  const showCompliance = reportHasTotals && complianceAdjustment > 0;
  const showAuditExposure = reportHasTotals && auditExposure > 0;
  const showCaptureGap = reportHasTotals && captureGap > 0;
  const showPackageAdequacy = reportHasTotals && packageAdequacyReview > 0;
  const showGazetteRepricing = reportHasTotals && gazetteRepricing > 0;
  const showMedulaPlaybook = reportHasTotals && medulaPlaybookCount > 0;
  const showDrugIndication = drugIndicationCount > 0;
  const extraSummaryStats = [
    showCompliance,
    showAuditExposure,
    showCaptureGap,
    showPackageAdequacy,
    showGazetteRepricing,
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
    <Surface variant="base" padding="lg" className="space-y-5">
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
        {showGazetteRepricing && (
          <Stat
            label={t("billing.summary.gazetteRepricing")}
            value={fmtTRY2(gazetteRepricing)}
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
        <Stat
          label={t("billing.summary.priorityTier")}
          value={
            <span style={{ color: priorityColor }}>
              {reportHasTotals ? fmtPriorityLabel(billingReport.priority) : t("common.unavailable")}
            </span>
          }
        />
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
      <RecommendedActionsPanel
        billingReport={billingReport}
        selectedActionId={selectedActionId}
        onSelectAction={onSelectAction}
      />
    </Surface>
  );
}

export function LabOptimizationSection({ labData }: { labData: BillingActionReport["lab"] }) {
  const t = useT();
  if (!isExactOutput(labData)) {
    return (
      <BillingSectionShell id="billing-lab" title={t("billing.lab.title")}>
        <ExactnessNotice block={labData} fallback={t("billing.lab.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (labData.flagged_tests.length === 0) {
    return null;
  }

  const combinedSavings =
    labData.hemogram_bundling_savings + (labData.session_fraction_savings ?? 0);

  return (
    <BillingSectionShell id="billing-lab" title={t("billing.lab.title")} total={fmtTRY2(combinedSavings)}>
      <TableWrap minWidth={820}>
        <thead>
          <tr>
            <th>{t("billing.lab.test")}</th>
            <th>{t("billing.lab.sutCode")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.lab.gazettePrice")}</th>
            <th>{t("billing.lab.flag")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.lab.savings")}</th>
          </tr>
        </thead>
        <tbody>
          {labData.flagged_tests.map((test, index) => (
            <tr key={`${test.sut_code}-${index}`}>
              <td>{test.test_name}</td>
              <td className="font-mono text-xs">{test.sut_code}</td>
              <td className="num-col tabular-nums text-right">{fmtTRY2(test.gazette_price)}</td>
              <td>
                <Chip
                  variant={chipVariantFromColor(
                    test.flag_type === "hemogram_unbundling"
                      ? "#D97706"
                      : test.flag_type === "session_fraction_overbilling"
                        ? "#B45309"
                        : "#B91C1C",
                  )}
                >
                  {fmtLabel(test.flag_type)}
                </Chip>
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(test.savings_try ?? null)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function CopayOptimizationSection({ copayData }: { copayData: BillingActionReport["copay"] }) {
  const t = useT();
  const [clauseDrawerKey, setClauseDrawerKey] = useState<string | null>(null);
  const copayExact = isExactOutput(copayData);
  const hasInsight =
    copayData.is_exempt ||
    copayData.rate_corrections.some(
      (correction) =>
        usesClaimCopayCorrectionShape(correction) ||
        usesInsightOnlyCopayCorrectionShape(correction),
    );

  if (!copayExact && !hasInsight) {
    return (
      <BillingSectionShell title={t("billing.copay.title")}>
        <ExactnessNotice block={copayData} fallback={t("billing.copay.unavailable")} />
      </BillingSectionShell>
    );
  }

  const exemptionGapTotal = copayExemptionGapTotal(copayData);
  const savingsColor = exemptionGapTotal > 0 ? ACCENT : "#71717A";
  const showIlaveColumn = copayShowsIlaveColumn(copayData);
  const ilaveTotal = copayData.ilave_ucret_total_try ?? 0;
  const copayOnlyDecomposition = copayData.line_decomposition_status === "copay_only";
  const insightOnlyRows = copayData.rate_corrections.filter((correction) =>
    usesInsightOnlyCopayCorrectionShape(correction),
  );
  const claimRows = copayData.rate_corrections.filter(
    (correction) => !usesInsightOnlyCopayCorrectionShape(correction),
  );
  const claimScopedChips = copayClaimScopedAnnexLabels(copayData);
  const hasWaiverGroundColumn = claimRows.some((row) => Boolean(copayCorrectionGroundKey(row)));
  const inpatientDrugGroundTotal =
    copayData.rx_copay_savings_by_ground?.inpatient_drug_1_8_5_8 ?? 0;
  const hasEk1aVisitSavings = copayData.rate_corrections.some(
    (row) =>
      row.exemption_ground === "ek1a_muayene" && (row.copay_component_try ?? 0) > 0,
  );

  const waiverGroundLabel = (ground: string | null) => {
    if (!ground) {
      return "—";
    }
    const key = `billing.copay.groundLabels.${ground}` as
      | "billing.copay.groundLabels.ek1a_muayene"
      | "billing.copay.groundLabels.inpatient_drug_1_8_5_8"
      | "billing.copay.groundLabels.ek4d_drug"
      | "billing.copay.groundLabels.ek4d_partial"
      | "billing.copay.groundLabels.composite_acil_servis"
      | "billing.copay.groundLabels.composite_koruyucu_saglik"
      | "billing.copay.groundLabels.composite_is_kazasi_meslek";
    const translated = t(key);
    return translated === key ? ground : translated;
  };

  return (
    <BillingSectionShell
      id="billing-copay"
      title={t("billing.copay.title")}
      total={copayExact ? fmtTRY2(exemptionGapTotal) : undefined}
    >
      <div className="space-y-4">
        {!copayExact && (
          <ExactnessNotice block={copayData} fallback={t("billing.copay.unavailable")} />
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Chip variant={chipVariantFromColor(copayData.is_exempt ? ACCENT : "#A1A1AA")}>
            {copayData.is_exempt ? getSutAlertBadgeLabel("exempt") : getSutAlertBadgeLabel("notExempt")}
          </Chip>
          {copayData.is_exempt && (
            <Chip variant="outline">{t("billing.copay.medulaActionChip")}</Chip>
          )}
          {copayData.exemption_disease && (
            <span className="text-sm" style={{ color: "#71717A" }}>
              {copayData.exemption_disease} ({copayData.exemption_range})
            </span>
          )}
          {copayData.exemption_sources && copayData.exemption_sources.length > 0 && (
            <ExemptionBasisChips
              copay={{
                exempt: copayData.is_exempt,
                n_qualifying: 0,
                qualifying_diagnoses: [],
                exemption_sources: copayData.exemption_sources,
                primary_exemption_category: copayData.primary_exemption_category,
              }}
              max={3}
            />
          )}
          {claimScopedChips.length > 0 ? (
            <EkAnnexChips labels={claimScopedChips} />
          ) : (
            <RuleSourceAttribution ruleSource={copayData.rule_source} />
          )}
        </div>

        {copayData.is_exempt && (
          <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
            {t("billing.copay.patientVsClaimExemptionNotice")}
          </p>
        )}

        {copayExact && (
          <>
            <div className={`grid gap-3 ${showIlaveColumn ? "md:grid-cols-4" : "md:grid-cols-3"}`}>
              <KpiCard label={t("billing.copay.visitSavings")} value={fmtTRY2(copayData.visit_copay_savings_try)} valueColor={savingsColor} />
              <KpiCard label={t("billing.copay.rxSavings")} value={fmtTRY2(copayData.rx_copay_savings_try)} valueColor={savingsColor} />
              <KpiCard label={t("billing.copay.totalSavings")} value={fmtTRY2(exemptionGapTotal)} valueColor={savingsColor} />
              {showIlaveColumn && (
                <KpiCard
                  label={t("billing.copay.ilaveUcretTotal")}
                  value={fmtTRY2(ilaveTotal)}
                  valueColor="#71717A"
                />
              )}
            </div>
            <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
              {t("billing.copay.exemptionGapFootnote")}
            </p>
            {showIlaveColumn && (
              <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                {t("billing.copay.ilaveUcretFootnote")}
              </p>
            )}
            {copayOnlyDecomposition && (
              <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                {t("billing.copay.partialDecompositionNotice")}
              </p>
            )}
            {hasEk1aVisitSavings && (
              <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                {t("billing.copay.ek1aScopeNotice")}
              </p>
            )}
            {inpatientDrugGroundTotal > 0 && (
              <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                {t("billing.copay.inpatientDrugWaiverNotice")}
              </p>
            )}
          </>
        )}

        {insightOnlyRows.length > 0 && (
          <div className="space-y-2">
            {insightOnlyRows.map((correction, index) => (
              <p key={`insight-${index}`} className="text-sm leading-relaxed text-[var(--text-secondary)]">
                {translateStructuredApiMessage(t, correction)}
              </p>
            ))}
          </div>
        )}

        {claimRows.length > 0 && (
          <>
          {copayExact && (
            <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
              {t("billing.copay.tableIntro")}
            </p>
          )}
          {copayData.is_exempt && (
            <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] p-3 text-xs leading-relaxed text-[var(--text-secondary)]">
              <span className="font-semibold text-[var(--text-primary)]">ℹ️ {t("billing.copay.cashierRefundNotice")}</span>
            </div>
          )}
          <TableWrap minWidth={840}>
            <thead>
              <tr>
                <th>{t("billing.copay.procedure")}</th>
                {hasWaiverGroundColumn ? <th>{t("billing.copay.waiverGround")}</th> : null}
                {usesClaimCopayCorrectionShape(claimRows[0]) ? (
                  <>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.billed")}</th>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.payable")}</th>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.copayComponent")}</th>
                    <th className="num-col tabular-nums text-right font-semibold text-[var(--success)]" style={WRAPPED_HEADER_STYLE} title={t("billing.copay.correctedPayableTooltip")}>
                      {t("billing.copay.correctedPayable")}
                    </th>
                    {showIlaveColumn ? (
                      <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.ilaveUcret")}</th>
                    ) : null}
                  </>
                ) : (
                  <>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.gazetteRate")}</th>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.correction")}</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {claimRows.map((correction, index) => (
                <tr key={`${copayCorrectionProcedureLabel(correction)}-${index}`}>
                  <td>{copayCorrectionProcedureLabel(correction)}</td>
                  {hasWaiverGroundColumn ? (
                    <td className="text-sm text-[var(--text-secondary)]">
                      {(() => {
                        const label = waiverGroundLabel(copayCorrectionGroundKey(correction));
                        const groundClauseKey = (correction.clause_ref?.clause_key ?? "").trim();
                        if (!groundClauseKey) {
                          return label;
                        }
                        const coordinate = (correction.clause_ref?.clause_coordinate ?? "").trim();
                        return (
                          <button
                            type="button"
                            data-clause-link={groundClauseKey}
                            onClick={() => setClauseDrawerKey(groundClauseKey)}
                            title={coordinate ? formatSutSectionLabel(coordinate) : undefined}
                            className="cursor-pointer underline decoration-dotted decoration-[var(--border-strong)] hover:text-[var(--text-primary)]"
                          >
                            {label}
                          </button>
                        );
                      })()}
                    </td>
                  ) : null}
                  {usesClaimCopayCorrectionShape(correction) ? (
                    <>
                      <td className="num-col tabular-nums text-right">
                        {fmtTRY2OrUnavailable(copayCorrectionBilledTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right">
                        {fmtTRY2OrUnavailable(copayCorrectionPayableTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right font-semibold text-[var(--gold)]">
                        {fmtTRY2OrUnavailable(copayCorrectionSavingsTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right font-semibold text-[var(--success)]" title={t("billing.copay.correctedPayableTooltip")}>
                        {fmtTRY2OrUnavailable(copayCorrectedPayableTry(correction))}
                      </td>
                      {showIlaveColumn ? (
                        <td className="num-col tabular-nums text-right text-xs text-[var(--text-secondary)]">
                          {(() => {
                            const status = resolveCopayIlaveStatus(correction);
                            if (status.kind === "numeric" && status.amount != null) {
                              return fmtTRY2(status.amount);
                            }
                            const label = t(status.labelKey, status.labelParams);
                            const tooltip = status.tooltipKey
                              ? t(status.tooltipKey, status.labelParams)
                              : undefined;
                            if (status.clauseKey) {
                              return (
                                <button
                                  type="button"
                                  data-clause-link={status.clauseKey}
                                  onClick={() => setClauseDrawerKey(status.clauseKey)}
                                  title={tooltip}
                                  className="cursor-pointer underline decoration-dotted decoration-[var(--border-strong)] hover:text-[var(--text-primary)]"
                                >
                                  {label}
                                </button>
                              );
                            }
                            return (
                              <span
                                title={tooltip}
                                className="cursor-help underline decoration-dotted decoration-[var(--border-strong)]"
                              >
                                {label}
                              </span>
                            );
                          })()}
                        </td>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <td className="num-col tabular-nums text-right">
                        {fmtTRY2OrUnavailable(copayCorrectionBilledTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                        {fmtTRY2OrUnavailable(copayCorrectionSavingsTry(correction))}
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </TableWrap>
          </>
        )}
      </div>
      <SutClauseDrawer clauseKey={clauseDrawerKey} onClose={() => setClauseDrawerKey(null)} />
    </BillingSectionShell>
  );
}

export function BillingStrategySection({ strategyData }: { strategyData: BillingActionReport["billing_strategy"] }) {
  const t = useT();
  const strategyExact = isExactOutput(strategyData);
  const heuristicRows = strategyData.recommendations.filter((item) =>
    usesHeuristicStrategyReviewShape(item),
  );
  const claimLevelRows = strategyData.recommendations.filter(
    (item) =>
      isClaimLevelStrategyRow(item) && item.recommendation_kind !== "optional_override",
  );
  const complianceViolations = strategyData.recommendations.filter((item) =>
    isComplianceViolationRow(item),
  );
  const mergedClaimRows = mergeClaimStrategyTableRows(claimLevelRows, complianceViolations);
  const hasRecommendations =
    heuristicRows.length > 0 ||
    claimLevelRows.length > 0 ||
    complianceViolations.length > 0;

  if (!strategyExact && !hasRecommendations) {
    return (
      <BillingSectionShell id="billing-strategy" title={t("billing.strategy.title")}>
        <ExactnessNotice block={strategyData} fallback={t("billing.strategy.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (!hasRecommendations) {
    return null;
  }

  const heuristicOnly = heuristicRows.length > 0 && mergedClaimRows.length === 0;
  const usesClaimTable = mergedClaimRows.length > 0;
  const savingsHeaderKey = usesClaimTable
    ? strategySavingsHeaderKey(claimLevelRows)
    : "billing.strategy.savings";
  const catalogAsOfFootnote = strategyCatalogAsOfFootnote(claimLevelRows);
  const hasOptionalOverride = claimLevelRows.some(
    (item) => item.recommendation_kind === "optional_override",
  );

  const renderSutRuleBadge = (item: (typeof claimLevelRows)[number]) => {
    const section = formatSutSectionLabel(item.sut_section_id ?? item.sut_section);
    if (isComplianceViolationRow(item)) {
      return section;
    }
    const label =
      item.recommendation_kind === "optional_override"
        ? t("billing.strategy.badgeOverride", { section })
        : t("billing.strategy.badgeMandatory", { section });
    return <Chip variant={chipVariantFromColor(strategyBadgeColor(item))}>{label}</Chip>;
  };

  return (
    <BillingSectionShell id="billing-strategy" title={t("billing.strategy.title")}>
      {!strategyExact && (
        <ExactnessNotice block={strategyData} fallback={t("billing.strategy.unavailable")} className="mb-4" />
      )}
      {usesClaimTable && catalogAsOfFootnote && (
        <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
          {t("billing.strategy.catalogAsOf", { date: catalogAsOfFootnote })}
        </p>
      )}
      {usesClaimTable && hasOptionalOverride && (
        <p className="mb-3 text-xs leading-relaxed rounded-lg px-3 py-2" style={{ background: "rgba(37, 99, 235, 0.08)", color: "#1D4ED8" }}>
          {t("billing.strategy.overrideScopeNotice")}
        </p>
      )}
      {heuristicOnly && (
        <TableWrap minWidth={760}>
          <thead>
            <tr>
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.chapter")}</th>
              <th>{t("billing.strategy.recommendation")}</th>
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
              <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.savings")}</th>
            </tr>
          </thead>
          <tbody>
            {heuristicRows.map((item, index) => (
              <tr key={`${strategyPrimaryLabel(item)}-${index}`}>
                <td className="font-semibold text-slate-950">{item.chapter ?? "—"}</td>
                <td>
                  <Chip variant="outline">{t("patient.workspace.reviewPackage")}</Chip>
                </td>
                <td>
                  {item.detail
                    ? translateStructuredApiMessage(t, item)
                    : translateApiText(strategySecondaryLabel(item))}
                </td>
                <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                  {fmtTRY2OrUnavailable(item.savings_try ?? null)}
                </td>
              </tr>
            ))}
          </tbody>
        </TableWrap>
      )}
      {usesClaimTable && (
        <TableWrap minWidth={1280}>
          <thead>
            <tr>
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.status")}</th>
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.claim")}</th>
              <th>{t("billing.strategy.recommendation")}</th>
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.recommendationKind")}</th>
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.sutSection")}</th>
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.paymentMethodKind")}</th>
              <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.packageTotal")}</th>
              <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.itemizedTotal")}</th>
              <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t(savingsHeaderKey)}</th>
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
            </tr>
          </thead>
          <tbody>
            {mergedClaimRows.map((item, index) => {
              const status = strategyRowStatus(item);
              const isViolation = isComplianceViolationRow(item);
              const savings = strategySavingsTryDisplay(item);
              const kindKey = strategyRecommendationKindMessageKey(item);
              const methodKey = strategyPaymentMethodKindMessageKey(item);
              return (
                <tr key={`${strategyPrimaryLabel(item)}-${item.procedure_code ?? "row"}-${index}`}>
                  <td>
                    <Chip variant={strategyRowStatusChipVariant(status)}>
                      {t(strategyRowStatusMessageKey(status))}
                    </Chip>
                  </td>
                  <td className="font-semibold text-slate-950">
                    {isViolation ? (item.claim_id ?? "—") : strategyPrimaryLabel(item)}
                  </td>
                  <td>
                    {isViolation ? (
                      <>
                        <div className="font-semibold text-slate-950">
                          {item.procedure_name ?? item.procedure_code ?? "—"}
                        </div>
                        {item.procedure_code && item.procedure_name && (
                          <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                            {item.procedure_code}
                          </div>
                        )}
                      </>
                    ) : (
                      <Chip variant={chipVariantFromColor(strategyModeLabel(item) === "package" ? ACCENT : "#2563EB")}>
                        {fmtLabel(strategyModeLabel(item))}
                      </Chip>
                    )}
                  </td>
                  <td>
                    {isViolation
                      ? "—"
                      : kindKey
                        ? (
                          <Chip variant={chipVariantFromColor(strategyBadgeColor(item))}>{t(kindKey)}</Chip>
                        )
                        : "—"}
                  </td>
                  <td>{renderSutRuleBadge(item)}</td>
                  <td>
                    {isViolation
                      ? fmtLabel(item.mandated_method ?? "—")
                      : methodKey
                        ? t(methodKey)
                        : "—"}
                  </td>
                  <td className="num-col tabular-nums text-right">
                    {isViolation ? "—" : fmtTRY2OrUnavailable(strategyPackageTotalTry(item))}
                  </td>
                  <td className="num-col tabular-nums text-right">
                    {isViolation ? "—" : fmtTRY2OrUnavailable(strategyItemizedTotalTry(item))}
                  </td>
                  <td
                    className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]"
                    style={!isViolation && savings.muted ? { color: "#71717A" } : undefined}
                  >
                    {isViolation
                      ? "—"
                      : savings.muted
                        ? t("billing.strategy.compliant")
                        : fmtTRY2OrUnavailable(savings.amount)}
                  </td>
                  <td className="text-sm text-[var(--text-secondary)]">
                    {isViolation
                      ? (item.detail ? translateStructuredApiMessage(t, item) : "—")
                      : (translateStructuredApiMessage(t, item) ||
                          translateApiText(strategySecondaryLabel(item)) ||
                          "—")}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </TableWrap>
      )}
      {!heuristicOnly && heuristicRows.length > 0 && (
        <div className="mt-6">
          <TableWrap minWidth={760}>
            <thead>
              <tr>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.chapter")}</th>
                <th>{t("billing.strategy.recommendation")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.savings")}</th>
              </tr>
            </thead>
            <tbody>
              {heuristicRows.map((item, index) => (
                <tr key={`heuristic-${strategyPrimaryLabel(item)}-${index}`}>
                  <td className="font-semibold text-slate-950">{item.chapter ?? "—"}</td>
                  <td>
                    <Chip variant="outline">{t("patient.workspace.reviewPackage")}</Chip>
                  </td>
                  <td>
                  {item.detail
                    ? translateStructuredApiMessage(t, item)
                    : translateApiText(strategySecondaryLabel(item))}
                </td>
                  <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                    {fmtTRY2OrUnavailable(item.savings_try ?? null)}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        </div>
      )}
    </BillingSectionShell>
  );
}

export function OptionalOverrideSection({
  strategyData,
}: {
  strategyData: BillingActionReport["billing_strategy"];
}) {
  const t = useT();
  const strategyExact = isExactOutput(strategyData);
  const rows = strategyData.recommendations.filter(
    (item) =>
      isClaimLevelStrategyRow(item) &&
      item.recommendation_kind === "optional_override" &&
      (item.savings_try ?? 0) > 0,
  );

  if (!strategyExact && rows.length === 0) {
    return null;
  }
  if (rows.length === 0) {
    return null;
  }

  const totalUplift =
    strategyData.optional_override_uplift_try ??
    rows.reduce((sum, row) => sum + (row.savings_try ?? 0), 0);

  return (
    <BillingSectionShell
      title={t("billing.optionalOverride.title")}
      total={fmtTRY2(totalUplift)}
    >
      <p
        className="mb-3 text-xs leading-relaxed rounded-lg px-3 py-2"
        style={{ background: "rgba(37, 99, 235, 0.08)", color: "#1D4ED8" }}
      >
        {t("billing.strategy.overrideScopeNotice")}
      </p>
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.optionalOverride.scopeFootnote")}
      </p>
      {!strategyExact && (
        <ExactnessNotice block={strategyData} fallback={t("billing.optionalOverride.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1080}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.optionalOverride.claim")}</th>
            <th>{t("billing.optionalOverride.recommended")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.optionalOverride.packageCode")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.optionalOverride.currentBilling")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.optionalOverride.packageTotal")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.optionalOverride.itemizedTotal")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.optionalOverride.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.optionalOverride.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.optionalOverride.note")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item, index) => (
            <tr key={`${item.claim_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <Chip variant={chipVariantFromColor(strategyBadgeColor(item))}>
                  {fmtLabel(strategyModeLabel(item))}
                </Chip>
              </td>
              <td className="font-mono text-sm text-[var(--text-primary)]">
                {item.recommended_package_code ?? "—"}
              </td>
              <td>{item.current_billing ?? "—"}</td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(strategyPackageTotalTry(item) ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(strategyItemizedTotalTry(item) ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {(() => {
                  const display = strategySavingsTryDisplay(item);
                  if (display.muted) {
                    return <span className="text-[var(--text-muted)]">—</span>;
                  }
                  return fmtTRY2OrUnavailable(display.amount);
                })()}
              </td>
              <td>{formatSutSectionLabel(item.sut_section_id)}</td>
              <td>{item.detail ? translateStructuredApiMessage(t, item) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function MaterialUpliftSection({
  materialData,
}: {
  materialData: NonNullable<BillingActionReport["material_uplift"]>;
}) {
  const t = useT();
  const materialExact = isExactOutput(materialData);
  const opportunities = materialData.opportunities ?? [];

  if (!materialExact && opportunities.length === 0) {
    return null;
  }
  if (opportunities.length === 0) {
    return null;
  }

  const confirmedUplift = materialData.confirmed_uplift_try ?? 0;

  return (
    <BillingSectionShell
      id="billing-material-uplift"
      title={t("billing.materialUplift.title")}
      total={fmtTRY2(confirmedUplift)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.materialUplift.scopeFootnote")}
      </p>
      {!materialExact && (
        <ExactnessNotice block={materialData} fallback={t("billing.materialUplift.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1040}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.materialUplift.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.materialUplift.procedure")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.materialUplift.material")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.materialUplift.actualBilled")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.materialUplift.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.materialUplift.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.materialUplift.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${item.material_code}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <div className="font-semibold text-slate-950">
                  {item.procedure_name ?? item.procedure_code ?? "—"}
                </div>
                {item.procedure_code && item.procedure_name && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {item.procedure_code}
                  </div>
                )}
              </td>
              <td>
                <div className="font-semibold text-slate-950">
                  {item.material_name ?? item.material_code ?? "—"}
                </div>
                {item.material_code && item.material_name && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {item.material_code}
                  </div>
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_billed_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={materialData.rule_source} />
              </td>
              <td>{formatSutSectionLabel(item.sut_section_id)}</td>
              <td>
                {item.detail || item.message_code
                  ? translateStructuredApiMessage(t, item)
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

function localizedCorrectiveSteps(
  item: {
    corrective_steps_tr?: string[];
    corrective_steps_en?: string[];
  },
): string[] {
  const locale = getModuleLocale();
  if (locale === "en") {
    return item.corrective_steps_en ?? item.corrective_steps_tr ?? [];
  }
  return item.corrective_steps_tr ?? item.corrective_steps_en ?? [];
}

export function ProcedureCaptureGapSection({
  captureData,
}: {
  captureData: NonNullable<BillingActionReport["procedure_capture_gap"]>;
}) {
  const t = useT();
  const captureExact = isExactOutput(captureData);
  const opportunities = captureData.opportunities ?? [];

  if (isOptionalIngestPending(captureData)) {
    return (
      <BillingSectionShell id="billing-procedure-capture-gap" title={t("billing.procedureCaptureGap.title")}>
        <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
          {t("billing.procedureCaptureGap.scopeFootnote")}
        </p>
        <ExactnessNotice block={captureData} fallback={t("billing.procedureCaptureGap.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (!captureExact && opportunities.length === 0) {
    return null;
  }
  if (opportunities.length === 0) {
    return null;
  }

  const gapTotal = captureData.confirmed_gap_try ?? captureData.total_gap_try ?? 0;

  return (
    <BillingSectionShell id="billing-procedure-capture-gap" title={t("billing.procedureCaptureGap.title")} total={fmtTRY2(gapTotal)}>
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.procedureCaptureGap.scopeFootnote")}
      </p>
      {!captureExact && (
        <ExactnessNotice block={captureData} fallback={t("billing.procedureCaptureGap.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1040}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureCaptureGap.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureCaptureGap.procedure")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureCaptureGap.serviceDate")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureCaptureGap.source")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.procedureCaptureGap.listPrice")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.procedureCaptureGap.actualBilled")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.procedureCaptureGap.gap")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureCaptureGap.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${item.procedure_code}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <div className="font-semibold text-slate-950">
                  {item.procedure_name ?? item.procedure_code ?? "—"}
                </div>
                {item.procedure_code && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {item.procedure_code}
                  </div>
                )}
              </td>
              <td>{item.service_date ? fmtDate(item.service_date) : "—"}</td>
              <td>{item.source ? translateApiText(item.source) : "—"}</td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.list_price_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_billed_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_gap_try ?? null)}
              </td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function ProcedureAddonUpliftSection({
  addonData,
}: {
  addonData: NonNullable<BillingActionReport["procedure_addon_uplift"]>;
}) {
  const t = useT();
  const addonExact = isExactOutput(addonData);
  const opportunities = addonData.opportunities ?? [];

  if (!addonExact && opportunities.length === 0) {
    return null;
  }
  if (opportunities.length === 0) {
    return null;
  }

  const confirmedUplift = addonData.confirmed_uplift_try ?? 0;

  return (
    <BillingSectionShell
      id="billing-procedure-addon-uplift"
      title={t("billing.procedureAddonUplift.title")}
      total={fmtTRY2(confirmedUplift)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.procedureAddonUplift.scopeFootnote")}
      </p>
      {!addonExact && (
        <ExactnessNotice block={addonData} fallback={t("billing.procedureAddonUplift.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1120}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureAddonUplift.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureAddonUplift.triggerProcedure")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureAddonUplift.expectedAddon")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.procedureAddonUplift.addonFactor")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.procedureAddonUplift.listPrice")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.procedureAddonUplift.actualBilled")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.procedureAddonUplift.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureAddonUplift.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.procedureAddonUplift.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${item.expected_addon_procedure_code}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <div className="font-semibold text-slate-950">
                  {item.trigger_procedure_name ?? item.trigger_procedure_code ?? "—"}
                </div>
                {item.trigger_procedure_code && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {item.trigger_procedure_code}
                  </div>
                )}
              </td>
              <td>
                <div className="font-semibold text-slate-950">
                  {item.expected_addon_procedure_name ?? item.expected_addon_procedure_code ?? "—"}
                </div>
                {item.expected_addon_procedure_code && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {item.expected_addon_procedure_code}
                  </div>
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {item.addon_factor != null ? `${Math.round(item.addon_factor * 100)}%` : "—"}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.list_price_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_billed_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={addonData.rule_source} />
              </td>
              <td>{formatSutSectionLabel(item.sut_section_id)}</td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function GazetteRepricingSection({
  repricingData,
}: {
  repricingData: NonNullable<BillingActionReport["gazette_repricing"]>;
}) {
  const t = useT();
  const repricingExact = isExactOutput(repricingData);
  const opportunities = repricingData.opportunities ?? [];

  if (!repricingExact && opportunities.length === 0) {
    return null;
  }
  if (opportunities.length === 0) {
    return null;
  }

  const reviewTotal =
    repricingData.review_repricing_try ?? repricingData.total_repricing_try ?? 0;

  return (
    <BillingSectionShell
      id="billing-gazette-repricing"
      title={t("billing.gazetteRepricing.title")}
      total={fmtTRY2(reviewTotal)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.gazetteRepricing.scopeFootnote")}
      </p>
      {!repricingExact && (
        <ExactnessNotice block={repricingData} fallback={t("billing.gazetteRepricing.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1180}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.gazetteRepricing.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.gazetteRepricing.procedure")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.gazetteRepricing.serviceDate")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.gazetteRepricing.amendmentDate")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.gazetteRepricing.priceAtService")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.gazetteRepricing.amendedPrice")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.gazetteRepricing.payablePerUnit")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.gazetteRepricing.repricingDelta")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.gazetteRepricing.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${item.procedure_line_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <div className="font-semibold text-slate-950">
                  {item.procedure_name ?? item.procedure_code ?? "—"}
                </div>
                {item.procedure_code && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {item.procedure_code}
                  </div>
                )}
              </td>
              <td>{item.service_date ? fmtDate(item.service_date) : "—"}</td>
              <td>{item.amendment_effective_date ? fmtDate(item.amendment_effective_date) : "—"}</td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.price_at_service_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.amended_list_price_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_payable_per_unit_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_repricing_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell
                  ruleSource={repricingData.rule_source}
                  rowCatalog={item.catalog}
                />
              </td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

function localizedReadinessReminder(item: {
  reminder_tr?: string;
  reminder_en?: string;
}): string {
  const locale = getModuleLocale();
  if (locale === "en") {
    return item.reminder_en ?? item.reminder_tr ?? "—";
  }
  return item.reminder_tr ?? item.reminder_en ?? "—";
}

function localizedPreventiveSteps(
  item: {
    preventive_steps_tr?: string[];
    preventive_steps_en?: string[];
  },
): string[] {
  const locale = getModuleLocale();
  if (locale === "en") {
    return item.preventive_steps_en ?? item.preventive_steps_tr ?? [];
  }
  return item.preventive_steps_tr ?? item.preventive_steps_en ?? [];
}

export function ClaimSubmissionChecklistSection({
  checklistData,
}: {
  checklistData: NonNullable<BillingActionReport["claim_submission_checklist"]>;
}) {
  const t = useT();
  const checklistExact = isExactOutput(checklistData);
  const items = checklistData.items ?? [];

  if (items.length === 0) {
    return null;
  }

  const itemCount = checklistData.item_count ?? items.length;

  return (
    <BillingSectionShell
      id="claim-submission-checklist"
      title={t("billing.claimChecklist.title")}
      total={String(itemCount)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.claimChecklist.scopeFootnote")}
      </p>
      {!checklistExact && (
        <ExactnessNotice block={checklistData} fallback={t("billing.claimChecklist.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1120}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.line")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.medulaRisk")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.severity")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.reminder")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.sutAnchor")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.steps")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item: ClaimSubmissionChecklist["items"][number], index: number) => (
            <tr key={`${item.claim_id}-${item.line_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <div>{item.line_name ?? "—"}</div>
                <div className="font-mono text-xs">{item.line_code ?? "—"}</div>
              </td>
              <td className="font-mono text-xs">{item.sonuc_kodu_risk ?? "—"}</td>
              <td>{item.severity ? getSutSeverityLabel(item.severity) : "—"}</td>
              <td>{localizedReadinessReminder(item)}</td>
              <td>{item.sut_anchor ?? "—"}</td>
              <td>
                <ul className="list-disc space-y-1 pl-4 text-sm">
                  {localizedPreventiveSteps(item).map((step, stepIndex) => (
                    <li key={`${item.checklist_id}-step-${stepIndex}`}>{step}</li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function MedulaRejectionPlaybookSection({
  playbookData,
}: {
  playbookData: NonNullable<BillingActionReport["medula_rejection_playbook"]>;
}) {
  const t = useT();
  const playbookExact = isExactOutput(playbookData);
  const entries = playbookData.entries ?? [];

  if (entries.length === 0) {
    return null;
  }

  const entryCount = playbookData.entry_count ?? entries.length;

  return (
    <BillingSectionShell
      id="medula-playbook"
      title={t("billing.medulaPlaybook.title")}
      total={String(entryCount)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.medulaPlaybook.scopeFootnote")}
      </p>
      {!playbookExact && (
        <ExactnessNotice block={playbookData} fallback={t("billing.medulaPlaybook.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1180}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.stage")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.code")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.message")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.procedure")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.sutAnchor")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.rebill")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.steps")}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((item, index) => (
            <tr key={`${item.claim_id}-${item.rejection_event_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>{item.medula_stage ? translateApiText(item.medula_stage) : "—"}</td>
              <td className="font-mono text-xs">{item.sonuc_kodu ?? "—"}</td>
              <td>{item.hata_mesaji ? translateApiText(item.hata_mesaji) : "—"}</td>
              <td>
                <div className="font-mono text-xs">
                  {item.related_line_type === "procedure" && item.related_procedure_code
                    ? item.related_procedure_code
                    : item.related_line_id ?? "—"}
                </div>
                {item.related_line_type && item.related_line_type !== "procedure" && (
                  <div className="text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                    {t(`billing.medulaPlaybook.lineType.${item.related_line_type}`)}
                  </div>
                )}
              </td>
              <td>{item.sut_anchor ?? "—"}</td>
              <td>{item.rebill_permitted ? t("billing.medulaPlaybook.yes") : t("billing.medulaPlaybook.no")}</td>
              <td>
                <ul className="list-disc space-y-1 pl-4 text-sm">
                  {localizedCorrectiveSteps(item).map((step, stepIndex) => (
                    <li key={`${item.playbook_id}-step-${stepIndex}`}>{step}</li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function DrugIndicationReviewSection({
  reviewData,
}: {
  reviewData: NonNullable<BillingActionReport["drug_indication"]>;
}) {
  const t = useT();
  const reviewExact = isExactOutput(reviewData);
  const violations = reviewData.violations ?? [];

  if (violations.length === 0) {
    return null;
  }

  const violationCount = reviewData.violation_count ?? violations.length;

  return (
    <BillingSectionShell
      id="drug-indication"
      title={t("billing.drugIndication.title")}
      total={String(violationCount)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.drugIndication.scopeFootnote")}
      </p>
      {!reviewExact && (
        <ExactnessNotice block={reviewData} fallback={t("billing.drugIndication.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1080}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.drug")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.violationKind")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.severity")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.primaryIcd10")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.ruleId")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.message")}</th>
          </tr>
        </thead>
        <tbody>
          {violations.map((item, index) => (
            <tr key={`${item.claim_id}-${item.drug_claim_line_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>{item.drug_name ?? "—"}</td>
              <td className="font-mono text-xs">{item.violation_kind ?? "—"}</td>
              <td>{item.severity ? getSutSeverityLabel(item.severity) : "—"}</td>
              <td className="font-mono text-xs">{item.primary_icd10 ?? "—"}</td>
              <td className="font-mono text-xs">{item.rule_id ?? "—"}</td>
              <td>{item.sut_section ?? "—"}</td>
              <td>{item.message_tr ? translateApiText(item.message_tr) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function DrgPackageAdequacyReviewSection({
  reviewData,
}: {
  reviewData: NonNullable<BillingActionReport["drg_package_adequacy"]>;
}) {
  const t = useT();
  const reviewExact = isExactOutput(reviewData);
  const opportunities = reviewData.opportunities ?? [];

  if (!reviewExact && opportunities.length === 0) {
    return null;
  }
  if (opportunities.length === 0) {
    return null;
  }

  const reviewUplift = reviewData.review_uplift_try ?? reviewData.total_uplift_try ?? 0;

  return (
    <BillingSectionShell id="billing-drg-package-adequacy" title={t("billing.packageAdequacyReview.title")}>
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.packageAdequacyReview.scopeFootnote")}
      </p>
      {reviewUplift > 0 && (
        <p className="mb-3 text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.careSettingReview.reviewTotal")}: {fmtTRY2(reviewUplift)}
        </p>
      )}
      {!reviewExact && (
        <ExactnessNotice block={reviewData} fallback={t("billing.packageAdequacyReview.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1200}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.primaryIcd10")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.clinicalProcedures")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.currentPackage")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.candidatePackage")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.packageAdequacyReview.currentPrice")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.packageAdequacyReview.candidatePrice")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.packageAdequacyReview.reviewDelta")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${item.candidate_package_code}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td className="font-mono text-xs">{item.primary_icd10 ?? "—"}</td>
              <td className="font-mono text-xs">
                {(item.clinical_procedure_codes ?? []).join(", ") || "—"}
              </td>
              <td>
                <div className="font-semibold text-slate-950">{item.current_package_code ?? "—"}</div>
                {(item.current_package_footprint ?? []).length > 0 && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {(item.current_package_footprint ?? []).join(", ")}
                  </div>
                )}
              </td>
              <td>
                <div className="font-semibold text-slate-950">{item.candidate_package_code ?? "—"}</div>
                {(item.candidate_package_footprint ?? []).length > 0 && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {(item.candidate_package_footprint ?? []).join(", ")}
                  </div>
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.current_package_price_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.candidate_package_price_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={reviewData.rule_source} />
              </td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function CareSettingReviewSection({
  reviewData,
}: {
  reviewData: NonNullable<BillingActionReport["care_setting_review"]>;
}) {
  const t = useT();
  const reviewExact = isExactOutput(reviewData);
  const opportunities = reviewData.opportunities ?? [];

  if (!reviewExact && opportunities.length === 0) {
    return null;
  }
  if (opportunities.length === 0) {
    return null;
  }

  const reviewUplift = reviewData.review_uplift_try ?? reviewData.total_uplift_try ?? 0;

  return (
    <BillingSectionShell id="billing-care-setting-review" title={t("billing.careSettingReview.title")}>
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.careSettingReview.scopeFootnote")}
      </p>
      {reviewUplift > 0 && (
        <p className="mb-3 text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.careSettingReview.reviewTotal")}: {fmtTRY2(reviewUplift)}
        </p>
      )}
      {!reviewExact && (
        <ExactnessNotice block={reviewData} fallback={t("billing.careSettingReview.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1120}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.claimType")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.actualSetting")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.alternateSetting")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.careSettingReview.actualBest")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.careSettingReview.alternateBest")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.careSettingReview.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>{item.claim_type ? translateApiText(item.claim_type) : "—"}</td>
              <td>
                <div>{item.actual_care_setting ? translateApiText(item.actual_care_setting) : "—"}</div>
                {item.actual_payment_method_kind && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {getPaymentMethodKindLabel(item.actual_payment_method_kind)}
                  </div>
                )}
              </td>
              <td>
                <div>{item.alternate_care_setting ? translateApiText(item.alternate_care_setting) : "—"}</div>
                {item.alternate_payment_method_kind && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {getPaymentMethodKindLabel(item.alternate_payment_method_kind)}
                  </div>
                )}
                {item.review_kind === "needs_clinical_review" && (
                  <div className="mt-2">
                    <Chip variant="warning">{t("billing.careSettingReview.reviewBadge")}</Chip>
                  </div>
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_best_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.alternate_best_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={reviewData.rule_source} />
              </td>
              <td>{formatSutSectionLabel(item.sut_section_id)}</td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function BloodComponentUpliftSection({
  bloodData,
}: {
  bloodData: NonNullable<BillingActionReport["blood_uplift"]>;
}) {
  const t = useT();
  const bloodExact = isExactOutput(bloodData);
  const opportunities = bloodData.opportunities ?? [];

  if (!bloodExact && opportunities.length === 0) {
    return null;
  }
  if (opportunities.length === 0) {
    return null;
  }

  const confirmedUplift = bloodData.confirmed_uplift_try ?? 0;

  return (
    <BillingSectionShell
      id="billing-blood-uplift"
      title={t("billing.bloodUplift.title")}
      total={fmtTRY2(confirmedUplift)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.bloodUplift.scopeFootnote")}
      </p>
      {!bloodExact && (
        <ExactnessNotice block={bloodData} fallback={t("billing.bloodUplift.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1040}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.bloodUplift.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.bloodUplift.procedure")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.bloodUplift.allowedFraction")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.bloodUplift.maxBillable")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.bloodUplift.actualBilled")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.bloodUplift.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.bloodUplift.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.bloodUplift.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${item.procedure_code}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <div className="font-semibold text-slate-950">
                  {item.procedure_name ?? item.procedure_code ?? "—"}
                </div>
                {item.procedure_code && item.procedure_name && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {item.procedure_code}
                  </div>
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {item.allowed_fraction != null
                  ? `${Math.round(item.allowed_fraction * 100)}%`
                  : "—"}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.max_billable_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_billed_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={bloodData.rule_source} />
              </td>
              <td>{formatSutSectionLabel(item.sut_section_id)}</td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function DrgUpliftSection({
  drgData,
}: {
  drgData: NonNullable<BillingActionReport["drg_uplift"]>;
}) {
  const t = useT();
  const drgExact = isExactOutput(drgData);
  const opportunities = drgData.opportunities ?? [];

  if (!drgExact && opportunities.length === 0) {
    return (
      <BillingSectionShell id="billing-drg-uplift" title={t("billing.drgUplift.title")}>
        <ExactnessNotice block={drgData} fallback={t("billing.drgUplift.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (opportunities.length === 0) {
    return null;
  }

  const confirmedUplift = drgData.confirmed_uplift_try ?? 0;

  return (
    <BillingSectionShell id="billing-drg-uplift" title={t("billing.drgUplift.title")} total={fmtTRY2(confirmedUplift)}>
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.drgUplift.scopeFootnote")}
      </p>
      {!drgExact && (
        <ExactnessNotice block={drgData} fallback={t("billing.drgUplift.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={960}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drgUplift.claim")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.drgUplift.itemizedTotal")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.drgUplift.packageTotal")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.drgUplift.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drgUplift.basis")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drgUplift.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drgUplift.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.itemized_total_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.package_total_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>{item.savings_basis ?? "—"}</td>
              <td>
                <BillingRegulatorySourceCell ruleSource={drgData.rule_source} />
              </td>
              <td>{formatSutSectionLabel(item.sut_section_id)}</td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function SessionUpliftSection({
  sessionData,
}: {
  sessionData: NonNullable<BillingActionReport["session_uplift"]>;
}) {
  const t = useT();
  const sessionExact = isExactOutput(sessionData);
  const opportunities = sessionData.opportunities ?? [];

  if (!sessionExact && opportunities.length === 0) {
    return (
      <BillingSectionShell id="billing-session-uplift" title={t("billing.sessionUplift.title")}>
        <ExactnessNotice block={sessionData} fallback={t("billing.sessionUplift.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (opportunities.length === 0) {
    return null;
  }

  const confirmedUplift =
    sessionData.confirmed_uplift_try ??
    opportunities
      .filter((row) => row.included_in_sgk_total !== false)
      .reduce((sum, row) => sum + (row.recoverable_uplift_try ?? 0), 0);
  const reviewUplift = sessionData.review_uplift_try ?? 0;

  return (
    <BillingSectionShell
      id="billing-session-uplift"
      title={t("billing.sessionUplift.title")}
      total={fmtTRY2(confirmedUplift)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.sessionUplift.scopeFootnote")}
      </p>
      {reviewUplift > 0 && (
        <p className="mb-3 text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.sessionUplift.reviewTotal")}: {fmtTRY2(reviewUplift)}
        </p>
      )}
      {!sessionExact && (
        <ExactnessNotice block={sessionData} fallback={t("billing.sessionUplift.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1080}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.procedure")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.primaryProcedure")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.sessionUplift.expectedBilled")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.sessionUplift.actualBilled")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.sessionUplift.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${item.procedure_code}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <div className="font-semibold text-slate-950">
                  {item.procedure_name ?? item.procedure_code ?? "—"}
                </div>
                {item.procedure_code && item.procedure_name && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {item.procedure_code}
                  </div>
                )}
                {item.review_kind === "needs_clinical_review" && (
                  <div className="mt-2">
                    <Chip variant="warning">{t("billing.sessionUplift.reviewBadge")}</Chip>
                  </div>
                )}
              </td>
              <td className="font-mono text-xs">{item.primary_procedure_code ?? "—"}</td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.expected_billed_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_billed_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {item.review_kind === "needs_clinical_review"
                  ? "—"
                  : fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={sessionData.rule_source} />
              </td>
              <td>{formatSutSectionLabel(item.sut_section_id)}</td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function MaterialsPreCheckSection({ materialsData }: { materialsData: BillingActionReport["materials"] }) {
  const t = useT();
  const ceilingEntries = Object.entries(materialsData.gazette_ceiling_by_specialty);
  const materialsExact = isExactOutput(materialsData);
  const intervalViolations = materialsData.miat_interval_violations ?? [];
  const bundledLines = materialsData.bundled_separate_billing ?? [];
  const proseViolations = materialsData.prose_bundling_violations ?? [];
  const specialtyProseViolations = materialsData.specialty_prose_violations ?? [];
  const kdvPriceReviews = materialsData.kdv_price_reviews ?? [];
  const hasExactListData =
    materialsData.pre_auth_required.length > 0 ||
    materialsData.miat_restricted.length > 0 ||
    intervalViolations.length > 0 ||
    bundledLines.length > 0 ||
    proseViolations.length > 0 ||
    specialtyProseViolations.length > 0 ||
    kdvPriceReviews.length > 0;
  const hasAnyData = hasExactListData || ceilingEntries.length > 0;

  if (!hasAnyData && materialsExact) {
    return null;
  }

  return (
    <BillingSectionShell id="materials-pre-check" title={t("billing.materials.title")}>
      <div className="space-y-4">
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.materials.advisoryFootnote")}
        </p>
        <MaterialBundlingScopeNotice scope={materialsData.coverage_scope} compact />
        <SpecialtyProseScopeNotice scope={materialsData.specialty_coverage_scope} compact />
        {!materialsExact && (
          <ExactnessNotice block={materialsData} fallback={t("billing.materials.unavailable")} />
        )}
        {materialsData.pre_auth_required.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#D97706" }}>
              {t("billing.materials.preAuth")}
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {materialsData.pre_auth_required.map((material, index) => (
                  <tr key={`${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td className="num-col tabular-nums text-right">{fmtTRY2(material.price_try)}</td>
                    <td>{material.note ? translateApiText(material.note) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {intervalViolations.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B91C1C" }}>
              {t("billing.materials.miatIntervalViolations")}
            </p>
            <TableWrap minWidth={920}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.lastUse")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.miatPeriod")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {intervalViolations.map((material, index) => (
                  <tr key={`miat-int-${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td>{material.last_use_date ? fmtDate(material.last_use_date) : "—"}</td>
                    <td>{material.miat_period}</td>
                    <td>{material.note ? translateApiText(material.note) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {materialsData.miat_restricted.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#64748B" }}>
              {t("billing.materials.miatCatalog")}
            </p>
            <TableWrap minWidth={900}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.miatPeriod")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {materialsData.miat_restricted.map((material, index) => (
                  <tr key={`${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td>{material.miat_period}</td>
                    <td className="num-col tabular-nums text-right">{fmtTRY2(material.price_try)}</td>
                    <td>{material.note ? translateApiText(material.note) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {bundledLines.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#D97706" }}>
              {t("billing.materials.bundledSeparate")}
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {bundledLines.map((material, index) => (
                  <tr key={`bundled-${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td className="num-col tabular-nums text-right">{fmtTRY2(material.price_try)}</td>
                    <td>{material.note ? translateApiText(material.note) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {proseViolations.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B45309" }}>
              {t("billing.materials.proseBundling")}
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {proseViolations.map((hit, index) => (
                  <tr key={`prose-${hit.material_code ?? "row"}-${hit.rule_id ?? "rule"}-${index}`}>
                    <td className="font-mono text-xs">{hit.material_code || "—"}</td>
                    <td>{hit.material_name || "—"}</td>
                    <td className="num-col tabular-nums text-right">
                      {hit.risk_amount != null ? fmtTRY2(hit.risk_amount) : "—"}
                    </td>
                    <td>{hit.message ? translateApiText(hit.message) : (hit.rule_id || "—")}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {specialtyProseViolations.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#7C3AED" }}>
              {t("billing.materials.specialtyProse")}
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {specialtyProseViolations.map((hit, index) => (
                  <tr
                    key={`specialty-prose-${hit.material_code ?? "row"}-${hit.rule_id ?? "rule"}-${index}`}
                  >
                    <td className="font-mono text-xs">{hit.material_code || "—"}</td>
                    <td>{hit.material_name || "—"}</td>
                    <td className="num-col tabular-nums text-right">
                      {hit.risk_amount != null ? fmtTRY2(hit.risk_amount) : "—"}
                    </td>
                    <td>{hit.message ? translateApiText(hit.message) : (hit.rule_id || "—")}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {kdvPriceReviews.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B45309" }}>
              {t("billing.materials.kdvPriceReviews")}
            </p>
            <TableWrap minWidth={920}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.billedAmount")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazetteCeiling")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {kdvPriceReviews.map((row, index) => (
                  <tr key={`kdv-${row.sut_code ?? "row"}-${index}`}>
                    <td className="font-mono text-xs">{row.sut_code || "—"}</td>
                    <td>{row.material_name || "—"}</td>
                    <td className="num-col tabular-nums text-right">
                      {row.billed_try != null ? fmtTRY2(row.billed_try) : "—"}
                    </td>
                    <td className="num-col tabular-nums text-right">
                      {row.gazette_ceiling_try != null ? fmtTRY2(row.gazette_ceiling_try) : "—"}
                    </td>
                    <td>{row.note ? translateApiText(row.note) : (row.kdv_applied ? t("billing.materials.kdvApplied") : "—")}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {!materialsExact && ceilingEntries.length > 0 && (
          <p className="text-sm text-[var(--text-secondary)]">
            {t("billing.materials.partialBenchmarkNotice")}
          </p>
        )}

        {ceilingEntries.length > 0 && (
          <Surface variant="base" padding="md">
            <Eyebrow>{t("billing.materials.ceilingEyebrow")}</Eyebrow>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {ceilingEntries.map(([specialty, amount]) => (
                <Surface key={specialty} variant="soft" padding="sm">
                  <Eyebrow>{specialty}</Eyebrow>
                  <p className="mt-1 font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]">
                    {fmtTRY2(amount)}
                  </p>
                </Surface>
              ))}
            </div>
          </Surface>
        )}
      </div>
    </BillingSectionShell>
  );
}

export function SutOptimizationSection({ optimization }: { optimization: PatientOptimization }) {
  const t = useT();
  const surchargeExact = isExactOutput(optimization.surcharge_exposure);
  const rateExact = isExactOutput(optimization.copay_rate_exposure);
  const drgExact = isExactOutput(optimization.drg_unbundling);
  const surchargeCount = optimization.surcharge_exposure.n_applicable_procedures;
  const rateCount = optimization.copay_rate_exposure.n_applicable_procedures;
  const drgRiskLabel = optimization.drg_unbundling?.has_unbundling_risk ? fmtRiskLabel("high") : fmtRiskLabel("low");

  return (
    <BillingSectionShell title={t("billing.sutOptimization.title")}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>{t("billing.sutOptimization.copayEyebrow")}</Eyebrow>
          <div className="flex flex-wrap items-center gap-2">
            <Chip variant={optimization.copay_exemptions.exempt ? "success" : "neutral"}>
              {optimization.copay_exemptions.exempt
                ? getSutAlertBadgeLabel("exempt")
                : getSutAlertBadgeLabel("notExempt")}
            </Chip>
            {optimization.copay_exemptions.exempt && (
              <ExemptionBasisChips copay={optimization.copay_exemptions} max={3} />
            )}
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            {getExemptionCategories(optimization.copay_exemptions).includes("ek1a_chronic")
              ? t("billing.sutOptimization.ek1aQualifying", {
                  count: fmtNum(optimization.copay_exemptions.qualifying_diagnoses.length),
                })
              : optimization.copay_exemptions.exempt
                ? t("billing.sutOptimization.exemptStatusVisit")
                : t("billing.sutOptimization.noWaiver")}
          </p>
        </Surface>

        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>{t("billing.sutOptimization.surchargeEyebrow")}</Eyebrow>
          <Chip
            variant={
              !surchargeExact
                ? "neutral"
                : (surchargeCount ?? 0) > 0
                  ? "warning"
                  : "success"
            }
          >
            {surchargeExact
              ? ((surchargeCount ?? 0) > 0
                ? t("billing.sutOptimization.flags", { count: fmtNum(surchargeCount ?? 0) })
                : getSutAlertBadgeLabel("clear"))
              : getSutAlertBadgeLabel("unavailable")}
          </Chip>
          {!surchargeExact && (
            <ExactnessNotice
              block={optimization.surcharge_exposure}
              fallback={t("billing.sutOptimization.surchargeUnavailable")}
            />
          )}
        </Surface>

        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>{t("billing.sutOptimization.copayRateEyebrow")}</Eyebrow>
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            {rateExact
              ? ((rateCount ?? 0) > 0
                ? t("billing.sutOptimization.cappedProcedures", { count: fmtNum(rateCount ?? 0) })
                : t("billing.sutOptimization.noRateCaps"))
              : t("common.unavailable")}
          </p>
          {!rateExact && (
            <ExactnessNotice
              block={optimization.copay_rate_exposure}
              fallback={t("billing.sutOptimization.copayRateUnavailable")}
            />
          )}
        </Surface>

        {optimization.drg_unbundling && (
          <Surface variant="soft" padding="md" className="space-y-2">
            <Eyebrow>{t("billing.sutOptimization.drgEyebrow")}</Eyebrow>
            <Chip
              variant={
                !drgExact
                  ? "neutral"
                  : optimization.drg_unbundling.has_unbundling_risk
                    ? "danger"
                    : "success"
              }
            >
              {drgExact ? drgRiskLabel : getSutAlertBadgeLabel("unavailable")}
            </Chip>
            {drgExact ? (
              <>
                <p className="text-xs text-[var(--text-secondary)]">
                  {t("billing.sutOptimization.recoverableSavings", {
                    amount: fmtTRY2OrUnavailable(optimization.drg_unbundling.total_potential_savings),
                  })}
                </p>
                {(optimization.drg_unbundling.total_sourced_savings ?? 0) > 0 && (
                  <p className="text-xs text-[var(--text-secondary)]">
                    {t("billing.sutOptimization.drgSourcedSavings", {
                      amount: fmtTRY2OrUnavailable(optimization.drg_unbundling.total_sourced_savings),
                    })}
                  </p>
                )}
              </>
            ) : (
              <ExactnessNotice
                block={optimization.drg_unbundling}
                fallback={t("billing.sutOptimization.drgUnavailable")}
              />
            )}
          </Surface>
        )}
      </div>
    </BillingSectionShell>
  );
}
