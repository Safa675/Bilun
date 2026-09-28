"use client";

import { useEffect, useRef } from "react";
import type { BillingActionReport, DrugIndicationFinding, DrugIndicationRouteEvidence } from "@/lib/domains/sut";
import { getSutSeverityLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { cn } from "@/lib/cn";
import { Chip, ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { WRAPPED_HEADER_STYLE, BillingSectionShell, TableWrap } from "./shared";

export function DrugIndicationReviewSection({
  reviewData,
  selectedFindingId,
}: {
  reviewData: NonNullable<BillingActionReport["drug_indication"]>;
  selectedFindingId?: string | null;
}) {
  const t = useT();
  const reviewExact = isExactOutput(reviewData);
  const findings = reviewData.findings ?? [];
  const violations = reviewData.violations ?? [];
  const evaluations = reviewData.evaluations ?? [];
  const findingRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!selectedFindingId) return;
    const target = findingRefs.current[selectedFindingId];
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.focus({ preventScroll: true });
  }, [reviewData.findings, selectedFindingId]);

  if (
    findings.length === 0 &&
    violations.length === 0 &&
    evaluations.length === 0 &&
    (reviewData.exactness_status === "exact" || reviewData.exactness_status === "not_applicable")
  ) {
    return null;
  }

  const violationCount =
    reviewData.violation_count ?? (findings.length > 0 ? findings.length : violations.length);

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

  const renderStructuredFinding = (finding: DrugIndicationFinding, index: number) => {
    const routes = finding.eligible_routes ?? [];
    const observed = finding.observed_icd10_codes ?? [];
    const missingInputs = finding.missing_inputs ?? [];
    return (
      <article
        key={finding.finding_id ?? `${finding.claim_id ?? "claim"}-${finding.drug_claim_line_id ?? index}`}
        ref={(node) => {
          if (finding.finding_id) findingRefs.current[finding.finding_id] = node;
        }}
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
  };

  return (
    <BillingSectionShell
      id="drug-indication"
      title={t("billing.drugIndication.title")}
      total={String(violationCount)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.drugIndication.scopeFootnote")}
      </p>
      {!reviewExact && (
        <ExactnessNotice block={reviewData} fallback={t("billing.drugIndication.unavailable")} className="mb-4" />
      )}
      {findings.length > 0 ? (
        <div className="grid gap-3">{findings.map(renderStructuredFinding)}</div>
      ) : violations.length > 0 ? (
        <details className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] p-4">
          <summary className="cursor-pointer font-semibold text-[var(--text-secondary)]">
            {t("billing.drugIndication.legacyDetails")}
          </summary>
          <TableWrap minWidth={1080}>
            <thead>
              <tr>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.claim")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.drug")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.violationKind")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.severity")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.primaryIcd10")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.ruleId")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.sutSection")}</th>
                <th style={WRAPPED_HEADER_STYLE}>{t("billing.drugIndication.message")}</th>
              </tr>
            </thead>
            <tbody>
              {violations.map((item, index) => (
                <tr key={`${item.claim_id}-${item.drug_claim_line_id}-${index}`}>
                  <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
                  <td>{item.drug_name ?? "—"}</td>
                  <td className="font-mono text-xs">{item.violation_kind ?? "—"}</td>
                  <td>{item.severity ? getSutSeverityLabel(item.severity) : "—"}</td>
                  <td className="font-mono text-xs">{item.primary_icd10 ?? "—"}</td>
                  <td className="font-mono text-xs">{item.rule_id ?? "—"}</td>
                  <td>{item.sut_section ?? "—"}</td>
                  <td>{item.message_tr ? translateApiText(item.message_tr) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        </details>
      ) : evaluations.length > 0 ? (
        <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-tint)] p-4">
          <p className="font-semibold text-[var(--text-primary)]">
            {evaluations.some((item) => item.applicability_status === "not_in_encoded_corpus")
              ? t("billing.drugIndication.corpusNoncoverage")
              : t("billing.drugIndication.evaluationOnly")}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
            {evaluations.some((item) => item.applicability_status === "not_in_encoded_corpus")
              ? t("billing.drugIndication.corpusNoncoverageDetail")
              : t("billing.drugIndication.evaluationOnlyDetail")}
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[var(--text-secondary)]">
            {evaluations.map((item, index) => (
              <li key={`${item.drug_claim_line_id ?? item.drug_name ?? "drug"}-${index}`}>
                {item.drug_name ?? "—"}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </BillingSectionShell>
  );
}
