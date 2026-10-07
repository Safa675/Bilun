import { describe, expect, it } from "vitest";
import { formatRequiredInputs, getExactnessDescription, getUnavailableMessage, hasRecoverableBillingTotals, isExactOutput } from "./sutExactness";

describe("sutExactness helpers", () => {
  it("explains exact, partial, not applicable and unavailable without changing status", () => {
    const t = (key: string) => key;
    expect(getExactnessDescription({ exactness_status: "exact" }, t)).toBe("billing.glossary.exact");
    expect(getExactnessDescription({ pricing_status: "partial_exact" }, t)).toBe("billing.glossary.partial");
    expect(getExactnessDescription({ exactness_status: "not_applicable" }, t)).toBe("billing.glossary.notApplicable");
    expect(getExactnessDescription({ exactness_status: "unknown_date" }, t)).toBe("billing.glossary.unavailable");
    expect(getExactnessDescription(undefined, t)).toBe("billing.glossary.unavailable");
  });
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

  it("treats uplift totals as recoverable even when report exactness is blocked", () => {
    expect(
      hasRecoverableBillingTotals({
        exactness_status: "missing_exact_inputs",
        sgk_uplift_try: 7634.02,
      }),
    ).toBe(true);
    expect(
      hasRecoverableBillingTotals({
        exactness_status: "missing_exact_inputs",
        recommended_actions: [{ action_id: "x" }],
      }),
    ).toBe(true);
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
