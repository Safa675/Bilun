import { describe, expect, it } from "vitest";
import type { BillingActionReport } from "@/lib/domains/sut";
import {
  claimComplianceFindingIdentity,
  isClaimComplianceFindingSelected,
  complianceBilledAtRisk,
  recoverableUplift,
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
