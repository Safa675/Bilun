"use client";

import type { PartialEngineCoverage } from "@/lib/api/sut";
import { Eyebrow, Stat, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtNum } from "../../shared";

export function PartialEnginePanel({
  engine,
  showTierC,
  showSubsections,
}: {
  engine: PartialEngineCoverage;
  showTierC?: boolean;
  showSubsections?: boolean;
}) {
  const t = useT();
  const subsections = showSubsections ? engine.subsection_coverage : undefined;
  const subsectionKeys = subsections ? Object.keys(subsections).sort() : [];

  return (
    <Surface variant="base" padding="sm" className="space-y-3 border border-[var(--border-subtle)]">
      <p className="font-mono text-[11px] font-semibold text-[var(--text-primary)]">
        {engine.rule_id}
      </p>
      <p className="text-xs text-[var(--text-muted)]">{engine.honesty_note}</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat
          label={t("sections.ruleDatabase.coverage.partialEngineEncoded")}
          value={`${fmtNum(engine.encoded_clause_rows)} (${engine.encoded_clause_pct}%)`}
        />
        {engine.deferred_gap_rows != null && engine.deferred_gap_rows > 0 && (
          <Stat
            label={t("sections.ruleDatabase.coverage.partialEngineDeferred")}
            value={fmtNum(engine.deferred_gap_rows)}
          />
        )}
        {engine.true_gap_rows != null && (
          <Stat
            label={t("sections.ruleDatabase.coverage.partialEngineTrueGaps")}
            value={fmtNum(engine.true_gap_rows)}
          />
        )}
        <Stat
          label={t("sections.ruleDatabase.coverage.partialEngineRulesOnDisk")}
          value={fmtNum(engine.prose_rules_on_disk)}
        />
        {engine.manifest_traced_clause_count != null && (
          <Stat
            label={t("sections.ruleDatabase.coverage.partialEngineManifestTraced")}
            value={fmtNum(engine.manifest_traced_clause_count)}
          />
        )}
        {engine.algorithmic_gap_rows > 0 && (
          <>
            <Stat
              label={t("sections.ruleDatabase.coverage.partialEngineGaps")}
              value={fmtNum(engine.algorithmic_gap_rows)}
            />
            <Stat
              label={t("sections.ruleDatabase.coverage.partialEngineUnencodedGaps")}
              value={fmtNum(engine.unencoded_gap_rows)}
            />
          </>
        )}
        {engine.kdv_pricing_clauses != null && engine.kdv_pricing_clauses > 0 && (
          <Stat
            label={t("sections.ruleDatabase.coverage.partialEngineKdvClauses")}
            value={fmtNum(engine.kdv_pricing_clauses)}
          />
        )}
        {showTierC && engine.encode_tier_c_deferred_count != null && (
          <Stat
            label={t("sections.ruleDatabase.coverage.partialEngineTierCDeferred")}
            value={fmtNum(engine.encode_tier_c_deferred_count)}
          />
        )}
      </div>
      {subsectionKeys.length > 0 && (
        <div className="space-y-1.5 border-t border-[var(--border-subtle)] pt-2">
          <Eyebrow tone="primary">
            {t("sections.ruleDatabase.coverage.partialEngineSubsections")}
          </Eyebrow>
          <div className="space-y-1">
            {subsectionKeys.map((sectionKey) => {
              const row = subsections![sectionKey];
              return (
                <div
                  key={sectionKey}
                  className="flex items-center justify-between text-xs text-[var(--text-secondary)]"
                >
                  <span className="font-mono">§{sectionKey}</span>
                  <span className="tabular-nums">
                    {fmtNum(row.encoded_clause_count)}/{fmtNum(row.clause_total)} (
                    {row.encoded_clause_pct}%)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Surface>
  );
}
