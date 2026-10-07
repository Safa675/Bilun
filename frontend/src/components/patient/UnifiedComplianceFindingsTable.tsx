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
import { motionScrollBehavior } from "@/lib/motion";

export interface UnifiedComplianceFindingsTableProps {
  rows: UnifiedComplianceFindingRow[];
  patientId: string;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  onOpenClause?: (clauseKey: string) => void;
  selectedFindingId?: string | null;
  activeClauseKey?: string | null;
}

/**
 * Row keyboard activation predicate.
 *
 * Returns true only when the keyboard event originates on the row itself
 * (not bubbled from a nested clause button or Inspect link) and the key is
 * Enter or Space. Keeps native activation of nested controls intact.
 */
export function shouldActivateRowOnKeyDown(event: {
  key: string;
  target: unknown;
  currentTarget: unknown;
}): boolean {
  if (event.key !== "Enter" && event.key !== " ") return false;
  return event.target === event.currentTarget;
}

export default function UnifiedComplianceFindingsTable({
  rows,
  patientId,
  selectedActionId,
  onSelectAction,
  onOpenClause,
  selectedFindingId,
  activeClauseKey,
}: UnifiedComplianceFindingsTableProps) {
  const t = useT();

  return (
    <DataTable minWidth={960} mobileStacked className="text-sm">
      <thead>
        <tr>
          <th>{t("billing.views.compliance.colStatus")}</th>
          <th>{t("billing.views.compliance.colSource")}</th>
          <th className="min-w-[30rem]">{t("billing.views.compliance.colFinding")}</th>
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

            const handleRowClick = (root?: HTMLElement) => {
              if (row.action && onSelectAction) {
                onSelectAction(row.action);
                const sectionId = recommendedActionSectionId(row.action.surface);
                if (sectionId && typeof document !== "undefined") {
                  const scope = root?.closest("[data-patient-findings]") ?? document;
                  const target = Array.from(scope.querySelectorAll<HTMLElement>("[id]"))
                    .find((element) => element.id === sectionId);
                  for (let ancestor = target; ancestor; ancestor = ancestor.parentElement ?? undefined) {
                    if (ancestor.tagName === "DETAILS") (ancestor as HTMLDetailsElement).open = true;
                  }
                  target?.scrollIntoView({
                    behavior: motionScrollBehavior(),
                    block: "start",
                  });
                }
              }
            };

            const canonicalSource = row.finding?.regulatory_source;
            const canonicalClauseKey = canonicalSource && typeof canonicalSource === "object"
              ? (canonicalSource as Record<string, unknown>).clause_key
              : null;
            const clauseKey = row.action?.clause_ref?.clause_key ||
              (typeof canonicalClauseKey === "string" ? canonicalClauseKey.trim() : "");
            const clauseCoordinate = row.action?.clause_ref?.clause_coordinate ||
              (clauseKey.includes("#") ? clauseKey.split("#")[0] : row.sutLabel);
            // Canonical Inspect always targets the claim-compliance section;
            // action row selection keeps its own source-section scroll behavior.
            const inspectSection = row.canonicalFindingId
              ? "claim-compliance"
              : (recommendedActionSectionId(row.action?.surface) ?? "claim-compliance");

            const href = buildSutBillingHref(patientId, {
              claimId: row.claimId ?? undefined,
              section: inspectSection ?? undefined,
              findingId: row.canonicalFindingId ?? undefined,
            });

            return (
              <tr
                key={row.rowId}
                data-finding-id={row.canonicalFindingId ?? undefined}
                data-selected={isSelected ? "true" : undefined}
                data-clause-key={clauseKey || undefined}
                data-source-active={clauseKey && clauseKey === activeClauseKey ? "true" : undefined}
                tabIndex={row.action ? 0 : undefined}
                className={cn(
                  row.action && "cursor-pointer",
                  isSelected && "bg-[var(--gold-subtle)]",
                )}
                onClick={(event) => handleRowClick(event.currentTarget)}
                onKeyDown={(e) => {
                  if (!shouldActivateRowOnKeyDown(e)) return;
                  e.preventDefault();
                  handleRowClick(e.currentTarget);
                }}
              >
                {/* 1. Durum */}
                <td data-label={t("billing.views.compliance.colStatus")}>
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
                <td data-label={t("billing.views.compliance.colSource")}>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {row.sourceLabels.map((label) => (
                      <Chip key={label} variant="neutral">
                        {label}
                      </Chip>
                    ))}
                  </div>
                </td>

                {/* 3. Bulgu / yapılması gereken */}
                <td className="min-w-0 min-[641px]:min-w-[30rem]" data-label={t("billing.views.compliance.colFinding")} data-stack-wide>
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
                <td data-label={t("billing.views.compliance.colClaim")} className="font-mono text-xs text-[var(--text-secondary)]">
                  {row.claimId || "—"}
                </td>

                {/* 5. Kod */}
                <td data-label={t("billing.views.compliance.colCode")} className="font-mono text-xs text-[var(--text-primary)]">
                  {row.code || "—"}
                </td>

                {/* 6. SUT */}
                <td data-label={t("billing.views.compliance.colSut")} className="text-sm text-[var(--text-secondary)]">
                  {row.sutLabel || clauseKey ? (
                    onOpenClause && clauseKey ? (
                      <button
                        type="button"
                        aria-label={t("billing.recommendedActions.inspectClause", {
                          coordinate: row.sutLabel ?? clauseCoordinate,
                        })}
                        className="whitespace-nowrap rounded-[var(--r-sm)] border border-[var(--border-strong)] px-2 py-1 font-mono text-xs transition-colors hover:bg-[var(--surface-tint)]"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenClause(clauseKey);
                        }}
                      >
                        {t("billing.wavea.sutClause", { coordinate: formatSutSectionLabel(clauseCoordinate ?? undefined) })}
                      </button>
                    ) : (
                      formatSutSectionLabel(row.sutLabel ?? undefined)
                    )
                  ) : (
                    "—"
                  )}
                </td>

                {/* 7. Risk tutarı */}
                <td data-label={t("billing.views.compliance.colAmount")} className="num-col text-right tabular-nums text-sm text-[var(--text-primary)]">
                  {row.amountValue != null ? (
                    <span className="whitespace-nowrap">
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
                <td data-label={t("billing.views.compliance.colInspect")} className="text-right">
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
