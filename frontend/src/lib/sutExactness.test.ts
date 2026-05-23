import { describe, expect, it } from "vitest";
import { formatRequiredInputs, getUnavailableMessage, hasRecoverableBillingTotals, isExactOutput } from "./sutExactness";

describe("sutExactness helpers", () => {
  it("requires explicit exactness metadata before treating a block as exact", () => {
    expect(isExactOutput({})).toBe(false);
    expect(isExactOutput(undefined)).toBe(false);
    expect(isExactOutput({ exactness_status: "exact" })).toBe(true);
    expect(isExactOutput({ pricing_status: "exact" })).toBe(true);
    expect(isExactOutput({ exactness_status: "missing_exact_inputs" })).toBe(false);
    expect(isExactOutput({ pricing_status: "unknown_date" })).toBe(false);
  });

  it("treats partial exact reports as having recoverable totals", () => {
    expect(hasRecoverableBillingTotals({ exactness_status: "partial_exact" })).toBe(true);
    expect(hasRecoverableBillingTotals({ exactness_status: "missing_exact_inputs" })).toBe(
      false,
    );
  });

  it("formats required input identifiers into readable labels", () => {
    expect(formatRequiredInputs(["billed_procedure_codes", "procedure_dates"])).toBe(
      "billed procedure codes, procedure dates",
    );
  });

  it("hides schema placeholder exactness_status from missing-input labels", () => {
    expect(formatRequiredInputs(["exactness_status", "claim_lines"])).toBe("claim lines");
  });

  it("builds a combined unavailable message from reason and missing inputs", () => {
    expect(
      getUnavailableMessage(
        {
          unavailable_reason: "Needs exact claim lines.",
          required_inputs_missing: ["itemized_billed_procedure_lines"],
        },
        "fallback",
      ),
    ).toBe(
      "Needs exact claim lines. Missing exact inputs: itemized billed procedure lines.",
    );
  });
});
