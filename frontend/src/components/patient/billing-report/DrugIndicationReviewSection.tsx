"use client";

import { useEffect, useRef } from "react";
import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { buildDrugIndicationSectionModel } from "./DrugIndicationReviewSection.model";
import { DrugIndicationFindingCard } from "./DrugIndicationFindingCard";
import { DrugIndicationLegacyTable, DrugIndicationEvaluationNotice } from "./DrugIndicationDetails";

export function DrugIndicationReviewSection({
  reviewData,
  selectedFindingId,
  selectedSection,
}: {
  reviewData: NonNullable<BillingActionReport["drug_indication"]>;
  selectedFindingId?: string | null;
  selectedSection?: string | null;
}) {
  const t = useT();
  const { reviewExact, violationCount, display } = buildDrugIndicationSectionModel(reviewData);
  const findingRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!selectedFindingId) return;
    const target = findingRefs.current[selectedFindingId];
    if (!target) return;
    for (let ancestor = target.parentElement; ancestor; ancestor = ancestor.parentElement) {
      if (ancestor.tagName === "DETAILS") (ancestor as HTMLDetailsElement).open = true;
    }
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.focus({ preventScroll: true });
  }, [reviewData.findings, selectedFindingId]);

  if (display.kind === "hidden") {
    return null;
  }

  return (
    <details
      id="drug-indication"
      open={selectedSection === "drug-indication" || (display.kind === "structured" && display.findings.some((finding) => finding.finding_id === selectedFindingId)) || undefined}
      className="scroll-mt-24 rounded-[var(--r-lg)] border border-[var(--border-subtle)] bg-[var(--surface-base)] p-3"
    >
      <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">
        {t("billing.drugIndication.title")} · {display.kind === "empty" && reviewData.violation_count == null
          ? t("billing.wavea.countUnavailable") : violationCount}
        {!reviewExact && <ExactnessNotice block={reviewData} fallback={t("billing.drugIndication.unavailable")} className="mt-2" />}
        {display.kind === "structured" && display.findings.map((finding, index) => (
          <span key={finding.finding_id ?? index} className="mt-1 block text-xs font-normal text-[var(--text-secondary)]">
            {finding.drug_name || finding.drug_code || "—"} · {t(`billing.drugIndication.certaintyLabels.${finding.evaluation_status === "evaluated" ? "evaluated" : finding.evaluation_status === "missing_inputs" ? "missing_inputs" : "unavailable"}`)}
          </span>
        ))}
        {display.kind === "structured" && <span className="mt-1 block text-xs font-normal text-[var(--danger)]">
          {t("billing.drugIndication.riskNotice")}
        </span>}
        {display.kind === "evaluations" && <span className="mt-1 block text-xs font-normal text-[var(--text-secondary)]">
          {t(display.hasCorpusNoncoverage ? "billing.drugIndication.corpusNoncoverage" : "billing.drugIndication.evaluationOnly")}
          <span className="block">{t(display.hasCorpusNoncoverage ? "billing.drugIndication.corpusNoncoverageDetail" : "billing.drugIndication.evaluationOnlyDetail")}</span>
        </span>}
      </summary>
      <div className="mt-3">
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.drugIndication.scopeFootnote")}
      </p>
      {display.kind === "structured" ? (
        <div className="grid gap-3">
          {display.findings.map((finding, index) => (
            <DrugIndicationFindingCard
              key={finding.finding_id ?? `${finding.claim_id ?? "claim"}-${finding.drug_claim_line_id ?? index}`}
              finding={finding}
              selectedFindingId={selectedFindingId}
              articleRef={(node) => {
                if (finding.finding_id) findingRefs.current[finding.finding_id] = node;
              }}
            />
          ))}
        </div>
      ) : display.kind === "legacy" ? (
        <DrugIndicationLegacyTable violations={display.violations} />
      ) : display.kind === "evaluations" ? (
        <DrugIndicationEvaluationNotice
          evaluations={display.evaluations}
          hasCorpusNoncoverage={display.hasCorpusNoncoverage}
        />
      ) : null}
      </div>
    </details>
  );
}
