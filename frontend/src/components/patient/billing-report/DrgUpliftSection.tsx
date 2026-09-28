"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, BillingRegulatorySourceCell, BillingSectionShell, TableWrap } from "./shared";

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
