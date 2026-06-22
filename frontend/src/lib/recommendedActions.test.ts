import { describe, expect, it } from "vitest";
import {
  getRecommendedActions,
  recommendedActionAmountParts,
  recommendedActionTitle,
} from "@/lib/recommendedActions";
import type { BillingActionReport, RecommendedActionItem } from "@/lib/domains/sut";

const t = (key: string, params?: Record<string, string | number>) => {
  if (params) {
    return `${key}:${JSON.stringify(params)}`;
  }
  return key;
};

describe("recommendedActions", () => {
  it("uses API recommended_actions when present", () => {
    const report = {
      recommended_actions: [
        {
          action_id: "copay:ek1a",
          surface: "copay",
          kind: "exemption_review",
        },
      ],
    } as BillingActionReport;

    expect(getRecommendedActions(report)).toHaveLength(1);
  });

  it("falls back to strategy and copay rows", () => {
    const report = {
      copay: {
        is_exempt: true,
        exemption_disease: "Endokrin",
      },
      billing_strategy: {
        recommendations: [
          {
            type: "compliance_violation",
            claim_id: "F-1",
            procedure_code: "608870",
            procedure_name: "Torakotomi",
            detail: "must use package",
          },
          {
            type: "informational",
            procedure_code: "703270",
          },
        ],
      },
    } as BillingActionReport;

    const actions = getRecommendedActions(report);
    expect(actions).toHaveLength(2);
    expect(actions.map((row) => row.kind)).toEqual([
      "exemption_review",
      "compliance_violation",
    ]);
    expect(
      recommendedActionTitle(t, actions[1]!),
    ).toContain("608870");
  });

  it("renders material rows with billed amount and material name title", () => {
    const action: RecommendedActionItem = {
      action_id: "materials:material_pre_auth:F-1:0",
      surface: "materials",
      kind: "material_pre_auth",
      material_code: "OP1198",
      material_name: "Ortez",
      billed_try: 1250,
      detail: "Pre-auth required",
      sut_section_id: "3.1.2",
    };

    expect(recommendedActionTitle(t, action)).toContain("OP1198");
    expect(recommendedActionTitle(t, action)).toContain("Ortez");

    const amount = recommendedActionAmountParts(t, action);
    expect(amount?.label).toBe("billing.recommendedActions.amountBilledAtRisk");
    expect(amount?.value).toBe(1250);
  });
});
