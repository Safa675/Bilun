"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateStructuredApiMessage } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, BillingRegulatorySourceCell, BillingSectionShell, TableWrap } from "./shared";

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
