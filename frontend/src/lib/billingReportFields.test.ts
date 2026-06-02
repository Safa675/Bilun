import { describe, expect, it } from "vitest";
import {
  copayCorrectionProcedureLabel,
  formatSutSectionLabel,
  isClaimLevelStrategyRow,
  isComplianceViolationRow,
  strategyCatalogAsOfFootnote,
  strategySavingsTryDisplay,
  isHeuristicDrugRecommendation,
  usesHeuristicStrategyReviewShape,
  usesInsightOnlyCopayCorrectionShape,
} from "./billingReportFields";

describe("billingReportFields honest gaps", () => {
  it("treats detail-only copay rows as insight-only", () => {
    const correction = {
      detail: "EK-1A exemption may apply for Diabetes (E10-E14).",
    };

    expect(usesInsightOnlyCopayCorrectionShape(correction)).toBe(true);
    expect(copayCorrectionProcedureLabel(correction)).toContain("EK-1A exemption");
  });

  it("detects heuristic strategy review rows", () => {
    expect(
      usesHeuristicStrategyReviewShape({
        chapter: "I",
        recommendation: "review_package_eligibility",
        savings_try: null,
        detail: "Review package eligibility for chapter I.",
      }),
    ).toBe(true);
  });

  it("identifies claim-level SUT strategy rows", () => {
    const row = {
      claim_id: "CLM1",
      recommendation: "package" as const,
      recommendation_kind: "mandatory_compliance" as const,
      payment_method_kind: "DRG_MANDATORY" as const,
      sut_section_id: "2.2.2.(1)",
      package_total_try: 1000,
      itemized_total_try: 800,
      savings_try: 0,
    };
    expect(isClaimLevelStrategyRow(row)).toBe(true);
    expect(strategySavingsTryDisplay(row)).toEqual({ amount: null, muted: true });
    expect(formatSutSectionLabel("2.2.2.(1)")).toBe("§2.2.2.(1)");
  });

  it("shows optional override savings as non-muted", () => {
    const row = {
      claim_id: "CLM2",
      recommendation: "itemized" as const,
      recommendation_kind: "optional_override" as const,
      savings_try: 120,
    };
    expect(strategySavingsTryDisplay(row)).toEqual({ amount: 120, muted: false });
  });

  it("collects catalog as-of dates from claim strategy rows", () => {
    expect(
      strategyCatalogAsOfFootnote([
        { catalog_as_of_date: "2024-01-15", claim_id: "A" },
        { catalog_as_of_date: "2024-01-15", claim_id: "B" },
        { catalog_as_of_date: "2024-02-01", claim_id: "C" },
      ]),
    ).toBe("2024-01-15, 2024-02-01");
  });

  it("detects heuristic drug recommendations", () => {
    expect(
      isHeuristicDrugRecommendation({
        drug_name: "X",
        issue: "generic_available",
        alternative: "Y",
        savings_try: null,
        savings_basis: "heuristic",
      }),
    ).toBe(true);
    expect(
      isHeuristicDrugRecommendation({
        drug_name: "X",
        issue: "discount_tier_applied",
        alternative: "X",
        savings_try: 12,
        savings_basis: "claim_line",
      }),
    ).toBe(false);
  });

  it("detects compliance violation rows", () => {
    expect(
      isComplianceViolationRow({
        type: "compliance_violation",
        claim_id: "CLM1",
        procedure_code: "610070",
      }),
    ).toBe(true);
  });
});
