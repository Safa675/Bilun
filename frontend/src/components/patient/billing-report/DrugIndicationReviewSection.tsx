"use client";

import { useEffect, useRef } from "react";
import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { BillingSectionShell } from "./shared";
import { buildDrugIndicationSectionModel } from "./DrugIndicationReviewSection.model";
import { DrugIndicationFindingCard } from "./DrugIndicationFindingCard";
import { DrugIndicationLegacyTable, DrugIndicationEvaluationNotice } from "./DrugIndicationDetails";

export function DrugIndicationReviewSection({
  reviewData,
  selectedFindingId,
}: {
  reviewData: NonNullable<BillingActionReport["drug_indication"]>;
  selectedFindingId?: string | null;
}) {
  const t = useT();
  const { reviewExact, violationCount, display } = buildDrugIndicationSectionModel(reviewData);
  const findingRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!selectedFindingId) return;
    const target = findingRefs.current[selectedFindingId];
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.focus({ preventScroll: true });
  }, [reviewData.findings, selectedFindingId]);

  if (display.kind === "hidden") {
    return null;
  }

  return (
    <BillingSectionShell
      id="drug-indication"
      title={t("billing.drugIndication.title")}
      total={String(violationCount)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.drugIndication.scopeFootnote")}
      </p>
      {!reviewExact && (
        <ExactnessNotice block={reviewData} fallback={t("billing.drugIndication.unavailable")} className="mb-4" />
      )}
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
    </BillingSectionShell>
  );
}
