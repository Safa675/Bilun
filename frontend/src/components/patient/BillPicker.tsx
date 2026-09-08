"use client";

import { useMemo } from "react";
import { Eyebrow } from "@/components/primitives";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { fmtDate } from "@/lib/i18n/formatters";
import { useT } from "@/lib/i18n/useTranslations";
import type { PatientClaimSummary } from "@/lib/domains/sut";

export interface BillPickerProps {
  claims: PatientClaimSummary[];
  selectedClaimId: string | null;
  onSelectClaim: (claimId: string | null) => void;
  disabled?: boolean;
}

function priorityDot(priority: string | null | undefined): string {
  switch (priority) {
    case "high":
      return "bg-[var(--danger)]";
    case "medium":
      return "bg-[var(--warning)]";
    case "low":
      return "bg-[var(--success)]";
    default:
      return "bg-[var(--text-muted)]";
  }
}

function priorityChipClass(priority: string | null | undefined): string {
  switch (priority) {
    case "high":
      return "border-[color-mix(in_srgb,var(--danger)_28%,transparent)] bg-[color-mix(in_srgb,var(--danger)_8%,transparent)] text-[var(--danger)]";
    case "medium":
      return "border-[color-mix(in_srgb,var(--warning)_28%,transparent)] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] text-[var(--warning)]";
    case "low":
      return "border-[color-mix(in_srgb,var(--success)_28%,transparent)] bg-[color-mix(in_srgb,var(--success)_8%,transparent)] text-[var(--success)]";
    default:
      return "border-[var(--border-subtle)] bg-[var(--surface-soft)] text-[var(--text-muted)]";
  }
}

/** Parse a claim date defensively; invalid/empty -> 0 so it sorts to the
 *  bottom instead of yielding NaN and corrupting the sort order. */
function claimDateMillis(iso: string | null | undefined): number {
  if (!iso) return 0;
  const ms = new Date(iso).getTime();
  return Number.isNaN(ms) ? 0 : ms;
}

export default function BillPicker({
  claims,
  selectedClaimId,
  onSelectClaim,
  disabled = false,
}: BillPickerProps) {
  const t = useT();
  const sortedClaims = useMemo(
    () =>
      [...claims].sort(
        (a, b) =>
          claimDateMillis(b.claim_start_date) - claimDateMillis(a.claim_start_date),
      ),
    [claims],
  );

  const allSelected = selectedClaimId === null;

  return (
    <div className="space-y-3">
      <Eyebrow>{t("patient.billPicker.label")}</Eyebrow>
      <div className="flex gap-2 overflow-x-auto pb-1">
        <button
          type="button"
          onClick={() => onSelectClaim(null)}
          disabled={disabled}
          className={`shrink-0 rounded-[var(--r-md)] border px-3 py-2.5 text-left text-sm transition-colors ${
            allSelected
              ? "border-[var(--gold)] bg-[var(--gold)]/10 text-[var(--text-primary)]"
              : "border-[var(--border-subtle)] bg-[var(--surface-base)] text-[var(--text-secondary)] hover:bg-[var(--surface-soft)]"
          } disabled:cursor-not-allowed disabled:opacity-60`}
        >
          <span className="block font-medium text-[var(--text-primary)]">
            {t("patient.billPicker.allBills")}
          </span>
          <span className="block text-xs text-[var(--text-muted)]">
            {claims.length}{" "}
            {claims.length === 1
              ? t("patient.billPicker.claimSingular")
              : t("patient.billPicker.claimPlural")}
          </span>
        </button>

        {sortedClaims.map((claim) => {
          const isSelected = selectedClaimId === claim.claim_id;
          const recoverable = claim.recoverable_try ?? null;
          const hasRecoverable = recoverable !== null && recoverable > 0;
          return (
            <button
              key={claim.claim_id}
              type="button"
              onClick={() => onSelectClaim(claim.claim_id)}
              disabled={disabled}
              className={`relative shrink-0 rounded-[var(--r-md)] border px-3 py-2.5 text-left text-sm transition-colors ${
                isSelected
                  ? "border-[var(--gold)] bg-[var(--gold)]/10"
                  : "border-[var(--border-subtle)] bg-[var(--surface-base)] hover:bg-[var(--surface-soft)]"
              } disabled:cursor-not-allowed disabled:opacity-60`}
            >
              <div className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${priorityDot(claim.priority)}`} />
                <span className="font-medium text-[var(--text-primary)]">
                  {fmtDate(claim.claim_start_date)}
                </span>
              </div>
              <span className="block text-xs text-[var(--text-muted)]">
                {claim.claim_id} · {t("patient.billPicker.billMeta", {
                  claimType: claim.claim_type,
                  amount: fmtTRY2(claim.expected_total_billed_try),
                })}
              </span>
              {hasRecoverable && (
                <span
                  className={`mt-1.5 inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${priorityChipClass(
                    claim.priority,
                  )}`}
                >
                  {fmtTRY2(recoverable)} {t("patient.billPicker.recoverable")}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
