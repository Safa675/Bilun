"use client";

import { useEffect, useState } from "react";
import {
  getRuleSections,
  getSectionClauses,
  sectionRollupRowKey,
  type RuleCoverageStatus,
  type SectionClausesResponse,
  type SectionRollupEntry,
  type SectionRollupResponse,
} from "@/lib/api/sut";
import { isAbortError } from "@/lib/api/request";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import {
  Chip,
  Surface,
  Toolbar,
  DataTable,
  DataTableHeader,
  DataTableHeaderCell,
  DataTableBody,
  DataTableRow,
  DataTableCell,
} from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtNum } from "../../shared";
import { COVERAGE_KEY, COVERAGE_VARIANT } from "./shared";
import { ClauseCard } from "./ClauseBrowserPanel";

const SECTIONS_PER_PAGE = 25;

export function SectionBrowserPanel({
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
