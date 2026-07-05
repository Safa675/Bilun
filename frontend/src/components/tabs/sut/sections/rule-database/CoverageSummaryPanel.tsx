"use client";

import type { CoverageSummary, RuleCoverageStatus } from "@/lib/api/sut";
import { Eyebrow, Stat, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtNum } from "../../shared";
import { CoverageChip } from "./shared";
import { GlossaryStrip } from "./GlossaryStrip";
import { GapCompositionBanner } from "./GapCompositionBanner";
import { PartialEnginePanel } from "./PartialEnginePanel";

export function CoverageSummaryPanel({ summary }: { summary: CoverageSummary }) {
  const t = useT();
  const { clauses, registry, meta, partial_engines: partialEngines } = summary;

  if (!meta.artifacts_available) {
    return (
      <Surface variant="soft" padding="md">
        <p className="text-sm text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.coverage.buildHint")}
        </p>
      </Surface>
    );
  }

  return (
    <Surface variant="soft" padding="md" className="space-y-4">
      <div className="flex items-center justify-between">
        <Eyebrow tone="primary">
          {t("sections.ruleDatabase.coverage.title")}
        </Eyebrow>
        {meta.generated_at && (
          <span className="text-xs text-[var(--text-muted)]">
            {t("sections.ruleDatabase.coverage.generatedAt", { date: meta.generated_at })}
          </span>
        )}
      </div>

      <GlossaryStrip
        clauseCount={clauses.total_extracted}
        ruleEngineCount={registry.total_rules}
        numberedClauseCount={clauses.numbered_clause_count ?? 0}
        proseClauseCount={clauses.prose_clause_count ?? 0}
        structuralClauseCount={clauses.structural_clause_count ?? 0}
      />

      <div className="grid grid-cols-2 gap-6">
        {/* Clauses column */}
        <div className="space-y-3">
          <Eyebrow tone="primary">
            {t("sections.ruleDatabase.coverage.clausesTitle")}
          </Eyebrow>
          <Stat
            label={t("sections.ruleDatabase.coverage.numberedClauses")}
            value={fmtNum(clauses.numbered_clause_count ?? 0)}
          />
          <p className="text-[11px] leading-tight text-[var(--text-muted)]">
            {t("sections.ruleDatabase.coverage.totalClausesNote", { count: fmtNum(clauses.total_extracted) })}
          </p>
          <Stat
            label={`${t("sections.ruleDatabase.coverage.algorithmicGaps")} (${clauses.algorithmic_gap_pct}%)`}
            value={fmtNum(clauses.algorithmic_gaps)}
            display="default"
          />
          <div className="space-y-1.5">
            {clauses.by_status.map((s) => (
              <div key={s.status} className="flex items-center justify-between text-xs">
                <CoverageChip status={s.status as RuleCoverageStatus} />
                <span className="tabular-nums text-[var(--text-secondary)]">{fmtNum(s.count)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Registry column */}
        <div className="space-y-3">
          <Eyebrow tone="primary">
            {t("sections.ruleDatabase.coverage.registryTitle")}
          </Eyebrow>
          <Stat
            label={t("sections.ruleDatabase.coverage.totalRuleEngines")}
            value={fmtNum(registry.total_rules)}
          />
          <div className="space-y-1.5">
            {registry.by_status.map((s) => (
              <div key={s.status} className="flex items-center justify-between text-xs">
                <CoverageChip status={s.status as RuleCoverageStatus} />
                <span className="tabular-nums text-[var(--text-secondary)]">{fmtNum(s.count)}</span>
              </div>
            ))}
          </div>
          {registry.zero_clause_matches.length > 0 && (
            <Surface variant="soft" padding="sm" className="border-[color-mix(in_srgb,var(--warning)_30%,transparent)] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)]">
              <p className="text-xs text-[var(--text-secondary)]">
                {t("sections.ruleDatabase.coverage.zeroClauseWarning")}: {fmtNum(registry.zero_clause_matches.length)}
              </p>
            </Surface>
          )}
        </div>
      </div>

      {clauses.top_gap_categories.length > 0 && (
        <div className="space-y-2 border-t border-[var(--border-subtle)] pt-3">
          <Eyebrow tone="primary">
            {t("sections.ruleDatabase.coverage.topGapCategories")}
          </Eyebrow>
          <div className="flex flex-wrap gap-2">
            {clauses.top_gap_categories.map((cat) => (
              <span
                key={cat.category}
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2.5 py-1 text-xs text-[var(--text-secondary)]"
              >
                <span>{cat.category}</span>
                <span className="tabular-nums font-semibold">{fmtNum(cat.count)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.gap_composition && <GapCompositionBanner summary={summary} />}

      {partialEngines &&
        (partialEngines.drug_indication_prose ||
          partialEngines.material_bundling_prose ||
          partialEngines.specialty_materials_prose ||
          partialEngines.payment_method_2_2 ||
          partialEngines.copay_general_1_8) && (
        <div className="space-y-3 border-t border-[var(--border-subtle)] pt-3">
          <Eyebrow tone="primary">
            {t("sections.ruleDatabase.coverage.partialEnginesTitle")}
          </Eyebrow>
          <div className="space-y-3">
            {partialEngines.drug_indication_prose && (
              <PartialEnginePanel
                engine={partialEngines.drug_indication_prose}
                showTierC
                showSubsections
              />
            )}
            {partialEngines.material_bundling_prose && (
              <PartialEnginePanel engine={partialEngines.material_bundling_prose} />
            )}
            {partialEngines.specialty_materials_prose && (
              <PartialEnginePanel engine={partialEngines.specialty_materials_prose} />
            )}
            {partialEngines.payment_method_2_2 && (
              <PartialEnginePanel engine={partialEngines.payment_method_2_2} />
            )}
            {partialEngines.copay_general_1_8 && (
              <PartialEnginePanel engine={partialEngines.copay_general_1_8} />
            )}
          </div>
        </div>
      )}
    </Surface>
  );
}
