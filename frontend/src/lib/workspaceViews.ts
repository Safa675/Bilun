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
  "wavea-reviews": "compliance",
  "wavea-advisories": "compliance",
  "billing-copay": "revenue",
  "wavea-financial": "revenue",
  "billing-session-uplift": "revenue",
  "billing-blood-uplift": "revenue",
  "billing-material-uplift": "revenue",
  "billing-procedure-addon-uplift": "revenue",
  "billing-procedure-capture-gap": "revenue",
  "billing-drg-package-adequacy": "revenue",
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

export function isClaimComplianceFindingSelected(
  row: Pick<ClaimComplianceFinding, "finding_id" | "action_id">,
  selectedFindingId: string | null | undefined,
): boolean {
  return Boolean(
    selectedFindingId && claimComplianceFindingIdentity(row) === selectedFindingId,
  );
}

export function scopedClaimComplianceFindings(
  report: BillingActionReport,
): ClaimComplianceFinding[] {
  return (report.claim_compliance?.findings ?? []).filter(
    (row) => row.patient_id === report.patient_id &&
      (!report.claim_id || row.claim_id === report.claim_id || row.claim_id == null),
  );
}

/**
 * Billed amount at risk across compliance-classified actions, with coverage.
 *
 * `count` is the number of counted at-risk actions and `known` how many of
 * them carry a billed amount. `total` sums only those `known` amounts, so it is
 * a partial figure whenever `known < count`; a missing (null) billed amount is
 * never treated as zero. Actions with `surface === "drug_indication"` are
 * deliberately left out of the total and of both counts.
 */
export interface BilledAtRiskSummary {
  total: number;
  known: number;
  count: number;
}

export function complianceBilledAtRiskSummary(
  report: BillingActionReport,
): BilledAtRiskSummary {
  let total = 0;
  let known = 0;
  let count = 0;
  for (const action of viewActions(report, "compliance")) {
    if (action.surface === "drug_indication") continue;
    count += 1;
    if (action.billed_try == null) continue;
    total += action.billed_try;
    known += 1;
  }
  return { total, known, count };
}

/**
 * Sum of billed amounts at risk across compliance-classified actions, or null
 * when any counted action lacks a billed amount (never a bare partial sum).
 */
export function complianceBilledAtRisk(report: BillingActionReport): number | null {
  const { total, known, count } = complianceBilledAtRiskSummary(report);
  return known === count ? total : null;
}

/**
 * Sum of amounts that may be missing, with coverage (same shape as
 * `BilledAtRiskSummary`). `count` is every amount offered, `known` how many are
 * present, and `total` adds only the present ones, so it is a partial figure
 * whenever `known < count`. A missing (null/undefined) amount is never zero.
 */
export interface KnownAmountsSum {
  total: number;
  known: number;
  count: number;
}

export function sumKnownAmounts(
  amounts: ReadonlyArray<number | null | undefined>,
): KnownAmountsSum {
  let total = 0;
  let known = 0;
  for (const amount of amounts) {
    if (amount == null) continue;
    total += amount;
    known += 1;
  }
  return { total, known, count: amounts.length };
}

/**
 * How much of a sum is known: "complete" (every amount present, or nothing to
 * sum), "none" (amounts exist but none is known: show a dash) or "partial".
 */
export type AmountCoverage = "complete" | "partial" | "none";

export function amountCoverage(sum: Pick<KnownAmountsSum, "known" | "count">): AmountCoverage {
  if (sum.known === sum.count) return "complete";
  return sum.known === 0 ? "none" : "partial";
}

/** SGK uplift shown on the revenue view (total fallback for partial reports). */
export function recoverableUplift(report: BillingActionReport): number | null {
  return report.sgk_uplift_try ?? report.total_recoverable_try ?? null;
}
