import { describe, expect, it } from "vitest";
import {
  copayCorrectionProcedureLabel,
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
});
