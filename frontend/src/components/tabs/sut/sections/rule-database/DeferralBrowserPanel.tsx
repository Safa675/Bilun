"use client";

import { useEffect, useState } from "react";
import {
  listDeferrals,
  type DeferralEntry,
  type DeferralListResponse,
} from "@/lib/api/sut";
import { isAbortError } from "@/lib/api/request";
import { cn } from "@/lib/cn";
import {
  Button,
  EmptyState,
  Surface,
  Toolbar,
  buttonActiveClass,
  inputClass,
} from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtNum } from "../../shared";

const STATUS_OPTIONS = ["", "emr_blocked", "non_actionable", "tier_c_deferred"] as const;
const PER_PAGE = 40;

export function DeferralBrowserPanel({
  onCoordinateClick,
}: {
  onCoordinateClick?: (coordinateOrId: string) => void;
}) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [status, setStatus] = useState<string>("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<DeferralListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setPage(1);
  }, [debouncedQuery, status]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await listDeferrals(
          {
            q: debouncedQuery || undefined,
            status: status || undefined,
            page,
            per_page: PER_PAGE,
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
  }, [debouncedQuery, status, page, t]);

  const rows: DeferralEntry[] = result?.deferrals ?? [];
  const totalPages = result?.total_pages ?? 0;
  const total = result?.total ?? 0;

  return (
    <div className="space-y-4">
      <Toolbar
        leading={
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("sections.ruleDatabase.deferrals.searchPlaceholder")}
            className={cn(inputClass, "min-w-[220px] max-w-[360px]")}
          />
        }
        trailing={
          <div className="flex items-center gap-2">
            {STATUS_OPTIONS.map((opt) => (
              <Button
                key={opt || "all"}
                variant="secondary"
                size="compact"
                onClick={() => setStatus(opt)}
                className={cn("text-[11px]", status === opt && buttonActiveClass)}
              >
                {opt
                  ? t(`sections.ruleDatabase.deferrals.status.${opt}`)
                  : t("sections.ruleDatabase.filters.all")}
              </Button>
            ))}
          </div>
        }
      />

      {error ? (
        <Surface variant="soft" padding="md" className="text-center">
          <p className="text-sm text-[var(--danger)]">{error}</p>
        </Surface>
      ) : rows.length === 0 && !loading ? (
        <EmptyState
          title={t("sections.ruleDatabase.deferrals.empty")}
          className="min-h-0 border-transparent bg-transparent"
        />
      ) : (
        <>
          <div className="text-[11px] text-[var(--text-muted)]">
            {t("sections.ruleDatabase.deferrals.resultCount", { count: fmtNum(total) })}
          </div>
          <ul className="space-y-1.5">
            {rows.map((row) => {
              const primary = row.clause_coordinate || row.clause_id || "";
              const rowKey = primary || row.defer_reason;
              return (
                <li
                  key={rowKey}
                  className="rounded-[var(--r-sm)] border border-[var(--border-subtle)] px-3 py-2"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => primary && onCoordinateClick?.(primary)}
                      className="rounded bg-[var(--surface-default)] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[var(--text-primary)] hover:opacity-80"
                    >
                      {primary || "—"}
                    </button>
                    <span className="rounded border border-[var(--border-subtle)] px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                      {t(`sections.ruleDatabase.deferrals.status.${row.status}`)}
                    </span>
                    {row.section_id && (
                      <span className="font-mono text-[10px] text-[var(--text-muted)]">
                        {row.section_id}
                      </span>
                    )}
                  </div>
                  {row.defer_reason && (
                    <p className="mt-1 text-[11px] text-[var(--text-secondary)]">{row.defer_reason}</p>
                  )}
                  {row.text_snippet && (
                    <p className="mt-1 line-clamp-2 text-[11px] text-[var(--text-muted)]">
                      {row.text_snippet}
                    </p>
                  )}
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
  );
}
