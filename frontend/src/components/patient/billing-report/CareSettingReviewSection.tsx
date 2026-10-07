"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { getPaymentMethodKindLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { Chip, ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, BillingRegulatorySourceCell, BillingSectionShell, TableWrap } from "./shared";

export function CareSettingReviewSection({
  reviewData,
}: {
  reviewData: NonNullable<BillingActionReport["care_setting_review"]>;
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
    <BillingSectionShell id="billing-care-setting-review" title={t("billing.careSettingReview.title")}>
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.careSettingReview.scopeFootnote")}
      </p>
      {reviewUplift != null && reviewUplift > 0 && (
        <p className="mb-3 text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.careSettingReview.reviewTotal")}: {fmtTRY2(reviewUplift)}
        </p>
      )}
      {!reviewExact && (
        <ExactnessNotice block={reviewData} fallback={t("billing.careSettingReview.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1120}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.claimType")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.actualSetting")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.alternateSetting")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.careSettingReview.actualBest")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.careSettingReview.alternateBest")}
            </th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.careSettingReview.uplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.common.regulatorySource")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.careSettingReview.note")}</th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((item, index) => (
            <tr key={`${item.claim_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>{item.claim_type ? translateApiText(item.claim_type) : "—"}</td>
              <td>
                <div>{item.actual_care_setting ? translateApiText(item.actual_care_setting) : "—"}</div>
                {item.actual_payment_method_kind && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {getPaymentMethodKindLabel(item.actual_payment_method_kind)}
                  </div>
                )}
              </td>
              <td>
                <div>{item.alternate_care_setting ? translateApiText(item.alternate_care_setting) : "—"}</div>
                {item.alternate_payment_method_kind && (
                  <div className="mt-1 font-mono text-xs" style={{ color: "#71717A" }}>
                    {getPaymentMethodKindLabel(item.alternate_payment_method_kind)}
                  </div>
                )}
                {item.review_kind === "needs_clinical_review" && (
                  <div className="mt-2">
                    <Chip variant="warning">{t("billing.careSettingReview.reviewBadge")}</Chip>
                  </div>
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.actual_best_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right">
                {fmtTRY2OrUnavailable(item.alternate_best_try ?? null)}
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(item.recoverable_uplift_try ?? null)}
              </td>
              <td>
                <BillingRegulatorySourceCell ruleSource={reviewData.rule_source} />
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
