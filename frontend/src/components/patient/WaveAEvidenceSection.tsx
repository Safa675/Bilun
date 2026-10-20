"use client";

import { useEffect, useRef, useState } from "react";
import { Chip, DataTable } from "@/components/primitives";
import PatientTabLink from "@/components/shell/PatientTabLink";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { getPatientWaveAEvidence } from "@/lib/api/waveaEvidence";
import { ApiRequestError } from "@/lib/apiClient";
import { buildSutBillingHref } from "@/lib/constants";
import type { WaveACoverage, WaveAEvidenceBlock, WaveAEvidencePage, WaveAEvidenceRow } from "@/lib/domains/waveaEvidence";
import { useT } from "@/lib/i18n/useTranslations";
import { findFindingRowElement } from "@/lib/patientRoute";
import { groupWaveAReviewRows } from "@/lib/groupWaveAReviewRows";
import { getWaveAEvidencePresentation } from "@/lib/waveaEvidencePresentation";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { motionScrollBehavior } from "@/lib/motion";

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
  const observedFields = ["observed_billed_amount_try", "observed_amount_basis", "observed_amount_unavailable_reason"] as const;
  if (kind === "financial_rows" && row.line_kind === "procedure") {
    if (!row.line_id || observedFields.some((field) => !(field in row))) return false;
    if (row.observed_billed_amount_try == null) {
      if (row.observed_amount_basis != null || ![
        "procedure_line_missing", "procedure_line_ambiguous", "procedure_line_owner_mismatch",
        "procedure_line_charge_invalid", "procedure_line_charge_not_cent_exact",
      ].includes(row.observed_amount_unavailable_reason ?? "")) return false;
    } else if (
      row.observed_amount_basis !== "procedure_claim_line.billed_amount_try" ||
      row.observed_amount_unavailable_reason != null ||
      !isCentAmount(row.observed_billed_amount_try)
    ) return false;
  } else if (observedFields.some((field) => field in row)) return false;
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

/** True when a patient preview block cannot be shown: absent, unavailable or failing the ownership and total checks. */
export function waveABlockUnavailable(block: WaveAEvidenceBlock | undefined, patientId: string, kind: WaveAEvidenceKind): boolean {
  return !validPatientBlock(block, patientId, kind);
}

/**
 * The one notice that stands in for every unavailable extended-evidence
 * section of a view. With `layerOff` the backend said the layer is not active
 * in this build; otherwise the cause is unknown and only "unavailable" is said.
 * Either way it never reads as a zero count.
 */
export function WaveAUnavailableNotice({ layerOff, className }: { layerOff: boolean; className?: string }) {
  const t = useT();
  return (
    <p
      id="wavea-unavailable"
      role="note"
      className={`scroll-mt-24 rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-3 text-sm text-[var(--text-muted)]${className ? ` ${className}` : ""}`}
    >
      {t(layerOff ? "billing.wavea.layerOff" : "billing.wavea.unavailable")}
    </p>
  );
}

export function matchesPatientEvidenceScope(page: WaveAEvidencePage, selectedClaimId?: string | null): boolean {
  return selectedClaimId
    ? page.scope === "bill" && page.claim_id === selectedClaimId
    : page.scope === "patient" && page.claim_id === null;
}

export function WaveACoverageSummary({ coverage, selectedSection }: {
  coverage?: WaveACoverage | null;
  selectedSection?: string | null;
}) {
  const t = useT();
  const groups = Object.entries(coverage?.by_group ?? {}).sort(([a], [b]) => a.localeCompare(b));
  const totals = groups.reduce(
    (sum, [, counts]) => ({
      evaluated: sum.evaluated + counts.evaluated,
      missing_inputs: sum.missing_inputs + counts.missing_inputs,
      unavailable: sum.unavailable + counts.unavailable,
    }),
    { evaluated: 0, missing_inputs: 0, unavailable: 0 },
  );
  return (
    <details id="wavea-coverage" open={selectedSection === "wavea-coverage" || undefined} className="scroll-mt-24 rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-3 text-sm">
      <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
        {t("billing.wavea.coverageTitle")} · {coverage
          ? t("billing.wavea.evaluationCount", { count: coverage.evaluation_count })
          : t("billing.wavea.countUnavailable")}
        <span className="mt-1 block text-xs font-normal tabular-nums text-[var(--text-secondary)]">
          {coverage ? t("billing.wavea.coverageSummary", {
            groups: groups.length,
            evaluated: totals.evaluated,
            missing: totals.missing_inputs,
            unavailable: totals.unavailable,
          }) : t("billing.wavea.unavailable")}
        </span>
        {coverage && (!coverage.available || totals.missing_inputs > 0 || totals.unavailable > 0) && (
          <span className="mt-1 block text-xs font-normal text-[var(--text-muted)]">{t("billing.wavea.coverageCompact")}</span>
        )}
        {coverage && !coverage.available && (
          <span className="mt-1 block text-xs font-normal text-[var(--text-muted)]">{t("billing.wavea.coveragePartial")}</span>
        )}
      </summary>
      {coverage && <>
        <h4 className="mt-2 font-medium">{t("billing.wavea.coverageDetails")}</h4>
        <div className="mt-2 space-y-2 text-[var(--text-secondary)]">
          {coverage.available && totals.missing_inputs === 0 && totals.unavailable === 0 && <p>{t("billing.wavea.coverageComplete")}</p>}
          <p className="text-xs">{t("billing.wavea.coverageExplainer")}</p>
        </div>
        {groups.length > 0 && (
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
        )}
      </>}
    </details>
  );
}

function clauseKey(row: WaveAEvidenceRow): string | null {
  const key = row.regulatory_source?.clause_key?.trim();
  return key || null;
}

function sourceReferences(row: WaveAEvidenceRow): string[] {
  const references = row.regulatory_source?.source_locators;
  const locators = (Array.isArray(references) ? references : []).filter((reference): reference is string =>
    typeof reference === "string" && reference.trim().length > 0,
  ).map((reference) => reference.trim());
  const fatura = row.regulatory_source?.fatura_inceleme_ref?.trim();
  if (fatura && !locators.includes(fatura)) locators.push(fatura);
  return locators;
}

function sourceStatusKey(row: WaveAEvidenceRow): string {
  return clauseKey(row) || sourceReferences(row).length > 0
    ? "billing.wavea.sourceLocator"
    : "billing.wavea.sourceUnverified";
}

function WaveATechnicalDetails({
  row,
  onOpenClause,
}: {
  row: WaveAEvidenceRow;
  onOpenClause?: (clauseKey: string) => void;
}) {
  const t = useT();
  const source = clauseKey(row);
  const references = sourceReferences(row);
  return (
    <details className="mt-2 text-xs text-[var(--text-muted)]">
      <summary className="cursor-pointer">{t("billing.wavea.technicalDetails")}</summary>
      <div className="mt-1 space-y-1 break-all">
        <p>{row.rule_id}{row.reason ? ` · ${row.reason}` : ""}</p>
        <p>{row.line_kind}{row.line_id ? `:${row.line_id}` : ""}</p>
        {source && onOpenClause ? (
          <button type="button" className="rounded-[var(--r-sm)] border border-[var(--border-strong)] px-2 py-1 font-mono whitespace-nowrap hover:bg-[var(--surface-tint)]" onClick={() => onOpenClause(source)}>{t("billing.wavea.sutClause", { coordinate: formatSutSectionLabel(source.split("#")[0]) })}</button>
        ) : source ? <p>{source}</p> : null}
        {references.length > 0 && <p>{references.join(" · ")}</p>}
      </div>
    </details>
  );
}

function PatientWaveAReviewList({
  rows,
  selectedFindingId,
  selectedClaimId,
  onOpenClause,
}: {
  rows: WaveAEvidenceRow[];
  selectedFindingId?: string | null;
  selectedClaimId?: string | null;
  onOpenClause?: (clauseKey: string) => void;
}) {
  const t = useT();
  const groups = groupWaveAReviewRows(rows);
  return (
    <div className="space-y-3">
      {groups.map((group) => {
        const first = group.rows[0];
        const copy = getWaveAEvidencePresentation(first, t);
        const selected = group.rows.some((row) => row.evidence_id === selectedFindingId);
        return (
          <article key={group.key} className="rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Chip variant="warning">{t("billing.wavea.review")}</Chip>
              <span className="text-xs tabular-nums text-[var(--text-muted)]">
                {group.claimCount > 0
                  ? t("billing.wavea.shownClaimCount", { count: group.claimCount })
                  : t("billing.wavea.claimReferenceUnavailable")}
              </span>
            </div>
            <h4 className="mt-2 font-semibold text-[var(--text-primary)]">{copy.title}</h4>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">{copy.nextStep}</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{t(sourceStatusKey(first))}</p>
            <details className="mt-3" open={selected || undefined}>
              <summary className="cursor-pointer text-sm font-medium text-[var(--text-primary)]">
                {t("billing.wavea.reviewGroupDetails", { count: group.rows.length })}
              </summary>
              <ul className="mt-2 divide-y divide-[var(--border-subtle)]">
                {group.rows.map((row) => {
                  const href = buildSutBillingHref(row.patient_id, {
                    claimId: row.claim_id ?? selectedClaimId ?? undefined,
                    section: sectionId("reviews"),
                    findingId: row.evidence_id,
                  });
                  return (
                    <li
                      key={row.evidence_id}
                      data-finding-id={row.evidence_id}
                      data-selected={selectedFindingId === row.evidence_id ? "true" : undefined}
                      className={`scroll-mt-24 py-3 text-sm ${selectedFindingId === row.evidence_id ? "bg-[var(--gold-subtle)]" : ""}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="break-all font-medium text-[var(--text-primary)]">
                          {row.claim_id || "—"}
                          {row.line_id ? ` · ${row.line_id}` : ""}
                        </span>
                        <PatientTabLink patientId={row.patient_id} href={href} className="underline">
                          {t("billing.wavea.evidenceLink")}
                        </PatientTabLink>
                      </div>
                      <WaveATechnicalDetails row={row} onOpenClause={onOpenClause} />
                    </li>
                  );
                })}
              </ul>
            </details>
          </article>
        );
      })}
    </div>
  );
}

function PatientWaveAAdvisoryList({
  rows,
  selectedFindingId,
  selectedClaimId,
  onOpenClause,
}: {
  rows: WaveAEvidenceRow[];
  selectedFindingId?: string | null;
  selectedClaimId?: string | null;
  onOpenClause?: (clauseKey: string) => void;
}) {
  const t = useT();
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {rows.map((row) => {
        const copy = getWaveAEvidencePresentation(row, t);
        const href = buildSutBillingHref(row.patient_id, {
          claimId: row.claim_id ?? selectedClaimId ?? undefined,
          section: sectionId("advisories"),
          findingId: row.evidence_id,
        });
        return (
          <article
            key={row.evidence_id}
            data-finding-id={row.evidence_id}
            data-selected={selectedFindingId === row.evidence_id ? "true" : undefined}
            className={`scroll-mt-24 rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-4 ${selectedFindingId === row.evidence_id ? "bg-[var(--gold-subtle)]" : ""}`}
          >
            <Chip variant="neutral">
              {t(row.advisory_kind === "information" ? "billing.wavea.information" : "billing.wavea.permission")}
            </Chip>
            <h4 className="mt-2 font-semibold text-[var(--text-primary)]">{copy.title}</h4>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">{copy.nextStep}</p>
            <p className="mt-2 break-all text-xs text-[var(--text-secondary)]">
              {row.claim_id || "—"}{row.line_id ? ` · ${row.line_id}` : ""}
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{t(sourceStatusKey(row))}</p>
            <PatientTabLink patientId={row.patient_id} href={href} className="mt-2 inline-block text-sm underline">
              {t("billing.wavea.evidenceLink")}
            </PatientTabLink>
            <WaveATechnicalDetails row={row} onOpenClause={onOpenClause} />
          </article>
        );
      })}
    </div>
  );
}

export function WaveAEvidenceRowsTable({
  rows,
  kind,
  onOpenClause,
  selectedFindingId,
  selectedClaimId,
  patientId,
}: {
  rows: WaveAEvidenceRow[];
  kind: WaveAEvidenceKind;
  onOpenClause?: (clauseKey: string) => void;
  selectedFindingId?: string | null;
  selectedClaimId?: string | null;
  patientId?: string;
}) {
  const t = useT();
  const financial = kind === "financial_rows";
  const section = sectionId(kind);

  return (
    <DataTable minWidth={880}>
      <thead>
        <tr>
          <th>{t("billing.wavea.type")}</th>
          <th>{t(financial ? "billing.wavea.technicalDetails" : "billing.wavea.ruleAndReason")}</th>
          <th>{t("billing.wavea.claimAndLine")}</th>
          <th>{t("billing.wavea.source")}</th>
          <th className="text-right">{financial ? t("billing.wavea.amount") : patientId ? t("billing.wavea.evidenceLink") : t("billing.wavea.patient")}</th>
          {financial && <th>{patientId ? t("billing.wavea.evidenceLink") : t("billing.wavea.patient")}</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const source = clauseKey(row);
          const authoredReferences = sourceReferences(row);
          const copy = getWaveAEvidencePresentation(row, t);
          const href = buildSutBillingHref(row.patient_id, {
            claimId: financial ? selectedClaimId ?? undefined : row.claim_id ?? selectedClaimId ?? undefined,
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
                {financial ? (
                  <>
                    <div className="font-mono text-xs text-[var(--text-primary)]">{row.rule_id}</div>
                    {row.reason && <div className="mt-1 text-xs text-[var(--text-secondary)]">{row.reason}</div>}
                  </>
                ) : (
                  <>
                    <div className="font-medium text-[var(--text-primary)]">{copy.title}</div>
                    <div className="mt-1 text-xs text-[var(--text-secondary)]">{copy.nextStep}</div>
                    <details className="mt-1 text-xs text-[var(--text-muted)]">
                      <summary className="cursor-pointer">{t("billing.wavea.technicalDetails")}</summary>
                      <p className="mt-1 break-all">{row.rule_id}{row.reason ? ` · ${row.reason}` : ""}</p>
                    </details>
                  </>
                )}
              </td>
              <td className="font-mono text-xs">
                {row.claim_id || "—"}
                {row.line_id ? ` · ${row.line_id}` : ""}
              </td>
              <td className="text-xs">
                {source && onOpenClause ? (
                  <button type="button" className="rounded-[var(--r-sm)] border border-[var(--border-strong)] px-2 py-1 font-mono whitespace-nowrap hover:bg-[var(--surface-tint)]" onClick={() => onOpenClause(source)}>
                    {t("billing.wavea.sutClause", { coordinate: formatSutSectionLabel(source.split("#")[0]) })}
                  </button>
                ) : source ? (
                  <span className="font-mono">{source}</span>
                ) : authoredReferences.length > 0 ? (
                  <span className="font-mono">
                    {authoredReferences.map((reference, index) => (
                      <span key={`${reference}:${index}`}>
                        {index > 0 ? " · " : null}
                        {onOpenClause && reference.includes("#") ? (
                          <button type="button" className="rounded-[var(--r-sm)] border border-[var(--border-strong)] px-2 py-1 font-mono whitespace-nowrap hover:bg-[var(--surface-tint)]" onClick={() => onOpenClause(reference)}>
                            {t("billing.wavea.sutClause", { coordinate: formatSutSectionLabel(reference.split("#")[0]) })}
                          </button>
                        ) : reference}
                      </span>
                    ))}
                  </span>
                ) : null}
                <div className={source || authoredReferences.length > 0 ? "mt-1 text-[var(--text-muted)]" : "text-[var(--text-muted)]"}>
                  {t(sourceStatusKey(row))}
                </div>
              </td>
              {financial && (
                <td className="text-right tabular-nums whitespace-nowrap">
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
                  {row.line_kind === "procedure" && row.observed_billed_amount_try == null &&
                    row.observed_amount_unavailable_reason && (
                      <div className="mt-1 text-xs text-[var(--text-secondary)]">
                        {t("billing.wavea.observedBilledCharge")}: {t(`billing.wavea.${row.observed_amount_unavailable_reason}`)}
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
                  {patientId ? t("billing.wavea.evidenceLink") : row.patient_id}
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
  selectedClaimId,
  selectedSection,
}: {
  patientId: string;
  kind: WaveAEvidenceKind;
  block?: WaveAEvidenceBlock;
  onOpenClause?: (clauseKey: string) => void;
  selectedFindingId?: string | null;
  selectedClaimId?: string | null;
  selectedSection?: string | null;
}) {
  const t = useT();
  const sectionRef = useRef<HTMLElement>(null);
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
  }, [patientId, kind, selectedClaimId, block?.available, block?.total_rows, block?.rows]);

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
      { kind, offset: 0, limit: 1, evidenceId: selectedFindingId, billClaimId: selectedClaimId },
      { signal: controller.signal },
    ).then((page) => {
      if (controller.signal.aborted) return;
      const exact = Array.isArray(page.rows) ? page.rows[0] : null;
      if (
        page.available !== true || page.patient_id !== patientId || page.kind !== kind ||
        !matchesPatientEvidenceScope(page, selectedClaimId) ||
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
  }, [patientId, kind, selectedClaimId, selectedFindingId, unavailable, rows]);

  useEffect(() => {
    if (!selectedFindingId || typeof document === "undefined") return;
    if (!rows.some((row) => row.evidence_id === selectedFindingId) && selectedRow?.evidence_id !== selectedFindingId) return;
    const target = sectionRef.current && findFindingRowElement(sectionRef.current, selectedFindingId);
    let parent = target?.parentElement;
    while (parent && parent !== sectionRef.current) {
      if (parent instanceof HTMLDetailsElement) parent.open = true;
      parent = parent.parentElement;
    }
    target?.scrollIntoView({
      behavior: motionScrollBehavior(),
      block: "start",
    });
  }, [rows, selectedRow, selectedFindingId]);

  const total = block?.total_rows;
  const canLoadMore = !unavailable && typeof total === "number" && rows.length < total;
  const displayRows = selectedRow && !rows.some((row) => row.evidence_id === selectedRow.evidence_id)
    ? [selectedRow, ...rows]
    : rows;
  const selectedInSection = selectedFindingId?.startsWith(evidencePrefix(kind)) ?? false;
  const loadMore = async () => {
    if (!canLoadMore || loading) return;
    const controller = new AbortController();
    pending.current = controller;
    setLoading(true);
    setError(false);
    try {
      const next = await getPatientWaveAEvidence(
        patientId,
        { kind, offset: rows.length, billClaimId: selectedClaimId },
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      const incoming = next.rows;
      if (
        next.available !== true ||
        next.patient_id !== patientId ||
        next.kind !== kind ||
        !matchesPatientEvidenceScope(next, selectedClaimId) ||
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

  const body = <>
      {unavailable ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.wavea.unavailable")}</p>
      ) : kind === "advisories" ? (
          <div className="space-y-2">
            <p className="text-xs text-[var(--text-muted)]">{t("billing.wavea.advisoryNotice")}</p>
            {displayRows.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">{t("billing.wavea.noRows")}</p>
            ) : (
              <PatientWaveAAdvisoryList rows={displayRows} onOpenClause={onOpenClause} selectedFindingId={selectedFindingId} selectedClaimId={selectedClaimId} />
            )}
          </div>
      ) : displayRows.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.wavea.noRows")}</p>
      ) : kind === "reviews" ? (
        <>
          <p className="text-xs text-[var(--text-muted)]">{t("billing.wavea.reviewNotice")}</p>
          <PatientWaveAReviewList rows={displayRows} onOpenClause={onOpenClause} selectedFindingId={selectedFindingId} selectedClaimId={selectedClaimId} />
        </>
      ) : (
        <WaveAEvidenceRowsTable rows={displayRows} kind={kind} onOpenClause={onOpenClause} selectedFindingId={selectedFindingId} selectedClaimId={selectedClaimId} patientId={patientId} />
      )}
      {error && <p role="alert" className="text-sm text-[var(--danger)]">{t("billing.wavea.loadFailed")}</p>}
      {canLoadMore && (
        <button type="button" disabled={loading} onClick={loadMore} className="text-sm font-medium underline disabled:opacity-50">
          {loading ? t("billing.wavea.loading") : t("billing.wavea.loadMore", { shown: rows.length, total })}
        </button>
      )}
    </>;

  return (
    <section ref={sectionRef} id={sectionId(kind)} className="space-y-2 scroll-mt-24">
      {kind === "financial_rows" ? <>
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{t(titleKey(kind))}</h3>
        {body}
      </> : (
        <details open={selectedInSection || selectedSection === sectionId(kind) || undefined} className="rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-3">
          <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">
            {t(kind === "reviews" ? "billing.wavea.reviewHeading" : titleKey(kind))} · {unavailable
              ? t("billing.wavea.countUnavailable")
              : t(kind === "reviews" ? "billing.wavea.reviewCount" : "billing.wavea.advisoryCount", { count: total })}
            {unavailable ? <span className="mt-1 block text-xs font-normal text-[var(--text-muted)]">{t("billing.wavea.unavailable")}</span>
              : <>
                {displayRows.some((row) => ["not_evaluated", "missing_inputs"].includes(row.evaluation_status)) && <span className="ml-2 text-xs font-normal text-[var(--text-muted)]">{t("billing.wavea.notEvaluated")}</span>}
                {displayRows.some((row) => row.evaluation_status === "unavailable") && <span className="ml-2 text-xs font-normal text-[var(--text-muted)]">{t("billing.wavea.statusUnavailable")}</span>}
                {displayRows.some((row) => ["partial", "partial_exact"].includes(row.evaluation_status)) && <span className="ml-2 text-xs font-normal text-[var(--text-muted)]">{t("billing.wavea.statusPartial")}</span>}
              </>}
          </summary>
          <div className="mt-3 space-y-2">{body}</div>
        </details>
      )}
    </section>
  );
}
