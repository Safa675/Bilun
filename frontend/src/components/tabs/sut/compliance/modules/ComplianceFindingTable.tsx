"use client";

import PatientTabLink from "@/components/shell/PatientTabLink";
import { ArrowRight } from "lucide-react";
import { Chip, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { recommendedActionSectionId } from "@/lib/recommendedActions";
import type {
  ClaimComplianceCohortSummary,
  ClaimComplianceEvaluation,
  ComplianceIndexPagination,
  ComplianceIndexRow,
} from "@/lib/domains/sut";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { fmtTRY2 } from "../../shared";
import { useT } from "@/lib/i18n/useTranslations";

const PATIENT_LINK_CLASS =
  "font-semibold text-[var(--text-primary)] hover:text-[var(--gold-hover)]";

function rowCode(row: ComplianceIndexRow): string {
  return row.procedure_code || row.material_code || row.drug_code || "—";
}

function rowName(row: ComplianceIndexRow): string | null {
  return row.procedure_name || row.material_name || null;
}

function rowHref(row: ComplianceIndexRow): string {
  const section = recommendedActionSectionId(row.source_surface) ??
    recommendedActionSectionId(row.surface);
  return buildSutBillingHref(row.patient_id, {
    claimId: row.claim_id ?? undefined,
    section: section ?? undefined,
  });
}

export interface ComplianceFindingTableProps {
  rows: ComplianceIndexRow[];
  loading: boolean;
  unavailable?: boolean;
  claimCompliance?: boolean;
  claimComplianceSummary?: ClaimComplianceCohortSummary | null;
  partialResults?: boolean;
  pagination?: ComplianceIndexPagination;
  onPageChange?: (offset: number) => void;
}

export function ComplianceFindingTable({
  rows,
  loading,
  unavailable = false,
  claimCompliance = false,
  claimComplianceSummary = null,
  partialResults = false,
  pagination,
  onPageChange,
}: ComplianceFindingTableProps) {
  const t = useT();

  if (loading) {
    return <SutAlertTableSkeleton />;
  }

  const counts = claimComplianceSummary?.counts ?? {
    evaluated: 0, missing_inputs: 0, unavailable: 0,
  };
  const detailEvaluations: ClaimComplianceEvaluation[] =
    claimComplianceSummary?.details ?? [];
  const nonEvaluatedCount = claimComplianceSummary?.non_evaluated_total ?? 0;

  return (
    <div className="space-y-3">
      {partialResults && (
        <p className="text-sm text-[var(--text-muted)]">{t("optimizer.claimCompliance.partialResults")}</p>
      )}
      {claimCompliance && (unavailable || !claimComplianceSummary) && (
        <p className="text-sm text-[var(--text-muted)]">{t("optimizer.claimCompliance.unavailable")}</p>
      )}
      {claimCompliance && (
        <p className="text-xs tabular-nums text-[var(--text-secondary)]">
          {t("optimizer.claimCompliance.evaluationSummary", counts)}
        </p>
      )}
      {claimCompliance && nonEvaluatedCount > 0 && (
        <details className="text-xs text-[var(--text-secondary)]">
          <summary className="cursor-pointer">
            {t("optimizer.claimCompliance.evaluationDetails", { count: detailEvaluations.length, total: nonEvaluatedCount })}
          </summary>
          <ul className="mt-2 space-y-1">
            {detailEvaluations.map((evaluation) => (
              <li key={`${evaluation.patient_id}:${evaluation.claim_id}:${evaluation.rule_id}`}>
                <PatientTabLink
                  patientId={evaluation.patient_id}
                  href={rowHref({ ...evaluation, surface: "claim_compliance" })}
                  className={PATIENT_LINK_CLASS}
                >
                  {evaluation.patient_id}
                </PatientTabLink>
                {" · "}{evaluation.claim_id || "—"} · {t(`optimizer.claimCompliance.${evaluation.rule_id}`)}: {t(`optimizer.claimCompliance.${evaluation.status}`)}
                {evaluation.missing_inputs.length > 0 ? ` (${evaluation.missing_inputs.join(", ")})` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    <DataTable minWidth={960}>
      <thead>
        <tr>
          <th>{t("optimizer.complianceIndex.patientId")}</th>
          <th>{t("optimizer.complianceIndex.claim")}</th>
          <th>{t("optimizer.complianceIndex.code")}</th>
          <th>{t("optimizer.complianceIndex.kind")}</th>
          <th className="text-right">{t("optimizer.complianceIndex.billed")}</th>
          <th>{t("optimizer.complianceIndex.sutSection")}</th>
          <th className="text-right">{t("optimizer.complianceIndex.inspect")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={7} className="py-8 text-center text-[var(--text-muted)]">
              {unavailable || (claimCompliance && !claimComplianceSummary)
                ? t(claimCompliance ? "optimizer.claimCompliance.unavailable" : "optimizer.complianceIndex.indexUnavailable")
                : partialResults || (claimCompliance && nonEvaluatedCount > 0)
                  ? t("optimizer.claimCompliance.incompleteFindings")
                  : t(claimCompliance ? "optimizer.claimCompliance.evaluatedNoFindings" : "optimizer.complianceIndex.noFindings")}
            </td>
          </tr>
        ) : (
          rows.map((row) => {
            const name = rowName(row);
            return (
              <tr key={`${row.patient_id}:${row.action_id}:${row.claim_id}:${rowCode(row)}`}>
                <td>
                  <PatientTabLink patientId={row.patient_id} href={rowHref(row)} className={PATIENT_LINK_CLASS}>
                    {row.patient_id}
                  </PatientTabLink>
                </td>
                <td className="text-[var(--text-secondary)]">{row.claim_id || "—"}</td>
                <td>
                  <div className="font-medium text-[var(--text-primary)]">{rowCode(row)}</div>
                  {name ? (
                    <div className="text-xs text-[var(--text-muted)]">{name}</div>
                  ) : null}
                </td>
                <td>
                  {row.kind ? (
                    <Chip variant="warning">{row.rule_id ? t(`optimizer.claimCompliance.${row.rule_id}`) : row.kind.replaceAll("_", " ")}</Chip>
                  ) : (
                    <span className="text-[var(--text-muted)]">—</span>
                  )}
                  {row.detail && <div className="mt-1 text-xs text-[var(--text-secondary)]">{row.detail}</div>}
                  {row.procedure_line_id && <div className="text-xs text-[var(--text-muted)]">{row.procedure_line_id}</div>}
                </td>
                <td className="text-right tabular-nums text-[var(--text-primary)]">
                  {row.billed_try != null ? fmtTRY2(row.billed_try) : "—"}
                </td>
                <td className="text-[var(--text-secondary)]">{row.sut_section_id || "—"}</td>
                <td className="text-right">
                  <PatientTabLink
                    patientId={row.patient_id}
                    href={rowHref(row)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--gold)] hover:text-[var(--gold-hover)]"
                  >
                    {t("optimizer.complianceIndex.openBill")}{" "}
                    <ArrowRight className="h-3 w-3" />
                  </PatientTabLink>
                </td>
              </tr>
            );
          })
        )}
      </tbody>
    </DataTable>
      {pagination && onPageChange && (pagination.offset > 0 || pagination.has_more) && (
        <div className="flex items-center justify-end gap-2 text-xs text-[var(--text-secondary)]">
          <button
            type="button"
            disabled={pagination.offset <= 0}
            onClick={() => onPageChange(Math.max(0, pagination.offset - pagination.limit))}
            className="rounded border border-[var(--border-subtle)] px-3 py-1.5 disabled:opacity-40"
          >
            {t("optimizer.pagination.prev")}
          </button>
          <span className="tabular-nums">
            {pagination.offset + 1}–{Math.min(pagination.offset + pagination.limit, pagination.total_matching)} / {pagination.total_matching}
          </span>
          <button
            type="button"
            disabled={!pagination.has_more}
            onClick={() => onPageChange(pagination.offset + pagination.limit)}
            className="rounded border border-[var(--border-subtle)] px-3 py-1.5 disabled:opacity-40"
          >
            {t("optimizer.pagination.next")}
          </button>
        </div>
      )}
    </div>
  );
}
