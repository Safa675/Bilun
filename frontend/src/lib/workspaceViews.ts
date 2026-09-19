import type {
  BillingActionReport,
  ClaimComplianceFinding,
  RecommendedActionItem,
} from "@/lib/domains/sut";
import { getFindingType, getRecommendedActions } from "@/lib/recommendedActions";
import type { FindingType } from "@/lib/recommendedActions";

export type WorkspaceViewId = "compliance" | "revenue" | "audit";

/**
 * The finding class each workspace view presents. The single source of truth
 * for view membership is `getFindingType` (`@/lib/recommendedActions`), which
 * consumes the backend-provided `finding_type` on each action row.
 */
export const WORKSPACE_VIEW_FINDING: Record<WorkspaceViewId, FindingType> = {
  compliance: "compliance",
  revenue: "opportunity",
  audit: "informational",
};

/**
 * Which workspace view owns each billing section anchor (`?section=` values).
 * Mirrors `RECOMMENDED_ACTION_SECTION_IDS` in `@/lib/recommendedActions`.
 */
export const SECTION_VIEW_MAP: Record<string, WorkspaceViewId> = {
  "billing-lab": "compliance",
  "billing-strategy": "compliance",
  "materials-pre-check": "compliance",
  "drug-indication": "compliance",
  "claim-compliance": "compliance",
  "billing-copay": "revenue",
  "billing-session-uplift": "revenue",
  "billing-blood-uplift": "revenue",
  "billing-material-uplift": "revenue",
  "billing-procedure-addon-uplift": "revenue",
  "billing-procedure-capture-gap": "revenue",
  "billing-drg-package-adequacy": "revenue",
  "billing-gazette-repricing": "revenue",
  "billing-drg-uplift": "revenue",
  "billing-care-setting-review": "revenue",
  "claim-submission-checklist": "audit",
  "medula-playbook": "audit",
};

export function viewForSection(sectionId: string | null | undefined): WorkspaceViewId | null {
  if (!sectionId) return null;
  return SECTION_VIEW_MAP[sectionId] ?? null;
}

/** Recommended actions belonging to one workspace view. */
export function viewActions(
  report: BillingActionReport,
  view: WorkspaceViewId,
): RecommendedActionItem[] {
  const finding = WORKSPACE_VIEW_FINDING[view];
  return getRecommendedActions(report).filter(
    (action) => getFindingType(action) === finding,
  );
}

/** Canonical identity for a claim-compliance finding, with old-payload fallback. */
export function claimComplianceFindingIdentity(
  row: Pick<ClaimComplianceFinding, "finding_id" | "action_id">,
): string | null {
  return row.finding_id ?? row.action_id ?? null;
}

export function scopedClaimComplianceFindings(
  report: BillingActionReport,
): ClaimComplianceFinding[] {
  return (report.claim_compliance?.findings ?? []).filter(
    (row) => row.patient_id === report.patient_id &&
      (!report.claim_id || row.claim_id === report.claim_id || row.claim_id == null),
  );
}

/** Sum of billed amounts at risk across compliance-classified actions. */
export function complianceBilledAtRisk(report: BillingActionReport): number {
  return viewActions(report, "compliance").reduce(
    (sum, action) => sum + (action.billed_try ?? 0),
    0,
  );
}

/** SGK uplift shown on the revenue view (total fallback for partial reports). */
export function recoverableUplift(report: BillingActionReport): number {
  return report.sgk_uplift_try ?? report.total_recoverable_try ?? 0;
}
