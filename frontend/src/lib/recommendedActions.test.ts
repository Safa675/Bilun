import { describe, expect, it } from "vitest";
import {
  getRecommendedActions,
  recommendedActionTitle,
} from "@/lib/recommendedActions";
import type { BillingActionReport } from "@/lib/domains/sut";

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
});
