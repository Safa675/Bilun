"use client";

import { Chip, Stat, Surface } from "@/components/primitives";
import type { CohortRecoverySummary } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { isExactOutput } from "@/lib/sutExactness";
import { fmtLabel, fmtNum, fmtNumOrUnavailable, fmtTRYOrUnavailable } from "../shared";

const CATEGORY_FIELDS = [
  { key: "lab", amount: "total_lab_savings", label: "labSavings" },
  { key: "copay_waiver", amount: "total_copay_savings", label: "copaySavings" },
  { key: "strategy_uplift", amount: "total_strategy_savings", label: "strategySavings" },
  { key: "optional_override", amount: "total_optional_override_uplift", patients: "n_optional_override_patients" },
  { key: "drg_uplift", amount: "total_drg_uplift", patients: "n_drg_uplift_patients" },
  { key: "blood_uplift", amount: "total_blood_uplift", patients: "n_blood_uplift_patients" },
  { key: "yatak_puani", amount: "total_yatak_puani", patients: "n_yatak_puani_patients" },
  { key: "icu_puani", amount: "total_icu_puani", patients: "n_icu_puani_patients" },
  { key: "yenidogan_yatak", amount: "total_yenidogan_yatak", patients: "n_yenidogan_yatak_patients" },
  { key: "refakatci", amount: "total_refakatci", patients: "n_refakatci_patients" },
  { key: "anestezi_puani", amount: "total_anestezi_puani", patients: "n_anestezi_puani_patients" },
  { key: "material_uplift", amount: "total_material_uplift", patients: "n_material_uplift_patients" },
  { key: "procedure_addon_uplift", amount: "total_procedure_addon_uplift", patients: "n_procedure_addon_patients" },
  { key: "capture_gap", amount: "total_capture_gap", label: "captureGapTotal" },
  { key: "package_adequacy_review", amount: "total_package_adequacy_review", label: "packageAdequacyReviewTotal" },
] as const;

export type RecoveryCategory = {
  key: string;
  label?: string;
  amount: number | null;
  patients: number | null;
};

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function recoveryCategories(data: CohortRecoverySummary): {
  rows: RecoveryCategory[];
  noFindings: RecoveryCategory[];
} {
  const available = isExactOutput(data) || data.exactness_status === "partial_exact";
  const rows: RecoveryCategory[] = CATEGORY_FIELDS.map((field) => ({
    key: field.key,
    label: "label" in field ? field.label : undefined,
    amount: available ? finiteNumber(data[field.amount]) : null,
    patients: "patients" in field ? finiteNumber(data[field.patients]) : null,
  }));
  const included = new Set(["sgk_uplift", "copay", "strategy", "medula_playbook", ...rows.map((row) => row.key)]);
  for (const [key, amount] of Object.entries(data.savings_by_category ?? {})) {
    if (!included.has(key)) {
      rows.push({ key, amount: available ? finiteNumber(amount) : null, patients: null });
    }
  }
  // A zero amount alone cannot prove that a category has no findings.
  const noFindings = isExactOutput(data)
    ? rows.filter((row) => row.amount === 0 && row.patients === 0)
    : [];
  const noFindingKeys = new Set(noFindings.map((row) => row.key));
  return {
    rows: rows.filter((row) => !noFindingKeys.has(row.key)).sort((a, b) =>
      a.amount === null ? (b.amount === null ? 0 : 1) : b.amount === null ? -1 : b.amount - a.amount),
    noFindings,
  };
}

export default function RevenueRecoverySummary({ data }: { data: CohortRecoverySummary }) {
  const t = useT();
  const exact = isExactOutput(data);
  const partial = data.exactness_status === "partial_exact";
  const { rows, noFindings } = recoveryCategories(data);
  const categoryLabel = (row: RecoveryCategory) => {
    const key = row.label ? `optimizer.kpis.${row.label}` : `optimizer.savingsCategory.${row.key}`;
    const label = t(key);
    return label === key ? fmtLabel(row.key) : label;
  };
  const state = exact ? "exact" : partial ? "partial_exact" : data.exactness_status ?? "missing_exact_inputs";

  return (
    <Surface variant="inset" padding="none" className="space-y-5 min-w-0">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border-subtle)] pb-5">
        <Stat
          label={t(partial ? "optimizer.kpis.partialRuleCalculatedTotal" : "optimizer.kpis.ruleCalculatedTotal")}
          value={<span className="whitespace-nowrap">{fmtTRYOrUnavailable(exact || partial ? data.grand_total_recoverable : null)}</span>}
          display="gold"
        />
        <div className="flex flex-wrap items-center gap-3 text-sm text-[var(--text-secondary)]">
          <span>{t("optimizer.kpis.patientsWithActions")}: <strong className="tabular-nums">{fmtNum(data.n_patients)}</strong></span>
          <Chip variant={exact ? "success" : "warning"}>{t(`billing.recommendedActions.exactness.${state}`)}</Chip>
        </div>
      </div>

      <div>
        <div className="hidden grid-cols-[minmax(0,1fr)_8rem_10rem_8rem] gap-4 border-b border-[var(--border-subtle)] pb-2 text-xs font-semibold text-[var(--text-muted)] lg:grid">
          <span>{t("optimizer.recoveryList.category")}</span>
          <span className="text-right">{t("optimizer.recoveryList.patients")}</span>
          <span className="text-right">{t("optimizer.recoveryList.amount")}</span>
          <span>{t("optimizer.recoveryList.exactness")}</span>
        </div>
        <ul className="divide-y divide-[var(--border-subtle)]">
          {rows.map((row) => (
            <li key={row.key} data-recovery-category={row.key} className="grid min-w-0 grid-cols-1 gap-2 py-3 lg:grid-cols-[minmax(0,1fr)_8rem_10rem_8rem] lg:items-center lg:gap-4">
              <span className="text-sm font-medium text-[var(--text-primary)]">{categoryLabel(row)}</span>
              <span className="flex justify-between gap-3 text-sm tabular-nums text-[var(--text-secondary)] lg:block lg:text-right">
                <span className="text-xs text-[var(--text-muted)] lg:hidden">{t("optimizer.recoveryList.patients")}</span>
                {fmtNumOrUnavailable(row.patients)}
              </span>
              <span className="flex justify-between gap-3 text-sm font-semibold tabular-nums text-[var(--text-primary)] lg:block lg:text-right">
                <span className="text-xs font-normal text-[var(--text-muted)] lg:hidden">{t("optimizer.recoveryList.amount")}</span>
                <span className="whitespace-nowrap">{fmtTRYOrUnavailable(row.amount)}</span>
              </span>
              <div><Chip variant={row.amount !== null && exact ? "success" : "warning"}>
                {t(`billing.recommendedActions.exactness.${row.amount === null ? "missing_exact_inputs" : state}`)}
              </Chip></div>
            </li>
          ))}
        </ul>
        {noFindings.length > 0 && (
          <p data-recovery-no-findings className="border-t border-[var(--border-subtle)] py-3 text-sm text-[var(--text-muted)]">
            {t("optimizer.recoveryList.noFindings")}: {noFindings.map(categoryLabel).join(", ")} · {fmtTRYOrUnavailable(0)} · {t("billing.recommendedActions.exactness.exact")}
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border-subtle)] py-3 text-sm text-[var(--text-secondary)]">
          <span>{t("optimizer.kpis.medulaPlaybookEntries")}</span>
          <span className="tabular-nums">{data.medula_rejection_ingest_available === true
            ? fmtNumOrUnavailable(data.total_medula_playbook_entries)
            : t("operations.queue.empty.noIngest")}</span>
        </div>
      </div>
    </Surface>
  );
}
