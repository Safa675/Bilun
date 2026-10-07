"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { getExactnessDescription, type ExactnessLike } from "@/lib/sutExactness";
import { useT } from "@/lib/i18n/useTranslations";
import { translateStructuredApiMessage } from "@/lib/apiMessages";
import { formatSutSectionLabel } from "@/lib/billingReportFields";
import { findingTypeChipVariant, findingTypeLabelKey, getFindingType, getRecommendedActions, recommendedActionSectionId, recommendedActionAmountParts, recommendedActionSurfaceLabel, recommendedActionTitle, type FindingType, type RecommendedActionItem } from "@/lib/recommendedActions";
import { cn } from "@/lib/cn";
import { Button, Chip, Eyebrow, Surface } from "@/components/primitives";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, TableWrap } from "./shared";
import { motionScrollBehavior } from "@/lib/motion";

export function RecommendedActionsPanel({
  billingReport,
  selectedActionId,
  onSelectAction,
  findingFilter,
  onOpenClause,
  activeClauseKey,
  compact = false,
  onShowAll,
}: {
  billingReport: BillingActionReport;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  /** Restrict rows to one finding class (engine view) or show all (overview). */
  findingFilter?: FindingType;
  /** When provided, rows with a canonical clause cite render an inspect button. */
  onOpenClause?: (clauseKey: string) => void;
  activeClauseKey?: string | null;
  /** Page overview: the existing amount ordering, limited to three actions. */
  compact?: boolean;
  onShowAll?: () => void;
}) {
  const t = useT();
  const allActions = getRecommendedActions(billingReport);
  const actions = findingFilter
    ? allActions.filter((action) => getFindingType(action) === findingFilter)
    : allActions;

  if (actions.length === 0) {
    return null;
  }

  if (compact) {
    const sourceBlocks: Record<string, ExactnessLike | null | undefined> = {
      lab: billingReport.lab,
      copay: billingReport.copay,
      materials: billingReport.materials,
      billing_strategy: billingReport.billing_strategy,
      payment_methods: billingReport.billing_strategy,
      claim_checklist: billingReport.claim_submission_checklist,
      medula_playbook: billingReport.medula_rejection_playbook,
      drug_indication: billingReport.drug_indication,
      session_uplift: billingReport.session_uplift,
      blood_uplift: billingReport.blood_uplift,
      material_uplift: billingReport.material_uplift,
      procedure_addon_uplift: billingReport.procedure_addon_uplift,
      procedure_capture_gap: billingReport.procedure_capture_gap,
      drg_package_adequacy: billingReport.drg_package_adequacy,
      drg_uplift: billingReport.drg_uplift,
      care_setting_review: billingReport.care_setting_review,
      yatak_puani: (billingReport as BillingActionReport & { yatak_puani?: ExactnessLike }).yatak_puani,
    };
    return (
      <Surface variant="base" padding="md" className="@container space-y-3" data-next-actions>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            {t("billing.recommendedActions.nextActions")}
          </h2>
          <button type="button" onClick={onShowAll} className="text-xs font-semibold text-[var(--gold)] hover:text-[var(--gold-hover)]">
            {t("billing.recommendedActions.showAll", { count: actions.length })}
          </button>
        </div>
        <ol className="divide-y divide-[var(--border-subtle)]">
          {actions.slice(0, 3).map((action) => {
            const amount = recommendedActionAmountParts(t, action);
            const source = sourceBlocks[action.surface];
            const exactness = source?.exactness_status ?? source?.pricing_status;
            const clauseKey = action.clause_ref?.clause_key ?? "";
            const cite = action.clause_ref?.clause_coordinate || action.sut_section_id || "";
            return (
              <li key={action.action_id} data-action-id={action.action_id} data-clause-key={clauseKey || undefined} data-source-active={clauseKey && clauseKey === activeClauseKey ? "true" : undefined} className={cn("grid grid-cols-1 items-center gap-3 py-2 first:pt-0 last:pb-0 @min-[300px]:grid-cols-[minmax(0,1fr)_auto] @min-[560px]:grid-cols-[minmax(0,1fr)_auto_auto]", action.action_id === selectedActionId && "bg-[var(--gold-subtle)]")}>
                <div className="min-w-0 @min-[300px]:col-span-2 @min-[560px]:col-span-1">
                  <button type="button" onClick={() => onSelectAction?.(action)} className="block w-full text-left text-sm font-medium leading-snug [overflow-wrap:anywhere] text-[var(--text-primary)] hover:text-[var(--gold-hover)]">
                    {recommendedActionTitle(t, action)}
                  </button>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-[var(--text-secondary)]">
                    <span>{recommendedActionSurfaceLabel(t, action.surface)}</span>
                    <Chip variant={exactness === "exact" ? "success" : "warning"} title={getExactnessDescription(source, t)}>
                      {exactness ? t(`billing.recommendedActions.exactness.${exactness}`) : t("common.unavailable")}
                    </Chip>
                  </div>
                </div>
                <div className="min-w-0 text-left @min-[560px]:text-right">
                  <span className="whitespace-nowrap tabular-nums text-sm font-semibold text-[var(--text-primary)]">
                    {amount?.value != null ? fmtTRY2(amount.value) : amount?.label ?? "—"}
                  </span>
                  {amount?.value != null && <span className="block text-xs text-[var(--text-secondary)]">{amount.label}</span>}
                </div>
                <Button variant="secondary" size="compact" disabled={!clauseKey || !onOpenClause} aria-label={clauseKey && onOpenClause ? t("billing.recommendedActions.inspectClause", { coordinate: cite }) : t("billing.recommendedActions.sourceUnavailable")} onClick={() => clauseKey && onOpenClause?.(clauseKey)} className="justify-self-start whitespace-nowrap @min-[300px]:justify-self-end">
                  {cite ? `${t("billing.recommendedActions.section")} ${formatSutSectionLabel(cite)}` : t("billing.recommendedActions.sourceUnavailable")}
                </Button>
              </li>
            );
          })}
        </ol>
      </Surface>
    );
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
            const handleSelect = (row: HTMLElement) => {
              onSelectAction?.(action);
              if (sectionId) {
                const root = row.closest("[data-patient-workspace]") ?? document;
                const target = Array.from(root.querySelectorAll("[id]")).find((element) => element.id === sectionId);
                for (let ancestor = target?.parentElement; ancestor; ancestor = ancestor.parentElement) {
                  if (ancestor.tagName === "DETAILS") (ancestor as HTMLDetailsElement).open = true;
                }
                target?.scrollIntoView({
                  behavior: motionScrollBehavior(),
                  block: "start",
                });
              }
            };
            return (
              <tr
                key={action.action_id}
                data-clause-key={clauseKey || undefined}
                data-source-active={clauseKey && clauseKey === activeClauseKey ? "true" : undefined}
                className={cn(
                  "cursor-pointer",
                  isActive && "bg-[var(--gold-subtle)]",
                )}
                onClick={(event) => handleSelect(event.currentTarget)}
                onKeyDown={
                  (event) => {
                    if ((event.key === "Enter" || event.key === " ") && event.target === event.currentTarget) {
                      event.preventDefault();
                      handleSelect(event.currentTarget);
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
                        className="inline-flex whitespace-nowrap rounded-[var(--r-sm)] border border-[var(--border-default)] bg-[var(--surface-base)] px-2 py-1 font-semibold transition-colors hover:text-[var(--gold-hover)]"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenClause(clauseKey);
                        }}
                      >
                        {t("billing.recommendedActions.section")} {formatSutSectionLabel(cite)}
                      </button>
                    ) : (
                      formatSutSectionLabel(cite)
                    )
                  ) : (
                    "—"
                  )}
                </td>
                <td className="num-col whitespace-nowrap tabular-nums text-right text-sm text-[var(--text-primary)]">
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
