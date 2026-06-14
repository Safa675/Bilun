"use client";

import { useMemo } from "react";
import { Eyebrow } from "@/components/primitives";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import type { PatientClaimSummary } from "@/lib/domains/sut";

export interface BillPickerProps {
  claims: PatientClaimSummary[];
  selectedClaimId: string | null;
  onSelectClaim: (claimId: string | null) => void;
  disabled?: boolean;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("tr-TR");
}

function priorityColor(priority: string | null | undefined): string {
  switch (priority) {
    case "high":
      return "bg-red-100 text-red-700 border-red-200";
    case "medium":
      return "bg-amber-100 text-amber-700 border-amber-200";
    case "low":
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    default:
      return "bg-[var(--surface-soft)] text-[var(--text-muted)] border-[var(--border-subtle)]";
  }
}

function priorityDot(priority: string | null | undefined): string {
  switch (priority) {
    case "high":
      return "bg-red-500";
    case "medium":
      return "bg-amber-500";
    case "low":
      return "bg-emerald-500";
    default:
      return "bg-[var(--text-muted)]";
  }
}

export function defaultSelectedClaimId(claims: PatientClaimSummary[]): string | null {
  if (claims.length === 0) return null;
  const sorted = [...claims].sort((a, b) => {
    const recoverableDiff = (b.recoverable_try ?? 0) - (a.recoverable_try ?? 0);
    if (recoverableDiff !== 0) return recoverableDiff;
    return new Date(b.claim_start_date).getTime() - new Date(a.claim_start_date).getTime();
  });
  return sorted[0]?.claim_id ?? null;
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
          new Date(b.claim_start_date).getTime() - new Date(a.claim_start_date).getTime(),
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
                {t("patient.billPicker.billMeta", {
                  claimType: claim.claim_type,
                  amount: fmtTRY2(claim.expected_total_billed_try),
                })}
              </span>
              {hasRecoverable && (
                <span
                  className={`mt-1.5 inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${priorityColor(
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
