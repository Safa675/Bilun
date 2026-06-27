"use client";

import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import {
  getClause,
  getProseInventory,
  getRuleCatalog,
  getRuleDetail,
  getRuleSections,
  getSectionClauses,
  listClauses,
  sectionRollupRowKey,
  type CoverageSummary,
  type FactCheckRollup,
  type FactCheckVerdict,
  type PartialEngineCoverage,
  type RuleCatalogEntry,
  type RuleClause,
  type RuleCoverageStatus,
  type RuleDetailResponse,
  type SectionClausesResponse,
  type SectionRollupEntry,
  type SectionRollupResponse,
} from "@/lib/api/sut";
import { isAbortError } from "@/lib/api/request";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import {
  Chip,
  Section,
  Surface,
  TabsRoot,
  TabsList,
  TabsTrigger,
  TabsContent,
  Toolbar,
  DataTable,
  DataTableHeader,
  DataTableHeaderCell,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  Eyebrow,
  Stat,
} from "@/components/primitives";
import { EkAnnexChips } from "@/components/sut/RegulatorySourceChips";
import { useSutApi } from "../useSutApi";
import { fmtNum } from "../shared";
import { useLocale } from "@/lib/i18n";
import { useT } from "@/lib/i18n/useTranslations";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  clauseUtilizationTier,
  ruleMotorLabel,
  UTILIZATION_CHIP_VARIANT,
  UTILIZATION_I18N_KEY,
} from "@/lib/clauseUtilization";

const COVERAGE_VARIANT: Record<RuleCoverageStatus, "success" | "warning" | "danger" | "neutral"> = {
  implemented: "success",
  partial: "warning",
  needs_claim_lines: "warning",
  missing: "danger",
  non_algorithmic: "neutral",
};

const COVERAGE_KEY: Record<RuleCoverageStatus, string> = {
  implemented: "implemented",
  partial: "partial",
  needs_claim_lines: "needsClaimLines",
  missing: "missing",
  non_algorithmic: "nonAlgorithmic",
};

const FACT_CHECK_VARIANT: Record<
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

const FACT_CHECK_KEY: Record<FactCheckVerdict, string> = {
  COMPLIANT: "compliant",
  PARTIAL: "partial",
  HEURISTIC: "heuristic",
  NEEDS_CLAIM_LINES: "needsClaimLines",
  WRONG: "wrong",
  OUT_OF_SCOPE: "outOfScope",
};

const STATUS_FILTERS: (RuleCoverageStatus | "all")[] = [
  "all",
  "implemented",
  "partial",
  "needs_claim_lines",
  "missing",
  "non_algorithmic",
];

const CLAUSES_PER_PAGE = 25;

function useLocalizedRule(rule: RuleCatalogEntry | null | undefined) {
  const locale = useLocale();
  if (!rule) {
    return { category: "", description: "" };
  }
  return {
    category: locale === "tr" && rule.rule_category_tr ? rule.rule_category_tr : rule.rule_category,
    description: locale === "tr" && rule.description_tr ? rule.description_tr : rule.description,
  };
}

function useDeonticLabel(modality: string | null | undefined) {
  const t = useT();
  if (!modality) return null;
  const key = `sections.ruleDatabase.deontic.${modality}`;
  const translated = t(key, { modality });
  return translated === key ? modality : translated;
}

function RuleDescription({ rule }: { rule: RuleCatalogEntry }) {
  const { description } = useLocalizedRule(rule);
  return (
    <p className="text-[11px] leading-snug text-[var(--text-secondary)]">
      {description}
    </p>
  );
}

function CoverageChip({ status }: { status: RuleCoverageStatus }) {
  const t = useT();
  return (
    <Chip variant={COVERAGE_VARIANT[status]} className="text-[10px]">
      {t(`sections.ruleDatabase.status.${COVERAGE_KEY[status]}`)}
    </Chip>
  );
}

function UtilizationChip({ clause }: { clause: RuleClause }) {
  const t = useT();
  const tier = clauseUtilizationTier(clause);
  return (
    <Chip variant={UTILIZATION_CHIP_VARIANT[tier]} className="text-[9px] uppercase tracking-wide">
      {t(UTILIZATION_I18N_KEY[tier])}
    </Chip>
  );
}

function GlossaryStrip({
  clauseCount,
  ruleEngineCount,
}: {
  clauseCount: number;
  ruleEngineCount: number;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  // Live figures fetched once from the prose-inventory + section rollup endpoints
  // (previously hardcoded 337 / 951 / 481, which drifted after pipeline rebuilds).
  const [jsonRuleCount, setJsonRuleCount] = useState<number | null>(null);
  const [sectionRows, setSectionRows] = useState<number | null>(null);
  const [uniqueSections, setUniqueSections] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const inv = await getProseInventory();
        if (!active) return;
        const sum = (inv.engines ?? [])
          .reduce((acc, e) => acc + (e.rule_count ?? 0), 0);
        setJsonRuleCount(sum);
      } catch {
        /* leave null — UI falls back */
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [rows, unique] = await Promise.all([
          getRuleSections({ per_page: 1, page: 1 }),
          getRuleSections({ per_page: 1, page: 1, consolidate: true }),
        ]);
        if (!active) return;
        setSectionRows(rows.total);
        setUniqueSections(unique.total);
      } catch {
        /* leave null */
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-soft)] px-3 py-2.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-[11px] font-medium text-[var(--text-secondary)]"
      >
        <span>{t("sections.ruleDatabase.coverage.glossary.toggle")}</span>
        <span className="text-[var(--text-muted)]">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <dl className="mt-2 space-y-1.5 text-[11px] leading-relaxed text-[var(--text-secondary)]">
          <div>
            <dt className="font-semibold text-[var(--text-primary)]">Hüküm</dt>
            <dd>
              {t("sections.ruleDatabase.coverage.glossary.hukum", { count: fmtNum(clauseCount) })}
            </dd>
          </div>
          <div>
            <dd>
              {t("sections.ruleDatabase.coverage.glossary.kuralMotoru", {
                count: ruleEngineCount,
              })}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-[var(--text-primary)]">JSON</dt>
            <dd>
              {t("sections.ruleDatabase.coverage.glossary.jsonSatir", { count: fmtNum(jsonRuleCount ?? 0) })}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-[var(--text-primary)]">§</dt>
            <dd>
              {t("sections.ruleDatabase.coverage.glossary.bolumSatiri", {
                count: fmtNum(sectionRows ?? 0),
                unique: fmtNum(uniqueSections ?? 0),
              })}
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
}

function FactCheckChip({ verdict }: { verdict: FactCheckVerdict }) {
  const t = useT();
  return (
    <Chip variant={FACT_CHECK_VARIANT[verdict]} className="text-[10px]">
      {t(`sections.ruleDatabase.factCheck.verdict.${FACT_CHECK_KEY[verdict]}`)}
    </Chip>
  );
}

function FactCheckRollupBanner({ rollup }: { rollup: FactCheckRollup }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const { by_verdict: counts } = rollup;
  const items = (
    [
      ["COMPLIANT", counts.COMPLIANT],
      ["PARTIAL", counts.PARTIAL],
      ["HEURISTIC", counts.HEURISTIC],
      ["NEEDS_CLAIM_LINES", counts.NEEDS_CLAIM_LINES],
      ["WRONG", counts.WRONG],
    ] as const
  ).filter(([, n]) => n > 0);

  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-soft)] px-3 py-2.5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-left"
      >
        <div>
          <p className="text-xs font-semibold text-[var(--text-secondary)]">
            {t("sections.ruleDatabase.factCheck.title")}
          </p>
          <p className="text-[10px] text-[var(--text-muted)]">
            {t("sections.ruleDatabase.factCheck.subtitle")}
          </p>
        </div>
        <span className="text-[10px] text-[var(--text-muted)]">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-2 border-t border-[var(--border-subtle)] pt-2">
          <p className="text-[10px] text-[var(--text-muted)]">
            {t("sections.ruleDatabase.factCheck.banner", {
              closed: rollup.audit_closed,
              total: fmtNum(rollup.total_units),
            })}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {items.map(([verdict, count]) => (
              <span
                key={verdict}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]"
              >
                <FactCheckChip verdict={verdict} />
                <span className="tabular-nums font-semibold">{fmtNum(count)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GapCompositionBanner({ summary }: { summary: CoverageSummary }) {
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

function PartialEnginePanel({
  engine,
  showTierC,
}: {
  engine: PartialEngineCoverage;
  showTierC?: boolean;
}) {
  const t = useT();

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
    </Surface>
  );
}

function CoverageSummaryPanel({ summary }: { summary: CoverageSummary }) {
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
      />

      <div className="grid grid-cols-2 gap-6">
        {/* Clauses column */}
        <div className="space-y-3">
          <Eyebrow tone="primary">
            {t("sections.ruleDatabase.coverage.clausesTitle")}
          </Eyebrow>
          <Stat
            label={t("sections.ruleDatabase.coverage.totalClauses")}
            value={fmtNum(clauses.total_extracted)}
          />
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
          partialEngines.specialty_materials_prose) && (
        <div className="space-y-3 border-t border-[var(--border-subtle)] pt-3">
          <Eyebrow tone="primary">
            {t("sections.ruleDatabase.coverage.partialEnginesTitle")}
          </Eyebrow>
          <div className="space-y-3">
            {partialEngines.drug_indication_prose && (
              <PartialEnginePanel
                engine={partialEngines.drug_indication_prose}
                showTierC
              />
            )}
            {partialEngines.material_bundling_prose && (
              <PartialEnginePanel engine={partialEngines.material_bundling_prose} />
            )}
            {partialEngines.specialty_materials_prose && (
              <PartialEnginePanel engine={partialEngines.specialty_materials_prose} />
            )}
          </div>
        </div>
      )}
    </Surface>
  );
}

const SECTIONS_PER_PAGE = 25;

function SectionBrowserPanel({
  onNavigateToRule,
  onUrlUpdate,
}: {
  onNavigateToRule?: (ruleId: string) => void;
  onUrlUpdate?: (updates: Record<string, string | null>) => void;
}) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [minGapCount, setMinGapCount] = useState<string>("");
  const [page, setPage] = useState(1);
  const [consolidate, setConsolidate] = useState(false);
  const [selectedSection, setSelectedSection] = useState<SectionRollupEntry | null>(null);

  // Stable filter inputs: empty string -> undefined so the API client omits the
  // query param and the effect's dependency identity matches backend semantics.
  const trimmedQuery = query.trim();
  const parsedGapCount = minGapCount ? parseInt(minGapCount, 10) : undefined;

  const [result, setResult] = useState<SectionRollupResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Refetch on any filter/page change (mirrors RuleDetailPanel's effect below).
  // NOTE: `useSutApi` is a fetch-once-when-enabled hook and silently ignores
  // param changes after the first load — wrong for a paginated/filtered panel.
  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getRuleSections(
          {
            page,
            per_page: SECTIONS_PER_PAGE,
            q: trimmedQuery || undefined,
            min_gap_count: parsedGapCount,
            consolidate: consolidate || undefined,
          },
          { signal: controller.signal },
        );
        if (!active || controller.signal.aborted) return;
        setResult(res);
      } catch (err) {
        if (!active || isAbortError(err)) return;
        setResult(null);
        setError(
          err instanceof Error ? err.message : t("sections.ruleDatabase.errors.loadFailed"),
        );
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [page, trimmedQuery, parsedGapCount, consolidate, t]);

  if (loading) {
    return <SutReferenceSectionSkeleton title={t("sections.ruleDatabase.sections.title")} />;
  }

  if (error) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <Chip variant="danger">{error}</Chip>
      </Surface>
    );
  }

  if (!result || !result.artifacts_available) {
    return (
      <Surface variant="soft" padding="lg" className="text-center">
        <p className="text-sm text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.sections.artifactsUnavailable")}
        </p>
      </Surface>
    );
  }

  const sections = result.sections;
  const totalPages = result.total_pages;

  return (
    <div className="space-y-4">
      <Toolbar
        leading={
          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            placeholder={t("sections.ruleDatabase.sections.searchPlaceholder")}
            className="sut-input min-w-[220px] max-w-[360px]"
          />
        }
        trailing={
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              value={minGapCount}
              onChange={(e) => { setMinGapCount(e.target.value); setPage(1); }}
              placeholder={t("sections.ruleDatabase.sections.minGapFilter")}
              className="sut-input w-[140px]"
            />
            <button
              type="button"
              onClick={() => { setConsolidate((v) => !v); setPage(1); }}
              className={`sut-section-btn sut-section-btn-compact text-[11px] whitespace-nowrap ${
                consolidate ? "sut-section-btn-active" : ""
              }`}
            >
              {t("sections.ruleDatabase.sections.consolidate")}
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-3">
          {sections.length === 0 ? (
            <Surface variant="soft" padding="md" className="text-center">
              <p className="text-sm text-[var(--text-secondary)]">
                {t("sections.ruleDatabase.sections.noMatches")}
              </p>
            </Surface>
          ) : (
            <>
              <DataTable minWidth={600}>
                <DataTableHeader>
                  <DataTableRow>
                    <DataTableHeaderCell className="text-left font-medium">
                      {t("sections.ruleDatabase.sections.columnSection")}
                    </DataTableHeaderCell>
                    <DataTableHeaderCell className="text-left font-medium">
                      {t("sections.ruleDatabase.sections.columnTitle")}
                    </DataTableHeaderCell>
                    <DataTableHeaderCell className="text-right font-medium">
                      {t("sections.ruleDatabase.sections.columnClauses")}
                    </DataTableHeaderCell>
                    <DataTableHeaderCell className="text-right font-medium">
                      {t("sections.ruleDatabase.sections.columnGaps")}
                    </DataTableHeaderCell>
                    <DataTableHeaderCell className="text-left font-medium">
                      {t("sections.ruleDatabase.sections.columnStatus")}
                    </DataTableHeaderCell>
                    <DataTableHeaderCell className="text-left font-medium">
                      {t("sections.ruleDatabase.sections.columnCategories")}
                    </DataTableHeaderCell>
                  </DataTableRow>
                </DataTableHeader>
                <DataTableBody>
                  {sections.map((section) => {
                    const isSelected =
                      selectedSection && sectionRollupRowKey(selectedSection) === sectionRollupRowKey(section);
                    return (
                      <DataTableRow
                        key={sectionRollupRowKey(section)}
                        onClick={() => {
                          setSelectedSection(section);
                          onUrlUpdate?.({ rdSection: section.section_id });
                        }}
                        className="cursor-pointer transition-colors hover:bg-[var(--surface-default)]"
                        {...(isSelected ? { "data-selected": true } : {})}
                      >
                        <DataTableCell className="font-mono text-xs text-[var(--text-primary)]">
                          {section.section_id}
                        </DataTableCell>
                        <DataTableCell className="text-xs text-[var(--text-secondary)]">
                          {section.section_title ?? "—"}
                        </DataTableCell>
                        <DataTableCell className="text-right text-xs tabular-nums text-[var(--text-secondary)]">
                          {fmtNum(section.clause_count)}
                        </DataTableCell>
                        <DataTableCell className="text-right text-xs tabular-nums text-[var(--danger)]">
                          {fmtNum(section.gap_clause_count)}
                        </DataTableCell>
                        <DataTableCell>
                          {section.worst_coverage_status && (
                            <Chip
                              variant={COVERAGE_VARIANT[section.worst_coverage_status as RuleCoverageStatus]}
                            >
                              {t(
                                `sections.ruleDatabase.status.${COVERAGE_KEY[section.worst_coverage_status as RuleCoverageStatus]}`,
                              )}
                            </Chip>
                          )}
                        </DataTableCell>
                        <DataTableCell>
                          <div className="flex flex-wrap gap-1">
                            {section.primary_categories.map((cat) => (
                              <Chip key={cat} variant="outline">
                                {cat}
                              </Chip>
                            ))}
                          </div>
                        </DataTableCell>
                      </DataTableRow>
                    );
                  })}
                </DataTableBody>
              </DataTable>

              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-3 text-sm text-[var(--text-muted)]">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="sut-section-btn sut-section-btn-compact disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {t("sections.ruleDatabase.pagination.prev")}
                  </button>
                  <span>
                    {t("sections.ruleDatabase.pagination.page", {
                      page: fmtNum(page),
                      totalPages: fmtNum(totalPages),
                    })}
                  </span>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="sut-section-btn sut-section-btn-compact disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {t("sections.ruleDatabase.pagination.next")}
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        <SectionDetailPane section={selectedSection} onNavigateToRule={onNavigateToRule} />
      </div>
    </div>
  );
}

function SectionDetailPane({
  section,
  onNavigateToRule,
}: {
  section: SectionRollupEntry | null;
  onNavigateToRule?: (ruleId: string) => void;
}) {
  const t = useT();
  const [clausePage, setClausePage] = useState(1);
  const [result, setResult] = useState<SectionClausesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sectionKey = section ? sectionRollupRowKey(section) : null;

  // Reset to page 1 when selection changes.
  useEffect(() => {
    setClausePage(1);
  }, [sectionKey]);

  useEffect(() => {
    if (!section) return;
    // Short-circuit: zero clauses → skip fetch.
    if (section.clause_count === 0) {
      setResult(null);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    let active = true;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getSectionClauses(
          {
            section_id: section.section_id!,
            section_title: section.section_title ?? undefined,
            page: clausePage,
            per_page: SECTIONS_PER_PAGE,
          },
          { signal: controller.signal },
        );
        if (!active || controller.signal.aborted) return;
        setResult(res);
      } catch (err) {
        if (!active || isAbortError(err)) return;
        setResult(null);
        setError(
          err instanceof Error ? err.message : t("sections.ruleDatabase.errors.loadFailed"),
        );
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [section, clausePage, t]);

  if (!section) {
    return (
      <Surface variant="soft" padding="md" className="h-full">
        <p className="text-sm text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.sections.detailPrompt")}
        </p>
      </Surface>
    );
  }

  const clauses = result?.clauses ?? [];
  const totalPages = result?.total_pages ?? 0;

  return (
    <Surface variant="soft" padding="md" className="h-full">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="font-mono text-sm font-semibold text-[var(--text-primary)]">
          {section.section_id}
          {section.section_title ? ` · ${section.section_title}` : ""}
        </h4>
        <span className="text-[11px] text-[var(--text-muted)]">
          {t("sections.ruleDatabase.sections.detailStats", {
            clauses: fmtNum(section.clause_count),
            gaps: fmtNum(section.gap_clause_count ?? 0),
          })}
        </span>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">{t("common.loading")}</p>
      ) : error ? (
        <p className="text-sm text-[var(--danger)]">{error}</p>
      ) : section.clause_count === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.detail.noClauses")}
        </p>
      ) : clauses.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.detail.noClauses")}
        </p>
      ) : (
        <>
          <ul className="space-y-2">
            {clauses.map((clause) => (
              <ClauseCard key={clause.clause_id} clause={clause} onNavigateToRule={onNavigateToRule} />
            ))}
          </ul>
          {totalPages > 1 && (
            <div className="mt-3 flex items-center justify-center gap-2 text-xs text-[var(--text-muted)]">
              <button
                type="button"
                disabled={clausePage <= 1}
                onClick={() => setClausePage((p) => Math.max(1, p - 1))}
                className="sut-section-btn sut-section-btn-compact disabled:opacity-50"
              >
                {t("sections.ruleDatabase.pagination.prev")}
              </button>
              <span>
                {t("sections.ruleDatabase.sections.clausePage", {
                  page: fmtNum(clausePage),
                  total: fmtNum(totalPages),
                })}
              </span>
              <button
                type="button"
                disabled={clausePage >= totalPages}
                onClick={() => setClausePage((p) => p + 1)}
                className="sut-section-btn sut-section-btn-compact disabled:opacity-50"
              >
                {t("sections.ruleDatabase.pagination.next")}
              </button>
            </div>
          )}
        </>
      )}
    </Surface>
  );
}

function ClauseBrowserPanel({
  initialQuery = "",
  initialClauseId,
  rules,
  onNavigateToRule,
  onUrlUpdate,
}: {
  initialQuery?: string;
  initialClauseId?: string | null;
  rules?: RuleCatalogEntry[] | null;
  onNavigateToRule?: (ruleId: string) => void;
  onUrlUpdate?: (updates: Record<string, string | null>) => void;
}) {
  const t = useT();
  const [query, setQuery] = useState(initialQuery);
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [gapFilter, setGapFilter] = useState(false);
  const [encodingFilter, setEncodingFilter] = useState(false);
  const [hideReferans, setHideReferans] = useState(true);
  const [ruleFilter, setRuleFilter] = useState<string>("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<SectionClausesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedClause, setSelectedClause] = useState<RuleClause | null>(null);

  // Re-sync query when parent passes a new initialQuery (e.g. prose anchor click).
  useEffect(() => {
    if (initialQuery) setQuery(initialQuery);
  }, [initialQuery]);

  // Deep link: ?rdClause=C002684 → fetch and pre-select that clause on mount.
  useEffect(() => {
    if (!initialClauseId) return;
    let active = true;
    (async () => {
      try {
        const clause = await getClause(initialClauseId);
        if (active && clause) setSelectedClause(clause);
      } catch {
        /* clause may not exist; silently ignore */
      }
    })();
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 300ms debounce on search input.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Reset to page 1 on any filter change.
  useEffect(() => {
    setPage(1);
  }, [debouncedQuery, statusFilter, gapFilter, encodingFilter, ruleFilter, hideReferans]);

  // Abort-aware fetch.
  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await listClauses(
          {
            q: debouncedQuery || undefined,
            page,
            per_page: CLAUSES_PER_PAGE,
            coverage_status: statusFilter || undefined,
            has_gap: gapFilter || undefined,
            has_encoding: encodingFilter || undefined,
            primary_rule_id: ruleFilter || undefined,
            exclude_non_algorithmic: hideReferans || undefined,
          },
          { signal: controller.signal },
        );
        if (!active || controller.signal.aborted) return;
        setResult(res);
        // Auto-select first clause in the results.
        if (res.clauses.length > 0) {
          setSelectedClause(res.clauses[0]);
        } else {
          setSelectedClause(null);
        }
      } catch (err) {
        if (!active || isAbortError(err)) return;
        setResult(null);
        setError(
          err instanceof Error ? err.message : t("sections.ruleDatabase.errors.loadFailed"),
        );
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [debouncedQuery, statusFilter, gapFilter, encodingFilter, ruleFilter, hideReferans, page, t]);

  const clauses = result?.clauses ?? [];
  const totalPages = result?.total_pages ?? 0;
  const total = result?.clause_total ?? 0;

  return (
    <div className="space-y-4">
      <Toolbar
        leading={
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("sections.ruleDatabase.clauses.searchPlaceholder")}
            className="sut-input min-w-[220px] max-w-[360px]"
          />
        }
        trailing={
          <div className="flex items-center gap-2">
            {STATUS_FILTERS.map((status) => (
              <button
                key={status}
                type="button"
                onClick={() =>
                  setStatusFilter((prev) => (prev === status ? "" : status))
                }
                className={`sut-section-btn sut-section-btn-compact text-[11px] ${
                  statusFilter === status ? "sut-section-btn-active" : ""
                }`}
              >
                {status === "all"
                  ? t("sections.ruleDatabase.filters.all")
                  : t(`sections.ruleDatabase.status.${COVERAGE_KEY[status]}`)}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setHideReferans((v) => !v)}
              className={`sut-section-btn sut-section-btn-compact text-[11px] ${
                hideReferans ? "sut-section-btn-active" : ""
              }`}
            >
              {t("sections.ruleDatabase.clauses.filterHideReferans")}
            </button>
            <button
              type="button"
              onClick={() => setGapFilter((v) => !v)}
              className={`sut-section-btn sut-section-btn-compact text-[11px] ${
                gapFilter ? "sut-section-btn-active" : ""
              }`}
            >
              {t("sections.ruleDatabase.clauses.filterGap")}
            </button>
            <button
              type="button"
              onClick={() => setEncodingFilter((v) => !v)}
              className={`sut-section-btn sut-section-btn-compact text-[11px] ${
                encodingFilter ? "sut-section-btn-active" : ""
              }`}
            >
              {t("sections.ruleDatabase.clauses.filterEncoded")}
            </button>
            {rules && rules.length > 0 && (
              <select
                value={ruleFilter}
                onChange={(e) => setRuleFilter(e.target.value)}
                className="sut-input max-w-[220px] truncate text-[11px]"
                aria-label={t("sections.ruleDatabase.clauses.filterMotor")}
              >
                <option value="">{t("sections.ruleDatabase.clauses.filterMotor")}</option>
                {rules.map((r) => (
                  <option key={r.rule_id} value={r.rule_id}>
                    {ruleMotorLabel(r.rule_id, t)}
                  </option>
                ))}
              </select>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-3">
          {error ? (
            <Surface variant="soft" padding="md" className="text-center">
              <p className="text-sm text-[var(--danger)]">{error}</p>
            </Surface>
          ) : clauses.length === 0 && !loading ? (
            <Surface variant="soft" padding="md" className="text-center">
              <p className="text-sm text-[var(--text-secondary)]">
                {t("sections.ruleDatabase.detail.noClauses")}
              </p>
            </Surface>
          ) : (
            <>
              <div className="text-[11px] text-[var(--text-muted)]">
                {t("sections.ruleDatabase.clauses.resultCount", { count: fmtNum(total) })}
              </div>
              <ul className="space-y-1.5">
                {clauses.map((clause) => {
                  const isSelected =
                    selectedClause?.clause_id === clause.clause_id;
                  return (
                    <li
                      key={clause.clause_id}
                      onClick={() => {
                        setSelectedClause(clause);
                        onUrlUpdate?.({ rdClause: clause.clause_id });
                      }}
                      className={`cursor-pointer rounded-[var(--r-sm)] border px-3 py-2 transition-colors hover:bg-[var(--surface-default)] ${
                        isSelected
                          ? "border-[var(--accent)] bg-[var(--surface-default)]"
                          : "border-[var(--border-subtle)]"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {clause.clause_id && (
                          <span className="rounded bg-[var(--surface-default)] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[var(--text-secondary)]">
                            {clause.clause_id}
                          </span>
                        )}
                        <UtilizationChip clause={clause} />
                        {clause.primary_rule_id && (
                          <span className="font-mono text-[10px] text-[var(--text-muted)]">
                            {clause.primary_rule_id}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-[var(--text-secondary)]">
                        {clause.text_tr}
                      </p>
                    </li>
                  );
                })}
              </ul>

              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-3 text-sm text-[var(--text-muted)]">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="sut-section-btn sut-section-btn-compact disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {t("sections.ruleDatabase.pagination.prev")}
                  </button>
                  <span>
                    {t("sections.ruleDatabase.pagination.page", {
                      page: fmtNum(page),
                      totalPages: fmtNum(totalPages),
                    })}
                  </span>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="sut-section-btn sut-section-btn-compact disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {t("sections.ruleDatabase.pagination.next")}
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Detail pane */}
        {selectedClause ? (
          <div>
            <ClauseCard clause={selectedClause} onNavigateToRule={onNavigateToRule} />
          </div>
        ) : (
          <Surface variant="soft" padding="md" className="h-full">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("sections.ruleDatabase.sections.detailPrompt")}
            </p>
          </Surface>
        )}
      </div>
    </div>
  );
}

function ProseInventoryPanel({
  onAnchorClick,
}: {
  onAnchorClick?: (anchor: string) => void;
}) {
  const t = useT();
  const {
    data: result,
    loading,
    error,
  } = useSutApi((opts) => getProseInventory(opts), {
    enabled: true,
    errorFallback: t("sections.ruleDatabase.errors.loadFailed"),
  });

  if (loading) {
    return <SutReferenceSectionSkeleton title={t("sections.ruleDatabase.prose.title")} />;
  }

  if (error) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <Chip variant="danger">{error}</Chip>
      </Surface>
    );
  }

  if (!result || !result.artifacts_available) {
    return (
      <Surface variant="soft" padding="lg" className="text-center">
        <p className="text-sm text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.prose.artifactsUnavailable")}
        </p>
      </Surface>
    );
  }

  const engines = result.engines;

  if (engines.length === 0) {
    return (
      <Surface variant="soft" padding="md" className="text-center">
        <p className="text-xs text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.prose.noEngines")}
        </p>
      </Surface>
    );
  }

  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] overflow-hidden">
      <table className="w-full text-[11px]">
        <thead className="bg-[var(--surface-soft)] text-[var(--text-muted)] uppercase tracking-wide">
          <tr>
            <th className="px-2 py-1.5 text-left font-medium">
              {t("sections.ruleDatabase.prose.ruleSet")}
            </th>
            <th className="px-2 py-1.5 text-left font-medium">
              {t("sections.ruleDatabase.prose.fileName")}
            </th>
            <th className="px-2 py-1.5 text-left font-medium">
              {t("sections.ruleDatabase.prose.effectiveDate")}
            </th>
            <th className="px-2 py-1.5 text-right font-medium">
              {t("sections.ruleDatabase.prose.ruleCount")}
            </th>
            <th className="px-2 py-1.5 text-left font-medium">
              {t("sections.ruleDatabase.prose.anchors")}
            </th>
          </tr>
        </thead>
        <tbody>
          {engines.map((engine) => (
            <tr
              key={engine.rule_set_id}
              className="border-t border-[var(--border-subtle)] hover:bg-[var(--surface-soft)]"
            >
              <td className="px-2 py-1.5 font-semibold text-[var(--text-primary)]">
                {engine.rule_set_id}
              </td>
              <td className="px-2 py-1.5 font-mono text-[var(--text-secondary)]">
                {engine.file_name}
              </td>
              <td className="px-2 py-1.5 text-[var(--text-secondary)]">
                {engine.effective_date ?? "—"}
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums text-[var(--text-secondary)]">
                {engine.rule_count ?? "—"}
              </td>
              <td className="px-2 py-1.5">
                <div className="flex flex-wrap gap-1">
                  {engine.sut_anchors.map((anchor) => (
                    <button
                      key={anchor}
                      type="button"
                      onClick={() => onAnchorClick?.(anchor)}
                      className="cursor-pointer transition-opacity hover:opacity-70"
                    >
                      <Chip variant="outline" className="text-[9px]">
                        {anchor}
                      </Chip>
                    </button>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RuleSourceChips({ rule }: { rule: RuleCatalogEntry }) {
  const sections = rule.sources.sut_sections;
  const annexes = rule.sources.annexes;
  if (sections.length === 0 && annexes.length === 0) {
    return null;
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <EkAnnexChips labels={annexes} />
      {sections.map((s) => (
        <Chip key={s} variant="outline" className="font-mono text-[10px]">
          {s}
        </Chip>
      ))}
    </span>
  );
}

export function RuleDatabaseSection() {
  const t = useT();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<RuleCoverageStatus | "all">("all");
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);

  // URL state: use rdTab/rdClause/rdSection to avoid colliding with the outer
  // app-shell ?tab= param (see constants.ts parseSutHomeTab).
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<string>(
    searchParams.get("rdTab") || "rules",
  );
  const [clauseSearchQ, setClauseSearchQ] = useState<string>(
    searchParams.get("rdSection") || "",
  );
  const initialClauseId = searchParams.get("rdClause");

  const updateUrl = (updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    updateUrl({ rdTab: tab });
  };

  const handleAnchorClick = (anchor: string) => {
    setActiveTab("clauses");
    setClauseSearchQ(anchor);
    updateUrl({ rdTab: "clauses", rdSection: anchor });
  };

  const handleNavigateToRule = (ruleId: string) => {
    setSelectedRuleId(ruleId);
    setActiveTab("rules");
    updateUrl({ rdTab: "rules", rdClause: null, rdSection: null });
  };

  const {
    data: catalog,
    loading,
    error,
  } = useSutApi((opts) => getRuleCatalog(opts), {
    enabled: true,
    errorFallback: t("sections.ruleDatabase.errors.loadFailed"),
  });

  const rules = catalog?.rules ?? null;
  const artifactsAvailable = catalog?.artifacts_available ?? true;

  const zeroClauseRuleIds = useMemo(() => {
    const matches = catalog?.coverage_summary?.registry?.zero_clause_matches ?? [];
    return new Set(matches.map((m) => m.rule_id));
  }, [catalog?.coverage_summary?.registry?.zero_clause_matches]);

  const filteredRules = useMemo(() => {
    if (!rules) return [];
    const needle = query.trim().toLowerCase();
    return rules.filter((rule) => {
      if (statusFilter !== "all" && rule.coverage_status !== statusFilter) return false;
      if (!needle) return true;
      const haystack = [
        rule.rule_id,
        rule.rule_category,
        rule.description,
        ...rule.sources.annexes,
        ...rule.sources.sut_sections,
        ...rule.keywords,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [rules, query, statusFilter]);

  const activeRuleId = selectedRuleId || (filteredRules.length > 0 ? filteredRules[0].rule_id : null);

  if (loading) return <SutReferenceSectionSkeleton title={t("sections.ruleDatabase.title")} />;

  if (error) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <Chip variant="danger">{error}</Chip>
      </Surface>
    );
  }

  return (
    <Section
      title={t("sections.ruleDatabase.title")}
      description={t("sections.ruleDatabase.subtitle", { total: fmtNum(rules?.length ?? 0) })}
      variant="inset"
      padding="none"
    >
      <Surface variant="base" padding="lg" className="space-y-4">
        {catalog?.coverage_summary && <CoverageSummaryPanel summary={catalog.coverage_summary} />}

        {!artifactsAvailable && (
          <Surface variant="soft" padding="md">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("sections.ruleDatabase.artifactsUnavailable")}
            </p>
          </Surface>
        )}

        {catalog?.fact_check && <FactCheckRollupBanner rollup={catalog.fact_check} />}

        <TabsRoot value={activeTab} onValueChange={handleTabChange}>
          <TabsList density="compact">
            <TabsTrigger value="rules" density="compact">
              {t("sections.ruleDatabase.tabs.rules")}
            </TabsTrigger>
            <TabsTrigger value="sections" density="compact">
              {t("sections.ruleDatabase.tabs.sections")}
            </TabsTrigger>
            <TabsTrigger value="clauses" density="compact">
              {t("sections.ruleDatabase.tabs.clauses")}
            </TabsTrigger>
            <TabsTrigger value="prose" density="compact">
              {t("sections.ruleDatabase.tabs.prose")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="rules" forceMount className="data-[state=inactive]:hidden">
            <div className="space-y-4 pt-4">
              <Toolbar
                leading={
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={t("sections.ruleDatabase.searchPlaceholder")}
                    className="sut-input min-w-[220px] max-w-[360px]"
                  />
                }
              >
                <div className="flex items-center gap-1.5 overflow-x-auto max-w-full no-scrollbar py-0.5">
                  {STATUS_FILTERS.map((status) => (
                    <button
                      key={status}
                      type="button"
                      onClick={() => setStatusFilter(status)}
                      className={`sut-section-btn sut-section-btn-compact ${statusFilter === status ? "sut-section-btn-active" : ""}`}
                    >
                      <span className="text-xs font-semibold">
                        {status === "all"
                          ? t("sections.ruleDatabase.filters.all")
                          : t(`sections.ruleDatabase.status.${COVERAGE_KEY[status]}`)}
                      </span>
                    </button>
                  ))}
                </div>
              </Toolbar>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-[340px_1fr]">
                <RuleList
                  rules={filteredRules}
                  selectedRuleId={activeRuleId}
                  onSelect={setSelectedRuleId}
                  zeroClauseRuleIds={zeroClauseRuleIds}
                />
                {activeRuleId ? (
                  <RuleDetailPanel
                    key={activeRuleId}
                    ruleId={activeRuleId}
                    artifactsAvailable={artifactsAvailable}
                    onNavigateToRule={handleNavigateToRule}
                  />
                ) : (
                  <Surface variant="soft" padding="lg" className="flex items-center justify-center">
                    <p className="text-sm text-[var(--text-secondary)]">
                      {t("sections.ruleDatabase.detail.selectPrompt")}
                    </p>
                  </Surface>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="sections" forceMount className="data-[state=inactive]:hidden">
            <div className="pt-4">
              <SectionBrowserPanel
                onNavigateToRule={handleNavigateToRule}
                onUrlUpdate={updateUrl}
              />
            </div>
          </TabsContent>

          <TabsContent value="clauses" forceMount className="data-[state=inactive]:hidden">
            <div className="pt-4">
              <ClauseBrowserPanel
                initialQuery={clauseSearchQ}
                initialClauseId={initialClauseId}
                rules={rules}
                onNavigateToRule={handleNavigateToRule}
                onUrlUpdate={updateUrl}
              />
            </div>
          </TabsContent>

          <TabsContent value="prose" forceMount className="data-[state=inactive]:hidden">
            <div className="pt-4">
              <ProseInventoryPanel onAnchorClick={handleAnchorClick} />
            </div>
          </TabsContent>
        </TabsRoot>
      </Surface>
    </Section>
  );
}

function RuleList({
  rules,
  selectedRuleId,
  onSelect,
  zeroClauseRuleIds,
}: {
  rules: RuleCatalogEntry[];
  selectedRuleId: string | null;
  onSelect: (ruleId: string) => void;
  zeroClauseRuleIds: Set<string>;
}) {
  const t = useT();

  if (rules.length === 0) {
    return (
      <Surface variant="soft" padding="md" className="text-center">
        <p className="text-xs text-[var(--text-secondary)]">{t("sections.ruleDatabase.noMatches")}</p>
      </Surface>
    );
  }

  return (
    <div className="space-y-2 overflow-y-auto max-h-[60vh]">
      {rules.map((rule) => {
        const isActive = rule.rule_id === selectedRuleId;
        return (
          <button
            key={rule.rule_id}
            type="button"
            onClick={() => onSelect(rule.rule_id)}
            className="block w-full text-left"
          >
            <Surface
              variant={isActive ? "tint" : "base"}
              padding="sm"
              className={`space-y-1.5 transition-colors ${
                isActive
                  ? "border-[var(--gold)]"
                  : "border-[var(--border-subtle)] hover:border-[var(--border-strong)]"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-mono text-[11px] font-semibold text-[var(--text-primary)]">
                  {ruleMotorLabel(rule.rule_id, t)}
                </span>
                <span className="flex flex-wrap justify-end gap-1">
                  {rule.fact_check_verdict && (
                    <FactCheckChip verdict={rule.fact_check_verdict} />
                  )}
                  <CoverageChip status={rule.coverage_status} />
                </span>
              </div>
              <RuleDescription rule={rule} />
              <div className="flex items-center justify-between gap-2">
                <RuleSourceChips rule={rule} />
                <span className="flex shrink-0 items-center gap-1">
                  {zeroClauseRuleIds.has(rule.rule_id) && (
                    <span
                      className="text-[10px] text-[var(--warning)]"
                      title={t("sections.ruleDatabase.coverage.zeroClauseWarning")}
                    >
                      ⚠
                    </span>
                  )}
                  <span className="text-[10px] tabular-nums text-[var(--text-muted)]">
                    {t("sections.ruleDatabase.list.clauseCount", {
                      count: fmtNum(rule.matched_clause_count),
                    })}
                  </span>
                </span>
              </div>
            </Surface>
          </button>
        );
      })}
    </div>
  );
}

function RuleDetailPanel({
  ruleId,
  artifactsAvailable,
  onNavigateToRule,
}: {
  ruleId: string;
  artifactsAvailable: boolean;
  onNavigateToRule?: (ruleId: string) => void;
}) {
  const t = useT();
  // Ref so the fetch reads a fresh translator without re-running on locale change.
  const tRef = useRef(t);
  tRef.current = t;
  const [detail, setDetail] = useState<RuleDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getRuleDetail(
          ruleId,
          { page, per_page: CLAUSES_PER_PAGE },
          { signal: controller.signal },
        );
        if (!active || controller.signal.aborted) return;
        setDetail(res);
      } catch (err) {
        if (!active || isAbortError(err)) return;
        setDetail(null);
        setError(
          err instanceof Error ? err.message : tRef.current("sections.ruleDatabase.errors.loadFailed"),
        );
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [ruleId, page]);

  const { category, description } = useLocalizedRule(detail?.rule);

  if (loading && !detail) {
    return <SutReferenceSectionSkeleton title={t("sections.ruleDatabase.detail.loading")} />;
  }

  if (error) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <Chip variant="danger">{error}</Chip>
      </Surface>
    );
  }

  if (!detail) {
    return null;
  }

  const { rule, clauses, clause_total, total_pages } = detail;

  return (
    <Surface variant="base" padding="md" className="space-y-4">
      <div className="space-y-2 border-b border-[var(--border-subtle)] pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">
            {ruleMotorLabel(rule.rule_id, t)}
          </span>
          <span className="flex flex-wrap gap-1">
            {rule.fact_check_verdict && <FactCheckChip verdict={rule.fact_check_verdict} />}
            <CoverageChip status={rule.coverage_status} />
          </span>
        </div>
        <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">{category}</p>
        <p className="text-sm leading-snug text-[var(--text-secondary)]">{description}</p>
        {rule.fact_check_units && rule.fact_check_units.length > 0 && (
          <p className="text-[10px] text-[var(--text-muted)]">
            {t("sections.ruleDatabase.factCheck.auditUnits", {
              units: rule.fact_check_units.join(", "),
            })}
            {rule.medula_overlap
              ? ` · ${t("sections.ruleDatabase.factCheck.medula", { tag: rule.medula_overlap })}`
              : ""}
          </p>
        )}
        {rule.fact_check_note && (
          <p className="text-[10px] text-[var(--text-muted)]">{rule.fact_check_note}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
            {t("sections.ruleDatabase.detail.sourcesLabel")}
          </span>
          <RuleSourceChips rule={rule} />
        </div>
        {rule.domain_modules.length > 0 && (
          <p className="text-[10px] text-[var(--text-muted)]">
            {t("sections.ruleDatabase.detail.implementedIn", {
              modules: rule.domain_modules.join(", "),
            })}
          </p>
        )}
      </div>

      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.detail.clausesTitle", { total: fmtNum(clause_total) })}
        </h4>
      </div>

      {!artifactsAvailable ? (
        <p className="text-sm text-[var(--text-secondary)]">{t("sections.ruleDatabase.detail.noArtifacts")}</p>
      ) : clauses.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">{t("sections.ruleDatabase.detail.noClauses")}</p>
      ) : (
        <>
          <ul className="space-y-3 overflow-y-auto max-h-[55vh]">
            {clauses.map((clause) => (
              <ClauseCard key={clause.clause_id} clause={clause} onNavigateToRule={onNavigateToRule} />
            ))}
          </ul>
          {total_pages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-2 text-sm text-[var(--text-muted)]">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="sut-section-btn sut-section-btn-compact disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("sections.ruleDatabase.pagination.prev")}
              </button>
              <span>
                {t("sections.ruleDatabase.pagination.page", {
                  page: fmtNum(page),
                  totalPages: fmtNum(total_pages),
                })}
              </span>
              <button
                type="button"
                disabled={page >= total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="sut-section-btn sut-section-btn-compact disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("sections.ruleDatabase.pagination.next")}
              </button>
            </div>
          )}
        </>
      )}
    </Surface>
  );
}

export function ClauseCard({
  clause,
  onNavigateToRule,
}: {
  clause: RuleClause;
  onNavigateToRule?: (ruleId: string) => void;
}) {
  const t = useT();
  const sectionLabel = [clause.section_id, clause.section_title].filter(Boolean).join(" · ");
  const deonticLabel = useDeonticLabel(clause.deontic_modality);
  const shownMatched = clause.matched_rule_ids.slice(0, 3);
  const overflowCount = clause.matched_rule_ids.length - shownMatched.length;
  const navigate = (rid: string) => (e: ReactMouseEvent) => {
    e.stopPropagation();
    onNavigateToRule?.(rid);
  };

  return (
    <li className="min-h-[80px] rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-soft)] p-3">
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        {clause.clause_id && (
          <span className="rounded bg-[var(--surface-default)] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[var(--text-secondary)]">
            {clause.clause_id}
          </span>
        )}
        {sectionLabel && (
          <span className="font-mono text-[11px] font-semibold text-[var(--text-primary)]">
            {sectionLabel}
          </span>
        )}
        {clause.is_primary && (
          <Chip variant="outline" className="text-[9px] uppercase tracking-wide">
            {t("sections.ruleDatabase.detail.primaryBadge")}
          </Chip>
        )}
        <UtilizationChip clause={clause} />
        <EkAnnexChips labels={clause.annex_refs} />
      </div>
      <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-[var(--text-primary)]">
        {clause.text_tr}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[var(--text-muted)]">
        {clause.primary_rule_id && (
          onNavigateToRule ? (
            <button
              type="button"
              onClick={navigate(clause.primary_rule_id)}
              className="rounded border border-[var(--border-subtle)] bg-[var(--surface-default)] px-1.5 py-0.5 font-mono transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
              title={t("sections.ruleDatabase.detail.motorJump")}
            >
              {t("sections.ruleDatabase.detail.motorLabel")}: {ruleMotorLabel(clause.primary_rule_id, t)}
            </button>
          ) : (
            <span className="font-mono">
              {t("sections.ruleDatabase.detail.motorLabel")}: {ruleMotorLabel(clause.primary_rule_id, t)}
            </span>
          )
        )}
        {deonticLabel && (
          <span className="font-mono uppercase tracking-wide">{deonticLabel}</span>
        )}
        {clause.source_effective_date && (
          <span>
            {t("sections.ruleDatabase.detail.effectiveDate", { date: clause.source_effective_date })}
          </span>
        )}
        {clause.amendment_refs.length > 0 && (
          <span>
            {t("sections.ruleDatabase.detail.amendments", {
              refs: clause.amendment_refs.join(", "),
            })}
          </span>
        )}
        {shownMatched.length > 0 && (
          <span className="inline-flex flex-wrap items-center gap-1">
            {shownMatched.map((rid) =>
              onNavigateToRule ? (
                <button
                  key={rid}
                  type="button"
                  onClick={navigate(rid)}
                  className="rounded border border-dashed border-[var(--border-subtle)] px-1.5 py-0.5 font-mono transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
                >
                  {rid}
                </button>
              ) : (
                <span key={rid} className="font-mono">{rid}</span>
              ),
            )}
            {overflowCount > 0 && (
              <span>
                {t("sections.ruleDatabase.detail.matchedMore", { count: overflowCount })}
              </span>
            )}
          </span>
        )}
      </div>
    </li>
  );
}
