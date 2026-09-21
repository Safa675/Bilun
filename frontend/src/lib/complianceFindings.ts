import type {
  BillingActionReport,
  ClaimComplianceFinding,
  RecommendedActionItem,
} from "@/lib/domains/sut";
import {
  recommendedActionAmountParts,
  recommendedActionPrimaryCode,
  recommendedActionSurfaceLabel,
  recommendedActionTitle,
} from "@/lib/recommendedActions";
import { translateStructuredApiMessage } from "@/lib/apiMessages";
import { scopedClaimComplianceFindings, viewActions } from "@/lib/workspaceViews";

export type UnifiedComplianceStatus =
  | "confirmed_violation"
  | "review_risk";

export interface UnifiedComplianceFindingRow {
  rowId: string;
  canonicalFindingId: string | null;
  sourceKind: "recommended_action" | "claim_compliance";
  sourceLabels: string[];
  status: UnifiedComplianceStatus;
  title: string;
  detail: string | null;
  claimId: string | null;
  code: string | null;
  sutLabel: string | null;
  amountValue: number | null;
  amountLabel: string | null;
  action: RecommendedActionItem | null;
  finding: ClaimComplianceFinding | null;
}

export type TranslateFn = (
  key: string,
  params?: Record<string, string | number | undefined | null>,
) => string;

const fallbackTranslate: TranslateFn = (key, params) => {
  if (!params) return key;
  return Object.entries(params).reduce(
    (acc, [k, v]) => acc.replace(new RegExp(`\\{${k}\\}`, "g"), String(v ?? "")),
    key,
  );
};



function resolveActionStatus(
  action: RecommendedActionItem,
  report: BillingActionReport,
): UnifiedComplianceStatus {
  if (action.kind === "compliance_violation") {
    return "confirmed_violation";
  }
  if (action.surface === "drug_indication" && action.finding_id) {
    const isViolation = report.drug_indication?.violations?.some(
      (v) => v.finding_id === action.finding_id,
    );
    if (isViolation) {
      return "confirmed_violation";
    }
  }
  return "review_risk";
}

function resolveFindingStatus(
  finding: ClaimComplianceFinding,
): UnifiedComplianceStatus {
  if (finding.status === "violation") {
    return "confirmed_violation";
  }
  return "review_risk";
}

function ruleLabel(
  t: TranslateFn,
  ruleId: string | null | undefined,
  kind: string | null | undefined,
): string {
  if (!ruleId) return kind?.replaceAll("_", " ") || "—";
  const key = `optimizer.claimCompliance.${ruleId}`;
  const translated = t(key);
  return translated === key ? (kind?.replaceAll("_", " ") || ruleId) : translated;
}

function findingSourceText(t: TranslateFn): string {
  const surfaceKey = "billing.recommendedActions.surfaces.claimCompliance";
  const translated = t(surfaceKey);
  if (translated !== surfaceKey) return translated;
  const optimizerKey = "optimizer.tabs.claim_compliance";
  const optTranslated = t(optimizerKey);
  if (optTranslated !== optimizerKey) return optTranslated;
  return "Fatura uyumluluğu";
}

function findingSutLabel(finding: ClaimComplianceFinding): string | null {
  const source = finding.regulatory_source;
  let structuredSource: string | null = null;
  if (typeof source === "string") {
    structuredSource = source;
  } else if (source && typeof source === "object") {
    const record = source as Record<string, unknown>;
    structuredSource = ["source_type", "clause_coordinate", "clause_key", "label"]
      .map((key) => record[key])
      .find((value): value is string => typeof value === "string" && value.length > 0) ?? null;
  }
  return [finding.sut_section_id, finding.source_engine, structuredSource]
    .filter((value): value is string => Boolean(value))
    .join(" · ") || null;
}

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function uniqueRowId(base: string, counts: Map<string, number>): string {
  const seen = counts.get(base) ?? 0;
  counts.set(base, seen + 1);
  if (seen === 0) return base;
  return `${base}:${seen}`;
}

export function buildUnifiedComplianceFindings(
  report: BillingActionReport,
  tOrOptions?: TranslateFn | { t?: TranslateFn },
): UnifiedComplianceFindingRow[] {
  const t = typeof tOrOptions === "function"
    ? tOrOptions
    : tOrOptions?.t ?? fallbackTranslate;

  const actions = viewActions(report, "compliance");
  const scopedFindings = scopedClaimComplianceFindings(report);

  // Map explicit canonical finding_id -> scoped finding for O(1) matching.
  // Deduplication rule: ONLY when both action and finding carry non-empty, equal finding_id.
  // Legacy action_id is navigation-only and never participates in dedupe.
  const findingMap = new Map<string, ClaimComplianceFinding>();
  for (const finding of scopedFindings) {
    const explicit = nonEmpty(finding.finding_id);
    if (explicit && !findingMap.has(explicit)) {
      findingMap.set(explicit, finding);
    }
  }

  // Group actions by explicit canonical finding_id before emitting rows.
  // Each explicit canonical id emits at most one row; order follows first appearance.
  type ActionGroup = { explicitId: string | null; items: RecommendedActionItem[] };
  const groups: ActionGroup[] = [];
  const groupIndexByExplicit = new Map<string, number>();
  for (const action of actions) {
    const explicit = nonEmpty(action.finding_id);
    if (explicit) {
      const idx = groupIndexByExplicit.get(explicit);
      if (idx == null) {
        groupIndexByExplicit.set(explicit, groups.length);
        groups.push({ explicitId: explicit, items: [action] });
      } else {
        groups[idx].items.push(action);
      }
    } else {
      groups.push({ explicitId: null, items: [action] });
    }
  }

  const mergedFindingIds = new Set<string>();
  const rowIdCounts = new Map<string, number>();
  const rows: UnifiedComplianceFindingRow[] = [];

  // 1. Process grouped actions in viewActions order
  groups.forEach((group) => {
    const { explicitId, items } = group;
    const primary = items[0];
    const primarySourceLabel = recommendedActionSurfaceLabel(t, primary.surface);
    const primaryAmountParts = recommendedActionAmountParts(t, primary);
    const primaryDetail =
      primary.detail ||
      (primary.message_code ? translateStructuredApiMessage(t, primary) : null) ||
      null;

    if (explicitId) {
      const matchedFinding = findingMap.get(explicitId);

      if (matchedFinding || items.length > 1) {
        // Grouped canonical row: one row per explicit canonical id.
        if (matchedFinding) {
          mergedFindingIds.add(explicitId);
        }
        const findingStatus = matchedFinding ? resolveFindingStatus(matchedFinding) : null;
        const anyActionViolation = items.some(
          (item) => resolveActionStatus(item, report) === "confirmed_violation",
        );
        const combinedStatus: UnifiedComplianceStatus =
          anyActionViolation || findingStatus === "confirmed_violation"
            ? "confirmed_violation"
            : "review_risk";

        // Stable-order unique source labels across all grouped actions + canonical once.
        const sourceLabels: string[] = [];
        for (const item of items) {
          const label = recommendedActionSurfaceLabel(t, item.surface);
          if (!sourceLabels.includes(label)) sourceLabels.push(label);
        }
        if (matchedFinding) {
          const findingLabel = findingSourceText(t);
          if (!sourceLabels.includes(findingLabel)) sourceLabels.push(findingLabel);
        }

        const findingCode = matchedFinding
          ? matchedFinding.procedure_code ||
            matchedFinding.material_code ||
            matchedFinding.drug_code ||
            matchedFinding.line_id ||
            null
          : null;

        const sutLabel =
          primary.clause_ref?.clause_coordinate ||
          primary.sut_section_id ||
          (matchedFinding ? findingSutLabel(matchedFinding) : null);

        let amountVal = primaryAmountParts?.value ?? null;
        let amountLbl = primaryAmountParts?.label ?? null;
        if (amountVal == null && matchedFinding?.billed_try != null) {
          amountVal = matchedFinding.billed_try;
          amountLbl = t("billing.recommendedActions.amountBilledAtRisk");
        }

        rows.push({
          rowId: uniqueRowId(`merged:${explicitId}`, rowIdCounts),
          canonicalFindingId: explicitId,
          sourceKind: "recommended_action",
          sourceLabels,
          status: combinedStatus,
          title: recommendedActionTitle(t, primary),
          detail: primaryDetail || matchedFinding?.detail || null,
          claimId: primary.claim_id ?? matchedFinding?.claim_id ?? null,
          code: recommendedActionPrimaryCode(primary) ?? findingCode,
          sutLabel,
          amountValue: amountVal,
          amountLabel: amountLbl,
          action: primary,
          finding: matchedFinding ?? null,
        });
        return;
      }

      // Single explicit action without a canonical match: action row carrying
      // the explicit canonical id for navigation, namespaced separately from merged.
      const actionStatus = resolveActionStatus(primary, report);
      rows.push({
        rowId: uniqueRowId(`action:${nonEmpty(primary.action_id) ?? explicitId}`, rowIdCounts),
        canonicalFindingId: explicitId,
        sourceKind: "recommended_action",
        sourceLabels: [primarySourceLabel],
        status: actionStatus,
        title: recommendedActionTitle(t, primary),
        detail: primaryDetail,
        claimId: primary.claim_id ?? null,
        code: recommendedActionPrimaryCode(primary),
        sutLabel: primary.clause_ref?.clause_coordinate || primary.sut_section_id || null,
        amountValue: primaryAmountParts?.value ?? null,
        amountLabel: primaryAmountParts?.label ?? null,
        action: primary,
        finding: null,
      });
      return;
    }

    // Action without explicit canonical identity.
    const actionStatus = resolveActionStatus(primary, report);
    rows.push({
      rowId: uniqueRowId(`action:${nonEmpty(primary.action_id) ?? `index-${rows.length}`}`, rowIdCounts),
      canonicalFindingId: null,
      sourceKind: "recommended_action",
      sourceLabels: [primarySourceLabel],
      status: actionStatus,
      title: recommendedActionTitle(t, primary),
      detail: primaryDetail,
      claimId: primary.claim_id ?? null,
      code: recommendedActionPrimaryCode(primary),
      sutLabel: primary.clause_ref?.clause_coordinate || primary.sut_section_id || null,
      amountValue: primaryAmountParts?.value ?? null,
      amountLabel: primaryAmountParts?.label ?? null,
      action: primary,
      finding: null,
    });
  });

  // 2. Append unmerged canonical findings with legacy navigation fallback.
  scopedFindings.forEach((finding, index) => {
    const explicit = nonEmpty(finding.finding_id);
    if (explicit && mergedFindingIds.has(explicit)) {
      return;
    }

    // Navigation identity: explicit finding_id preferred, legacy action_id fallback.
    // The fallback is selection/deep-link only and never used for cross-source dedupe.
    const navigationId = explicit ?? nonEmpty(finding.action_id);

    const baseRowId = navigationId
      ? `canonical:${navigationId}`
      : `canonical:claim_compliance:${finding.rule_id ?? "unknown"}:${index}`;

    const status = resolveFindingStatus(finding);
    const findingLabel = findingSourceText(t);
    const code =
      finding.procedure_code ||
      finding.material_code ||
      finding.drug_code ||
      finding.line_id ||
      null;

    const sutLabel = findingSutLabel(finding);

    // Preserve explicit zero (and any numeric) amounts; only null/undefined is unknown.
    const amountValue = finding.billed_try != null ? finding.billed_try : null;

    const amountLabel =
      amountValue != null
        ? t("billing.recommendedActions.amountBilledAtRisk")
        : null;

    rows.push({
      rowId: uniqueRowId(baseRowId, rowIdCounts),
      canonicalFindingId: navigationId,
      sourceKind: "claim_compliance",
      sourceLabels: [findingLabel],
      status,
      title: ruleLabel(t, finding.rule_id, finding.kind),
      detail: finding.detail || null,
      claimId: finding.claim_id ?? null,
      code,
      sutLabel,
      amountValue,
      amountLabel,
      action: null,
      finding,
    });
  });

  return rows;
}
