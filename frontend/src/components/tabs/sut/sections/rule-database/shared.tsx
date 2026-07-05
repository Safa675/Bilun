"use client";

import type {
  FactCheckVerdict,
  RuleCatalogEntry,
  RuleClause,
  RuleCoverageStatus,
} from "@/lib/api/sut";
import {
  clauseUtilizationTier,
  UTILIZATION_CHIP_VARIANT,
  UTILIZATION_I18N_KEY,
} from "@/lib/clauseUtilization";
import { useLocale } from "@/lib/i18n";
import { useT } from "@/lib/i18n/useTranslations";
import { Chip } from "@/components/primitives";

export const COVERAGE_VARIANT: Record<RuleCoverageStatus, "success" | "warning" | "danger" | "neutral"> = {
  implemented: "success",
  partial: "warning",
  needs_claim_lines: "warning",
  missing: "danger",
  non_algorithmic: "neutral",
};

export const COVERAGE_KEY: Record<RuleCoverageStatus, string> = {
  implemented: "implemented",
  partial: "partial",
  needs_claim_lines: "needsClaimLines",
  missing: "missing",
  non_algorithmic: "nonAlgorithmic",
};

export const FACT_CHECK_VARIANT: Record<
  FactCheckVerdict,
  "success" | "warning" | "danger" | "neutral"
> = {
  COMPLIANT: "success",
  PARTIAL: "warning",
  HEURISTIC: "warning",
  NEEDS_CLAIM_LINES: "warning",
  WRONG: "danger",
  OUT_OF_SCOPE: "neutral",
};

export const FACT_CHECK_KEY: Record<FactCheckVerdict, string> = {
  COMPLIANT: "compliant",
  PARTIAL: "partial",
  HEURISTIC: "heuristic",
  NEEDS_CLAIM_LINES: "needsClaimLines",
  WRONG: "wrong",
  OUT_OF_SCOPE: "outOfScope",
};

export const STATUS_FILTERS: (RuleCoverageStatus | "all")[] = [
  "all",
  "implemented",
  "partial",
  "needs_claim_lines",
  "missing",
  "non_algorithmic",
];

export const CLAUSES_PER_PAGE = 25;

export function useLocalizedRule(rule: RuleCatalogEntry | null | undefined) {
  const locale = useLocale();
  if (!rule) {
    return { category: "", description: "" };
  }
  return {
    category: locale === "tr" && rule.rule_category_tr ? rule.rule_category_tr : rule.rule_category,
    description: locale === "tr" && rule.description_tr ? rule.description_tr : rule.description,
  };
}

export function useDeonticLabel(modality: string | null | undefined) {
  const t = useT();
  if (!modality) return null;
  const key = `sections.ruleDatabase.deontic.${modality}`;
  const translated = t(key, { modality });
  return translated === key ? modality : translated;
}

export function RuleDescription({ rule }: { rule: RuleCatalogEntry }) {
  const { description } = useLocalizedRule(rule);
  return (
    <p className="text-[11px] leading-snug text-[var(--text-secondary)]">
      {description}
    </p>
  );
}

export function CoverageChip({ status }: { status: RuleCoverageStatus }) {
  const t = useT();
  return (
    <Chip variant={COVERAGE_VARIANT[status]} className="text-[10px]">
      {t(`sections.ruleDatabase.status.${COVERAGE_KEY[status]}`)}
    </Chip>
  );
}

export function UtilizationChip({ clause }: { clause: RuleClause }) {
  const t = useT();
  const tier = clauseUtilizationTier(clause);
  return (
    <Chip variant={UTILIZATION_CHIP_VARIANT[tier]} className="text-[9px] uppercase tracking-wide">
      {t(UTILIZATION_I18N_KEY[tier])}
    </Chip>
  );
}

export function FactCheckChip({ verdict }: { verdict: FactCheckVerdict }) {
  const t = useT();
  return (
    <Chip variant={FACT_CHECK_VARIANT[verdict]} className="text-[10px]">
      {t(`sections.ruleDatabase.factCheck.verdict.${FACT_CHECK_KEY[verdict]}`)}
    </Chip>
  );
}
