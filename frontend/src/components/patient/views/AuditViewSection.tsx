"use client";

import { useCallback, useEffect, useState } from "react";
import type { BillingActionReport, RecommendedActionItem } from "@/lib/domains/sut";
import {
  ClaimSubmissionChecklistSection,
  MedulaRejectionPlaybookSection,
  RecommendedActionsPanel,
} from "@/components/patient/SutBillingReportSections";
import { fmtNum, KpiCard } from "@/components/tabs/sut/shared";
import { useT } from "@/lib/i18n/useTranslations";
import { viewActions } from "@/lib/workspaceViews";
import { Eyebrow, Surface } from "@/components/primitives";

const ERROR_COLOR = "#B91C1C";
const READY_COLOR = "#2F6E4E";

const STORAGE_KEY_PREFIX = "bilun:checklist:ready:";

/**
 * Client-side "file ready" state for the pre-flight checklist.
 * Persisted per patient in localStorage (no backend schema change).
 */
function useChecklistReady(patientId: string) {
  const [readyIds, setReadyIds] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(`${STORAGE_KEY_PREFIX}${patientId}`);
      if (raw) {
        setReadyIds(new Set(JSON.parse(raw) as string[]));
      }
    } catch {
      // Ignore malformed local state — start empty.
    }
  }, [patientId]);

  const toggleReady = useCallback(
    (id: string) => {
      setReadyIds((previous) => {
        const next = new Set(previous);
        if (next.has(id)) {
          next.delete(id);
        } else {
          next.add(id);
        }
        try {
          window.localStorage.setItem(
            `${STORAGE_KEY_PREFIX}${patientId}`,
            JSON.stringify([...next]),
          );
        } catch {
          // Storage unavailable — state stays in-memory for this session.
        }
        return next;
      });
    },
    [patientId],
  );

  return { readyIds, toggleReady };
}

/**
 * View 3 — Gönderim Öncesi Evrak & İnceleme (Pre-Flight Audit).
 *
 * Groups the surfaces `getFindingType` classifies as `informational`
 * (claim checklist + MEDULA playbook) with their KPIs and the
 * file-ready confirmation mechanism.
 */
export default function AuditViewSection({
  billingReport,
  patientId,
  selectedActionId,
  onSelectAction,
  onOpenClause,
}: {
  billingReport: BillingActionReport;
  patientId: string;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  onOpenClause?: (sectionId: string) => void;
}) {
  const t = useT();
  const { readyIds, toggleReady } = useChecklistReady(patientId);
  const viewActionsList = viewActions(billingReport, "audit");

  const rawChecklistItems = billingReport.claim_submission_checklist?.items ?? [];
  const checklistItems = rawChecklistItems.filter((item) => item.checklist_id);
  // Keep the checklist KPI and the ready KPI on the SAME denominator. The
  // backend count is len(items) today (block_registry `item_count`), but
  // deriving the total from the rendered items makes the invariant explicit:
  // every item shown below is checkable, so the ready count can never be
  // silently smaller than the total.
  const checklistCount =
    rawChecklistItems.length > 0
      ? rawChecklistItems.length
      : (billingReport.claim_submission_checklist_count ?? 0);
  const errorCount = billingReport.claim_submission_checklist?.error_count ?? 0;
  const readyCount = checklistItems.filter((item) => readyIds.has(item.checklist_id as string)).length;

  return (
    <div className="space-y-4">
      <p className="text-sm leading-snug text-[var(--text-secondary)]">
        {t("billing.views.audit.description")}
      </p>

      <div className="grid gap-6 sm:grid-cols-3">
        <KpiCard
          label={t("billing.views.audit.kpiChecklist")}
          value={fmtNum(checklistCount)}
        />
        <KpiCard
          label={t("billing.views.audit.kpiErrors")}
          value={fmtNum(errorCount)}
          valueColor={errorCount > 0 ? ERROR_COLOR : undefined}
        />
        <KpiCard
          label={t("billing.views.audit.kpiReady")}
          value={fmtNum(readyCount)}
          valueColor={readyCount > 0 ? READY_COLOR : undefined}
          sub={`${readyCount} / ${checklistItems.length}`}
        />
      </div>

      {checklistItems.length > 0 && (
        <Surface variant="soft" padding="md" className="space-y-3">
          <Eyebrow>{t("billing.views.audit.readyToggle")}</Eyebrow>
          <ul className="space-y-2">
            {checklistItems.map((item) => {
              const id = item.checklist_id as string;
              const label = item.sut_anchor ?? id;
              const checked = readyIds.has(id);
              return (
                <li key={id}>
                  <label
                    className="flex cursor-pointer items-start gap-3 rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-4 py-3"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleReady(id)}
                      aria-label={t("billing.views.audit.readyAria", { item: label })}
                      className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--gold)]"
                    />
                    <span className="text-sm leading-snug text-[var(--text-secondary)]">
                      {label}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </Surface>
      )}

      {viewActionsList.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">{t("billing.views.noItems")}</p>
      ) : (
        <RecommendedActionsPanel
          billingReport={billingReport}
          findingFilter="informational"
          selectedActionId={selectedActionId}
          onSelectAction={onSelectAction}
          onOpenClause={onOpenClause}
        />
      )}

      {billingReport.claim_submission_checklist && (
        <ClaimSubmissionChecklistSection
          checklistData={billingReport.claim_submission_checklist}
        />
      )}
      {billingReport.medula_rejection_playbook && (
        <MedulaRejectionPlaybookSection
          playbookData={billingReport.medula_rejection_playbook}
        />
      )}
    </div>
  );
}
