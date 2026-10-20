import { describe, expect, it } from "vitest";
import type { BillingActionReport } from "@/lib/domains/sut";
import type { TranslateFn } from "./complianceFindings";
import { buildComplianceCoverage } from "./complianceCoverage";

// Echo the key and its parameters, so the test pins which sentence is chosen.
const t: TranslateFn = (key, params) =>
  params ? `${key}${JSON.stringify(params)}` : key;

const off = { available: false, unavailable_reason: "wavea_capability_unavailable", total_rows: null, rows: [], has_more: false };

function report(overrides: Record<string, unknown>, statuses: string[], findings: unknown[] = []): BillingActionReport {
  return {
    patient_id: "P-1",
    claim_compliance: {
      findings,
      evaluations: statuses.map((status, index) => ({
        patient_id: "P-1", claim_id: "C-1", rule_id: `rule_${index}`, status, missing_inputs: [],
      })),
    },
    ...overrides,
  } as unknown as BillingActionReport;
}

describe("buildComplianceCoverage", () => {
  it("says what ran, with no missing-data wording, when every evaluation ran", () => {
    const coverage = buildComplianceCoverage(report({}, Array(5).fill("evaluated")), t)!;
    expect(coverage.summaryText).toBe('billing.views.compliance.coverageAllRan{"count":5,"findings":0}');
    expect(coverage.checkCount).toBe(5);
    expect(coverage.nonEvaluatedTotal).toBe(0);
    expect(coverage.extendedLayerOff).toBe(false);
  });

  it("counts checks as distinct rules, not as rule-by-claim evaluations", () => {
    const twoClaims = report({}, []);
    twoClaims.claim_compliance!.evaluations = ["C-1", "C-2"].flatMap((claim_id) =>
      ["a", "b", "c"].map((rule_id) => ({
        patient_id: "P-1", claim_id, rule_id, status: "evaluated", missing_inputs: [],
      })),
    ) as never;
    expect(buildComplianceCoverage(twoClaims, t)!.checkCount).toBe(3);
  });

  it("names the findings when the checks raised some", () => {
    const finding = { patient_id: "P-1", claim_id: "C-1", rule_id: "rule_0" };
    const coverage = buildComplianceCoverage(report({}, ["evaluated", "evaluated"], [finding]), t)!;
    expect(coverage.summaryText).toBe('billing.views.compliance.coverageAllRanFindings{"count":2,"findings":1}');
  });

  it("keeps the gap wording only when something is missing or unavailable", () => {
    const coverage = buildComplianceCoverage(report({}, ["evaluated", "missing_inputs", "unavailable"]), t)!;
    expect(coverage.summaryText).toBe(
      'billing.views.compliance.coverageSummary{"evaluated":1,"findings":0}' +
      'billing.views.compliance.coverageMissing{"count":1}' +
      'billing.views.compliance.coverageUnavailable{"count":1}',
    );
    expect(coverage.nonEvaluatedTotal).toBe(2);
  });

  it("never reports an empty evaluation list as everything having run", () => {
    const coverage = buildComplianceCoverage(report({}, []), t)!;
    expect(coverage.summaryText).toBe("billing.views.compliance.coverageNoneRan");
  });

  it("flags the extended layer as off only when all three evidence blocks say so", () => {
    const allOff = { claim_reviews: off, claim_advisories: off, financial_findings: off };
    expect(buildComplianceCoverage(report(allOff, ["evaluated"]), t)!.extendedLayerOff).toBe(true);
    expect(buildComplianceCoverage(report({ ...allOff, financial_findings: undefined }, ["evaluated"]), t)!.extendedLayerOff).toBe(false);
  });

  it("returns null without a claim-compliance projection", () => {
    expect(buildComplianceCoverage({ patient_id: "P-1" } as unknown as BillingActionReport, t)).toBeNull();
  });
});
