"use client";

import type { CSSProperties, ReactNode } from "react";
import type { BillingActionReport, PatientOptimization } from "@/lib/domains/sut";
import { SUT_ALERT_BADGE_LABELS } from "@/lib/sutLabels";
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
} from "@/lib/billingReportFields";
import { theme } from "@/lib/theme";
import { SUT_BRAND } from "@/lib/constants";
import { Chip, DataTable, Eyebrow, Section, Stat, Surface } from "@/components/primitives";
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
  const reportExact = isExactOutput(billingReport);
  const reportHasTotals = hasRecoverableBillingTotals(billingReport);
  const priorityColor = reportHasTotals ? PRIORITY_COLORS[billingReport.priority] : "#71717A";
  const statusLabel = reportExact
    ? fmtPriorityLabel(billingReport.priority)
    : reportHasTotals
      ? "Partial exact"
      : "Unavailable";

  return (
    <Surface variant="base" padding="lg" className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Eyebrow>{SUT_BRAND.billingTitle}</Eyebrow>
          <p className="mt-1 font-mono text-base text-[var(--text-secondary)]">
            {billingReport.patient_id}
          </p>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
            Normative SUT rule review across labs, drugs, copay policy, billing strategy, and materials controls.
          </p>
        </div>
        <StatusChip label={statusLabel} color={priorityColor} />
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Stat
          label="Rule-calculated opportunity"
          value={
            reportHasTotals
              ? fmtTRY2(billingReport.total_recoverable_try)
              : "Unavailable"
          }
          display={reportHasTotals ? "gold" : "default"}
        />
        <Stat
          label="Recommended actions"
          value={reportHasTotals ? fmtNum(billingReport.action_count) : "Review sections"}
        />
        <Stat
          label="Priority tier"
          value={
            <span style={{ color: priorityColor }}>
              {reportHasTotals ? fmtPriorityLabel(billingReport.priority) : "Unavailable"}
            </span>
          }
        />
      </div>
      {!reportExact && reportHasTotals && (
        <ExactnessNotice
          block={billingReport}
          fallback="Section totals are exact where marked; review section-level exactness before treating the aggregate as fully exact."
        />
      )}
      {!reportHasTotals && (
        <ExactnessNotice
          block={billingReport}
          fallback="Billing totals remain unavailable until every billing section is exact."
        />
      )}
    </Surface>
  );
}

export function LabOptimizationSection({ labData }: { labData: BillingActionReport["lab"] }) {
  if (!isExactOutput(labData)) {
    return (
      <BillingSectionShell title="Lab optimization">
        <ExactnessNotice
          block={labData}
          fallback="Lab optimization findings are unavailable until the billing input contract is exact."
        />
      </BillingSectionShell>
    );
  }

  if (labData.flagged_tests.length === 0) {
    return null;
  }

  const combinedSavings = labData.hemogram_bundling_savings + labData.duplicate_test_savings;

  return (
    <BillingSectionShell title="Lab optimization" total={fmtTRY2(combinedSavings)}>
      <TableWrap minWidth={820}>
        <thead>
          <tr>
            <th>Test</th>
            <th>SUT code</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Gazette price</th>
            <th>Flag</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Savings</th>
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
  if (!isExactOutput(drugData)) {
    return (
      <BillingSectionShell title="Drug optimization">
        <ExactnessNotice
          block={drugData}
          fallback="Drug optimization savings require exact dispensed drug claim lines and billed drug amounts."
        />
      </BillingSectionShell>
    );
  }

  if (drugData.drug_recommendations.length === 0) {
    return null;
  }

  return (
    <BillingSectionShell title="Drug optimization" total={fmtTRY2(drugData.generic_substitution_savings)}>
      <TableWrap minWidth={860}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>Drug</th>
            <th>Issue</th>
            <th style={WRAPPED_HEADER_STYLE}>Alternative</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Savings</th>
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
              <td title={recommendation.issue === "discount_tier_applied" ? (recommendation.detail || "Tier correction on same drug") : recommendation.alternative}>
                {recommendation.issue === "discount_tier_applied" ? "Tier correction" : recommendation.alternative}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2(recommendation.savings_try)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function CopayOptimizationSection({ copayData }: { copayData: BillingActionReport["copay"] }) {
  if (!isExactOutput(copayData)) {
    return (
      <BillingSectionShell title="Copay optimization">
        <ExactnessNotice
          block={copayData}
          fallback="Copay optimization totals remain unavailable until both visit and prescription claim inputs are exact."
        />
      </BillingSectionShell>
    );
  }

  const savingsColor = copayData.total_copay_savings_try > 0 ? ACCENT : "#71717A";

  return (
    <BillingSectionShell title="Copay optimization" total={fmtTRY2(copayData.total_copay_savings_try)}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <StatusChip
            label={copayData.is_exempt ? SUT_ALERT_BADGE_LABELS.exempt : SUT_ALERT_BADGE_LABELS.notExempt}
            color={copayData.is_exempt ? ACCENT : "#A1A1AA"}
          />
          {copayData.exemption_disease && (
            <span className="text-sm" style={{ color: "#71717A" }}>
              {copayData.exemption_disease} ({copayData.exemption_range})
            </span>
          )}
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <KpiCard label="Visit copay savings" value={fmtTRY2(copayData.visit_copay_savings_try)} valueColor={savingsColor} />
          <KpiCard label="Rx copay savings" value={fmtTRY2(copayData.rx_copay_savings_try)} valueColor={savingsColor} />
          <KpiCard label="Total copay savings" value={fmtTRY2(copayData.total_copay_savings_try)} valueColor={savingsColor} />
        </div>

        {copayData.rate_corrections.length > 0 && (
          <TableWrap minWidth={760}>
            <thead>
              <tr>
                <th>Procedure</th>
                {usesClaimCopayCorrectionShape(copayData.rate_corrections[0]) ? (
                  <>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Billed</th>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Payable</th>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Copay component</th>
                  </>
                ) : (
                  <>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Gazette rate</th>
                    <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Correction</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {copayData.rate_corrections.map((correction, index) => (
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
  const strategyExact = isExactOutput(strategyData);

  if (!strategyExact) {
    return (
      <BillingSectionShell title="Billing strategy">
        <div className="sut-exactness-notice">
          {getUnavailableMessage(
            strategyData,
            "Billing strategy recommendations require exact billed procedure lines.",
          )}
        </div>
      </BillingSectionShell>
    );
  }

  if (strategyData.recommendations.length === 0) {
    return null;
  }

  return (
    <BillingSectionShell title="Billing strategy">
      <TableWrap minWidth={980}>
        <thead>
          <tr>
            {usesClaimStrategyShape(strategyData.recommendations[0]) ? (
              <>
                <th style={WRAPPED_HEADER_STYLE}>Claim</th>
                <th>Recommendation</th>
              </>
            ) : (
              <>
                <th style={WRAPPED_HEADER_STYLE}>Chapter</th>
                <th>Group</th>
                <th>Strategy</th>
              </>
            )}
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Package total</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Itemized total</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Savings</th>
          </tr>
        </thead>
        <tbody>
          {strategyData.recommendations.map((item, index) => (
            <tr key={`${strategyPrimaryLabel(item)}-${index}`}>
              {usesClaimStrategyShape(item) ? (
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
                </>
              )}
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(strategyPackageTotalTry(item))}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(strategyItemizedTotalTry(item))}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2(item.savings_try)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

export function MaterialsPreCheckSection({ materialsData }: { materialsData: BillingActionReport["materials"] }) {
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
    <BillingSectionShell title="Materials pre-check">
      <div className="space-y-4">
        {!materialsExact && (
          <ExactnessNotice
            block={materialsData}
            fallback="Material ceiling estimates remain unavailable until this section is fully exact."
          />
        )}
        {materialsData.pre_auth_required.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#D97706" }}>
              Pre-authorization required
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>SUT code</th>
                  <th>Material</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Gazette price</th>
                  <th style={WRAPPED_HEADER_STYLE}>Note</th>
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
              MIAT restricted
            </p>
            <TableWrap minWidth={900}>
              <thead>
                <tr>
                  <th>SUT code</th>
                  <th>Material</th>
                  <th style={WRAPPED_HEADER_STYLE}>MIAT period</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>Gazette price</th>
                  <th style={WRAPPED_HEADER_STYLE}>Note</th>
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
            <Eyebrow>Gazette ceiling (p90) by specialty</Eyebrow>
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
  const surchargeExact = isExactOutput(optimization.surcharge_exposure);
  const rateExact = isExactOutput(optimization.copay_rate_exposure);
  const drgExact = isExactOutput(optimization.drg_unbundling);
  const surchargeCount = optimization.surcharge_exposure.n_applicable_procedures;
  const rateCount = optimization.copay_rate_exposure.n_applicable_procedures;
  const drgRiskLabel = optimization.drg_unbundling?.has_unbundling_risk ? fmtRiskLabel("high") : fmtRiskLabel("low");

  return (
    <BillingSectionShell title="SUT optimization findings">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>Copay exemption</Eyebrow>
          <Chip variant={optimization.copay_exemptions.exempt ? "success" : "neutral"}>
            {optimization.copay_exemptions.exempt
              ? SUT_ALERT_BADGE_LABELS.exempt
              : SUT_ALERT_BADGE_LABELS.notExempt}
          </Chip>
          <p className="text-xs text-[var(--text-secondary)]">
            {fmtNum(optimization.copay_exemptions.qualifying_diagnoses.length)} qualifying diagnoses
          </p>
        </Surface>

        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>Surcharge compliance</Eyebrow>
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
                ? `${fmtNum(surchargeCount ?? 0)} flags`
                : SUT_ALERT_BADGE_LABELS.clear)
              : SUT_ALERT_BADGE_LABELS.unavailable}
          </Chip>
          {!surchargeExact && (
            <p className="text-xs text-[var(--text-secondary)]">
              {getUnavailableMessage(
                optimization.surcharge_exposure,
                "Surcharge compliance needs exact billed procedure codes and procedure dates.",
              )}
            </p>
          )}
        </Surface>

        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>Copay rate compliance</Eyebrow>
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            {rateExact
              ? ((rateCount ?? 0) > 0
                ? `${fmtNum(rateCount ?? 0)} capped procedures`
                : "No rate caps applicable")
              : "Unavailable"}
          </p>
          {!rateExact && (
            <p className="text-xs text-[var(--text-secondary)]">
              {getUnavailableMessage(
                optimization.copay_rate_exposure,
                "Copay rate compliance needs exact billed procedure codes and procedure dates.",
              )}
            </p>
          )}
        </Surface>

        {optimization.drg_unbundling && (
          <Surface variant="soft" padding="md" className="space-y-2">
            <Eyebrow>DRG unbundling risk</Eyebrow>
            <Chip
              variant={
                !drgExact
                  ? "neutral"
                  : optimization.drg_unbundling.has_unbundling_risk
                    ? "danger"
                    : "success"
              }
            >
              {drgExact ? drgRiskLabel : SUT_ALERT_BADGE_LABELS.unavailable}
            </Chip>
            {drgExact ? (
              <p className="text-xs text-[var(--text-secondary)]">
                Potential savings: {fmtTRY2OrUnavailable(optimization.drg_unbundling.total_potential_savings)}
              </p>
            ) : (
              <p className="text-xs text-[var(--text-secondary)]">
                {getUnavailableMessage(
                  optimization.drg_unbundling,
                  "DRG unbundling risk needs exact itemized billed procedure lines and package eligibility context.",
                )}
              </p>
            )}
          </Surface>
        )}
      </div>
    </BillingSectionShell>
  );
}
