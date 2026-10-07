import { describe, expect, it } from "vitest";
import type { BillingActionReport } from "@/lib/domains/sut";
import {
  claimComplianceFindingIdentity,
  isClaimComplianceFindingSelected,
  complianceBilledAtRisk,
  complianceBilledAtRiskSummary,
  amountCoverage,
  recoverableUplift,
  sumKnownAmounts,
  scopedClaimComplianceFindings,
  viewActions,
  viewForSection,
} from "@/lib/workspaceViews";

const report = {
  patient_id: "P-VIEWS",
  total_recoverable_try: 23192.18,
  sgk_uplift_try: 23192.18,
  recommended_actions: [
    {
      action_id: "a1",
      surface: "materials",
      kind: "material_pre_auth",
      finding_type: "compliance",
      billed_try: 100,
    },
    {
      action_id: "a2",
      surface: "drug_indication",
      kind: "drug_indication",
      finding_type: "compliance",
      billed_try: 40,
    },
    {
      action_id: "a3",
      surface: "yatak_puani",
      kind: "yatak_puani_standard_bed",
      finding_type: "opportunity",
      sgk_uplift_try: 50,
    },
    {
      action_id: "a4",
      surface: "billing_strategy",
      kind: "optional_override",
      finding_type: "opportunity",
      sgk_uplift_try: 10,
    },
    {
      action_id: "a5",
      surface: "claim_checklist",
      kind: "documentation_requirement",
      finding_type: "informational",
    },
    {
      action_id: "a6",
      surface: "medula_playbook",
      kind: "medula_rejection",
      finding_type: "informational",
    },
  ],
} as unknown as BillingActionReport;

describe("workspaceViews", () => {
  it("maps billing section anchors to their owning view", () => {
    expect(viewForSection("billing-lab")).toBe("compliance");
    expect(viewForSection("materials-pre-check")).toBe("compliance");
    expect(viewForSection("drug-indication")).toBe("compliance");
    expect(viewForSection("wavea-reviews")).toBe("compliance");
    expect(viewForSection("wavea-advisories")).toBe("compliance");
    expect(viewForSection("billing-copay")).toBe("revenue");
    expect(viewForSection("billing-session-uplift")).toBe("revenue");
    expect(viewForSection("wavea-financial")).toBe("revenue");
    expect(viewForSection("claim-submission-checklist")).toBe("audit");
    expect(viewForSection("medula-playbook")).toBe("audit");
    expect(viewForSection("unknown-section")).toBeNull();
    expect(viewForSection(null)).toBeNull();
  });

  it("buckets actions by the getFindingType classification", () => {
    const compliance = viewActions(report, "compliance");
    const revenue = viewActions(report, "revenue");
    const audit = viewActions(report, "audit");

    expect(compliance.map((a) => a.action_id)).toEqual(["a1", "a2"]);
    expect(revenue.map((a) => a.action_id)).toEqual(["a3", "a4"]);
    expect(audit.map((a) => a.action_id)).toEqual(["a5", "a6"]);
  });

  it("sums billed-at-risk amounts for the compliance view", () => {
    expect(complianceBilledAtRisk(report)).toBe(100);
    expect(complianceBilledAtRiskSummary(report)).toEqual({ total: 100, known: 1, count: 1 });
  });

  describe("billed-at-risk with missing billed amounts", () => {
    const withActions = (
      actions: Array<Record<string, unknown>>,
    ): BillingActionReport =>
      ({
        patient_id: "P-NULLS",
        recommended_actions: actions.map((action, index) => ({
          action_id: `n${index}`,
          surface: "materials",
          kind: "material_pre_auth",
          finding_type: "compliance",
          ...action,
        })),
      }) as unknown as BillingActionReport;

    it("is a complete exact sum when every counted action has a billed amount", () => {
      const complete = withActions([{ billed_try: 192.32 }, { billed_try: 192.32 }]);
      expect(complianceBilledAtRiskSummary(complete)).toEqual({
        total: 384.64,
        known: 2,
        count: 2,
      });
      expect(complianceBilledAtRisk(complete)).toBe(384.64);
    });

    it("keeps an explicit zero billed amount as a known amount", () => {
      const zero = withActions([{ billed_try: 0 }, { billed_try: 25 }]);
      expect(complianceBilledAtRiskSummary(zero)).toEqual({ total: 25, known: 2, count: 2 });
      expect(complianceBilledAtRisk(zero)).toBe(25);
    });

    it("reports a partial sum, never a bare total, when one amount is missing", () => {
      const partial = withActions([{ billed_try: 100 }, { billed_try: null }]);
      expect(complianceBilledAtRiskSummary(partial)).toEqual({ total: 100, known: 1, count: 2 });
      expect(complianceBilledAtRisk(partial)).toBeNull();
    });

    it("treats an absent billed_try the same as null", () => {
      const absent = withActions([{ billed_try: 100 }, {}]);
      expect(complianceBilledAtRiskSummary(absent)).toEqual({ total: 100, known: 1, count: 2 });
      expect(complianceBilledAtRisk(absent)).toBeNull();
    });

    it("has no known amount when every counted action is missing one", () => {
      const none = withActions([
        { billed_try: null },
        { billed_try: null },
        { billed_try: null },
      ]);
      expect(complianceBilledAtRiskSummary(none)).toEqual({ total: 0, known: 0, count: 3 });
      expect(complianceBilledAtRisk(none)).toBeNull();
    });

    it("keeps excluding drug_indication actions from the total and from the coverage counts", () => {
      const drugOnlyMissing = withActions([
        { billed_try: 100 },
        { surface: "drug_indication", kind: "drug_indication", billed_try: null },
      ]);
      expect(complianceBilledAtRiskSummary(drugOnlyMissing)).toEqual({
        total: 100,
        known: 1,
        count: 1,
      });
      expect(complianceBilledAtRisk(drugOnlyMissing)).toBe(100);

      const drugWithAmount = withActions([
        { billed_try: 100 },
        { surface: "drug_indication", kind: "drug_indication", billed_try: 40 },
      ]);
      expect(complianceBilledAtRiskSummary(drugWithAmount)).toEqual({
        total: 100,
        known: 1,
        count: 1,
      });
    });

    it("ignores non-compliance actions that lack a billed amount", () => {
      const mixed = withActions([
        { billed_try: 100 },
        { finding_type: "opportunity", surface: "yatak_puani", kind: "yatak_puani_standard_bed" },
      ]);
      expect(complianceBilledAtRiskSummary(mixed)).toEqual({ total: 100, known: 1, count: 1 });
      expect(complianceBilledAtRisk(mixed)).toBe(100);
    });
  });

  it("keeps generic claim-compliance findings scoped and keyed by canonical identity", () => {
    const claimReport = {
      patient_id: "P-VIEWS",
      claim_id: "C-VIEWS",
      claim_compliance: {
        findings: [
          {
            finding_id: "canonical-wave-a",
            action_id: "legacy-alias",
            patient_id: "P-VIEWS",
            claim_id: "C-VIEWS",
            rule_id: "future_rule_without_frontend_registration",
            line_kind: "material",
            line_id: "M-1",
          },
          {
            finding_id: "foreign-claim",
            action_id: "foreign-alias",
            patient_id: "P-VIEWS",
            claim_id: "OTHER-CLAIM",
            rule_id: "future_rule_without_frontend_registration",
            line_kind: "material",
            line_id: "M-2",
          },
        ],
      },
    } as unknown as BillingActionReport;

    const findings = scopedClaimComplianceFindings(claimReport);
    expect(findings).toHaveLength(1);
    expect(claimComplianceFindingIdentity(findings[0])).toBe("canonical-wave-a");
  });

  it("matches canonical finding ids and safely ignores an unknown deep-link id", () => {
    const row = {
      finding_id: "canonical-wave-a",
      action_id: "legacy-alias",
    };

    expect(isClaimComplianceFindingSelected(row, "canonical-wave-a")).toBe(true);
    expect(isClaimComplianceFindingSelected(row, "unknown-finding")).toBe(false);
    expect(isClaimComplianceFindingSelected(row, null)).toBe(false);
  });

  it("prefers sgk_uplift_try and falls back to total_recoverable_try", () => {
    expect(recoverableUplift(report)).toBe(23192.18);
    expect(
      recoverableUplift({
        ...report,
        sgk_uplift_try: undefined,
      } as unknown as BillingActionReport),
    ).toBe(23192.18);
    expect(
      recoverableUplift({
        ...report,
        sgk_uplift_try: undefined,
        total_recoverable_try: 0,
      } as unknown as BillingActionReport),
    ).toBe(0);
  });
});

describe("sumKnownAmounts / amountCoverage", () => {
  it("sums every amount when none is missing", () => {
    const sum = sumKnownAmounts([100, 50.5, 0]);
    expect(sum).toEqual({ total: 150.5, known: 3, count: 3 });
    expect(amountCoverage(sum)).toBe("complete");
  });

  it("sums only the known amounts and reports a partial coverage when one is missing", () => {
    const sum = sumKnownAmounts([100, null, undefined, 25]);
    expect(sum).toEqual({ total: 125, known: 2, count: 4 });
    expect(amountCoverage(sum)).toBe("partial");
  });

  it("reports none, not a zero total, when every amount is missing", () => {
    const sum = sumKnownAmounts([null, undefined]);
    expect(sum).toEqual({ total: 0, known: 0, count: 2 });
    expect(amountCoverage(sum)).toBe("none");
  });

  it("treats an empty list as complete (nothing to sum)", () => {
    const sum = sumKnownAmounts([]);
    expect(sum).toEqual({ total: 0, known: 0, count: 0 });
    expect(amountCoverage(sum)).toBe("complete");
  });

  it("keeps a real zero amount known", () => {
    expect(amountCoverage(sumKnownAmounts([0, 0]))).toBe("complete");
  });
});
