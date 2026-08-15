import { translateApiText } from "@/lib/apiMessages";
import type {
  BillingStrategyRecommendation,
  CopayOptimization,
} from "./domains/sut";

export type CopayRateCorrectionRow = CopayOptimization["rate_corrections"][number];
export type BillingStrategyRow =
  BillingStrategyRecommendation["recommendations"][number];

export function copayCorrectionProcedureLabel(
  correction: CopayRateCorrectionRow,
): string {
  if (correction.name?.trim()) {
    return correction.code?.trim()
      ? `${correction.name} (${correction.code})`
      : correction.name;
  }
  if (correction.procedure?.trim()) {
    return correction.procedure;
  }
  if (correction.code?.trim()) {
    return correction.code;
  }
  return correction.detail?.trim() || "—";
}

export function copayCorrectionBilledTry(
  correction: CopayRateCorrectionRow,
): number | null {
  if (typeof correction.billed_try === "number") {
    return correction.billed_try;
  }
  if (typeof correction.gazette_rate === "number") {
    return correction.gazette_rate;
  }
  return null;
}

export function copayCorrectionPayableTry(
  correction: CopayRateCorrectionRow,
): number | null {
  if (typeof correction.payable_try === "number") {
    return correction.payable_try;
  }
  return null;
}

export function copayCorrectionSavingsTry(
  correction: CopayRateCorrectionRow,
): number | null {
  if (typeof correction.copay_component_try === "number") {
    return correction.copay_component_try;
  }
  if (typeof correction.correction_try === "number") {
    return correction.correction_try;
  }
  return null;
}

export function copayCorrectionIlaveTry(
  correction: CopayRateCorrectionRow,
): number | null {
  if (typeof correction.ilave_ucret_try === "number") {
    return correction.ilave_ucret_try;
  }
  return null;
}

export function copayCorrectedPayableTry(
  correction: CopayRateCorrectionRow,
): number | null {
  const billed = copayCorrectionBilledTry(correction);
  const payable = copayCorrectionPayableTry(correction);
  const copay = copayCorrectionSavingsTry(correction);

  if (billed != null) {
    return billed;
  }
  if (payable != null && copay != null) {
    return payable + copay;
  }
  return payable;
}

export type CopayIlaveStatusKind =
  | "numeric"
  | "drug_prohibited"
  | "cancer_exempt"
  | "emergency_exempt"
  | "unavailable";

export interface CopayIlaveStatus {
  kind: CopayIlaveStatusKind;
  amount?: number;
  labelKey: string;
  tooltipKey: string;
  /** Interpolation params ({coordinate}, {law}) composed from backend clause refs. */
  labelParams: { coordinate: string; law: string };
  /** Surcharge clause_key when resolvable — enables the clause drawer link. */
  clauseKey: string;
  clauseCoordinate: string;
}

const ILAVE_REASON_BY_STATUS: Record<
  string,
  Pick<CopayIlaveStatus, "kind" | "labelKey" | "tooltipKey">
> = {
  drug_prohibited: {
    kind: "drug_prohibited",
    labelKey: "billing.copay.ilaveReasons.drugProhibited",
    tooltipKey: "billing.copay.ilaveReasons.drugProhibitedTooltip",
  },
  cancer_exempt: {
    kind: "cancer_exempt",
    labelKey: "billing.copay.ilaveReasons.cancerExempt",
    tooltipKey: "billing.copay.ilaveReasons.cancerExemptTooltip",
  },
  emergency_exempt: {
    kind: "emergency_exempt",
    labelKey: "billing.copay.ilaveReasons.emergencyExempt",
    tooltipKey: "billing.copay.ilaveReasons.emergencyExemptTooltip",
  },
};

/**
 * Render the backend-decided ilave ücret (surcharge) outcome of a copay row.
 *
 * Primary path: the backend emits `ilave_ucret_status` together with the
 * governing §1.9 clause (`ilave_clause_ref`); the cite shown in the label and
 * tooltip is composed from that ref (coordinate + statutory law), never
 * hardcoded. Rows without a backend status keep the conservative fallback:
 * numeric passthrough or "—". The backend decides — no client heuristics.
 */
export function resolveCopayIlaveStatus(
  correction: CopayRateCorrectionRow,
): CopayIlaveStatus {
  const reason = ILAVE_REASON_BY_STATUS[correction.ilave_ucret_status ?? ""];
  if (reason) {
    const ref = correction.ilave_clause_ref ?? correction.clause_ref ?? null;
    const coordinate = (ref?.clause_coordinate ?? "").trim();
    return {
      kind: reason.kind,
      labelKey: reason.labelKey,
      tooltipKey: reason.tooltipKey,
      labelParams: {
        coordinate: coordinate ? `§${coordinate}` : "",
        law: (ref?.statutory_law ?? "").trim(),
      },
      clauseKey: (ref?.clause_key ?? "").trim(),
      clauseCoordinate: coordinate,
    };
  }

  const ilaveTry = copayCorrectionIlaveTry(correction);
  if (typeof ilaveTry === "number" && ilaveTry > 0) {
    return {
      kind: "numeric",
      amount: ilaveTry,
      labelKey: "",
      tooltipKey: "",
      labelParams: { coordinate: "", law: "" },
      clauseKey: "",
      clauseCoordinate: "",
    };
  }

  return {
    kind: "unavailable",
    labelKey: "common.unavailable",
    tooltipKey: "billing.copay.ilaveUcretFootnote",
    labelParams: { coordinate: "", law: "" },
    clauseKey: "",
    clauseCoordinate: "",
  };
}

export function copayExemptionGapTotal(copay: CopayOptimization): number {
  return (
    copay.patient_copay_waived_total_try ??
    copay.visit_copay_savings_try + copay.rx_copay_savings_try
  );
}

export function copayShowsIlaveColumn(copay: CopayOptimization): boolean {
  if (copay.line_decomposition_status !== "exact") {
    return false;
  }
  return (copay.ilave_ucret_total_try ?? 0) > 0 ||
    copay.rate_corrections.some((row) => (copayCorrectionIlaveTry(row) ?? 0) > 0);
}

export function copayCorrectionGroundKey(
  correction: CopayRateCorrectionRow,
): string | null {
  const ground = correction.exemption_ground?.trim();
  return ground || null;
}

/**
 * Annex chips for the claim-scoped copay table, derived from the backend
 * `clause_ref` on each rate-correction row: the annex when present, else the
 * clause coordinate. Deduped in first-seen (row) order — no hardcoded list.
 */
export function copayClaimScopedAnnexLabels(
  copay: CopayOptimization,
): string[] {
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const row of copay.rate_corrections) {
    const ref = row.clause_ref;
    if (!ref) {
      continue;
    }
    const annex = (ref.annex ?? "").trim();
    const coordinate = (ref.clause_coordinate ?? "").trim();
    const label = annex || (coordinate ? formatSutSectionLabel(coordinate) : "");
    if (!label || seen.has(label)) {
      continue;
    }
    seen.add(label);
    labels.push(label);
  }
  return labels;
}

export function usesClaimCopayCorrectionShape(
  correction: CopayRateCorrectionRow,
): boolean {
  return (
    typeof correction.copay_component_try === "number" ||
    typeof correction.billed_try === "number" ||
    Boolean(correction.code?.trim() && correction.name?.trim())
  );
}

export function usesInsightOnlyCopayCorrectionShape(
  correction: CopayRateCorrectionRow,
): boolean {
  return Boolean(correction.detail?.trim()) && !usesClaimCopayCorrectionShape(correction);
}

export function strategyPrimaryLabel(row: BillingStrategyRow): string {
  return row.claim_id?.trim() || row.chapter?.trim() || "—";
}

export function strategySecondaryLabel(row: BillingStrategyRow): string {
  if (row.detail?.trim()) {
    return translateApiText(row.detail);
  }
  if (row.chapter_description?.trim()) {
    return translateApiText(row.chapter_description);
  }
  return row.ek2c_group?.trim() || "";
}

export function strategyModeLabel(row: BillingStrategyRow): string {
  return row.recommendation?.trim() || row.strategy?.trim() || "unknown";
}

export function strategyPackageTotalTry(row: BillingStrategyRow): number | null {
  if (typeof row.package_total_try === "number") {
    return row.package_total_try;
  }
  if (typeof row.package_price === "number") {
    return row.package_price;
  }
  return null;
}

export function strategyItemizedTotalTry(row: BillingStrategyRow): number | null {
  if (typeof row.itemized_total_try === "number") {
    return row.itemized_total_try;
  }
  if (typeof row.itemized_estimate === "number") {
    return row.itemized_estimate;
  }
  return null;
}

export function usesClaimStrategyShape(row: BillingStrategyRow): boolean {
  return isClaimLevelStrategyRow(row);
}

export function isClaimLevelStrategyRow(row: BillingStrategyRow): boolean {
  return Boolean(
    row.claim_id?.trim() &&
      (row.recommendation === "package" || row.recommendation === "itemized") &&
      row.recommendation_kind,
  );
}

export function isComplianceViolationRow(row: BillingStrategyRow): boolean {
  return row.type === "compliance_violation";
}

export function formatSutSectionLabel(sectionId?: string): string {
  const trimmed = sectionId?.trim();
  if (!trimmed) {
    return "—";
  }
  return trimmed.startsWith("§") ? trimmed : `§${trimmed}`;
}

export function strategyBadgeColor(row: BillingStrategyRow): string {
  if (row.recommendation_kind === "optional_override") {
    return "#2563EB";
  }
  if (row.recommendation_kind === "mandatory_compliance") {
    return "#D97706";
  }
  return "#64748B";
}

export function strategySavingsTryDisplay(row: BillingStrategyRow): {
  amount: number | null;
  muted: boolean;
} {
  const savings = row.savings_try ?? null;
  if (
    row.recommendation_kind === "mandatory_compliance" &&
    (savings === 0 || savings === null)
  ) {
    return { amount: null, muted: true };
  }
  return { amount: savings, muted: false };
}

export function strategyPaymentMethodKindMessageKey(
  row: BillingStrategyRow,
): string | null {
  switch (row.payment_method_kind) {
    case "DRG_MANDATORY":
      return "billing.strategy.methodDrgMandatory";
    case "DRG_OVERRIDABLE":
      return "billing.strategy.methodDrgOverridable";
    case "ITEMIZED":
      return "billing.strategy.methodItemized";
    case "NOT_IN_SUT":
      return "billing.strategy.methodNotInSut";
    default:
      return null;
  }
}

export function strategyRecommendationKindMessageKey(
  row: BillingStrategyRow,
): string | null {
  switch (row.recommendation_kind) {
    case "mandatory_compliance":
      return "billing.strategy.kindMandatoryCompliance";
    case "optional_override":
      return "billing.strategy.kindOptionalOverride";
    default:
      return null;
  }
}

export function strategySavingsHeaderKey(rows: BillingStrategyRow[]): string {
  if (rows.some((row) => row.recommendation_kind === "optional_override")) {
    return "billing.strategy.optionalSavings";
  }
  if (rows.some((row) => row.recommendation_kind === "mandatory_compliance")) {
    return "billing.strategy.correctiveSavings";
  }
  return "billing.strategy.savings";
}

export function usesHeuristicStrategyReviewShape(row: BillingStrategyRow): boolean {
  return (
    row.recommendation === "review_package_eligibility" &&
    !usesClaimStrategyShape(row)
  );
}

export function strategyCatalogAsOfFootnote(rows: BillingStrategyRow[]): string | null {
  const dates = rows
    .map((row) => row.catalog_as_of_date?.trim())
    .filter((value): value is string => Boolean(value));
  if (!dates.length) {
    return null;
  }
  const unique = [...new Set(dates)].sort();
  return unique.join(", ");
}

/** UI status for the merged claim-level + violation strategy table. */
export type StrategyRowStatus = "violation" | "compliant" | "review";

export function strategyRowStatus(row: BillingStrategyRow): StrategyRowStatus {
  if (isComplianceViolationRow(row)) {
    return "violation";
  }
  const savings = strategySavingsTryDisplay(row);
  return savings.muted ? "compliant" : "review";
}

export function strategyRowStatusMessageKey(status: StrategyRowStatus): string {
  switch (status) {
    case "violation":
      return "billing.strategy.statusViolation";
    case "compliant":
      return "billing.strategy.statusCompliant";
    default:
      return "billing.strategy.statusReview";
  }
}

export function strategyRowStatusChipVariant(
  status: StrategyRowStatus,
): "danger" | "success" | "warning" {
  switch (status) {
    case "violation":
      return "danger";
    case "compliant":
      return "success";
    default:
      return "warning";
  }
}

/**
 * Merge claim-level strategy rows with compliance violations for one table.
 * Violations first; claim-level rows keep money columns.
 */
export function mergeClaimStrategyTableRows(
  claimLevelRows: BillingStrategyRow[],
  complianceViolations: BillingStrategyRow[],
): BillingStrategyRow[] {
  return [...complianceViolations, ...claimLevelRows];
}

