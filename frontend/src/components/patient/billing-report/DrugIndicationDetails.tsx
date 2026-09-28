"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { getSutSeverityLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { WRAPPED_HEADER_STYLE, TableWrap } from "./shared";

type DrugReviewData = NonNullable<BillingActionReport["drug_indication"]>;

export function DrugIndicationLegacyTable({ violations }: { violations: DrugReviewData["violations"] }) {
  const t = useT();
  return (
    <details className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] p-4">
      <summary className="cursor-pointer font-semibold text-[var(--text-secondary)]">
        {t("billing.drugIndication.legacyDetails")}
      </summary>
      <TableWrap minWidth={1080}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.drug")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.violationKind")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.severity")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.primaryIcd10")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.ruleId")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.sutSection")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.message")}</th>
          </tr>
        </thead>
        <tbody>
          {violations.map((item, index) => (
            <tr key={`${item.claim_id}-${item.drug_claim_line_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>{item.drug_name ?? "—"}</td>
              <td className="font-mono text-xs">{item.violation_kind ?? "—"}</td>
              <td>{item.severity ? getSutSeverityLabel(item.severity) : "—"}</td>
              <td className="font-mono text-xs">{item.primary_icd10 ?? "—"}</td>
              <td className="font-mono text-xs">{item.rule_id ?? "—"}</td>
              <td>{item.sut_section ?? "—"}</td>
              <td>{item.message_tr ? translateApiText(item.message_tr) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </details>
  );
}

export function DrugIndicationEvaluationNotice({
  evaluations,
  hasCorpusNoncoverage,
}: {
  evaluations: NonNullable<DrugReviewData["evaluations"]>;
  hasCorpusNoncoverage: boolean;
}) {
  const t = useT();
  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] p-4">
      <p className="font-semibold text-[var(--text-primary)]">
        {hasCorpusNoncoverage
          ? t("billing.drugIndication.corpusNoncoverage")
          : t("billing.drugIndication.evaluationOnly")}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
        {hasCorpusNoncoverage
          ? t("billing.drugIndication.corpusNoncoverageDetail")
          : t("billing.drugIndication.evaluationOnlyDetail")}
      </p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[var(--text-secondary)]">
        {evaluations.map((item, index) => (
          <li key={`${item.drug_claim_line_id ?? item.drug_name ?? "drug"}-${index}`}>
            {item.drug_name ?? "—"}
          </li>
        ))}
      </ul>
    </div>
  );
}
