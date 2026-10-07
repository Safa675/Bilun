"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtDate } from "@/lib/i18n/formatters";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput, isOptionalIngestPending } from "@/lib/sutExactness";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, BillingSectionShell, TableWrap } from "./shared";

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

  const gapTotal = captureData.confirmed_gap_try ?? captureData.total_gap_try ?? null;

  return (
    <BillingSectionShell id="billing-procedure-capture-gap" title={t("billing.procedureCaptureGap.title")} total={gapTotal == null ? "—" : fmtTRY2(gapTotal)}>
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
