"use client";

import PatientTabLink from "@/components/shell/PatientTabLink";
import { ArrowRight } from "lucide-react";
import { Chip, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { recommendedActionSectionId } from "@/lib/recommendedActions";
import type { ComplianceIndexRow } from "@/lib/domains/sut";
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
  const section =
    recommendedActionSectionId(row.source_surface) ??
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
}

export function ComplianceFindingTable({
  rows,
  loading,
  unavailable = false,
}: ComplianceFindingTableProps) {
  const t = useT();

  if (loading) {
    return <SutAlertTableSkeleton />;
  }

  return (
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
              {unavailable
                ? t("optimizer.complianceIndex.indexUnavailable")
                : t("optimizer.complianceIndex.noFindings")}
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
                    <Chip variant="warning">{row.kind.replaceAll("_", " ")}</Chip>
                  ) : (
                    <span className="text-[var(--text-muted)]">—</span>
                  )}
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
  );
}
