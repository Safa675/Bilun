"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { translateStructuredApiMessage } from "@/lib/apiMessages";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { findingTypeChipVariant, findingTypeLabelKey, getFindingType, getRecommendedActions, recommendedActionSectionId, recommendedActionAmountParts, recommendedActionSurfaceLabel, recommendedActionTitle, type FindingType, type RecommendedActionItem } from "@/lib/recommendedActions";
import { cn } from "@/lib/cn";
import { Chip, Eyebrow } from "@/components/primitives";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, TableWrap } from "./shared";

export function RecommendedActionsPanel({
  billingReport,
  selectedActionId,
  onSelectAction,
  findingFilter,
  onOpenClause,
}: {
  billingReport: BillingActionReport;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  /** Restrict rows to one finding class (engine view) or show all (overview). */
  findingFilter?: FindingType;
  /** When provided, rows with a canonical clause cite render an inspect button. */
  onOpenClause?: (clauseKey: string) => void;
}) {
  const t = useT();
  const allActions = getRecommendedActions(billingReport);
  const actions = findingFilter
    ? allActions.filter((action) => getFindingType(action) === findingFilter)
    : allActions;

  if (actions.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 border-t border-[var(--border-subtle)] pt-5">
      <Eyebrow>{t("billing.recommendedActions.listTitle")}</Eyebrow>
      <TableWrap minWidth={920}>
        <thead>
          <tr>
            <th>{t("billing.recommendedActions.surface")}</th>
            <th>{t("billing.summary.recommendedActions")}</th>
            {!billingReport.scope && (
              <th style={WRAPPED_HEADER_STYLE}>{t("billing.recommendedActions.claim")}</th>
            )}
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.recommendedActions.section")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>
              {t("billing.recommendedActions.amountBilledOrUplift")}
            </th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.recommendedActions.detail")}</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((action) => {
            const amount = recommendedActionAmountParts(t, action);
            const sectionId = recommendedActionSectionId(action.surface);
            const isActive = action.action_id === selectedActionId;
            const findingType = getFindingType(action);
            const clauseRef = action.clause_ref ?? null;
            const clauseKey = clauseRef?.clause_key ?? "";
            const cite = clauseRef?.clause_coordinate || action.sut_section_id || "";
            // Selection drives invoice-line highlighting (independent of scroll),
            // so every row is clickable; scroll is a bonus when an anchor exists.
            const handleSelect = () => {
              onSelectAction?.(action);
              if (sectionId) {
                document.getElementById(sectionId)?.scrollIntoView({
                  behavior: "smooth",
                  block: "start",
                });
              }
            };
            return (
              <tr
                key={action.action_id}
                className={cn(
                  "cursor-pointer",
                  isActive && "bg-[var(--gold-subtle)]",
                )}
                onClick={handleSelect}
                onKeyDown={
                  (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      handleSelect();
                    }
                  }
                }
                tabIndex={0}
              >
                <td>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Chip variant="neutral">
                      {recommendedActionSurfaceLabel(t, action.surface)}
                    </Chip>
                    <Chip variant={findingTypeChipVariant(findingType)}>
                      {t(findingTypeLabelKey(findingType))}
                    </Chip>
                  </div>
                </td>
                <td className="font-medium text-[var(--text-primary)]">
                  {recommendedActionTitle(t, action)}
                </td>
                {!billingReport.scope && (
                  <td className="font-mono text-xs text-[var(--text-secondary)]">
                    {action.claim_id ?? "—"}
                  </td>
                )}
                <td className="text-sm text-[var(--text-secondary)]">
                  {cite ? (
                    onOpenClause && clauseKey ? (
                      <button
                        type="button"
                        aria-label={t("billing.recommendedActions.inspectClause", {
                          coordinate: cite,
                        })}
                        className="underline decoration-dotted underline-offset-2 transition-colors hover:text-[var(--gold-hover)]"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenClause(clauseKey);
                        }}
                      >
                        {formatSutSectionLabel(cite)}
                      </button>
                    ) : (
                      formatSutSectionLabel(cite)
                    )
                  ) : (
                    "—"
                  )}
                </td>
                <td className="num-col tabular-nums text-right text-sm text-[var(--text-primary)]">
                  {amount ? (
                    <span>
                      {amount.value != null ? fmtTRY2(amount.value) : amount.label}
                      {amount.value != null ? (
                        <span className="block text-xs text-[var(--text-secondary)]">
                          {amount.label}
                        </span>
                      ) : null}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="text-sm text-[var(--text-secondary)]">
                  {action.detail || action.message_code
                    ? translateStructuredApiMessage(t, action)
                    : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </TableWrap>
    </div>
  );
}
