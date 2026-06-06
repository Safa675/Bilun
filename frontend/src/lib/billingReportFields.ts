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
    return row.detail;
  }
  if (row.chapter_description?.trim()) {
    return row.chapter_description;
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

export function isProcedureMandateRow(row: BillingStrategyRow): boolean {
  return Boolean(row.procedure_code?.trim() && !row.recommendation_kind);
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

export function strategyPaymentMethodKindLabel(row: BillingStrategyRow): string {
  return row.payment_method_kind?.trim() || "—";
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

