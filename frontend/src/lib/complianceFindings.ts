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

export function buildUnifiedComplianceFindings(
  report: BillingActionReport,
  tOrOptions?: TranslateFn | { t?: TranslateFn },
): UnifiedComplianceFindingRow[] {
  const t = typeof tOrOptions === "function"
    ? tOrOptions
    : tOrOptions?.t ?? fallbackTranslate;

  const actions = viewActions(report, "compliance");
  const scopedFindings = scopedClaimComplianceFindings(report);

  // Map canonical finding_id -> scoped finding for O(1) canonical matching.
  // Deduplication rule: ONLY when both action and finding carry non-empty, equal finding_id.
  const findingMap = new Map<string, ClaimComplianceFinding>();
  for (const finding of scopedFindings) {
    if (finding.finding_id && finding.finding_id.trim().length > 0) {
      findingMap.set(finding.finding_id, finding);
    }
  }

  const mergedFindingIds = new Set<string>();
  const rows: UnifiedComplianceFindingRow[] = [];

  // 1. Process actions in viewActions order
  for (const action of actions) {
    const canonicalId =
      action.finding_id && action.finding_id.trim().length > 0
        ? action.finding_id
        : null;

    const matchedFinding = canonicalId ? findingMap.get(canonicalId) : undefined;
    const actionStatus = resolveActionStatus(action, report);
    const actionSourceLabel = recommendedActionSurfaceLabel(t, action.surface);
    const amountParts = recommendedActionAmountParts(t, action);
    const detail =
      action.detail ||
      (action.message_code ? translateStructuredApiMessage(t, action) : null) ||
      null;

    if (matchedFinding && canonicalId) {
      mergedFindingIds.add(canonicalId);
      const findingStatus = resolveFindingStatus(matchedFinding);
      const findingLabel = findingSourceText(t);
      const combinedStatus: UnifiedComplianceStatus =
        actionStatus === "confirmed_violation" || findingStatus === "confirmed_violation"
          ? "confirmed_violation"
          : "review_risk";

      const findingCode =
        matchedFinding.procedure_code ||
        matchedFinding.material_code ||
        matchedFinding.drug_code ||
        matchedFinding.line_id ||
        null;

      const sutLabel =
        action.clause_ref?.clause_coordinate ||
        action.sut_section_id ||
        findingSutLabel(matchedFinding);

      let amountVal = amountParts?.value ?? null;
      let amountLbl = amountParts?.label ?? null;
      if (amountVal == null && matchedFinding.billed_try != null && matchedFinding.billed_try > 0) {
        amountVal = matchedFinding.billed_try;
        amountLbl = t("billing.recommendedActions.amountBilledAtRisk");
      }

      rows.push({
        rowId: canonicalId,
        canonicalFindingId: canonicalId,
        sourceKind: "recommended_action",
        sourceLabels: [actionSourceLabel, findingLabel],
        status: combinedStatus,
        title: recommendedActionTitle(t, action),
        detail: detail || matchedFinding.detail || null,
        claimId: action.claim_id ?? matchedFinding.claim_id ?? null,
        code: recommendedActionPrimaryCode(action) ?? findingCode,
        sutLabel,
        amountValue: amountVal,
        amountLabel: amountLbl,
        action,
        finding: matchedFinding,
      });
    } else {
      rows.push({
        rowId: action.action_id,
        canonicalFindingId: canonicalId,
        sourceKind: "recommended_action",
        sourceLabels: [actionSourceLabel],
        status: actionStatus,
        title: recommendedActionTitle(t, action),
        detail,
        claimId: action.claim_id ?? null,
        code: recommendedActionPrimaryCode(action),
        sutLabel: action.clause_ref?.clause_coordinate || action.sut_section_id || null,
        amountValue: amountParts?.value ?? null,
        amountLabel: amountParts?.label ?? null,
        action,
        finding: null,
      });
    }
  }

  // 2. Append unmerged canonical findings
  scopedFindings.forEach((finding, index) => {
    if (finding.finding_id && mergedFindingIds.has(finding.finding_id)) {
      return;
    }

    const canonicalFindingId =
      finding.finding_id && finding.finding_id.trim().length > 0
        ? finding.finding_id
        : null;

    const rowId =
      canonicalFindingId ??
      finding.action_id ??
      `claim_compliance:${finding.rule_id}:${index}`;

    const status = resolveFindingStatus(finding);
    const findingLabel = findingSourceText(t);
    const code =
      finding.procedure_code ||
      finding.material_code ||
      finding.drug_code ||
      finding.line_id ||
      null;

    const sutLabel = findingSutLabel(finding);

    const amountValue =
      finding.billed_try != null && finding.billed_try > 0
        ? finding.billed_try
        : null;

    const amountLabel =
      amountValue != null
        ? t("billing.recommendedActions.amountBilledAtRisk")
        : null;

    rows.push({
      rowId,
      canonicalFindingId,
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
