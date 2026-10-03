"use client";

import type { CoverageEvidence } from "@/lib/api/sut";
import { Eyebrow, Stat } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtNum } from "../../shared";

export function CoverageEvidencePanel({ evidence }: { evidence: CoverageEvidence }) {
  const t = useT();
  const value = (count: number | null | undefined) =>
    count == null ? t("sections.ruleDatabase.coverage.evidenceUnknown") : fmtNum(count);
  return (
    <section className="space-y-3 border-b border-[var(--border-subtle)] pb-3">
      <Eyebrow tone="primary">{t("sections.ruleDatabase.coverage.evidenceTitle")}</Eyebrow>
      <div className="grid grid-cols-2 gap-3">
        <Stat label={t("sections.ruleDatabase.coverage.evidenceSource")}
          value={value(evidence.available ? evidence.source_represented_clause_count : null)} />
        <Stat label={t("sections.ruleDatabase.coverage.evidencePredicate")}
          value={value(evidence.available ? evidence.executable_predicate_rule_count : null)} />
        <Stat label={t("sections.ruleDatabase.coverage.evidenceInputs")}
          value={value(evidence.available ? evidence.inputs_available_count : null)} />
        <Stat label={t("sections.ruleDatabase.coverage.evidenceEvaluated")}
          value={value(evidence.available ? evidence.actually_evaluated_count : null)} />
      </div>
      <p className="text-xs text-[var(--text-muted)]">
        {t("sections.ruleDatabase.coverage.evidenceNote")}
      </p>
    </section>
  );
}
