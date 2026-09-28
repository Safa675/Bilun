"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, BillingRegulatorySourceCell, BillingSectionShell, TableWrap } from "./shared";

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
