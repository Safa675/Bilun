"use client";

import type { RefCallback } from "react";
import type { DrugIndicationFinding, DrugIndicationRouteEvidence } from "@/lib/domains/sut";
import { getSutSeverityLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { cn } from "@/lib/cn";
import { Chip } from "@/components/primitives";

export function DrugIndicationFindingCard({
  finding,
  selectedFindingId,
  articleRef,
}: {
  finding: DrugIndicationFinding;
  selectedFindingId?: string | null;
  articleRef: RefCallback<HTMLElement>;
}) {
  const t = useT();

  const findingTitle = (kind: string | null | undefined) => {
    const knownKinds = new Set([
      "indication_mismatch",
      "missing_diagnosis",
      "missing_board_report",
      "needs_report_verification",
      "ambiguous_route",
      "report_duration_mismatch",
      "prescriber_specialty_mismatch",
      "inpatient_supply_required",
      "biomarker_mismatch",
      "needs_biomarker_verification",
      "prior_therapy_mismatch",
      "needs_prior_therapy_verification",
      "needs_dose_verification",
      "annual_max_exceeded",
      "loading_dose_exceeded",
    ]);
    return knownKinds.has(kind ?? "")
      ? t(`billing.drugIndication.findingTitles.${kind}`)
      : t("billing.drugIndication.technicalDetails");
  };

  const certaintyLabel = (status: string | null | undefined) => {
    const key =
      status === "evaluated"
        ? "evaluated"
        : status === "missing_inputs"
          ? "missing_inputs"
          : "unavailable";
    return t(`billing.drugIndication.certaintyLabels.${key}`);
  };

  const severityVariant = (severity: string | null | undefined) => {
    if (severity === "error") return "danger" as const;
    if (severity === "review") return "warning" as const;
    return "neutral" as const;
  };

  const routeCodes = (route: DrugIndicationRouteEvidence) => {
    const codes = [...(route.icd10_codes ?? []), ...(route.icd10_ranges ?? [])];
    const source = route.sut_section ? ` · ${route.sut_section}` : "";
    return `${codes.length > 0 ? codes.join(", ") : "—"}${source}`;
  };

  const routes = finding.eligible_routes ?? [];
  const observed = finding.observed_icd10_codes ?? [];
  const missingInputs = finding.missing_inputs ?? [];
  return (
    <article
      ref={articleRef}
      data-finding-id={finding.finding_id ?? undefined}
      data-selected={finding.finding_id === selectedFindingId ? "true" : undefined}
      tabIndex={finding.finding_id === selectedFindingId ? -1 : undefined}
      className={cn(
        "rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] p-4",
        finding.finding_id === selectedFindingId && "ring-2 ring-[var(--accent)] ring-offset-2",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-[var(--text-primary)]">
            {findingTitle(finding.finding_kind)}
          </p>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {finding.drug_name ?? "—"}
            {finding.drug_code ? ` · ${finding.drug_code}` : ""}
            {finding.claim_id ? ` · ${finding.claim_id}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip variant={severityVariant(finding.severity)}>
            {finding.severity ? getSutSeverityLabel(finding.severity) : "—"}
          </Chip>
          <Chip variant="outline">{certaintyLabel(finding.evaluation_status)}</Chip>
        </div>
      </div>

      <p className="mt-4 rounded-[var(--r-sm)] border border-[color-mix(in_srgb,var(--danger)_22%,transparent)] bg-[color-mix(in_srgb,var(--danger)_7%,transparent)] px-3 py-2 text-sm font-medium leading-relaxed text-[var(--danger)]">
        {t("billing.drugIndication.riskNotice")}
      </p>

      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
            {t("billing.drugIndication.observedDiagnoses")}
          </dt>
          <dd className="mt-1 font-mono text-[var(--text-primary)]">
            {observed.length > 0 ? observed.join(", ") : t("billing.drugIndication.noDiagnosisCode")}
          </dd>
          {finding.observed_icd10_truncated && (
            <p className="mt-1 text-xs italic text-[var(--text-muted)]">
              {t("billing.drugIndication.observedDiagnosesTruncated")}
            </p>
          )}
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
            {t("billing.drugIndication.eligibleRoutes")}
          </dt>
          <dd className="mt-1 text-[var(--text-primary)]">
            {routes.length > 0
              ? [...new Set(routes.map((route) => routeCodes(route)))].join(" · ")
              : t("billing.drugIndication.noRouteEvidence")}
          </dd>
          {(finding.eligible_routes_truncated ||
            routes.some((route) => route.icd10_codes_truncated || route.icd10_ranges_truncated)) && (
            <p className="mt-1 text-xs italic text-[var(--text-muted)]">
              {t("billing.drugIndication.routeValuesTruncated")}
            </p>
          )}
        </div>
      </dl>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
            {t("billing.drugIndication.explanation")}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-[var(--text-primary)]">
            {finding.explanation_tr ? translateApiText(finding.explanation_tr) : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
            {t("billing.drugIndication.nextAction")}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-[var(--text-primary)]">
            {finding.recommended_action_tr
              ? translateApiText(finding.recommended_action_tr)
              : "—"}
          </p>
        </div>
      </div>

      <details className="mt-4 border-t border-[var(--border-subtle)] pt-3 text-sm">
        <summary className="cursor-pointer font-semibold text-[var(--text-secondary)]">
          {t("billing.drugIndication.technicalDetails")}
        </summary>
        <div className="mt-3 grid gap-3 text-xs text-[var(--text-secondary)] md:grid-cols-2">
          <p>
            <span className="font-semibold">{t("billing.drugIndication.violationKind")}:</span>{" "}
            <span className="font-mono">{finding.finding_kind ?? "—"}</span>
          </p>
          <p>
            <span className="font-semibold">{t("billing.drugIndication.ruleId")}:</span>{" "}
            <span className="font-mono">{finding.selected_rule_id ?? "—"}</span>
          </p>
          <p>
            <span className="font-semibold">{t("billing.drugIndication.matchedDiagnoses")}:</span>{" "}
            <span className="font-mono">{(finding.matched_icd10_codes ?? []).join(", ") || "—"}</span>
          </p>
          <p>
            <span className="font-semibold">{t("billing.drugIndication.sutSection")}:</span>{" "}
            {routes.map((route) => route.sut_section).filter(Boolean).join(", ") || "—"}
          </p>
          {missingInputs.length > 0 && (
            <p className="md:col-span-2">
              <span className="font-semibold">{t("billing.drugIndication.certainty")}:</span>{" "}
              {missingInputs.join(", ")}
            </p>
          )}
          <div className="md:col-span-2">
            {routes.map((route) => (
              <div key={`${route.rule_id ?? "route"}-${route.sut_section ?? "section"}`} className="mb-2">
                <span className="font-mono">{route.rule_id ?? "—"}</span>
                {route.regulatory_summary_tr ? ` — ${translateApiText(route.regulatory_summary_tr)}` : ""}
              </div>
            ))}
          </div>
          {(finding.eligible_routes_truncated ||
            routes.some((route) => route.icd10_codes_truncated || route.icd10_ranges_truncated)) && (
            <p className="md:col-span-2 italic">{t("billing.drugIndication.routesTruncated")}</p>
          )}
        </div>
      </details>
    </article>
  );
}
