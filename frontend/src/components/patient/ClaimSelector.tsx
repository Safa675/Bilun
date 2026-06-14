"use client";

import { useMemo } from "react";
import { ChevronDownIcon } from "lucide-react";
import { Eyebrow } from "@/components/primitives";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import type { PatientClaimSummary } from "@/lib/domains/sut";

export interface ClaimSelectorProps {
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

export default function ClaimSelector({
  claims,
  selectedClaimId,
  onSelectClaim,
  disabled = false,
}: ClaimSelectorProps) {
  const t = useT();
  const sortedClaims = useMemo(
    () =>
      [...claims].sort(
        (a, b) =>
          new Date(b.claim_start_date).getTime() -
          new Date(a.claim_start_date).getTime(),
      ),
    [claims],
  );

  return (
    <div className="space-y-2">
      <Eyebrow>{t("patient.claimSelector.label")}</Eyebrow>
      <div className="relative">
        <select
          aria-label={t("patient.claimSelector.label")}
          value={selectedClaimId ?? ""}
          onChange={(e) => onSelectClaim(e.target.value || null)}
          disabled={disabled || claims.length === 0}
          className="w-full appearance-none rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-2.5 pr-10 text-sm text-[var(--text-primary)] outline-none transition-colors focus:border-[var(--gold)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <option value="">
            {t("patient.claimSelector.allClaims")} (
            {t("patient.claimSelector.claimCount", { count: claims.length })}
            {claims.length === 1
              ? t("patient.claimSelector.claimSingular")
              : t("patient.claimSelector.claimPlural")}
            )
          </option>
          {sortedClaims.map((claim) => (
            <option key={claim.claim_id} value={claim.claim_id}>
              {claim.claim_id} · {fmtDate(claim.claim_start_date)} ·{" "}
              {fmtTRY2(claim.expected_total_billed_try)} TL
            </option>
          ))}
        </select>
        <ChevronDownIcon
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]"
        />
      </div>
    </div>
  );
}
