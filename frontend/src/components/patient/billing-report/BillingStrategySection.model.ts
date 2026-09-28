import type { BillingActionReport } from "@/lib/domains/sut";
import {
  isClaimLevelStrategyRow,
  isComplianceViolationRow,
  mergeClaimStrategyTableRows,
  strategyCatalogAsOfFootnote,
  strategySavingsHeaderKey,
  usesHeuristicStrategyReviewShape,
  type BillingStrategyRow,
} from "@/lib/billingReportFields";
import { isExactOutput } from "@/lib/sutExactness";

type BillingStrategySectionModel = { kind: "unavailable" } | { kind: "hidden" } | {
  kind: "content";
  strategyExact: boolean;
  heuristicRows: BillingStrategyRow[];
  claimLevelRows: BillingStrategyRow[];
  mergedClaimRows: BillingStrategyRow[];
  heuristicOnly: boolean;
  usesClaimTable: boolean;
  savingsHeaderKey: string;
  catalogAsOfFootnote: string | null;
};

export function buildBillingStrategySectionModel(
  strategyData: BillingActionReport["billing_strategy"],
): BillingStrategySectionModel {
  const strategyExact = isExactOutput(strategyData);
  const heuristicRows = strategyData.recommendations.filter((item) =>
    usesHeuristicStrategyReviewShape(item),
  );
  const claimLevelRows = strategyData.recommendations.filter(
    (item) => isClaimLevelStrategyRow(item) && item.recommendation_kind !== "optional_override",
  );
  const complianceViolations = strategyData.recommendations.filter((item) =>
    isComplianceViolationRow(item),
  );
  // These categories can overlap. Preserve each original membership and order.
  const mergedClaimRows = mergeClaimStrategyTableRows(claimLevelRows, complianceViolations);
  const hasRecommendations =
    heuristicRows.length > 0 || claimLevelRows.length > 0 || complianceViolations.length > 0;

  if (!hasRecommendations) {
    return { kind: strategyExact ? "hidden" : "unavailable" };
  }

  const usesClaimTable = mergedClaimRows.length > 0;
  return {
    kind: "content",
    strategyExact,
    heuristicRows,
    claimLevelRows,
    mergedClaimRows,
    heuristicOnly: heuristicRows.length > 0 && mergedClaimRows.length === 0,
    usesClaimTable,
    savingsHeaderKey: usesClaimTable ? strategySavingsHeaderKey(claimLevelRows) : "billing.strategy.savings",
    catalogAsOfFootnote: strategyCatalogAsOfFootnote(claimLevelRows),
  };
}
