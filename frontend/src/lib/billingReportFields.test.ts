import { describe, expect, it } from "vitest";
import {
  copayCorrectionBilledTry,
  copayCorrectionPayableTry,
  copayCorrectionProcedureLabel,
  copayCorrectionSavingsTry,
  strategyItemizedTotalTry,
  strategyModeLabel,
  strategyPackageTotalTry,
  strategyPrimaryLabel,
  usesClaimCopayCorrectionShape,
  usesClaimStrategyShape,
} from "./billingReportFields";

describe("billingReportFields", () => {
  it("maps claim-based copay correction rows", () => {
    const row = {
      code: "700670",
      name: "Kalıcı kalp pili takılması",
      billed_try: 3861.96,
      payable_try: 2510.28,
      copay_component_try: 1351.68,
    };

    expect(usesClaimCopayCorrectionShape(row)).toBe(true);
    expect(copayCorrectionProcedureLabel(row)).toBe(
      "Kalıcı kalp pili takılması (700670)",
    );
    expect(copayCorrectionBilledTry(row)).toBe(3861.96);
    expect(copayCorrectionPayableTry(row)).toBe(2510.28);
    expect(copayCorrectionSavingsTry(row)).toBe(1351.68);
  });

  it("maps claim-based billing strategy rows", () => {
    const row = {
      claim_id: "F-SENTETIK-HASTA-0001-003",
      recommendation: "itemized" as const,
      package_total_try: 15428.95,
      itemized_total_try: 609.74,
      savings_try: 14819.21,
      detail: "Itemized billing yields higher recovery.",
    };

    expect(usesClaimStrategyShape(row)).toBe(true);
    expect(strategyPrimaryLabel(row)).toBe("F-SENTETIK-HASTA-0001-003");
    expect(strategyModeLabel(row)).toBe("itemized");
    expect(strategyPackageTotalTry(row)).toBe(15428.95);
    expect(strategyItemizedTotalTry(row)).toBe(609.74);
  });
});
