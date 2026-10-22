"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { getSutAlertBadgeLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { translateStructuredApiMessage } from "@/lib/apiMessages";
import { copayCorrectionBilledTry, copayCorrectionGroundKey, copayCorrectionPayableTry, copayCorrectionProcedureLabel, copayCorrectionSavingsTry, copayCorrectedPayableTry, resolveCopayIlaveStatus, formatSutSectionLabel, usesClaimCopayCorrectionShape } from "@/lib/billingReportFields";
import { ExemptionBasisChips } from "@/components/sut/ExemptionBasisChips";
import { EkAnnexChips, RuleSourceAttribution } from "@/components/sut/RegulatorySourceChips";
import { Chip, ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable, KpiCard } from "@/components/tabs/sut/shared";
import { buildCopaySectionModel } from "./CopayOptimizationSection.model";
import { ACCENT, WRAPPED_HEADER_STYLE, chipVariantFromColor, BillingSectionShell, TableWrap } from "./shared";

export function CopayOptimizationSection({ copayData, onOpenClause }: {
  copayData: BillingActionReport["copay"];
  onOpenClause?: (clauseKey: string) => void;
}) {
  const t = useT();
  const model = buildCopaySectionModel(copayData);

  if (model.kind === "unavailable") {
    return (
      <BillingSectionShell title={t("billing.copay.title")}>
        <ExactnessNotice block={copayData} fallback={t("billing.copay.unavailable")} />
      </BillingSectionShell>
    );
  }

  const {
    copayExact,
    exemptionGapTotal,
    showIlaveColumn,
    ilaveTotal,
    copayOnlyDecomposition,
    insightOnlyRows,
    claimRows,
    claimScopedChips,
    hasWaiverGroundColumn,
    inpatientDrugGroundTotal,
    hasEk1aVisitSavings,
    ek1aWithoutWaivableLine,
    copayState,
    usesClaimTableHeader,
  } = model;
  const savingsColor = exemptionGapTotal != null && exemptionGapTotal > 0 ? ACCENT : "var(--text-muted)";

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
      total={copayExact ? exemptionGapTotal == null ? "—" : fmtTRY2(exemptionGapTotal) : undefined}
    >
      <div className="space-y-4">
        {!copayExact && (
          <ExactnessNotice block={copayData} fallback={t("billing.copay.unavailable")} />
        )}

        <div className="flex flex-wrap items-center gap-3">
          {copayState === "partial" ? (
            <Chip variant="warning">{getSutAlertBadgeLabel("ek1aReportMissing")}</Chip>
          ) : (
            <Chip variant={chipVariantFromColor(copayData.is_exempt ? ACCENT : "var(--text-disabled)")}>
              {copayData.is_exempt ? getSutAlertBadgeLabel("exempt") : getSutAlertBadgeLabel("notExempt")}
            </Chip>
          )}
          {copayData.is_exempt && (
            <Chip variant="outline">{t("billing.copay.medulaActionChip")}</Chip>
          )}
          {copayData.exemption_disease && (
            <span className="text-sm" style={{ color: "var(--text-muted)" }}>
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
              <KpiCard label={t("billing.copay.visitSavings")} value={copayData.visit_copay_savings_try == null ? "—" : fmtTRY2(copayData.visit_copay_savings_try)} valueColor={savingsColor} />
              <KpiCard label={t("billing.copay.rxSavings")} value={copayData.rx_copay_savings_try == null ? "—" : fmtTRY2(copayData.rx_copay_savings_try)} valueColor={savingsColor} />
              <KpiCard label={t("billing.copay.totalSavings")} value={exemptionGapTotal == null ? "—" : fmtTRY2(exemptionGapTotal)} valueColor={savingsColor} />
              {showIlaveColumn && (
                <KpiCard
                  label={t("billing.copay.ilaveUcretTotal")}
                  value={ilaveTotal == null ? "—" : fmtTRY2(ilaveTotal)}
                  valueColor="var(--text-muted)"
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
            {ek1aWithoutWaivableLine && (
              <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                {t("billing.copay.ek1aNoWaivableLine")}
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
                {usesClaimTableHeader ? (
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
                        if (!groundClauseKey || !onOpenClause) {
                          return label;
                        }
                        const coordinate = (correction.clause_ref?.clause_coordinate ?? "").trim();
                        return (
                          <span className="inline-flex flex-wrap items-center gap-2">
                            {label}
                            <button
                              type="button"
                              data-clause-link={groundClauseKey}
                              onClick={() => onOpenClause(groundClauseKey)}
                              title={coordinate ? formatSutSectionLabel(coordinate) : undefined}
                              className="rounded-[var(--r-sm)] border border-[var(--border-strong)] px-2 py-1 font-mono text-xs whitespace-nowrap hover:bg-[var(--surface-tint)]"
                            >
                              {t("billing.wavea.sutClause", { coordinate: formatSutSectionLabel(coordinate || groundClauseKey.split("#")[0]) })}
                            </button>
                          </span>
                        );
                      })()}
                    </td>
                  ) : null}
                  {usesClaimCopayCorrectionShape(correction) ? (
                    <>
                      <td className="num-col tabular-nums text-right whitespace-nowrap">
                        {fmtTRY2OrUnavailable(copayCorrectionBilledTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right whitespace-nowrap">
                        {fmtTRY2OrUnavailable(copayCorrectionPayableTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right whitespace-nowrap font-semibold text-[var(--gold)]">
                        {fmtTRY2OrUnavailable(copayCorrectionSavingsTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right whitespace-nowrap font-semibold text-[var(--success)]" title={t("billing.copay.correctedPayableTooltip")}>
                        {fmtTRY2OrUnavailable(copayCorrectedPayableTry(correction))}
                      </td>
                      {showIlaveColumn ? (
                        <td className="num-col tabular-nums text-right whitespace-nowrap text-xs text-[var(--text-secondary)]">
                          {(() => {
                            const status = resolveCopayIlaveStatus(correction);
                            if (status.kind === "numeric" && status.amount != null) {
                              return fmtTRY2(status.amount);
                            }
                            const label = t(status.labelKey, status.labelParams);
                            const tooltip = status.tooltipKey
                              ? t(status.tooltipKey, status.labelParams)
                              : undefined;
                            if (status.clauseKey && onOpenClause) {
                              return (
                                <span className="inline-flex flex-wrap items-center justify-end gap-2">
                                  {label}
                                  <button
                                    type="button"
                                    data-clause-link={status.clauseKey}
                                    onClick={() => onOpenClause(status.clauseKey)}
                                    title={tooltip}
                                    className="rounded-[var(--r-sm)] border border-[var(--border-strong)] px-2 py-1 font-mono text-xs whitespace-nowrap hover:bg-[var(--surface-tint)]"
                                  >
                                    {t("billing.wavea.sutClause", { coordinate: formatSutSectionLabel(status.clauseCoordinate || status.clauseKey.split("#")[0]) })}
                                  </button>
                                </span>
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
                      <td className="num-col tabular-nums text-right whitespace-nowrap">
                        {fmtTRY2OrUnavailable(copayCorrectionBilledTry(correction))}
                      </td>
                      <td className="num-col tabular-nums text-right whitespace-nowrap font-semibold text-[var(--text-primary)]">
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
    </BillingSectionShell>
  );
}
