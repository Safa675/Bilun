"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getProseInventory,
  getRuleCatalog,
  getRuleDetail,
  getRuleSections,
  type CoverageSummary,
  type FactCheckRollup,
  type FactCheckVerdict,
  type ProseInventoryResponse,
  type RuleCatalogEntry,
  type RuleClause,
  type RuleCoverageStatus,
  type RuleDetailResponse,
  type SectionRollupResponse,
} from "@/lib/api/sut";
import { isAbortError } from "@/lib/api/request";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { Chip, Section, Surface } from "@/components/primitives";
import { EkAnnexChips } from "@/components/sut/RegulatorySourceChips";
import { useSutApi } from "../useSutApi";
import { fmtNum } from "../shared";
import { useLocale } from "@/lib/i18n";
import { useT } from "@/lib/i18n/useTranslations";

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

function CoverageSummaryPanel({ summary }: { summary: CoverageSummary }) {
  const t = useT();
  const { clauses, registry, meta } = summary;

  if (!meta.artifacts_available) {
    return (
      <div className="rounded-[var(--r-md)] border border-[color-mix(in_srgb,var(--warning)_30%,transparent)] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] px-3 py-2 text-xs text-[var(--text-secondary)]">
        {t("sections.ruleDatabase.coverage.buildHint")}
      </div>
    );
  }

  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-soft)] px-3 py-2.5 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.coverage.title")}
        </p>
        {meta.generated_at && (
          <p className="text-[10px] text-[var(--text-muted)]">
            {t("sections.ruleDatabase.coverage.generatedAt", { date: meta.generated_at })}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        {/* Clauses column */}
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
            {t("sections.ruleDatabase.coverage.clausesTitle")}
          </p>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-semibold tabular-nums text-[var(--text-primary)]">
              {fmtNum(clauses.total_extracted)}
            </span>
            <span className="text-[10px] text-[var(--text-muted)]">
              {t("sections.ruleDatabase.coverage.totalExtracted")}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-base font-semibold tabular-nums text-[var(--danger)]">
              {fmtNum(clauses.algorithmic_gaps)}
            </span>
            <span className="text-[10px] text-[var(--text-muted)]">
              {t("sections.ruleDatabase.coverage.algorithmicGaps")} ({clauses.algorithmic_gap_pct}%)
            </span>
          </div>
          <div className="space-y-1">
            {clauses.by_status.map((s) => (
              <div key={s.status} className="flex items-center justify-between text-[10px]">
                <Chip variant={COVERAGE_VARIANT[s.status as RuleCoverageStatus]} className="text-[9px]">
                  {t(`sections.ruleDatabase.status.${COVERAGE_KEY[s.status as RuleCoverageStatus]}`)}
                </Chip>
                <span className="tabular-nums text-[var(--text-secondary)]">{fmtNum(s.count)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Registry column */}
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
            {t("sections.ruleDatabase.coverage.registryTitle")}
          </p>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-semibold tabular-nums text-[var(--text-primary)]">
              {fmtNum(registry.total_rules)}
            </span>
            <span className="text-[10px] text-[var(--text-muted)]">
              {t("sections.ruleDatabase.coverage.totalExtracted")}
            </span>
          </div>
          <div className="space-y-1">
            {registry.by_status.map((s) => (
              <div key={s.status} className="flex items-center justify-between text-[10px]">
                <Chip variant={COVERAGE_VARIANT[s.status as RuleCoverageStatus]} className="text-[9px]">
                  {t(`sections.ruleDatabase.status.${COVERAGE_KEY[s.status as RuleCoverageStatus]}`)}
                </Chip>
                <span className="tabular-nums text-[var(--text-secondary)]">{fmtNum(s.count)}</span>
              </div>
            ))}
          </div>
          {registry.zero_clause_matches.length > 0 && (
            <div className="rounded border border-[color-mix(in_srgb,var(--warning)_30%,transparent)] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] px-2 py-1 text-[10px] text-[var(--text-secondary)]">
              {t("sections.ruleDatabase.coverage.zeroClauseWarning")}: {fmtNum(registry.zero_clause_matches.length)}
            </div>
          )}
        </div>
      </div>

      {clauses.top_gap_categories.length > 0 && (
        <div className="space-y-1 border-t border-[var(--border-subtle)] pt-2">
          <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
            {t("sections.ruleDatabase.coverage.topGapCategories")}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {clauses.top_gap_categories.map((cat) => (
              <span
                key={cat.category}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]"
              >
                <span>{cat.category}</span>
                <span className="tabular-nums font-semibold">{fmtNum(cat.count)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const SECTIONS_PER_PAGE = 25;

function SectionBrowserPanel() {
  const t = useT();
  const [query, setQuery] = useState("");
  const [minGapCount, setMinGapCount] = useState<string>("");
  const [page, setPage] = useState(1);

  const params = useMemo(
    () => ({
      page,
      per_page: SECTIONS_PER_PAGE,
      q: query.trim() || undefined,
      min_gap_count: minGapCount ? parseInt(minGapCount, 10) : undefined,
    }),
    [page, query, minGapCount],
  );

  const {
    data: result,
    loading,
    error,
  } = useSutApi((opts) => getRuleSections(params, opts), {
    enabled: true,
    errorFallback: t("sections.ruleDatabase.errors.loadFailed"),
  });

  useEffect(() => {
    setPage(1);
  }, [query, minGapCount]);

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
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("sections.ruleDatabase.sections.searchPlaceholder")}
          className="sut-input"
          style={{ flex: 1, minWidth: 220, maxWidth: 360 }}
        />
        <input
          type="number"
          min={0}
          value={minGapCount}
          onChange={(e) => setMinGapCount(e.target.value)}
          placeholder={t("sections.ruleDatabase.sections.minGapFilter")}
          className="sut-input"
          style={{ width: 120 }}
        />
      </div>

      {sections.length === 0 ? (
        <Surface variant="soft" padding="md" className="text-center">
          <p className="text-xs text-[var(--text-secondary)]">
            {t("sections.ruleDatabase.sections.noMatches")}
          </p>
        </Surface>
      ) : (
        <>
          <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] overflow-hidden">
            <table className="w-full text-[11px]">
              <thead className="bg-[var(--surface-soft)] text-[var(--text-muted)] uppercase tracking-wide">
                <tr>
                  <th className="px-2 py-1.5 text-left font-medium">
                    {t("sections.ruleDatabase.sections.columnSection")}
                  </th>
                  <th className="px-2 py-1.5 text-left font-medium">
                    {t("sections.ruleDatabase.sections.columnTitle")}
                  </th>
                  <th className="px-2 py-1.5 text-right font-medium">
                    {t("sections.ruleDatabase.sections.columnClauses")}
                  </th>
                  <th className="px-2 py-1.5 text-right font-medium">
                    {t("sections.ruleDatabase.sections.columnGaps")}
                  </th>
                  <th className="px-2 py-1.5 text-left font-medium">
                    {t("sections.ruleDatabase.sections.columnStatus")}
                  </th>
                  <th className="px-2 py-1.5 text-left font-medium">
                    {t("sections.ruleDatabase.sections.columnCategories")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sections.map((section) => (
                  <tr
                    key={section.section_id ?? "unknown"}
                    className="border-t border-[var(--border-subtle)] hover:bg-[var(--surface-soft)]"
                  >
                    <td className="px-2 py-1.5 font-mono text-[var(--text-primary)]">
                      {section.section_id}
                    </td>
                    <td className="px-2 py-1.5 text-[var(--text-secondary)]">
                      {section.section_title ?? "—"}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-[var(--text-secondary)]">
                      {fmtNum(section.clause_count)}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-[var(--danger)]">
                      {fmtNum(section.gap_clause_count)}
                    </td>
                    <td className="px-2 py-1.5">
                      {section.worst_coverage_status && (
                        <Chip
                          variant={COVERAGE_VARIANT[section.worst_coverage_status as RuleCoverageStatus]}
                          className="text-[9px]"
                        >
                          {t(
                            `sections.ruleDatabase.status.${COVERAGE_KEY[section.worst_coverage_status as RuleCoverageStatus]}`,
                          )}
                        </Chip>
                      )}
                    </td>
                    <td className="px-2 py-1.5">
                      <div className="flex flex-wrap gap-1">
                        {section.primary_categories.map((cat) => (
                          <Chip key={cat} variant="outline" className="text-[9px]">
                            {cat}
                          </Chip>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 text-[11px] text-[var(--text-muted)]">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="sut-section-btn"
                style={{ padding: "3px 10px" }}
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
                className="sut-section-btn"
                style={{ padding: "3px 10px" }}
              >
                {t("sections.ruleDatabase.pagination.next")}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ProseInventoryPanel() {
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
                    <Chip key={anchor} variant="outline" className="text-[9px]">
                      {anchor}
                    </Chip>
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

type RuleDatabaseTab = "rules" | "sections" | "prose";

const RULE_DB_TABS: RuleDatabaseTab[] = ["rules", "sections", "prose"];

export function RuleDatabaseSection() {
  const t = useT();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<RuleCoverageStatus | "all">("all");
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<RuleDatabaseTab>("rules");

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
  const activeRuleId = selectedRuleId ?? rules?.[0]?.rule_id ?? null;

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

  if (loading) {
    return <SutReferenceSectionSkeleton title={t("sections.ruleDatabase.loading")} />;
  }

  if (error) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <Chip variant="danger">{error}</Chip>
      </Surface>
    );
  }

  if (!rules || rules.length === 0) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <p className="text-sm text-[var(--text-secondary)]">{t("sections.ruleDatabase.empty")}</p>
      </Surface>
    );
  }

  return (
    <Section
      title={t("sections.ruleDatabase.title")}
      description={t("sections.ruleDatabase.subtitle", { total: fmtNum(rules.length) })}
    >
      {catalog?.coverage_summary && <CoverageSummaryPanel summary={catalog.coverage_summary} />}

      {!artifactsAvailable && (
        <div className="rounded-[var(--r-md)] border border-[color-mix(in_srgb,var(--warning)_30%,transparent)] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] px-3 py-2 text-xs text-[var(--text-secondary)]">
          {t("sections.ruleDatabase.artifactsUnavailable")}
        </div>
      )}

      {catalog?.fact_check && <FactCheckRollupBanner rollup={catalog.fact_check} />}

      <div className="flex flex-wrap gap-1.5 border-b border-[var(--border-subtle)] pb-2">
        {RULE_DB_TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`sut-section-btn sut-section-btn-compact ${activeTab === tab ? "sut-section-btn-active" : ""}`}
          >
            <span className="text-[11px] font-semibold">
              {t(`sections.ruleDatabase.tabs.${tab}`)}
            </span>
          </button>
        ))}
      </div>

      {activeTab === "rules" && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("sections.ruleDatabase.searchPlaceholder")}
              className="sut-input"
              style={{ flex: 1, minWidth: 220, maxWidth: 360 }}
            />
            <div className="flex flex-wrap gap-1.5">
              {STATUS_FILTERS.map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => setStatusFilter(status)}
                  className={`sut-section-btn sut-section-btn-compact ${statusFilter === status ? "sut-section-btn-active" : ""}`}
                >
                  <span className="text-[11px] font-semibold">
                    {status === "all"
                      ? t("sections.ruleDatabase.filters.all")
                      : t(`sections.ruleDatabase.status.${COVERAGE_KEY[status]}`)}
                  </span>
                </button>
              ))}
            </div>
          </div>

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
              />
            ) : (
              <Surface variant="soft" padding="lg" className="flex items-center justify-center">
                <p className="text-sm text-[var(--text-secondary)]">
                  {t("sections.ruleDatabase.detail.selectPrompt")}
                </p>
              </Surface>
            )}
          </div>
        </>
      )}

      {activeTab === "sections" && <SectionBrowserPanel />}

      {activeTab === "prose" && <ProseInventoryPanel />}
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
    <div className="space-y-2" style={{ maxHeight: 560, overflowY: "auto" }}>
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
                  {rule.rule_id}
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
}: {
  ruleId: string;
  artifactsAvailable: boolean;
}) {
  const t = useT();
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
  }, [ruleId, page, t]);

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
          <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">{rule.rule_id}</span>
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
          <ul className="space-y-3" style={{ maxHeight: 460, overflowY: "auto" }}>
            {clauses.map((clause) => (
              <ClauseCard key={clause.clause_id} clause={clause} />
            ))}
          </ul>
          {total_pages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-1 text-[11px] text-[var(--text-muted)]">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="sut-section-btn"
                style={{ padding: "3px 10px" }}
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
                className="sut-section-btn"
                style={{ padding: "3px 10px" }}
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

function ClauseCard({ clause }: { clause: RuleClause }) {
  const t = useT();
  const sectionLabel = [clause.section_id, clause.section_title].filter(Boolean).join(" · ");
  const deonticLabel = useDeonticLabel(clause.deontic_modality);

  return (
    <li className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-soft)] p-3">
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
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
        <EkAnnexChips labels={clause.annex_refs} />
      </div>
      <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-[var(--text-primary)]">
        {clause.text_tr}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[var(--text-muted)]">
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
      </div>
    </li>
  );
}
