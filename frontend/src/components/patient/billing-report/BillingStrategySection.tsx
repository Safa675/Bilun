"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText, translateStructuredApiMessage } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { formatSutSectionLabel, isClaimLevelStrategyRow, isComplianceViolationRow, mergeClaimStrategyTableRows, strategyBadgeColor, strategyItemizedTotalTry, strategyModeLabel, strategyPackageTotalTry, strategyPaymentMethodKindMessageKey, strategyPrimaryLabel, strategyRecommendationKindMessageKey, strategyCatalogAsOfFootnote, strategyRowStatus, strategyRowStatusChipVariant, strategyRowStatusMessageKey, strategySavingsHeaderKey, strategySavingsTryDisplay, strategySecondaryLabel, usesHeuristicStrategyReviewShape } from "@/lib/billingReportFields";
import { Chip, ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtLabel, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { ACCENT, WRAPPED_HEADER_STYLE, chipVariantFromColor, BillingSectionShell, TableWrap } from "./shared";

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
