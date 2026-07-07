"use client";

import { useEffect, useRef, useState } from "react";
import {
  getRuleDetail,
  type RuleCatalogEntry,
  type RuleDetailResponse,
} from "@/lib/api/sut";
import { isAbortError } from "@/lib/api/request";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { Chip, Surface, Button, EmptyState } from "@/components/primitives";
import { EkAnnexChips } from "@/components/sut/RegulatorySourceChips";
import { useT } from "@/lib/i18n/useTranslations";
import { ruleMotorLabel } from "@/lib/clauseUtilization";
import { fmtNum } from "../../shared";
import {
  CLAUSES_PER_PAGE,
  CoverageChip,
  FactCheckChip,
  RuleDescription,
  useLocalizedRule,
} from "./shared";
import { ClauseCard } from "./ClauseBrowserPanel";

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

export function RuleList({
  rules,
  selectedRuleId,
  onSelect,
  zeroClauseRuleIds,
  onClearFilters,
}: {
  rules: RuleCatalogEntry[];
  selectedRuleId: string | null;
  onSelect: (ruleId: string) => void;
  zeroClauseRuleIds: Set<string>;
  onClearFilters?: () => void;
}) {
  const t = useT();

  if (rules.length === 0) {
    return (
      <EmptyState
        title={t("sections.ruleDatabase.noMatches")}
        className="min-h-0 border-transparent bg-transparent"
        action={
          onClearFilters ? (
            <Button variant="secondary" size="compact" onClick={onClearFilters}>
              {t("sections.ruleDatabase.clearFilters")}
            </Button>
          ) : undefined
        }
      />
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

export function RuleDetailPanel({
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
                  totalPages: fmtNum(total_pages),
                })}
              </span>
              <Button
                variant="secondary"
                size="compact"
                disabled={page >= total_pages}
                onClick={() => setPage((p) => p + 1)}
              >
                {t("sections.ruleDatabase.pagination.next")}
              </Button>
            </div>
          )}
        </>
      )}
    </Surface>
  );
}
