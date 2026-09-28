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
import { isExactOutput } from "@/lib/sutExactness";

type CopaySectionModel = { kind: "unavailable" } | {
  kind: "content";
  copayExact: boolean;
  exemptionGapTotal: number;
  showIlaveColumn: boolean;
  ilaveTotal: number;
  copayOnlyDecomposition: boolean;
  insightOnlyRows: CopayRateCorrectionRow[];
  claimRows: CopayRateCorrectionRow[];
  claimScopedChips: string[];
  hasWaiverGroundColumn: boolean;
  inpatientDrugGroundTotal: number;
  hasEk1aVisitSavings: boolean;
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

  return {
    kind: "content",
    copayExact,
    exemptionGapTotal: copayExemptionGapTotal(copayData),
    showIlaveColumn: copayShowsIlaveColumn(copayData),
    ilaveTotal: copayData.ilave_ucret_total_try ?? 0,
    copayOnlyDecomposition: copayData.line_decomposition_status === "copay_only",
    insightOnlyRows,
    claimRows,
    claimScopedChips: copayClaimScopedAnnexLabels(copayData),
    hasWaiverGroundColumn: claimRows.some((row) => Boolean(copayCorrectionGroundKey(row))),
    inpatientDrugGroundTotal: copayData.rx_copay_savings_by_ground?.inpatient_drug_1_8_5_8 ?? 0,
    hasEk1aVisitSavings: copayData.rate_corrections.some(
      (row) => row.exemption_ground === "ek1a_muayene" && (row.copay_component_try ?? 0) > 0,
    ),
    // Legacy and claim rows can coexist; only the first row chooses the header.
    usesClaimTableHeader: claimRows.length > 0 && usesClaimCopayCorrectionShape(claimRows[0]),
  };
}
