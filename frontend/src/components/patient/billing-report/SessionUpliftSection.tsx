"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { Chip, ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { amountCoverage, sumKnownAmounts } from "@/lib/workspaceViews";
import { WRAPPED_HEADER_STYLE, BillingRegulatorySourceCell, BillingSectionShell, TableWrap } from "./shared";

export function SessionUpliftSection({
  sessionData,
}: {
  sessionData: NonNullable<BillingActionReport["session_uplift"]>;
}) {
  const t = useT();
  const sessionExact = isExactOutput(sessionData);
  const opportunities = sessionData.opportunities ?? [];

  if (!sessionExact && opportunities.length === 0) {
    return (
      <BillingSectionShell id="billing-session-uplift" title={t("billing.sessionUplift.title")}>
        <ExactnessNotice block={sessionData} fallback={t("billing.sessionUplift.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (opportunities.length === 0) {
    return null;
  }

  // The reported confirmed total is used as-is. Only when it is absent do we sum
  // the rows, and a row without an uplift amount is unknown (its cell shows
  // "unavailable"), never zero: show a dash or a labelled partial total.
  const rowSum = sumKnownAmounts(
    opportunities
      .filter((row) => row.included_in_sgk_total !== false)
      .map((row) => row.recoverable_uplift_try),
  );
  const reportedConfirmed = sessionData.confirmed_uplift_try;
  const confirmedUplift = reportedConfirmed ?? rowSum.total;
  const totalCoverage = reportedConfirmed != null ? "complete" : amountCoverage(rowSum);
  const reviewUplift = sessionData.review_uplift_try ?? null;

  return (
    <BillingSectionShell
      id="billing-session-uplift"
      title={t("billing.sessionUplift.title")}
      total={totalCoverage === "none" ? "—" : fmtTRY2(confirmedUplift)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.sessionUplift.scopeFootnote")}
      </p>
      {totalCoverage !== "complete" && (
        <p className="mb-3 text-xs leading-relaxed text-[var(--text-secondary)]">
          {totalCoverage === "none"
            ? t("billing.sessionUplift.totalNone", { count: rowSum.count })
            : t("billing.sessionUplift.totalPartial", {
                known: rowSum.known,
                count: rowSum.count,
              })}
        </p>
      )}
      {reviewUplift != null && reviewUplift > 0 && (
        <p className="mb-3 text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.sessionUplift.reviewTotal")}: {fmtTRY2(reviewUplift)}
        </p>
      )}
      {!sessionExact && (
        <ExactnessNotice block={sessionData} fallback={t("billing.sessionUplift.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1080}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.procedure")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.primaryProcedure")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.sessionUplift.expectedBilled")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.sessionUplift.actualBilled")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.sessionUplift.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.sessionUplift.note")}</th>
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
                {item.review_kind === "needs_clinical_review" && (
                  <div className="mt-2">
                    <Chip variant="warning">{t("billing.sessionUplift.reviewBadge")}</Chip>
                  </div>
                )}
              </td>
              <td className="font-mono text-xs">{item.primary_procedure_code ?? "—"}</td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.expected_billed_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_billed_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {item.review_kind === "needs_clinical_review"
                  ? "—"
                  : fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={sessionData.rule_source} />
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
