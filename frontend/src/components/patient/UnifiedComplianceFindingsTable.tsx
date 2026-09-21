"use client";

import { ArrowRight } from "lucide-react";
import { Chip, DataTable } from "@/components/primitives";
import PatientTabLink from "@/components/shell/PatientTabLink";
import { buildSutBillingHref } from "@/lib/constants";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import {
  recommendedActionSectionId,
  type RecommendedActionItem,
} from "@/lib/recommendedActions";
import type { UnifiedComplianceFindingRow } from "@/lib/complianceFindings";
import { cn } from "@/lib/cn";

export interface UnifiedComplianceFindingsTableProps {
  rows: UnifiedComplianceFindingRow[];
  patientId: string;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  onOpenClause?: (clauseKey: string) => void;
  selectedFindingId?: string | null;
}

export default function UnifiedComplianceFindingsTable({
  rows,
  patientId,
  selectedActionId,
  onSelectAction,
  onOpenClause,
  selectedFindingId,
}: UnifiedComplianceFindingsTableProps) {
  const t = useT();

  return (
    <DataTable minWidth={960} className="text-[0.82rem]">
      <thead>
        <tr>
          <th>{t("billing.views.compliance.colStatus")}</th>
          <th>{t("billing.views.compliance.colSource")}</th>
          <th>{t("billing.views.compliance.colFinding")}</th>
          <th>{t("billing.views.compliance.colClaim")}</th>
          <th>{t("billing.views.compliance.colCode")}</th>
          <th>{t("billing.views.compliance.colSut")}</th>
          <th className="num-col tabular-nums text-right">
            {t("billing.views.compliance.colAmount")}
          </th>
          <th className="text-right">
            {t("billing.views.compliance.colInspect")}
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td
              colSpan={8}
              className="py-8 text-center text-sm text-[var(--text-muted)]"
            >
              {t("billing.views.compliance.noFindings")}
            </td>
          </tr>
        ) : (
          rows.map((row) => {
            const isActionSelected = Boolean(
              selectedActionId && row.action?.action_id === selectedActionId,
            );
            const isFindingSelected = Boolean(
              selectedFindingId &&
                row.canonicalFindingId &&
                row.canonicalFindingId === selectedFindingId,
            );
            const isSelected = isActionSelected || isFindingSelected;

            const handleRowClick = () => {
              if (row.action && onSelectAction) {
                onSelectAction(row.action);
                const sectionId = recommendedActionSectionId(row.action.surface);
                if (sectionId && typeof document !== "undefined") {
                  document.getElementById(sectionId)?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                  });
                }
              }
            };

            const clauseKey = row.action?.clause_ref?.clause_key ?? "";
            const section =
              recommendedActionSectionId(row.action?.surface) ?? "claim-compliance";

            const href = buildSutBillingHref(patientId, {
              claimId: row.claimId ?? undefined,
              section: section ?? undefined,
              findingId: row.canonicalFindingId ?? undefined,
            });

            return (
              <tr
                key={row.rowId}
                data-finding-id={row.canonicalFindingId ?? undefined}
                data-selected={isSelected ? "true" : undefined}
                tabIndex={row.action ? 0 : undefined}
                className={cn(
                  row.action && "cursor-pointer",
                  isSelected && "bg-[var(--gold-subtle)]",
                )}
                onClick={handleRowClick}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleRowClick();
                  }
                }}
              >
                {/* 1. Durum */}
                <td>
                  <Chip
                    variant={
                      row.status === "confirmed_violation" ? "danger" : "warning"
                    }
                  >
                    {row.status === "confirmed_violation"
                      ? t("billing.views.compliance.statusConfirmedViolation")
                      : t("billing.views.compliance.statusReviewRisk")}
                  </Chip>
                </td>

                {/* 2. Kaynak */}
                <td>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {row.sourceLabels.map((label) => (
                      <Chip key={label} variant="neutral">
                        {label}
                      </Chip>
                    ))}
                  </div>
                </td>

                {/* 3. Bulgu / yapılması gereken */}
                <td>
                  <div className="font-medium text-[var(--text-primary)]">
                    {row.title}
                  </div>
                  {row.detail && (
                    <div className="mt-1 text-xs text-[var(--text-secondary)]">
                      {row.detail}
                    </div>
                  )}
                </td>

                {/* 4. Fatura */}
                <td className="font-mono text-xs text-[var(--text-secondary)]">
                  {row.claimId || "—"}
                </td>

                {/* 5. Kod */}
                <td className="font-mono text-xs text-[var(--text-primary)]">
                  {row.code || "—"}
                </td>

                {/* 6. SUT */}
                <td className="text-sm text-[var(--text-secondary)]">
                  {row.sutLabel ? (
                    onOpenClause && clauseKey ? (
                      <button
                        type="button"
                        aria-label={t("billing.recommendedActions.inspectClause", {
                          coordinate: row.sutLabel,
                        })}
                        className="underline decoration-dotted underline-offset-2 transition-colors hover:text-[var(--gold-hover)]"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenClause(clauseKey);
                        }}
                      >
                        {formatSutSectionLabel(row.sutLabel)}
                      </button>
                    ) : (
                      formatSutSectionLabel(row.sutLabel)
                    )
                  ) : (
                    "—"
                  )}
                </td>

                {/* 7. Risk tutarı */}
                <td className="num-col text-right tabular-nums text-sm text-[var(--text-primary)]">
                  {row.amountValue != null ? (
                    <span>
                      {fmtTRY2(row.amountValue)}
                      {row.amountLabel ? (
                        <span className="block text-xs text-[var(--text-secondary)]">
                          {row.amountLabel}
                        </span>
                      ) : null}
                    </span>
                  ) : row.amountLabel ? (
                    <span>{row.amountLabel}</span>
                  ) : (
                    "—"
                  )}
                </td>

                {/* 8. İncele */}
                <td className="text-right">
                  {row.canonicalFindingId ? (
                    <PatientTabLink
                      patientId={patientId}
                      href={href}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--gold)] hover:text-[var(--gold-hover)]"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {t("billing.views.compliance.inspectAction")}{" "}
                      <ArrowRight className="h-3 w-3" />
                    </PatientTabLink>
                  ) : (
                    <span className="text-[var(--text-muted)]">—</span>
                  )}
                </td>
              </tr>
            );
          })
        )}
      </tbody>
    </DataTable>
  );
}
