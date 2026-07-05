"use client";

import { useEffect, useState } from "react";
import { getProseInventory, getRuleSections } from "@/lib/api/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtNum } from "../../shared";

export function GlossaryStrip({
  clauseCount,
  ruleEngineCount,
  numberedClauseCount,
  proseClauseCount,
  structuralClauseCount,
}: {
  clauseCount: number;
  ruleEngineCount: number;
  numberedClauseCount: number;
  proseClauseCount: number;
  structuralClauseCount: number;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  // Live figures fetched once from the prose-inventory + section rollup endpoints
  // (previously hardcoded 337 / 951 / 481, which drifted after pipeline rebuilds).
  const [jsonRuleCount, setJsonRuleCount] = useState<number | null>(null);
  const [sectionRows, setSectionRows] = useState<number | null>(null);
  const [uniqueSections, setUniqueSections] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const inv = await getProseInventory();
        if (!active) return;
        const sum = (inv.engines ?? [])
          .reduce((acc, e) => acc + (e.rule_count ?? 0), 0);
        setJsonRuleCount(sum);
      } catch {
        /* leave null — UI falls back */
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [rows, unique] = await Promise.all([
          getRuleSections({ per_page: 1, page: 1 }),
          getRuleSections({ per_page: 1, page: 1, consolidate: true }),
        ]);
        if (!active) return;
        setSectionRows(rows.total);
        setUniqueSections(unique.total);
      } catch {
        /* leave null */
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-soft)] px-3 py-2.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-[11px] font-medium text-[var(--text-secondary)]"
      >
        <span>{t("sections.ruleDatabase.coverage.glossary.toggle")}</span>
        <span className="text-[var(--text-muted)]">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <dl className="mt-2 space-y-1.5 text-[11px] leading-relaxed text-[var(--text-secondary)]">
          <div>
            <dt className="font-semibold text-[var(--text-primary)]">Hüküm</dt>
            <dd>
              {t("sections.ruleDatabase.coverage.glossary.hukum", { count: fmtNum(clauseCount) })}
            </dd>
            <dd className="mt-1 text-[var(--text-muted)]">
              {t("sections.ruleDatabase.coverage.glossary.hukumTurleri", {
                numbered: fmtNum(numberedClauseCount),
                prose: fmtNum(proseClauseCount),
                structural: fmtNum(structuralClauseCount),
              })}
            </dd>
          </div>
          <div>
            <dd>
              {t("sections.ruleDatabase.coverage.glossary.kuralMotoru", {
                count: ruleEngineCount,
              })}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-[var(--text-primary)]">JSON</dt>
            <dd>
              {t("sections.ruleDatabase.coverage.glossary.jsonSatir", { count: fmtNum(jsonRuleCount ?? 0) })}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-[var(--text-primary)]">§</dt>
            <dd>
              {t("sections.ruleDatabase.coverage.glossary.bolumSatiri", {
                count: fmtNum(sectionRows ?? 0),
                unique: fmtNum(uniqueSections ?? 0),
              })}
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
}
