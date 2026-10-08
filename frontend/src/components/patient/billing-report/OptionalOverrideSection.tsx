"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateStructuredApiMessage } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { formatSutSectionLabel, isClaimLevelStrategyRow, strategyBadgeColor, strategyItemizedTotalTry, strategyModeLabel, strategyPackageTotalTry, strategySavingsTryDisplay } from "@/lib/billingReportFields";
import { Chip, ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtLabel, fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, chipVariantFromColor, BillingSectionShell, TableWrap } from "./shared";

export function OptionalOverrideSection({
  strategyData,
  collapsed = false,
}: {
  strategyData: BillingActionReport["billing_strategy"];
  collapsed?: boolean;
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

  // Every row passed the `savings_try > 0` filter above (the backend's
  // optional_override_opportunities predicate), so no summed row lacks an amount.
  const totalUplift =
    strategyData.optional_override_uplift_try ??
    rows.reduce((sum, row) => sum + (row.savings_try ?? 0), 0);

  return (
    <BillingSectionShell
      id="billing-optional-override"
      title={t("billing.optionalOverride.title")}
      total={fmtTRY2(totalUplift)}
      collapsed={collapsed}
      count={rows.length}
      exactness={strategyData}
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
