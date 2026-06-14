"use client";

import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHeader,
  DataTableHeaderCell,
  DataTableRow,
  Eyebrow,
  Section,
  Surface,
} from "@/components/primitives";
import { fmtNum, fmtTRY2 } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import type {
  ClaimDrugLine,
  ClaimMaterialLine,
  ClaimProcedureLine,
  PatientClaimDetail,
} from "@/lib/domains/sut";

interface ClaimDetailPanelProps {
  claim: PatientClaimDetail;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("tr-TR");
}

function EmptyLineState({ message }: { message: string }) {
  return (
    <p className="py-4 text-center text-sm text-[var(--text-muted)]">{message}</p>
  );
}

function ProcedureTable({ lines }: { lines: ClaimProcedureLine[] }) {
  const t = useT();
  if (lines.length === 0) {
    return <EmptyLineState message={t("patient.claimDetail.noProcedures")} />;
  }
  return (
    <DataTable minWidth={640}>
      <DataTableHeader>
        <DataTableRow>
          <DataTableHeaderCell>{t("patient.claimDetail.date")}</DataTableHeaderCell>
          <DataTableHeaderCell>{t("patient.claimDetail.code")}</DataTableHeaderCell>
          <DataTableHeaderCell>{t("patient.claimDetail.name")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.quantity")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.billed")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.payable")}</DataTableHeaderCell>
        </DataTableRow>
      </DataTableHeader>
      <DataTableBody>
        {lines.map((line) => (
          <DataTableRow key={line.procedure_line_id}>
            <DataTableCell>{fmtDate(line.procedure_date)}</DataTableCell>
            <DataTableCell className="font-mono text-xs">{line.procedure_code}</DataTableCell>
            <DataTableCell>{line.procedure_name}</DataTableCell>
            <DataTableCell numeric>{fmtNum(line.quantity)}</DataTableCell>
            <DataTableCell numeric>{fmtTRY2(line.billed_amount_try)}</DataTableCell>
            <DataTableCell numeric>{fmtTRY2(line.expected_payable_try)}</DataTableCell>
          </DataTableRow>
        ))}
      </DataTableBody>
    </DataTable>
  );
}

function MaterialTable({ lines }: { lines: ClaimMaterialLine[] }) {
  const t = useT();
  if (lines.length === 0) {
    return <EmptyLineState message={t("patient.claimDetail.noMaterials")} />;
  }
  return (
    <DataTable minWidth={640}>
      <DataTableHeader>
        <DataTableRow>
          <DataTableHeaderCell>{t("patient.claimDetail.date")}</DataTableHeaderCell>
          <DataTableHeaderCell>{t("patient.claimDetail.code")}</DataTableHeaderCell>
          <DataTableHeaderCell>{t("patient.claimDetail.name")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.quantity")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.billed")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.payable")}</DataTableHeaderCell>
        </DataTableRow>
      </DataTableHeader>
      <DataTableBody>
        {lines.map((line) => (
          <DataTableRow key={line.material_line_id}>
            <DataTableCell>{fmtDate(line.material_date)}</DataTableCell>
            <DataTableCell className="font-mono text-xs">{line.material_code}</DataTableCell>
            <DataTableCell>{line.material_name}</DataTableCell>
            <DataTableCell numeric>{fmtNum(line.quantity)}</DataTableCell>
            <DataTableCell numeric>{fmtTRY2(line.billed_amount_try)}</DataTableCell>
            <DataTableCell numeric>{fmtTRY2(line.expected_payable_try)}</DataTableCell>
          </DataTableRow>
        ))}
      </DataTableBody>
    </DataTable>
  );
}

function DrugTable({ lines }: { lines: ClaimDrugLine[] }) {
  const t = useT();
  if (lines.length === 0) {
    return <EmptyLineState message={t("patient.claimDetail.noDrugs")} />;
  }
  return (
    <DataTable minWidth={640}>
      <DataTableHeader>
        <DataTableRow>
          <DataTableHeaderCell>{t("patient.claimDetail.date")}</DataTableHeaderCell>
          <DataTableHeaderCell>{t("patient.claimDetail.code")}</DataTableHeaderCell>
          <DataTableHeaderCell>{t("patient.claimDetail.name")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.quantity")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.billed")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.payable")}</DataTableHeaderCell>
        </DataTableRow>
      </DataTableHeader>
      <DataTableBody>
        {lines.map((line) => (
          <DataTableRow key={line.drug_claim_line_id}>
            <DataTableCell>{fmtDate(line.drug_claim_date)}</DataTableCell>
            <DataTableCell className="font-mono text-xs">{line.drug_code}</DataTableCell>
            <DataTableCell>{line.drug_name}</DataTableCell>
            <DataTableCell numeric>{fmtNum(line.quantity)}</DataTableCell>
            <DataTableCell numeric>{fmtTRY2(line.billed_amount_try)}</DataTableCell>
            <DataTableCell numeric>{fmtTRY2(line.expected_payable_try)}</DataTableCell>
          </DataTableRow>
        ))}
      </DataTableBody>
    </DataTable>
  );
}

export default function ClaimDetailPanel({ claim }: ClaimDetailPanelProps) {
  const t = useT();

  return (
    <Surface variant="soft" padding="md" className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Eyebrow>{t("patient.claimDetail.eyebrow")}</Eyebrow>
          <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
            {claim.claim_id}
          </h3>
          <p className="text-sm text-[var(--text-secondary)]">
            {claim.episode_id} · {claim.claim_type} · {claim.primary_icd10}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-[var(--text-muted)]">
            {t("patient.claimDetail.period")}
          </p>
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {fmtDate(claim.claim_start_date)} — {fmtDate(claim.claim_end_date)}
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] p-3">
          <p className="text-xs text-[var(--text-muted)]">{t("patient.claimDetail.totalBilled")}</p>
          <p className="text-base font-semibold text-[var(--text-primary)]">
            {fmtTRY2(claim.expected_total_billed_try)}
          </p>
        </div>
        <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] p-3">
          <p className="text-xs text-[var(--text-muted)]">{t("patient.claimDetail.totalPayable")}</p>
          <p className="text-base font-semibold text-[var(--text-primary)]">
            {fmtTRY2(claim.expected_total_payable_try)}
          </p>
        </div>
        <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] p-3">
          <p className="text-xs text-[var(--text-muted)]">{t("patient.claimDetail.lines")}</p>
          <p className="text-base font-semibold text-[var(--text-primary)]">
            {claim.procedures.length + claim.materials.length + claim.drugs.length}
          </p>
        </div>
      </div>

      <Section title={t("patient.claimDetail.proceduresTitle")}>
        <ProcedureTable lines={claim.procedures} />
      </Section>

      <Section title={t("patient.claimDetail.materialsTitle")}>
        <MaterialTable lines={claim.materials} />
      </Section>

      <Section title={t("patient.claimDetail.drugsTitle")}>
        <DrugTable lines={claim.drugs} />
      </Section>
    </Surface>
  );
}
