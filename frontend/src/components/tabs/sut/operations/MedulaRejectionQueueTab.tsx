"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import PatientTabLink from "@/components/shell/PatientTabLink";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtDate } from "@/lib/i18n/formatters";
import { getMedulaRejectionQueue } from "@/lib/api/sut";
import { buildSutPatientHref } from "@/lib/constants";
import type {
  MedulaRejectionQueueResponse,
  MedulaRejectionQueueRow,
} from "@/lib/domains/sut";
import {
  Button,
  DataTable,
  Section,
  Stat,
  Surface,
  inputClass,
  selectClass,
} from "@/components/primitives";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { fmtNum } from "../shared";
import { cn } from "@/lib/cn";

const WRAPPED_HEADER_STYLE = {
  whiteSpace: "normal" as const,
  minWidth: 120,
};

const PATIENT_LINK_CLASS =
  "font-semibold text-[var(--text-primary)] hover:text-[var(--gold-hover)]";

type TranslationFn = (key: string) => string;

function RelatedLineCell({
  lineType,
  lineId,
  procedureCode,
  t,
}: {
  lineType?: string;
  lineId?: string;
  procedureCode?: string;
  t: TranslationFn;
}) {
  const chipKey = `operations.queue.lineType.${lineType || "claim"}`;
  const chip = t(chipKey);
  const shownChip = chip === chipKey ? t("operations.queue.lineType.claim") : chip;
  const id = lineId || procedureCode;
  return (
    <div className="flex flex-col gap-1">
      <span className="inline-flex w-fit rounded border border-[var(--border-subtle)] px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        {shownChip}
      </span>
      {id ? (
        <span className="font-mono text-xs">{procedureCode ? procedureCode : id}</span>
      ) : (
        <span className="text-xs text-[var(--text-muted)]">—</span>
      )}
    </div>
  );
}

export default function MedulaRejectionQueueTab() {
  const t = useT();
  const [data, setData] = useState<MedulaRejectionQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    sonuc_kodu: "",
    medula_stage: "",
    matched_only: false,
    rebill_permitted_only: false,
    q: "",
  });

  const pageSize = 50;

  const updateFilter = useCallback(
    (patch: Partial<typeof filters>) => {
      setPage(1);
      setExpandedId(null);
      setFilters((current) => ({ ...current, ...patch }));
    },
    [],
  );

  const fetchQueue = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const result = await getMedulaRejectionQueue(
          {
            page,
            page_size: pageSize,
            sonuc_kodu: filters.sonuc_kodu || undefined,
            medula_stage: filters.medula_stage || undefined,
            rebill_permitted: filters.rebill_permitted_only || undefined,
            playbook_matched: filters.matched_only || undefined,
            q: filters.q || undefined,
          },
          { signal },
        );
        if (!signal.aborted) {
          setData(result);
        }
      } catch (err) {
        if (!signal.aborted) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false);
        }
      }
    },
    [page, filters, pageSize],
  );

  useEffect(() => {
    const controller = new AbortController();
    // Data is loaded on mount / filter change; this matches the project's
    // existing effect-driven API pattern in other tabs.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchQueue(controller.signal);
    return () => controller.abort();
  }, [fetchQueue]);

  const hasFilters =
    filters.sonuc_kodu ||
    filters.medula_stage ||
    filters.matched_only ||
    filters.rebill_permitted_only ||
    filters.q;

  const rows = data?.rows ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / pageSize));
  const codeOptions = data?.facets?.sonuc_kodu ?? [];
  const stageOptions = data?.facets?.medula_stage ?? [];
  const stats = data?.stats;
  const readableLabel = (kind: "stages" | "playbooks", value: string) => {
    const key = `operations.queue.${kind}.${value}`;
    const label = t(key);
    return label === key ? value : label;
  };

  return (
    <div className="space-y-5">
      {data?.ingest_available && stats && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Surface variant="inset" padding="sm" className="border-b border-[var(--border-subtle)] lg:border-b-0">
            <Stat label={t("operations.queue.kpis.total")} value={fmtNum(stats.n_events ?? 0)} />
          </Surface>
          <Surface variant="inset" padding="sm" className="border-b border-[var(--border-subtle)] lg:border-b-0">
            <Stat label={t("operations.queue.kpis.matched")} value={fmtNum(stats.n_matched ?? 0)} />
          </Surface>
          <Surface variant="inset" padding="sm">
            <Stat
              label={t("operations.queue.kpis.rebillable")}
              value={fmtNum(stats.n_rebill_permitted ?? 0)}
            />
          </Surface>
        </div>
      )}

      <Surface variant="base" padding="lg">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              {t("operations.queue.filters.resultCode")}
            </label>
            <select
              value={filters.sonuc_kodu}
              onChange={(e) => updateFilter({ sonuc_kodu: e.target.value })}
              className={selectClass}
            >
              <option value="">{t("operations.queue.filters.all")}</option>
              {codeOptions.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              {t("operations.queue.filters.stage")}
            </label>
            <select
              value={filters.medula_stage}
              onChange={(e) => updateFilter({ medula_stage: e.target.value })}
              className={selectClass}
            >
              <option value="">{t("operations.queue.filters.all")}</option>
              {stageOptions.map((stage) => (
                <option key={stage} value={stage}>
                  {readableLabel("stages", stage)}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              {t("operations.queue.filters.searchPlaceholder")}
            </label>
            <input
              type="text"
              value={filters.q}
              onChange={(e) => updateFilter({ q: e.target.value })}
              className={inputClass}
            />
          </div>
          <div className="flex flex-col justify-end gap-2">
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={filters.matched_only}
                onChange={(e) => updateFilter({ matched_only: e.target.checked })}
                className="rounded border-[var(--border-subtle)]"
              />
              {t("operations.queue.filters.matchedOnly")}
            </label>
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={filters.rebill_permitted_only}
                onChange={(e) => updateFilter({ rebill_permitted_only: e.target.checked })}
                className="rounded border-[var(--border-subtle)]"
              />
              {t("operations.queue.filters.rebillPermittedOnly")}
            </label>
          </div>
        </div>
      </Surface>

      {error && (
        <Surface variant="base" padding="lg">
          <p className="text-sm text-[var(--danger)]">{error}</p>
        </Surface>
      )}

      {loading && !data && <SutAlertTableSkeleton />}

      {!data?.ingest_available && !loading && !error && (
        <Surface variant="base" padding="lg">
          <p className="text-sm text-[var(--text-secondary)]">
            {t("operations.queue.empty.noIngest")}
          </p>
        </Surface>
      )}

      {data?.ingest_available && rows.length === 0 && !loading && (
        <Surface variant="base" padding="lg">
          <p className="text-sm text-[var(--text-secondary)]">
            {hasFilters ? t("optimizer.pagination.noMatching") : t("operations.queue.empty.noEvents")}
          </p>
        </Surface>
      )}

      {data?.ingest_available && rows.length > 0 && (
        <Section
          title={t("operations.queue.title")}
          trailing={
            <span className="font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]">
              {fmtNum(data.total)}
            </span>
          }
        >
          <DataTable minWidth={1180} className="text-sm">
            <thead>
              <tr>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.patient")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.claim")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.rejectionDate")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.stage")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.resultCode")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.message")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.relatedLine")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.playbook")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("operations.queue.columns.rebill")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: MedulaRejectionQueueRow) => {
                const expanded = expandedId === row.rejection_event_id;
                const steps = row.corrective_steps_tr ?? [];
                return (
                  <Fragment key={row.rejection_event_id}>
                    <tr
                      className={cn("cursor-pointer", expanded && "bg-[var(--surface-soft)]")}
                      onClick={() =>
                        setExpandedId(expanded ? null : row.rejection_event_id)
                      }
                    >
                      <td className="whitespace-nowrap">
                        <PatientTabLink
                          patientId={row.patient_id}
                          href={buildSutPatientHref(row.patient_id)}
                          className={PATIENT_LINK_CLASS}
                          onClick={(event) => event.stopPropagation()}
                        >
                          {row.patient_id}
                        </PatientTabLink>
                      </td>
                      <td className="whitespace-nowrap">
                        <PatientTabLink
                          patientId={row.patient_id}
                          href={buildSutPatientHref(row.patient_id, {
                            claimId: row.claim_id,
                            section: "medula-playbook",
                          })}
                          className={cn("font-mono text-xs whitespace-nowrap", PATIENT_LINK_CLASS)}
                          onClick={(event) => event.stopPropagation()}
                        >
                          {row.claim_id}
                        </PatientTabLink>
                      </td>
                      <td className="whitespace-nowrap">{row.rejection_timestamp ? fmtDate(row.rejection_timestamp) : "—"}</td>
                      <td>{row.medula_stage ? readableLabel("stages", row.medula_stage) : "—"}</td>
                      <td className="font-mono text-xs">{row.sonuc_kodu}</td>
                      <td lang="tr">{row.hata_mesaji || "—"}</td>
                      <td>
                        <RelatedLineCell
                          lineType={row.related_line_type}
                          lineId={row.related_line_id}
                          procedureCode={row.related_procedure_code ?? undefined}
                          t={t}
                        />
                      </td>
                      <td>
                        {row.playbook_matched
                          ? (row.playbook_key ? readableLabel("playbooks", row.playbook_key) : "—")
                          : t("operations.queue.values.noTemplate")}
                      </td>
                      <td>
                        {row.rebill_permitted === true
                          ? t("operations.queue.values.yes")
                          : row.rebill_permitted === false
                            ? t("operations.queue.values.no")
                            : "—"}
                      </td>
                    </tr>
                    {expanded && (
                      <tr>
                        <td colSpan={9} className="bg-[var(--surface-soft)]">
                          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                            {t("operations.queue.correctiveSteps")}
                          </p>
                          {steps.length > 0 ? (
                            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-[var(--text-secondary)]">
                              {steps.map((step, index) => (
                                <li key={`${row.rejection_event_id}-step-${index}`}>{step}</li>
                              ))}
                            </ol>
                          ) : (
                            <p className="mt-2 text-sm text-[var(--text-muted)]">
                              {t("operations.queue.noCorrectiveSteps")}
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </DataTable>

          <div className="mt-4 flex items-center justify-between">
            <Button
              type="button"
              variant="secondary"
              size="compact"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page <= 1 || loading}
            >
              {t("optimizer.pagination.prev")}
            </Button>
            <span className="text-xs font-semibold tabular-nums text-[var(--text-secondary)]">
              {page} / {totalPages}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="compact"
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              disabled={page >= totalPages || loading}
            >
              {t("optimizer.pagination.next")}
            </Button>
          </div>
        </Section>
      )}
    </div>
  );
}
