"use client";

import { useEffect, useState } from "react";
import { getClause, type RuleClause } from "@/lib/api/sut";
import { isAbortError } from "@/lib/api/request";
import { useT } from "@/lib/i18n/useTranslations";
import { formatSutSectionLabel } from "@/lib/billingReportFields";

/**
 * Global clause-text drawer: given a Track E `clause_key` (coord#hash),
 * fetches the clause via GET /api/rules/clauses/{clause_key} and renders
 * coordinate, section title, and gazette text (`text_tr`). Display text is
 * never duplicated into billing findings — it always comes from the corpus.
 * Renders nothing while `clauseKey` is null (closed). The body remounts per
 * clause_key so each open starts from fresh loading state.
 */
export function SutClauseDrawer({
  clauseKey,
  onClose,
}: {
  clauseKey: string | null;
  onClose: () => void;
}) {
  if (!clauseKey) {
    return null;
  }
  return <SutClauseDrawerBody key={clauseKey} clauseKey={clauseKey} onClose={onClose} />;
}

function SutClauseDrawerBody({
  clauseKey,
  onClose,
}: {
  clauseKey: string;
  onClose: () => void;
}) {
  const t = useT();
  const [clause, setClause] = useState<RuleClause | null>(null);
  const [failed, setFailed] = useState(false);
  const loading = clause === null && !failed;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getClause(clauseKey, { signal: controller.signal })
      .then((result) => {
        if (active) setClause(result);
      })
      .catch((error) => {
        if (!active || isAbortError(error)) return;
        setFailed(true);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [clauseKey]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const coordinateLabel = clause?.clause_coordinate
    ? formatSutSectionLabel(clause.clause_coordinate)
    : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-24"
      role="dialog"
      aria-modal="true"
      aria-label={t("billing.clauseDrawer.ariaLabel")}
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-[var(--r-lg)] border border-[var(--border-subtle)] bg-[var(--surface-base)] shadow-[var(--shadow-2)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-4 py-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              {t("billing.clauseDrawer.kicker")}
            </p>
            <h2 className="truncate font-mono text-sm font-semibold text-[var(--text-primary)]">
              {coordinateLabel ?? t("billing.clauseDrawer.title")}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="shrink-0 rounded-[var(--r-md)] px-2 py-1 text-lg leading-none text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-tint)] hover:text-[var(--text-primary)]"
          >
            &times;
          </button>
        </div>

        <div className="max-h-[60vh] space-y-3 overflow-y-auto px-4 py-4">
          {loading && (
            <p className="text-sm text-[var(--text-secondary)]">{t("common.loading")}</p>
          )}
          {failed && (
            <p className="text-sm text-[var(--danger)]">{t("common.loadFailed")}</p>
          )}
          {clause && (
            <>
              {clause.section_title && (
                <p lang="tr" className="text-xs font-semibold text-[var(--text-secondary)]">
                  {clause.section_title}
                </p>
              )}
              <p lang="tr" className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-primary)]">
                {clause.text_tr ?? t("common.unavailable")}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
