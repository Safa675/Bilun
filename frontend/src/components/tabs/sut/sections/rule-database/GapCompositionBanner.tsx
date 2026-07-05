"use client";

import type { CoverageSummary } from "@/lib/api/sut";
import { Eyebrow, Stat, Surface } from "@/components/primitives";
import { useLocale } from "@/lib/i18n";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtNum } from "../../shared";

export function GapCompositionBanner({ summary }: { summary: CoverageSummary }) {
  const t = useT();
  const locale = useLocale();
  const composition = summary.gap_composition;
  if (!composition || composition.total_algorithmic_gaps <= 0) {
    return null;
  }
  const footnote =
    locale === "tr" && composition.footnote_tr
      ? composition.footnote_tr
      : composition.footnote_en;

  return (
    <Surface
      variant="soft"
      padding="md"
      className="border-[color-mix(in_srgb,var(--primary)_20%,transparent)] bg-[color-mix(in_srgb,var(--primary)_6%,transparent)]"
    >
      <Eyebrow tone="primary">{t("sections.ruleDatabase.coverage.gapCompositionTitle")}</Eyebrow>
      <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">{footnote}</p>
      <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat
          label={t("sections.ruleDatabase.coverage.gapCompositionDrugShare")}
          value={`${composition.drug_indication_gap_pct_of_gaps}%`}
        />
        <Stat
          label={t("sections.ruleDatabase.coverage.gapCompositionOptimizerExDrug")}
          value={fmtNum(composition.optimizer_gaps_excluding_drug)}
        />
        <Stat
          label={t("sections.ruleDatabase.coverage.gapCompositionNonAlgorithmic")}
          value={fmtNum(composition.non_algorithmic_clause_rows)}
        />
        <Stat
          label={t("sections.ruleDatabase.coverage.algorithmicGaps")}
          value={fmtNum(composition.total_algorithmic_gaps)}
        />
      </div>
    </Surface>
  );
}
