"use client";

import { useEffect, useRef, useState } from "react";
import { Chip, DataTable } from "@/components/primitives";
import PatientTabLink from "@/components/shell/PatientTabLink";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { getPatientWaveAEvidence } from "@/lib/api/waveaEvidence";
import { ApiRequestError } from "@/lib/apiClient";
import { buildSutBillingHref } from "@/lib/constants";
import type { WaveACoverage, WaveAEvidenceBlock, WaveAEvidenceRow } from "@/lib/domains/waveaEvidence";
import { useT } from "@/lib/i18n/useTranslations";
import { findFindingRowElement } from "@/lib/patientRoute";

export type WaveAEvidenceKind = "reviews" | "advisories" | "financial_rows";

function evidencePrefix(kind: WaveAEvidenceKind): string {
  return kind === "financial_rows" ? "wavea_financial:"
    : kind === "advisories" ? "wavea_advisory:"
    : "wavea_review:";
}

function sectionId(kind: WaveAEvidenceKind): string {
  return kind === "financial_rows" ? "wavea-financial"
    : kind === "advisories" ? "wavea-advisories"
    : "wavea-reviews";
}

function titleKey(kind: WaveAEvidenceKind): string {
  return kind === "financial_rows" ? "billing.wavea.financialTitle"
    : kind === "advisories" ? "billing.wavea.advisoryTitle"
    : "billing.wavea.reviewTitle";
}

function isCentAmount(value: number): boolean {
  const minorUnits = value * 100;
  return Number.isFinite(value) && value >= 0 &&
    Number.isSafeInteger(Math.round(minorUnits)) &&
    Math.abs(minorUnits - Math.round(minorUnits)) < 1e-6;
}

export function validRowForKind(row: WaveAEvidenceRow, patientId: string, kind: WaveAEvidenceKind): boolean {
  if (row.patient_id !== patientId || row.evidence_id !== evidencePrefix(kind) + row.source_evidence_id) {
    return false;
  }
  if (row.observed_billed_amount_try != null && (
    kind !== "financial_rows" || row.line_kind !== "procedure" || !row.line_id ||
    row.observed_amount_basis !== "procedure_claim_line.billed_amount_try" ||
    !isCentAmount(row.observed_billed_amount_try)
  )) return false;
  if (row.observed_amount_basis != null && row.observed_billed_amount_try == null) return false;
  if (kind !== "advisories") return true;
  return (row.advisory_kind === "permission" || row.advisory_kind === "information") &&
    row.money_semantics === "unpriced_advisory" &&
    row.financial_kind == null && row.confirmed_amount_try == null;
}

function validPatientBlock(block: WaveAEvidenceBlock | undefined, patientId: string, kind: WaveAEvidenceKind): boolean {
  if (
    block?.available !== true ||
    !Number.isInteger(block.total_rows) ||
    (block.total_rows ?? -1) < 0 ||
    !Array.isArray(block.rows) ||
    block.rows.length > block.total_rows! ||
    block.has_more !== (block.rows.length < block.total_rows!)
  ) return false;
  return new Set(block.rows.map((row) => row.evidence_id)).size === block.rows.length &&
    block.rows.every((row) => validRowForKind(row, patientId, kind));
}

export function WaveACoverageSummary({ coverage }: { coverage?: WaveACoverage | null }) {
  const t = useT();
  if (!coverage) return null;
  const groups = Object.entries(coverage.by_group ?? {}).sort(([a], [b]) => a.localeCompare(b));
  const totals = groups.reduce(
    (sum, [, counts]) => ({
      evaluated: sum.evaluated + counts.evaluated,
      missing_inputs: sum.missing_inputs + counts.missing_inputs,
      unavailable: sum.unavailable + counts.unavailable,
    }),
    { evaluated: 0, missing_inputs: 0, unavailable: 0 },
  );
  return (
    <section className="rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-3 text-sm">
      <h3 className="font-semibold text-[var(--text-primary)]">{t("billing.wavea.coverageTitle")}</h3>
      <p className="mt-1 text-[var(--text-secondary)]">
        {t("billing.wavea.coverageSummary", {
          groups: groups.length,
          evaluated: totals.evaluated,
          missing: totals.missing_inputs,
          unavailable: totals.unavailable,
        })}
      </p>
      {!coverage.available && (
        <p className="mt-1 text-[var(--text-muted)]">{t("billing.wavea.coveragePartial")}</p>
      )}
      {groups.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer font-medium">{t("billing.wavea.groupDetails")}</summary>
          <ul className="mt-2 space-y-1">
            {groups.map(([group, counts]) => (
              <li key={group} className="flex flex-wrap justify-between gap-2 border-t border-[var(--border-subtle)] pt-1">
                <span className="font-mono text-xs">{group}</span>
                <span className="tabular-nums text-xs">
                  {t("billing.wavea.groupCounts", {
                    evaluated: counts.evaluated,
                    missing: counts.missing_inputs,
                    unavailable: counts.unavailable,
                  })}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function clauseKey(row: WaveAEvidenceRow): string | null {
  const key = row.regulatory_source?.clause_key?.trim();
  return key || null;
}

function sourceReferences(row: WaveAEvidenceRow): string[] {
  const references = row.regulatory_source?.source_locators;
  if (!Array.isArray(references)) return [];
  const locators = references.filter((reference): reference is string =>
    typeof reference === "string" && reference.trim().length > 0,
  ).map((reference) => reference.trim());
  const fatura = row.regulatory_source?.fatura_inceleme_ref?.trim();
  if (fatura && !locators.includes(fatura)) locators.push(fatura);
  return locators;
}

export function WaveAEvidenceRowsTable({
  rows,
  kind,
  onOpenClause,
  selectedFindingId,
}: {
  rows: WaveAEvidenceRow[];
  kind: WaveAEvidenceKind;
  onOpenClause?: (clauseKey: string) => void;
  selectedFindingId?: string | null;
}) {
  const t = useT();
  const financial = kind === "financial_rows";
  const section = sectionId(kind);

  return (
    <DataTable minWidth={880}>
      <thead>
        <tr>
          <th>{t("billing.wavea.type")}</th>
          <th>{t("billing.wavea.ruleAndReason")}</th>
          <th>{t("billing.wavea.claimAndLine")}</th>
          <th>{t("billing.wavea.source")}</th>
          <th className="text-right">{financial ? t("billing.wavea.amount") : t("billing.wavea.patient")}</th>
          {financial && <th>{t("billing.wavea.patient")}</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const source = clauseKey(row);
          const authoredReferences = sourceReferences(row);
          const href = buildSutBillingHref(row.patient_id, {
            claimId: row.claim_id ?? undefined,
            section,
            findingId: row.evidence_id,
          });
          return (
            <tr
              key={row.evidence_id}
              data-finding-id={row.evidence_id}
              data-selected={selectedFindingId === row.evidence_id ? "true" : undefined}
              className={selectedFindingId === row.evidence_id ? "bg-[var(--gold-subtle)]" : undefined}
            >
              <td>
                <Chip variant={kind === "advisories" ? "neutral" : "warning"}>
                  {financial
                    ? t(row.financial_kind === "uplift" ? "billing.wavea.uplift" : "billing.wavea.risk")
                    : kind === "advisories"
                      ? t(row.advisory_kind === "information" ? "billing.wavea.information" : "billing.wavea.permission")
                    : t("billing.wavea.review")}
                </Chip>
              </td>
              <td>
                <div className="font-mono text-xs text-[var(--text-primary)]">{row.rule_id}</div>
                {row.reason && <div className="mt-1 text-xs text-[var(--text-secondary)]">{row.reason}</div>}
              </td>
              <td className="font-mono text-xs">
                {row.claim_id || "—"}
                {row.line_id ? ` · ${row.line_kind}:${row.line_id}` : ""}
              </td>
              <td className="text-xs">
                {source && onOpenClause ? (
                  <button type="button" className="underline" onClick={() => onOpenClause(source)}>
                    {source}
                  </button>
                ) : source ? (
                  <span className="font-mono">{source}</span>
                ) : authoredReferences.length > 0 ? (
                  <span className="font-mono">
                    {authoredReferences.map((reference, index) => (
                      <span key={`${reference}:${index}`}>
                        {index > 0 ? " · " : null}
                        {onOpenClause && reference.includes("#") ? (
                          <button type="button" className="underline" onClick={() => onOpenClause(reference)}>
                            {reference}
                          </button>
                        ) : reference}
                      </span>
                    ))}
                  </span>
                ) : (
                  <span className="text-[var(--text-muted)]">{t("billing.wavea.sourceUnverified")}</span>
                )}
                <div className="mt-1 text-[var(--text-muted)]">
                  {row.source_status === "structured_locator" || authoredReferences.length > 0
                    ? t("billing.wavea.sourceLocator")
                    : t("billing.wavea.sourceUnverified")}
                </div>
              </td>
              {financial && (
                <td className="text-right tabular-nums">
                  {row.amount_status !== "confirmed" ||
                  typeof row.confirmed_amount_try !== "number" ||
                  !Number.isFinite(row.confirmed_amount_try)
                    ? t("billing.wavea.amountUnavailable")
                    : fmtTRY2(row.confirmed_amount_try)}
                  {row.observed_billed_amount_try != null && (
                    <div className="mt-1 text-xs text-[var(--text-secondary)]">
                      {t("billing.wavea.observedBilledCharge")}: {fmtTRY2(row.observed_billed_amount_try)}
                      <div className="text-[var(--text-muted)]">{t("billing.wavea.procedureLineBasis")}</div>
                    </div>
                  )}
                  <div className="text-xs text-[var(--text-muted)]">
                    {row.headline_relation === "separate_yatak_reconciliation"
                      ? t("billing.wavea.separateReconciliation")
                      : t("billing.wavea.notInHeadline")}
                  </div>
                </td>
              )}
              <td>
                <PatientTabLink patientId={row.patient_id} href={href} className="underline">
                  {row.patient_id}
                </PatientTabLink>
              </td>
            </tr>
          );
        })}
      </tbody>
    </DataTable>
  );
}

/** A bounded patient preview; later pages come from the separate evidence table. */
export function PatientWaveAEvidenceSection({
  patientId,
  kind,
  block,
  onOpenClause,
  selectedFindingId,
}: {
  patientId: string;
  kind: WaveAEvidenceKind;
  block?: WaveAEvidenceBlock;
  onOpenClause?: (clauseKey: string) => void;
  selectedFindingId?: string | null;
}) {
  const t = useT();
  const [rows, setRows] = useState(block?.rows ?? []);
  const [unavailable, setUnavailable] = useState(!validPatientBlock(block, patientId, kind));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [selectedRow, setSelectedRow] = useState<WaveAEvidenceRow | null>(null);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => {
    pending.current?.abort();
    pending.current = null;
    setRows(block?.rows ?? []);
    setUnavailable(!validPatientBlock(block, patientId, kind));
    setLoading(false);
    setError(false);
    setSelectedRow(null);
    return () => pending.current?.abort();
  }, [patientId, kind, block?.available, block?.total_rows, block?.rows]);

  useEffect(() => {
    const prefix = evidencePrefix(kind);
    if (
      unavailable || !selectedFindingId?.startsWith(prefix) ||
      rows.some((row) => row.evidence_id === selectedFindingId)
    ) {
      setSelectedRow(null);
      return;
    }
    const controller = new AbortController();
    getPatientWaveAEvidence(
      patientId,
      { kind, offset: 0, limit: 1, evidenceId: selectedFindingId },
      { signal: controller.signal },
    ).then((page) => {
      if (controller.signal.aborted) return;
      const exact = Array.isArray(page.rows) ? page.rows[0] : null;
      if (
        page.available !== true || page.patient_id !== patientId || page.kind !== kind ||
        page.pagination?.total_matching !== 1 || !Array.isArray(page.rows) || page.rows.length !== 1 ||
        exact?.evidence_id !== selectedFindingId || !validRowForKind(exact, patientId, kind)
      ) {
        setUnavailable(true);
        setRows([]);
        return;
      }
      setSelectedRow(exact);
    }).catch((cause) => {
      if (controller.signal.aborted) return;
      if (cause instanceof ApiRequestError && (cause.status === 404 || cause.status === 405)) {
        setUnavailable(true);
        setRows([]);
      } else {
        setError(true);
      }
    });
    return () => controller.abort();
  }, [patientId, kind, selectedFindingId, unavailable, rows]);

  useEffect(() => {
    if (!selectedFindingId || typeof document === "undefined") return;
    if (!rows.some((row) => row.evidence_id === selectedFindingId) && selectedRow?.evidence_id !== selectedFindingId) return;
    findFindingRowElement(document, selectedFindingId)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, [rows, selectedRow, selectedFindingId]);

  const total = block?.total_rows;
  const canLoadMore = !unavailable && typeof total === "number" && rows.length < total;
  const displayRows = selectedRow && !rows.some((row) => row.evidence_id === selectedRow.evidence_id)
    ? [selectedRow, ...rows]
    : rows;
  const loadMore = async () => {
    if (!canLoadMore || loading) return;
    const controller = new AbortController();
    pending.current = controller;
    setLoading(true);
    setError(false);
    try {
      const next = await getPatientWaveAEvidence(
        patientId,
        { kind, offset: rows.length },
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      const incoming = next.rows;
      if (
        next.available !== true ||
        next.patient_id !== patientId ||
        next.kind !== kind ||
        next.pagination.offset !== rows.length ||
        next.pagination.total_matching !== total ||
        !Array.isArray(incoming) ||
        incoming.length === 0 ||
        incoming.some((row) => !validRowForKind(row, patientId, kind))
      ) {
        setUnavailable(true);
        setRows([]);
        return;
      }
      const identities = new Set([...rows, ...incoming].map((row) => row.evidence_id));
      if (identities.size !== rows.length + incoming.length) {
        setUnavailable(true);
        setRows([]);
        return;
      }
      setRows((current) => [...current, ...incoming]);
    } catch (cause) {
      if (!controller.signal.aborted) {
        if (cause instanceof ApiRequestError && (cause.status === 404 || cause.status === 405)) {
          setUnavailable(true);
          setRows([]);
        } else {
          setError(true);
        }
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
      if (pending.current === controller) pending.current = null;
    }
  };

  return (
    <section id={sectionId(kind)} className="space-y-2 scroll-mt-24">
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">
        {t(titleKey(kind))}
      </h3>
      {kind === "advisories" && (
        <p className="text-xs text-[var(--text-muted)]">{t("billing.wavea.advisoryNotice")}</p>
      )}
      {unavailable ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.wavea.unavailable")}</p>
      ) : displayRows.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.wavea.noRows")}</p>
      ) : (
        <WaveAEvidenceRowsTable rows={displayRows} kind={kind} onOpenClause={onOpenClause} selectedFindingId={selectedFindingId} />
      )}
      {error && <p role="alert" className="text-sm text-[var(--danger)]">{t("billing.wavea.loadFailed")}</p>}
      {canLoadMore && (
        <button type="button" disabled={loading} onClick={loadMore} className="text-sm font-medium underline disabled:opacity-50">
          {loading ? t("billing.wavea.loading") : t("billing.wavea.loadMore", { shown: rows.length, total })}
        </button>
      )}
    </section>
  );
}
