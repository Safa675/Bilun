import type { BillingActionReport } from "@/lib/domains/sut";
import {
  copayClaimScopedAnnexLabels,
  copayCorrectionGroundKey,
  copayExemptionGapTotal,
  copayShowsIlaveColumn,
  usesClaimCopayCorrectionShape,
  usesInsightOnlyCopayCorrectionShape,
  type CopayRateCorrectionRow,
} from "@/lib/billingReportFields";
import { getCopayExemptionState, type CopayExemptionState } from "@/lib/copayExemption";
import { isExactOutput } from "@/lib/sutExactness";

type CopaySectionModel = { kind: "unavailable" } | {
  kind: "content";
  copayExact: boolean;
  exemptionGapTotal: number | null;
  showIlaveColumn: boolean;
  ilaveTotal: number | null;
  copayOnlyDecomposition: boolean;
  insightOnlyRows: CopayRateCorrectionRow[];
  claimRows: CopayRateCorrectionRow[];
  claimScopedChips: string[];
  hasWaiverGroundColumn: boolean;
  inpatientDrugGroundTotal: number;
  hasEk1aVisitSavings: boolean;
  /** Exempt on EK-1A alone, but no line of this bill is an outpatient exam it waives. */
  ek1aWithoutWaivableLine: boolean;
  copayState: CopayExemptionState;
  usesClaimTableHeader: boolean;
};

export function buildCopaySectionModel(
  copayData: BillingActionReport["copay"],
): CopaySectionModel {
  const copayExact = isExactOutput(copayData);
  const hasInsight =
    copayData.is_exempt ||
    copayData.rate_corrections.some(
      (correction) =>
        usesClaimCopayCorrectionShape(correction) ||
        usesInsightOnlyCopayCorrectionShape(correction),
    );

  if (!copayExact && !hasInsight) {
    return { kind: "unavailable" };
  }

  const insightOnlyRows = copayData.rate_corrections.filter((correction) =>
    usesInsightOnlyCopayCorrectionShape(correction),
  );
  const claimRows = copayData.rate_corrections.filter(
    (correction) => !usesInsightOnlyCopayCorrectionShape(correction),
  );
  const hasEk1aVisitSavings = copayData.rate_corrections.some(
    (row) => row.exemption_ground === "ek1a_muayene" && (row.copay_component_try ?? 0) > 0,
  );
  const countingGrounds = (copayData.exemption_sources ?? [])
    .filter((source) => source.counts_toward_exempt !== false)
    .map((source) => source.category);
  const ek1aOnlyExempt =
    copayData.is_exempt &&
    countingGrounds.length > 0 &&
    countingGrounds.every((category) => category === "ek1a_chronic");

  return {
    kind: "content",
    copayExact,
    exemptionGapTotal: copayExemptionGapTotal(copayData),
    showIlaveColumn: copayShowsIlaveColumn(copayData),
    ilaveTotal: copayData.ilave_ucret_total_try ?? null,
    copayOnlyDecomposition: copayData.line_decomposition_status === "copay_only",
    insightOnlyRows,
    claimRows,
    claimScopedChips: copayClaimScopedAnnexLabels(copayData),
    hasWaiverGroundColumn: claimRows.some((row) => Boolean(copayCorrectionGroundKey(row))),
    inpatientDrugGroundTotal: copayData.rx_copay_savings_by_ground?.inpatient_drug_1_8_5_8 ?? 0,
    hasEk1aVisitSavings,
    ek1aWithoutWaivableLine: ek1aOnlyExempt && !hasEk1aVisitSavings,
    copayState: getCopayExemptionState({
      exempt: copayData.is_exempt,
      partial_exempt: copayData.copay_primary_outcome === "partial_exempt",
      exemption_sources: copayData.exemption_sources,
    }),
    // Legacy and claim rows can coexist; only the first row chooses the header.
    usesClaimTableHeader: claimRows.length > 0 && usesClaimCopayCorrectionShape(claimRows[0]),
  };
}
