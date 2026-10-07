"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, BillingRegulatorySourceCell, BillingSectionShell, TableWrap } from "./shared";

export function DrgPackageAdequacyReviewSection({
  reviewData,
}: {
  reviewData: NonNullable<BillingActionReport["drg_package_adequacy"]>;
}) {
  const t = useT();
  const reviewExact = isExactOutput(reviewData);
  const opportunities = reviewData.opportunities ?? [];

  if (!reviewExact && opportunities.length === 0) {
    return null;
  }
  if (opportunities.length === 0) {
    return null;
  }

  const reviewUplift = reviewData.review_uplift_try ?? reviewData.total_uplift_try ?? null;

  return (
    <BillingSectionShell id="billing-drg-package-adequacy" title={t("billing.packageAdequacyReview.title")}>
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.packageAdequacyReview.scopeFootnote")}
      </p>
      {reviewUplift != null && reviewUplift > 0 && (
        <p className="mb-3 text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.careSettingReview.reviewTotal")}: {fmtTRY2(reviewUplift)}
        </p>
      )}
      {!reviewExact && (
        <ExactnessNotice block={reviewData} fallback={t("billing.packageAdequacyReview.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1200}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.primaryIcd10")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.clinicalProcedures")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.currentPackage")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.candidatePackage")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.packageAdequacyReview.currentPrice")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.packageAdequacyReview.candidatePrice")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.packageAdequacyReview.reviewDelta")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.packageAdequacyReview.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${item.candidate_package_code}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td className="font-mono text-xs">{item.primary_icd10 ?? "—"}</td>
              <td className="font-mono text-xs">
                {(item.clinical_procedure_codes ?? []).join(", ") || "—"}
              </td>
              <td>
                <div className="font-semibold text-slate-950">{item.current_package_code ?? "—"}</div>
                {(item.current_package_footprint ?? []).length > 0 && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {(item.current_package_footprint ?? []).join(", ")}
                  </div>
                )}
              </td>
              <td>
                <div className="font-semibold text-slate-950">{item.candidate_package_code ?? "—"}</div>
                {(item.candidate_package_footprint ?? []).length > 0 && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {(item.candidate_package_footprint ?? []).join(", ")}
                  </div>
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.current_package_price_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.candidate_package_price_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={reviewData.rule_source} />
              </td>
              <td>{item.detail ? translateApiText(item.detail) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}
