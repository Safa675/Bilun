"use client";

import { useEffect, useState } from "react";
import { getCohortWaveAEvidence, getCohortWaveAIndex } from "@/lib/api/waveaEvidence";
import { ApiRequestError } from "@/lib/apiClient";
import type { WaveACohortEvidencePage, WaveAEvidenceIndexPage } from "@/lib/domains/waveaEvidence";
import { useT } from "@/lib/i18n/useTranslations";
import { WaveACoverageSummary, WaveAEvidenceRowsTable, validRowForKind, type WaveAEvidenceKind } from "./WaveAEvidenceSection";

const PAGE_SIZE = 20;

export function validCohortEvidencePage(
  page: WaveACohortEvidencePage,
  kind: WaveAEvidenceKind,
  offset: number,
  selected: readonly string[] | undefined,
  index: WaveAEvidenceIndexPage | null,
  includeCoverage: boolean,
): boolean {
  const pagination = page?.pagination;
  const rows = page?.rows;
  const total = pagination?.total_matching;
  const coverage = page?.patient_coverage;
  const prefix = kind === "financial_rows" ? "wavea_financial:"
    : kind === "advisories" ? "wavea_advisory:"
    : "wavea_review:";
  if (
    page?.available !== true || page.kind !== kind ||
    !coverage || !Number.isInteger(coverage.selected) || coverage.selected < 0 ||
    !Number.isInteger(coverage.available) || coverage.available < 0 ||
    !Number.isInteger(coverage.unavailable) || coverage.unavailable < 0 ||
    coverage.available + coverage.unavailable !== coverage.selected ||
    page.unavailable_reason !== (coverage.unavailable > 0 ? "some_patients_unavailable" : null) ||
    (selected != null && coverage.selected !== selected.length) ||
    !pagination || pagination.offset !== offset || pagination.limit !== PAGE_SIZE ||
    !Number.isInteger(total) || (total ?? -1) < 0 ||
    page.counts?.matching_rows !== total ||
    !Array.isArray(rows) || rows.length > PAGE_SIZE ||
    (offset < total! && rows.length === 0) ||
    pagination.has_more !== (offset + rows.length < total!) ||
    new Set(rows.map((row) => row.evidence_id)).size !== rows.length ||
    rows.some((row) =>
      !row.patient_id ||
      !row.evidence_id.startsWith(prefix) ||
      !validRowForKind(row, row.patient_id, kind) ||
      (kind === "advisories" &&
        ((row.advisory_kind !== "permission" && row.advisory_kind !== "information") ||
        row.money_semantics !== "unpriced_advisory" ||
        row.financial_kind != null || row.confirmed_amount_try != null)) ||
      (selected != null && !selected.includes(row.patient_id)))
  ) return false;
  if (!includeCoverage) return true;
  const counts = index?.counts;
  const indexCoverage = index?.patient_coverage;
  if (
    index?.available !== true || !counts ||
    !indexCoverage || indexCoverage.selected !== coverage.selected ||
    indexCoverage.available !== coverage.available ||
    indexCoverage.unavailable !== coverage.unavailable ||
    index.unavailable_reason !== page.unavailable_reason ||
    !Number.isInteger(counts.evaluation_count) || counts.evaluation_count < 0 ||
    !Number.isInteger(counts.review_count) || counts.review_count < 0 ||
    !Number.isInteger(counts.advisory_count) || counts.advisory_count < 0 ||
    !Number.isInteger(counts.financial_count) || counts.financial_count < 0 ||
    !counts.by_group || typeof counts.by_group !== "object" ||
    total !== (kind === "financial_rows" ? counts.financial_count
      : kind === "advisories" ? counts.advisory_count : counts.review_count) ||
    index.pagination.total_matching !== coverage.selected
  ) return false;
  return Object.values(counts.by_group).every((group) =>
    group && [group.evaluated, group.missing_inputs, group.unavailable]
      .every((count) => Number.isInteger(count) && count >= 0));
}

export function CohortWaveAEvidenceSection({
  kind,
  cohortPatientIds,
  cohortFilterActive,
  includeCoverage = false,
}: {
  kind: WaveAEvidenceKind;
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
  includeCoverage?: boolean;
}) {
  const t = useT();
  const idsKey = cohortFilterActive ? JSON.stringify([...cohortPatientIds].sort()) : "*";
  const selectedIds = cohortFilterActive ? JSON.parse(idsKey) as string[] : undefined;
  const emptySelection = cohortFilterActive && selectedIds?.length === 0;
  const [offset, setOffset] = useState(0);
  const [result, setResult] = useState<WaveACohortEvidencePage | null>(null);
  const [index, setIndex] = useState<WaveAEvidenceIndexPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => setOffset(0), [idsKey, kind]);
  useEffect(() => {
    if (emptySelection) {
      setResult(null);
      setIndex(null);
      setLoading(false);
      setFailed(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    setResult(null);
    setIndex(null);
    const selected = cohortFilterActive ? JSON.parse(idsKey) as string[] : undefined;
    const page = getCohortWaveAEvidence(
      { kind, patientIds: selected, limit: PAGE_SIZE, offset },
      { signal: controller.signal },
    );
    const coverage = includeCoverage
      ? getCohortWaveAIndex({ patientIds: selected, limit: 1 }, { signal: controller.signal })
      : Promise.resolve(null);
    Promise.all([page, coverage]).then(([next, nextIndex]) => {
      if (controller.signal.aborted) return;
      if (!validCohortEvidencePage(next, kind, offset, selected, nextIndex, includeCoverage)) {
        setResult(next.available === false ? next : null);
        setFailed(next.available !== false);
        setIndex(null);
      } else {
        setResult(next);
        setIndex(nextIndex);
      }
      setLoading(false);
    }).catch((cause) => {
      if (!controller.signal.aborted) {
        const oldEndpoint = cause instanceof ApiRequestError &&
          (cause.status === 404 || cause.status === 405);
        setResult(oldEndpoint ? {
          available: false,
          unavailable_reason: "wavea_capability_unavailable",
          counts: null,
          rows: [],
          pagination: { total_matching: null, limit: PAGE_SIZE, offset, has_more: null },
        } : null);
        setIndex(null);
        setLoading(false);
        setFailed(!oldEndpoint);
      }
    });
    return () => controller.abort();
  }, [kind, idsKey, cohortFilterActive, emptySelection, offset, includeCoverage]);

  const total = result?.pagination.total_matching;
  const available = !loading && !failed && result?.available === true;
  const title = t(kind === "financial_rows" ? "billing.wavea.financialTitle"
    : kind === "advisories" ? "billing.wavea.advisoryTitle" : "billing.wavea.reviewTitle");

  return (
    <section className="space-y-3" aria-label={title}>
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
      {includeCoverage && kind === "reviews" && index?.available === true && index.counts && (
        <WaveACoverageSummary coverage={{
          schema_version: "wavea-evidence-v2",
          available: index.patient_coverage?.unavailable === 0,
          unavailable_reason: index.unavailable_reason,
          tracked_rule_count: 0,
          evaluation_count: index.counts.evaluation_count,
          by_group: index.counts.by_group,
        }} />
      )}
      {available && (result.patient_coverage?.unavailable ?? 0) > 0 && (
        <p className="text-sm text-[var(--text-muted)]">
          {t("billing.wavea.partialCohort", { count: result.patient_coverage!.unavailable })}
        </p>
      )}
      {emptySelection ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.wavea.noSelectedPatients")}</p>
      ) : loading ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.wavea.loading")}</p>
      ) : !available ? (
        <p role={failed ? "alert" : undefined} className="text-sm text-[var(--text-muted)]">
          {t(failed ? "billing.wavea.loadFailed" : "billing.wavea.unavailable")}
        </p>
      ) : result.rows.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.wavea.noRows")}</p>
      ) : (
        <WaveAEvidenceRowsTable rows={result.rows} kind={kind} />
      )}
      {available && typeof total === "number" && total > PAGE_SIZE && (
        <div className="flex items-center justify-between gap-3 text-sm">
          <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="underline disabled:opacity-50">
            {t("billing.wavea.previous")}
          </button>
          <span className="tabular-nums">{t("billing.wavea.pageRange", {
            from: offset + 1,
            through: Math.min(offset + PAGE_SIZE, total),
            total,
          })}</span>
          <button type="button" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)} className="underline disabled:opacity-50">
            {t("billing.wavea.next")}
          </button>
        </div>
      )}
    </section>
  );
}
