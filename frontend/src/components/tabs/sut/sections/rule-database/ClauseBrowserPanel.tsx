"use client";

import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import {
  getClause,
  listClauses,
  type RuleCatalogEntry,
  type RuleClause,
  type SectionClausesResponse,
} from "@/lib/api/sut";
import { isAbortError } from "@/lib/api/request";
import { cn } from "@/lib/cn";
import {
  Chip,
  Surface,
  Toolbar,
  Button,
  EmptyState,
  buttonActiveClass,
  inputClass,
} from "@/components/primitives";
import { EkAnnexChips } from "@/components/sut/RegulatorySourceChips";
import { useT } from "@/lib/i18n/useTranslations";
import { ruleMotorLabel } from "@/lib/clauseUtilization";
import { fmtNum } from "../../shared";
import { CLAUSES_PER_PAGE, COVERAGE_KEY, STATUS_FILTERS, UtilizationChip, useDeonticLabel } from "./shared";

function clauseDeepLinkKey(clause: RuleClause): string {
  // Prefer unique opaque id for deep-links / React keys. Coordinates collide
  // across in-force rows; get_clause(coord) returns null when ambiguous.
  return clause.clause_id || clause.clause_coordinate || "";
}

function CopyableCoordinate({
  coordinate,
  clauseId,
}: {
  coordinate: string | null;
  clauseId: string | null;
}) {
  const t = useT();
  const primary = coordinate || clauseId;
  if (!primary) return null;

  const copy = (e: ReactMouseEvent) => {
    e.stopPropagation();
    void navigator.clipboard?.writeText(primary);
  };

  return (
    <button
      type="button"
      onClick={copy}
      title={t("sections.ruleDatabase.clauses.copyCoordinate")}
      className="rounded bg-[var(--surface-default)] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[var(--text-primary)] transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--surface-soft)]"
    >
      {primary}
    </button>
  );
}

export function ClauseBrowserPanel({
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
  const [hideHeadings, setHideHeadings] = useState(true);
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

  // Deep link: ?rdClause=2.2.1.(1) or C002684 → fetch and pre-select.
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
  }, [debouncedQuery, statusFilter, gapFilter, encodingFilter, ruleFilter, hideReferans, hideHeadings]);

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
            exclude_headings: hideHeadings || undefined,
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
  }, [debouncedQuery, statusFilter, gapFilter, encodingFilter, ruleFilter, hideReferans, hideHeadings, page, t]);

  const clauses = result?.clauses ?? [];
  const totalPages = result?.total_pages ?? 0;
  const total = result?.clause_total ?? 0;

  const resetFilters = () => {
    setQuery("");
    setStatusFilter("");
    setGapFilter(false);
    setEncodingFilter(false);
    setRuleFilter("");
  };

  return (
    <div className="space-y-4">
      <Toolbar
        leading={
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("sections.ruleDatabase.clauses.searchPlaceholder")}
            className={cn(inputClass, "min-w-[220px] max-w-[360px]")}
          />
        }
        trailing={
          <div className="flex items-center gap-2">
            {STATUS_FILTERS.map((status) => (
              <Button
                key={status}
                variant="secondary"
                size="compact"
                onClick={() =>
                  setStatusFilter((prev) => (prev === status ? "" : status))
                }
                className={cn("text-[11px]", statusFilter === status && buttonActiveClass)}
              >
                {status === "all"
                  ? t("sections.ruleDatabase.filters.all")
                  : t(`sections.ruleDatabase.status.${COVERAGE_KEY[status]}`)}
              </Button>
            ))}
            <Button
              variant="secondary"
              size="compact"
              onClick={() => setHideReferans((v) => !v)}
              className={cn("text-[11px]", hideReferans && buttonActiveClass)}
            >
              {t("sections.ruleDatabase.clauses.filterHideReferans")}
            </Button>
            <Button
              variant="secondary"
              size="compact"
              onClick={() => setHideHeadings((v) => !v)}
              className={cn("text-[11px]", hideHeadings && buttonActiveClass)}
            >
              {t("sections.ruleDatabase.clauses.filterHideHeadings")}
            </Button>
            <Button
              variant="secondary"
              size="compact"
              onClick={() => setGapFilter((v) => !v)}
              className={cn("text-[11px]", gapFilter && buttonActiveClass)}
            >
              {t("sections.ruleDatabase.clauses.filterGap")}
            </Button>
            <Button
              variant="secondary"
              size="compact"
              onClick={() => setEncodingFilter((v) => !v)}
              className={cn("text-[11px]", encodingFilter && buttonActiveClass)}
            >
              {t("sections.ruleDatabase.clauses.filterEncoded")}
            </Button>
            {rules && rules.length > 0 && (
              <select
                value={ruleFilter}
                onChange={(e) => setRuleFilter(e.target.value)}
                className={cn(inputClass, "max-w-[220px] truncate text-[11px]")}
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
            <EmptyState
              title={t("sections.ruleDatabase.detail.noClauses")}
              className="min-h-0 border-transparent bg-transparent"
              action={
                <Button variant="secondary" size="compact" onClick={resetFilters}>
                  {t("sections.ruleDatabase.resetFilters")}
                </Button>
              }
            />
          ) : (
            <>
              <div className="text-[11px] text-[var(--text-muted)]">
                {t("sections.ruleDatabase.clauses.resultCount", { count: fmtNum(total) })}
              </div>
              <ul className="space-y-1.5">
                {clauses.map((clause) => {
                  const isSelected =
                    selectedClause?.clause_id === clause.clause_id;
                  const rowKey = clause.clause_id || clause.clause_coordinate || "";
                  return (
                    <li
                      key={rowKey}
                      onClick={() => {
                        setSelectedClause(clause);
                        onUrlUpdate?.({ rdClause: clauseDeepLinkKey(clause) || null });
                      }}
                      className={`cursor-pointer rounded-[var(--r-sm)] border px-3 py-2 transition-colors hover:bg-[var(--surface-default)] ${
                        isSelected
                          ? "border-[var(--accent)] bg-[var(--surface-default)]"
                          : "border-[var(--border-subtle)]"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <CopyableCoordinate
                          coordinate={clause.clause_coordinate}
                          clauseId={clause.clause_id}
                        />
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
                  <Button
                    variant="secondary"
                    size="compact"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    {t("sections.ruleDatabase.pagination.prev")}
                  </Button>
                  <span>
                    {t("sections.ruleDatabase.pagination.page", {
                      page: fmtNum(page),
                      totalPages: fmtNum(totalPages),
                    })}
                  </span>
                  <Button
                    variant="secondary"
                    size="compact"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    {t("sections.ruleDatabase.pagination.next")}
                  </Button>
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
        <CopyableCoordinate
          coordinate={clause.clause_coordinate}
          clauseId={clause.clause_id}
        />
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
