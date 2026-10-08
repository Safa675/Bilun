"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, BillingRegulatorySourceCell, BillingSectionShell, TableWrap } from "./shared";

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

  const confirmedUplift = addonData.confirmed_uplift_try ?? null;

  return (
    <BillingSectionShell
      id="billing-procedure-addon-uplift"
      title={t("billing.procedureAddonUplift.title")}
      total={confirmedUplift == null ? "—" : fmtTRY2(confirmedUplift)}
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
