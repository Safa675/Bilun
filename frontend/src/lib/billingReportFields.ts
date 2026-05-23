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
  return correction.procedure?.trim() || correction.code?.trim() || "—";
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
    Boolean(correction.code?.trim())
  );
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
  return Boolean(row.claim_id?.trim()) || typeof row.package_total_try === "number";
}
