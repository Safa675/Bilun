"use client";

import { useMemo } from "react";
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

import { fmtDate } from "@/lib/i18n/formatters";
import { cn } from "@/lib/cn";

export type HighlightCodeSet = {
  procedures: Set<string>;
  labs: Set<string>;
  materials: Set<string>;
  drugs: Set<string>;
};

export interface OriginalBillViewProps {
  claim: PatientClaimDetail;
  /** When set, invoice lines whose code appears in the matching section set are
   *  highlighted — driven by the selected recommended action. */
  highlightCodes?: HighlightCodeSet | null;
}

type InvoiceLine = {
  id: string;
  date: string;
  code: string;
  name: string;
  quantity: number;
  billedAmountTry: number;
  expectedPayableTry: number;
};

function isLabProcedure(line: ClaimProcedureLine): boolean {
  return line.procedure_category.trim().toLowerCase() === "laboratuvar";
}

function sumField(lines: InvoiceLine[], field: "billedAmountTry" | "expectedPayableTry"): number {
  return lines.reduce((total, line) => total + line[field], 0);
}

/** Sunulan fatura: yalnızca billed>0 satırlar ara toplama girer (ghost alternatif yollar hariç). */
function sumPresentedField(
  lines: InvoiceLine[],
  field: "billedAmountTry" | "expectedPayableTry",
): number {
  return lines
    .filter((line) => line.billedAmountTry > 0)
    .reduce((total, line) => total + line[field], 0);
}

function countLegacyGhostLines(lines: InvoiceLine[]): number {
  return lines.filter(
    (line) => line.billedAmountTry <= 0 && line.expectedPayableTry > 0,
  ).length;
}

function procedureToLine(line: ClaimProcedureLine): InvoiceLine {
  return {
    id: line.procedure_line_id,
    date: line.procedure_date,
    code: line.procedure_code,
    name: line.procedure_name,
    quantity: line.quantity,
    billedAmountTry: line.billed_amount_try,
    expectedPayableTry: line.expected_payable_try,
  };
}

function materialToLine(line: ClaimMaterialLine): InvoiceLine {
  return {
    id: line.material_line_id,
    date: line.material_date,
    code: line.material_code,
    name: line.material_name,
    quantity: line.quantity,
    billedAmountTry: line.billed_amount_try,
    expectedPayableTry: line.expected_payable_try,
  };
}

function drugToLine(line: ClaimDrugLine): InvoiceLine {
  return {
    id: line.drug_claim_line_id,
    date: line.drug_claim_date,
    code: line.drug_code,
    name: line.drug_name,
    quantity: line.quantity,
    billedAmountTry: line.billed_amount_try,
    expectedPayableTry: line.expected_payable_try,
  };
}

function EmptyLineState({ message }: { message: string }) {
  return (
    <p className="py-4 text-center text-sm text-[var(--text-muted)]">{message}</p>
  );
}

function SectionSubtotal({
  label,
  billed,
  payable,
}: {
  label: string;
  billed: number;
  payable: number;
}) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-x-6 gap-y-1 border-t border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-2 text-sm">
      <span className="font-medium text-[var(--text-secondary)]">{label}</span>
      <span className="tabular-nums text-[var(--text-primary)]">
        {fmtTRY2(billed)}
      </span>
      <span className="tabular-nums text-[var(--text-primary)]">
        {fmtTRY2(payable)}
      </span>
    </div>
  );
}

function InvoiceLineTable({
  lines,
  emptyMessage,
  highlightedCodes,
}: {
  lines: InvoiceLine[];
  emptyMessage: string;
  highlightedCodes?: Set<string>;
}) {
  const t = useT();

  if (lines.length === 0) {
    return <EmptyLineState message={emptyMessage} />;
  }

  return (
    <DataTable minWidth={720}>
      <DataTableHeader>
        <DataTableRow>
          <DataTableHeaderCell>{t("patient.claimDetail.date")}</DataTableHeaderCell>
          <DataTableHeaderCell>{t("patient.claimDetail.code")}</DataTableHeaderCell>
          <DataTableHeaderCell>{t("patient.claimDetail.name")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.claimDetail.quantity")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.originalBill.asSubmitted")}</DataTableHeaderCell>
          <DataTableHeaderCell numeric>{t("patient.originalBill.sutExpected")}</DataTableHeaderCell>
        </DataTableRow>
      </DataTableHeader>
      <DataTableBody>
        {lines.map((line) => {
          const isHighlighted = highlightedCodes?.has(line.code) ?? false;
          return (
            <DataTableRow
              key={line.id}
              className={cn(
                isHighlighted && "bg-[var(--gold-subtle)] ring-1 ring-inset ring-[var(--gold-light)]",
              )}
            >
              <DataTableCell>{fmtDate(line.date)}</DataTableCell>
              <DataTableCell className="font-mono text-xs">{line.code}</DataTableCell>
              <DataTableCell>{line.name}</DataTableCell>
              <DataTableCell numeric>{fmtNum(line.quantity)}</DataTableCell>
              <DataTableCell numeric>{fmtTRY2(line.billedAmountTry)}</DataTableCell>
              <DataTableCell numeric>{fmtTRY2(line.expectedPayableTry)}</DataTableCell>
            </DataTableRow>
          );
        })}
      </DataTableBody>
    </DataTable>
  );
}

function InvoiceSection({
  title,
  lines,
  emptyMessage,
  subtotalLabel,
  highlightedCodes,
}: {
  title: string;
  lines: InvoiceLine[];
  emptyMessage: string;
  subtotalLabel: string;
  highlightedCodes?: Set<string>;
}) {
  if (lines.length === 0) {
    return (
      <Section title={title}>
        <EmptyLineState message={emptyMessage} />
      </Section>
    );
  }

  return (
    <Section title={title}>
      <div className="overflow-hidden rounded-[var(--r-md)] border border-[var(--border-subtle)]">
        <InvoiceLineTable
          lines={lines}
          emptyMessage={emptyMessage}
          highlightedCodes={highlightedCodes}
        />
        <SectionSubtotal
          label={subtotalLabel}
          billed={sumPresentedField(lines, "billedAmountTry")}
          payable={sumPresentedField(lines, "expectedPayableTry")}
        />
      </div>
    </Section>
  );
}

export default function OriginalBillView({ claim, highlightCodes }: OriginalBillViewProps) {
  const t = useT();

  const sections = useMemo(() => {
    const procedureLines = claim.procedures.filter((line) => !isLabProcedure(line));
    const labLines = claim.procedures.filter(isLabProcedure);

    return {
      procedures: procedureLines.map(procedureToLine),
      labs: labLines.map(procedureToLine),
      materials: claim.materials.map(materialToLine),
      drugs: claim.drugs.map(drugToLine),
    };
  }, [claim.drugs, claim.materials, claim.procedures]);

  const allLines = useMemo(
    () => [
      ...sections.procedures,
      ...sections.labs,
      ...sections.materials,
      ...sections.drugs,
    ],
    [sections],
  );

  const linesBilledTotal = sumPresentedField(allLines, "billedAmountTry");
  const linesPayableTotal = sumPresentedField(allLines, "expectedPayableTry");
  const legacyGhostLineCount = countLegacyGhostLines(allLines);

  return (
    <Surface variant="base" padding="lg" className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--border-subtle)] pb-5">
        <div className="min-w-0">
          <Eyebrow>{t("patient.originalBill.eyebrow")}</Eyebrow>
          <h2 className="mt-1 font-[var(--font-display)] text-xl font-medium tracking-tight text-[var(--text-primary)]">
            {t("patient.originalBill.title")}
          </h2>
          <p className="mt-1 font-mono text-sm text-[var(--text-secondary)]">{claim.claim_id}</p>
          {[claim.episode_id, claim.claim_type, claim.primary_icd10].filter(Boolean).length > 0 && (
            <p className="mt-2 text-sm text-[var(--text-secondary)]">
              {[claim.episode_id, claim.claim_type, claim.primary_icd10]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
          {(claim.department || claim.facility_tier) && (
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              {[claim.department, claim.facility_tier && `${t("patient.originalBill.facility")} ${claim.facility_tier}`]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="text-xs text-[var(--text-muted)]">{t("patient.claimDetail.period")}</p>
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {fmtDate(claim.claim_start_date)} — {fmtDate(claim.claim_end_date)}
          </p>
        </div>
      </div>

      <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("patient.originalBill.description")}
      </p>
      <p className="text-xs text-[var(--text-muted)]">{t("patient.originalBill.optimizationHint")}</p>
      {legacyGhostLineCount > 0 && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          {t("patient.originalBill.legacyGhostLineFootnote", {
            count: legacyGhostLineCount,
          })}
        </p>
      )}

      <InvoiceSection
        title={t("patient.originalBill.proceduresTitle")}
        lines={sections.procedures}
        emptyMessage={t("patient.claimDetail.noProcedures")}
        subtotalLabel={t("patient.originalBill.sectionSubtotal", {
          section: t("patient.originalBill.proceduresTitle"),
        })}
        highlightedCodes={highlightCodes?.procedures}
      />

      <InvoiceSection
        title={t("patient.originalBill.labsTitle")}
        lines={sections.labs}
        emptyMessage={t("patient.originalBill.noLabs")}
        subtotalLabel={t("patient.originalBill.sectionSubtotal", {
          section: t("patient.originalBill.labsTitle"),
        })}
        highlightedCodes={highlightCodes?.labs}
      />

      <InvoiceSection
        title={t("patient.originalBill.materialsTitle")}
        lines={sections.materials}
        emptyMessage={t("patient.claimDetail.noMaterials")}
        subtotalLabel={t("patient.originalBill.sectionSubtotal", {
          section: t("patient.originalBill.materialsTitle"),
        })}
        highlightedCodes={highlightCodes?.materials}
      />

      <InvoiceSection
        title={t("patient.originalBill.drugsTitle")}
        lines={sections.drugs}
        emptyMessage={t("patient.claimDetail.noDrugs")}
        subtotalLabel={t("patient.originalBill.sectionSubtotal", {
          section: t("patient.originalBill.drugsTitle"),
        })}
        highlightedCodes={highlightCodes?.drugs}
      />

      <div className="rounded-[var(--r-md)] border border-[var(--border-strong)] bg-[var(--surface-soft)] p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-xs text-[var(--text-muted)]">{t("patient.originalBill.linesSubtotal")}</p>
            <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
              {fmtTRY2(linesBilledTotal)} → {fmtTRY2(linesPayableTotal)}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">{t("patient.claimDetail.totalBilled")}</p>
            <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
              {fmtTRY2(claim.expected_total_billed_try)}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">{t("patient.claimDetail.totalPayable")}</p>
            <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
              {fmtTRY2(claim.expected_total_payable_try)}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">{t("patient.originalBill.variance")}</p>
            <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
              {fmtTRY2(Math.max(0, claim.expected_total_billed_try - linesBilledTotal))} /{" "}
              {fmtTRY2(Math.max(0, claim.expected_total_payable_try - linesPayableTotal))}
            </p>
          </div>
        </div>
      </div>
    </Surface>
  );
}
