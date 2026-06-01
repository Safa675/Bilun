"use client";

import type { CSSProperties, ReactNode } from "react";
import type { BillingActionReport, PatientOptimization } from "@/lib/domains/sut";
import { getSutAlertBadgeLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { getUnavailableMessage, hasRecoverableBillingTotals, isExactOutput } from "@/lib/sutExactness";
import {
  copayCorrectionBilledTry,
  copayCorrectionPayableTry,
  copayCorrectionProcedureLabel,
  copayCorrectionSavingsTry,
  strategyItemizedTotalTry,
  strategyModeLabel,
  strategyPackageTotalTry,
  strategyPrimaryLabel,
  strategySecondaryLabel,
  usesClaimCopayCorrectionShape,
  usesClaimStrategyShape,
  usesHeuristicStrategyReviewShape,
  usesInsightOnlyCopayCorrectionShape,
} from "@/lib/billingReportFields";
import { theme } from "@/lib/theme";
import { ExemptionBasisChips } from "@/components/sut/ExemptionBasisChips";
import { Chip, DataTable, Eyebrow, Section, Stat, Surface } from "@/components/primitives";
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

export function StatusChip({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="sut-status-chip"
      style={{ "--sut-chip-color": color } as CSSProperties}
    >
      {label}
    </span>
  );
}

type ExactnessBlock = Parameters<typeof getUnavailableMessage>[0];

export function ExactnessNotice({
  block,
  fallback,
}: {
  block: ExactnessBlock;
  fallback: string;
}) {
  return (
    <div className="sut-exactness-notice">
      {getUnavailableMessage(block, fallback)}
    </div>
  );
}

export function BillingSectionShell({
  title,
  total,
  children,
}: {
  title: string;
  total?: string;
  children: ReactNode;
}) {
  return (
    <Section
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

export function BillingSummary({ billingReport }: { billingReport: BillingActionReport }) {
  const t = useT();
  const reportExact = isExactOutput(billingReport);
  const reportHasTotals = hasRecoverableBillingTotals(billingReport);
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
          <Eyebrow>{t("billing.summary.title")}</Eyebrow>
          <p className="mt-1 font-mono text-base text-[var(--text-secondary)]">
            {billingReport.patient_id}
          </p>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
            {t("billing.summary.description")}
          </p>
        </div>
        <StatusChip label={statusLabel} color={priorityColor} />
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Stat
          label={t("billing.summary.ruleCalculatedOpportunity")}
          value={
            reportHasTotals
              ? fmtTRY2(billingReport.total_recoverable_try)
              : t("common.unavailable")
          }
          display={reportHasTotals ? "gold" : "default"}
        />
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

export function LabOptimizationSection({ labData }: { labData: BillingActionReport["lab"] }) {
  const t = useT();
  if (!isExactOutput(labData)) {
    return (
      <BillingSectionShell title={t("billing.lab.title")}>
        <ExactnessNotice block={labData} fallback={t("billing.lab.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (labData.flagged_tests.length === 0) {
    return null;
  }

  const combinedSavings = labData.hemogram_bundling_savings + labData.duplicate_test_savings;

  return (
    <BillingSectionShell title={t("billing.lab.title")} total={fmtTRY2(combinedSavings)}>
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
                <StatusChip
                  label={fmtLabel(test.flag_type)}
                  color={test.flag_type === "hemogram_unbundling" ? "#D97706" : "#B91C1C"}
                />
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2(test.savings_try)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function DrugOptimizationSection({ drugData }: { drugData: BillingActionReport["drug"] }) {
  const t = useT();
  const drugExact = isExactOutput(drugData);
  const hasRecommendations = drugData.drug_recommendations.length > 0;

  if (!drugExact && !hasRecommendations) {
    return (
      <BillingSectionShell title={t("billing.drug.title")}>
        <ExactnessNotice block={drugData} fallback={t("billing.drug.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (!hasRecommendations) {
    return null;
  }

  return (
    <BillingSectionShell
      title={t("billing.drug.title")}
      total={drugExact ? fmtTRY2(drugData.generic_substitution_savings) : undefined}
    >
      {!drugExact && (
        <ExactnessNotice block={drugData} fallback={t("billing.drug.unavailable")} />
      )}
      <TableWrap minWidth={860}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drug.drug")}</th>
            <th>{t("billing.drug.issue")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drug.alternative")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.drug.savings")}</th>
          </tr>
        </thead>
        <tbody>
          {drugData.drug_recommendations.map((recommendation, index) => (
            <tr key={`${recommendation.drug_name}-${index}`}>
              <td title={recommendation.drug_name}>{recommendation.drug_name}</td>
              <td>
                <StatusChip
                  label={fmtLabel(recommendation.issue)}
                  color={recommendation.issue === "passivated" ? "#B91C1C" : "#D97706"}
                />
              </td>
              <td title={recommendation.issue === "discount_tier_applied" ? (recommendation.detail || t("billing.drug.tierCorrectionSameDrug")) : recommendation.alternative}>
                {recommendation.issue === "discount_tier_applied" ? t("billing.drug.tierCorrection") : recommendation.alternative}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(recommendation.savings_try ?? null)}
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

  const savingsColor = copayData.total_copay_savings_try > 0 ? ACCENT : "#71717A";
  const insightOnlyRows = copayData.rate_corrections.filter((correction) =>
    usesInsightOnlyCopayCorrectionShape(correction),
  );
  const claimRows = copayData.rate_corrections.filter(
    (correction) => !usesInsightOnlyCopayCorrectionShape(correction),
  );

  return (
    <BillingSectionShell
      title={t("billing.copay.title")}
      total={
        copayExact
          ? fmtTRY2(copayData.visit_copay_savings_try + copayData.rx_copay_savings_try)
          : undefined
      }
    >
      <div className="space-y-4">
        {!copayExact && (
          <ExactnessNotice block={copayData} fallback={t("billing.copay.unavailable")} />
        )}

        <div className="flex flex-wrap items-center gap-3">
          <StatusChip
            label={copayData.is_exempt ? getSutAlertBadgeLabel("exempt") : getSutAlertBadgeLabel("notExempt")}
            color={copayData.is_exempt ? ACCENT : "#A1A1AA"}
          />
          {copayData.exemption_disease && (
            <span className="text-sm" style={{ color: "#71717A" }}>
              {copayData.exemption_disease} ({copayData.exemption_range})
            </span>
          )}
        </div>

        {copayExact && (
          <div className="grid gap-3 md:grid-cols-3">
            <KpiCard label={t("billing.copay.visitSavings")} value={fmtTRY2(copayData.visit_copay_savings_try)} valueColor={savingsColor} />
            <KpiCard label={t("billing.copay.rxSavings")} value={fmtTRY2(copayData.rx_copay_savings_try)} valueColor={savingsColor} />
            <KpiCard label={t("billing.copay.totalSavings")} value={fmtTRY2(copayData.total_copay_savings_try)} valueColor={savingsColor} />
          </div>
        )}

        {insightOnlyRows.length > 0 && (
          <div className="space-y-2">
            {insightOnlyRows.map((correction, index) => (
              <p key={`insight-${index}`} className="text-sm leading-relaxed text-[var(--text-secondary)]">
                {correction.detail}
              </p>
            ))}
          </div>
        )}

        {claimRows.length > 0 && (
          <TableWrap minWidth={760}>
            <thead>
              <tr>
                <th>{t("billing.copay.procedure")}</th>
                {usesClaimCopayCorrectionShape(claimRows[0]) ? (
                  <>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.billed")}</th>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.payable")}</th>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.copay.copayComponent")}</th>
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
                  {usesClaimCopayCorrectionShape(correction) ? (
                    <>
                      <td className="num-col tabular-nums text-right">
                        {fmtTRY2OrUnavailable(copayCorrectionBilledTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right">
                        {fmtTRY2OrUnavailable(copayCorrectionPayableTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                        {fmtTRY2OrUnavailable(copayCorrectionSavingsTry(correction))}
                      </td>
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
        )}
      </div>
    </BillingSectionShell>
  );
}

export function BillingStrategySection({ strategyData }: { strategyData: BillingActionReport["billing_strategy"] }) {
  const t = useT();
  const strategyExact = isExactOutput(strategyData);
  const hasRecommendations = strategyData.recommendations.length > 0;

  if (!strategyExact && !hasRecommendations) {
    return (
      <BillingSectionShell title={t("billing.strategy.title")}>
        <div className="sut-exactness-notice">
          {getUnavailableMessage(strategyData, t("billing.strategy.unavailable"))}
        </div>
      </BillingSectionShell>
    );
  }

  if (!hasRecommendations) {
    return null;
  }

  const heuristicOnly = strategyData.recommendations.every((item) =>
    usesHeuristicStrategyReviewShape(item),
  );

  return (
    <BillingSectionShell title={t("billing.strategy.title")}>
      {!strategyExact && (
        <div className="sut-exactness-notice mb-4">
          {getUnavailableMessage(strategyData, t("billing.strategy.unavailable"))}
        </div>
      )}
      <TableWrap minWidth={heuristicOnly ? 760 : 980}>
        <thead>
          <tr>
            {heuristicOnly ? (
              <>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.chapter")}</th>
                <th>{t("billing.strategy.recommendation")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.savings")}</th>
              </>
            ) : usesClaimStrategyShape(strategyData.recommendations[0]) ? (
              <>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.claim")}</th>
                <th>{t("billing.strategy.recommendation")}</th>
                <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.packageTotal")}</th>
                <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.itemizedTotal")}</th>
                <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.savings")}</th>
              </>
            ) : (
              <>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.chapter")}</th>
                <th>{t("billing.strategy.group")}</th>
                <th>{t("billing.strategy.strategy")}</th>
                <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.packageTotal")}</th>
                <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.itemizedTotal")}</th>
                <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.strategy.savings")}</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {strategyData.recommendations.map((item, index) => (
            <tr key={`${strategyPrimaryLabel(item)}-${index}`}>
              {usesHeuristicStrategyReviewShape(item) ? (
                <>
                  <td className="font-semibold text-slate-950">{item.chapter ?? "—"}</td>
                  <td>
                    <StatusChip
                      label={t("patient.workspace.reviewPackage")}
                      color="#2563EB"
                    />
                  </td>
                  <td>{item.detail ?? strategySecondaryLabel(item)}</td>
                  <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                    {fmtTRY2OrUnavailable(item.savings_try ?? null)}
                  </td>
                </>
              ) : usesClaimStrategyShape(item) ? (
                <>
                  <td>
                    <div className="font-semibold text-slate-950">{strategyPrimaryLabel(item)}</div>
                    {strategySecondaryLabel(item) && (
                      <div className="mt-1 text-xs" style={{ color: "#71717A" }}>
                        {strategySecondaryLabel(item)}
                      </div>
                    )}
                  </td>
                  <td>
                    <StatusChip
                      label={fmtLabel(strategyModeLabel(item))}
                      color={strategyModeLabel(item) === "package" ? ACCENT : "#2563EB"}
                    />
                  </td>
                  <td className="num-col tabular-nums text-right">
                    {fmtTRY2OrUnavailable(strategyPackageTotalTry(item))}
                  </td>
                  <td className="num-col tabular-nums text-right">
                    {fmtTRY2OrUnavailable(strategyItemizedTotalTry(item))}
                  </td>
                  <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                    {fmtTRY2OrUnavailable(item.savings_try ?? null)}
                  </td>
                </>
              ) : (
                <>
                  <td>
                    <div className="font-semibold text-slate-950">{item.chapter_description}</div>
                    <div className="mt-1 text-xs" style={{ color: "#71717A" }}>
                      {item.chapter}
                    </div>
                  </td>
                  <td>{item.ek2c_group}</td>
                  <td>
                    <StatusChip
                      label={fmtLabel(strategyModeLabel(item))}
                      color={strategyModeLabel(item) === "package" ? ACCENT : "#2563EB"}
                    />
                  </td>
                  <td className="num-col tabular-nums text-right">
                    {fmtTRY2OrUnavailable(strategyPackageTotalTry(item))}
                  </td>
                  <td className="num-col tabular-nums text-right">
                    {fmtTRY2OrUnavailable(strategyItemizedTotalTry(item))}
                  </td>
                  <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                    {fmtTRY2OrUnavailable(item.savings_try ?? null)}
                  </td>
                </>
              )}
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
  const hasExactListData =
    materialsData.pre_auth_required.length > 0 ||
    materialsData.miat_restricted.length > 0;
  const hasAnyData = hasExactListData || ceilingEntries.length > 0;

  if (!hasAnyData && materialsExact) {
    return null;
  }

  return (
    <BillingSectionShell title={t("billing.materials.title")}>
      <div className="space-y-4">
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
                    <td>{material.note}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {materialsData.miat_restricted.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B91C1C" }}>
              {t("billing.materials.miat")}
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
                    <td>{material.note}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {materialsExact && ceilingEntries.length > 0 && (
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
            <p className="text-xs text-[var(--text-secondary)]">
              {getUnavailableMessage(
                optimization.surcharge_exposure,
                t("billing.sutOptimization.surchargeUnavailable"),
              )}
            </p>
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
            <p className="text-xs text-[var(--text-secondary)]">
              {getUnavailableMessage(
                optimization.copay_rate_exposure,
                t("billing.sutOptimization.copayRateUnavailable"),
              )}
            </p>
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
              <p className="text-xs text-[var(--text-secondary)]">
                {t("billing.sutOptimization.potentialSavings", {
                  amount: fmtTRY2OrUnavailable(optimization.drg_unbundling.total_potential_savings),
                })}
              </p>
            ) : (
              <p className="text-xs text-[var(--text-secondary)]">
                {getUnavailableMessage(
                  optimization.drg_unbundling,
                  t("billing.sutOptimization.drgUnavailable"),
                )}
              </p>
            )}
          </Surface>
        )}
      </div>
    </BillingSectionShell>
  );
}
