"use client";

import { useState } from "react";
import type { FactCheckRollup } from "@/lib/api/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtNum } from "../../shared";
import { FactCheckChip } from "./shared";

export function FactCheckRollupBanner({ rollup }: { rollup: FactCheckRollup }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const { by_verdict: counts } = rollup;
  const items = (
    [
      ["COMPLIANT", counts.COMPLIANT],
      ["PARTIAL", counts.PARTIAL],
      ["HEURISTIC", counts.HEURISTIC],
      ["NEEDS_CLAIM_LINES", counts.NEEDS_CLAIM_LINES],
      ["WRONG", counts.WRONG],
    ] as const
  ).filter(([, n]) => n > 0);

  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-soft)] px-3 py-2.5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between text-left"
      >
        <div>
          <p className="text-xs font-semibold text-[var(--text-secondary)]">
            {t("sections.ruleDatabase.factCheck.title")}
          </p>
          <p className="text-[10px] text-[var(--text-muted)]">
            {t("sections.ruleDatabase.factCheck.subtitle")}
          </p>
        </div>
        <span className="text-[10px] text-[var(--text-muted)]">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-2 border-t border-[var(--border-subtle)] pt-2">
          <p className="text-[10px] text-[var(--text-muted)]">
            {t("sections.ruleDatabase.factCheck.banner", {
              closed: rollup.audit_closed,
              total: fmtNum(rollup.total_units),
            })}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {items.map(([verdict, count]) => (
              <span
                key={verdict}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]"
              >
                <FactCheckChip verdict={verdict} />
                <span className="tabular-nums font-semibold">{fmtNum(count)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
