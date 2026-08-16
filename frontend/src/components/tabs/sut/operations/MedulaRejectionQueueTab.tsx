"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtDateTime } from "@/lib/i18n/formatters";
import { translateApiText } from "@/lib/apiMessages";
import { getMedulaRejectionQueue } from "@/lib/api/sut";
import { buildSutPatientHref } from "@/lib/constants";
import type {
  MedulaRejectionQueueResponse,
  MedulaRejectionQueueRow,
} from "@/lib/domains/sut";
import {
  DataTable,
  Eyebrow,
  Section,
  Surface,
} from "@/components/primitives";

const WRAPPED_HEADER_STYLE = {
  whiteSpace: "normal" as const,
  minWidth: 120,
};

type TranslationFn = (key: string) => string;

/**
 * Renders the offending line a MEDULA rejection points at. Shows a small type
 * chip (İşlem/Malzeme/İlaç/Fatura) plus the line id; for procedures the
 * procedure code is shown as well. This replaces the old "Procedure" column
 * that always pointed at an unrelated exam line.
 */
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
      <span className="inline-flex w-fit rounded border border-[var(--border-subtle)] px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    sonuc_kodu: "",
    medula_stage: "",
    matched_only: false,
    rebill_permitted_only: false,
    q: "",
  });

  const pageSize = 50;

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

  const visibleRows = filters.matched_only
    ? (data?.rows ?? []).filter((row) => row.playbook_matched)
    : (data?.rows ?? []);

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / pageSize));

  return (
    <div className="space-y-5">
      <Surface variant="base" padding="lg">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              {t("operations.queue.filters.resultCode")}
            </label>
            <input
              type="text"
              value={filters.sonuc_kodu}
              onChange={(e) =>
                setFilters((f) => ({ ...f, sonuc_kodu: e.target.value, page: 1 }))
              }
              placeholder="1688"
              className="w-full rounded-md border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-1.5 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              {t("operations.queue.filters.stage")}
            </label>
            <input
              type="text"
              value={filters.medula_stage}
              onChange={(e) =>
                setFilters((f) => ({ ...f, medula_stage: e.target.value, page: 1 }))
              }
              placeholder="fatura_kayit"
              className="w-full rounded-md border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-1.5 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              {t("operations.queue.filters.searchPlaceholder")}
            </label>
            <input
              type="text"
              value={filters.q}
              onChange={(e) =>
                setFilters((f) => ({ ...f, q: e.target.value, page: 1 }))
              }
              className="w-full rounded-md border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-1.5 text-sm"
            />
          </div>
          <div className="flex flex-col justify-end gap-2">
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={filters.matched_only}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, matched_only: e.target.checked, page: 1 }))
                }
                className="rounded border-[var(--border-subtle)]"
              />
              {t("operations.queue.filters.matchedOnly")}
            </label>
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={filters.rebill_permitted_only}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    rebill_permitted_only: e.target.checked,
                    page: 1,
                  }))
                }
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

      {!data?.ingest_available && !loading && !error && (
        <Surface variant="base" padding="lg">
          <p className="text-sm text-[var(--text-secondary)]">
            {t("operations.queue.empty.noIngest")}
          </p>
        </Surface>
      )}

      {data?.ingest_available && visibleRows.length === 0 && !loading && (
        <Surface variant="base" padding="lg">
          <p className="text-sm text-[var(--text-secondary)]">
            {hasFilters ? t("optimizer.pagination.noMatching") : t("operations.queue.empty.noEvents")}
          </p>
        </Surface>
      )}

      {data?.ingest_available && visibleRows.length > 0 && (
        <Section
          title={t("operations.queue.title")}
          trailing={
            <span className="font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]">
              {data?.total ?? 0}
            </span>
          }
        >
          <DataTable minWidth={1180} className="text-[0.82rem]">
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
              {visibleRows.map((row: MedulaRejectionQueueRow) => (
                <tr key={row.rejection_event_id}>
                  <td>
                    <Link
                      href={buildSutPatientHref(row.patient_id)}
                      className="font-semibold text-slate-950 hover:text-[var(--gold-hover)]"
                    >
                      {row.patient_id}
                    </Link>
                  </td>
                  <td>
                    <Link
                      href={buildSutPatientHref(row.patient_id, {
                        claimId: row.claim_id,
                        section: "medula-playbook",
                      })}
                      className="font-mono text-xs font-semibold text-slate-950 hover:text-[var(--gold-hover)]"
                    >
                      {row.claim_id}
                    </Link>
                  </td>
                  <td>{row.rejection_timestamp ? fmtDateTime(row.rejection_timestamp) : "—"}</td>
                  <td>{row.medula_stage ? translateApiText(row.medula_stage) : "—"}</td>
                  <td className="font-mono text-xs">{row.sonuc_kodu}</td>
                  <td>{row.hata_mesaji ? translateApiText(row.hata_mesaji) : "—"}</td>
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
                      ? row.playbook_key ?? "—"
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
              ))}
            </tbody>
          </DataTable>

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="rounded-md border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:opacity-50"
            >
              {t("optimizer.pagination.prev")}
            </button>
            <span className="text-xs font-semibold text-[var(--text-secondary)]">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="rounded-md border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:opacity-50"
            >
              {t("optimizer.pagination.next")}
            </button>
          </div>
        </Section>
      )}
    </div>
  );
}
