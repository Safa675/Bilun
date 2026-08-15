import { describe, expect, it } from "vitest";
import {
  copayClaimScopedAnnexLabels,
  copayCorrectedPayableTry,
  copayCorrectionProcedureLabel,
  formatSutSectionLabel,
  isClaimLevelStrategyRow,
  isComplianceViolationRow,
  mergeClaimStrategyTableRows,
  resolveCopayIlaveStatus,
  strategyCatalogAsOfFootnote,
  strategyRowStatus,
  strategySavingsTryDisplay,
  usesHeuristicStrategyReviewShape,
  usesInsightOnlyCopayCorrectionShape,
} from "./billingReportFields";
import type { CopayOptimization } from "./domains/sut";

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

  it("detects compliance violation rows", () => {
    expect(
      isComplianceViolationRow({
        type: "compliance_violation",
        claim_id: "CLM1",
        procedure_code: "610070",
      }),
    ).toBe(true);
  });

  it("merges violations ahead of claim-level strategy rows", () => {
    const claim = {
      claim_id: "CLM1",
      recommendation: "package" as const,
      recommendation_kind: "mandatory_compliance" as const,
      savings_try: 0,
    };
    const violation = {
      type: "compliance_violation" as const,
      claim_id: "CLM1",
      procedure_code: "610070",
    };
    const merged = mergeClaimStrategyTableRows([claim], [violation]);
    expect(merged).toEqual([violation, claim]);
    expect(strategyRowStatus(violation)).toBe("violation");
    expect(strategyRowStatus(claim)).toBe("compliant");
  });

  it("calculates corrected full payable for copay rate corrections", () => {
    const row = {
      code: "A11925",
      billed_try: 111.55,
      payable_try: 80.32,
      copay_component_try: 31.24,
    };
    expect(copayCorrectedPayableTry(row)).toBe(111.55);

    const rowWithoutBilled = {
      payable_try: 80.32,
      copay_component_try: 31.24,
    };
    expect(copayCorrectedPayableTry(rowWithoutBilled)).toBeCloseTo(111.56, 1);
  });

  it("renders backend-decided ilave ucret reasons from clause refs", () => {
    // Drug (A11925 / inpatient): backend decides drug_prohibited + §1.9.1.
    const drugRow = {
      code: "A11925",
      name: "MONOVAS 5 MG",
      exemption_ground: "inpatient_drug_1_8_5_8",
      clause_ref: {
        clause_key: "1.8.5.(8)#abc123",
        clause_coordinate: "1.8.5.(8)",
        annex: "",
      },
      ilave_ucret_status: "drug_prohibited" as const,
      ilave_clause_ref: {
        clause_key: "1.9.1#52ade285",
        clause_coordinate: "1.9.1",
        statutory_law: "5510 Sayılı Kanun Madde 73",
      },
    };
    const statusDrug = resolveCopayIlaveStatus(drugRow);
    expect(statusDrug.kind).toBe("drug_prohibited");
    expect(statusDrug.labelKey).toBe("billing.copay.ilaveReasons.drugProhibited");
    expect(statusDrug.labelParams.coordinate).toBe("§1.9.1");
    expect(statusDrug.labelParams.law).toBe("5510 Sayılı Kanun Madde 73");
    expect(statusDrug.clauseKey).toBe("1.9.1#52ade285");

    // Cancer (C90 / Multiple Miyelom): backend decides cancer_exempt + §1.9.3.ç.
    const cancerRow = {
      code: "520010",
      name: "Muayene",
      exemption_ground: "ek1a_muayene",
      ilave_ucret_status: "cancer_exempt" as const,
      ilave_clause_ref: {
        clause_key: "1.9.3.ç#726ecd58",
        clause_coordinate: "1.9.3.ç",
      },
    };
    const statusCancer = resolveCopayIlaveStatus(cancerRow);
    expect(statusCancer.kind).toBe("cancer_exempt");
    expect(statusCancer.labelKey).toBe("billing.copay.ilaveReasons.cancerExempt");
    expect(statusCancer.labelParams.coordinate).toBe("§1.9.3.ç");
    expect(statusCancer.clauseKey).toBe("1.9.3.ç#726ecd58");

    // Emergency (composite_acil_servis): backend decides emergency_exempt + §1.9.3.a.
    const emergencyRow = {
      code: "520030",
      name: "Acil",
      exemption_ground: "composite_acil_servis",
      ilave_ucret_status: "emergency_exempt" as const,
      ilave_clause_ref: {
        clause_key: "1.9.3.a#67236cf6",
        clause_coordinate: "1.9.3.a",
      },
    };
    const statusEmergency = resolveCopayIlaveStatus(emergencyRow);
    expect(statusEmergency.kind).toBe("emergency_exempt");
    expect(statusEmergency.labelKey).toBe("billing.copay.ilaveReasons.emergencyExempt");
    expect(statusEmergency.labelParams.coordinate).toBe("§1.9.3.a");
    expect(statusEmergency.clauseKey).toBe("1.9.3.a#67236cf6");
  });

  it("falls back to numeric passthrough or unavailable without backend status", () => {
    // No ilave_ucret_status + positive ilave → numeric passthrough.
    const numericRow = {
      code: "610010",
      ilave_ucret_try: 150.0,
    };
    const statusNumeric = resolveCopayIlaveStatus(numericRow);
    expect(statusNumeric.kind).toBe("numeric");
    expect(statusNumeric.amount).toBe(150.0);
    expect(statusNumeric.clauseKey).toBe("");

    // No ilave_ucret_status + no ilave → unavailable, no drawer link.
    const bareRow = { code: "610020" };
    const statusBare = resolveCopayIlaveStatus(bareRow);
    expect(statusBare.kind).toBe("unavailable");
    expect(statusBare.labelKey).toBe("common.unavailable");
    expect(statusBare.clauseKey).toBe("");

    // Status present but non-exempt ("none" / "applicable") → still falls back.
    const noneRow = { code: "610030", ilave_ucret_status: "none" as const };
    expect(resolveCopayIlaveStatus(noneRow).kind).toBe("unavailable");
    const applicableRow = {
      code: "610040",
      ilave_ucret_status: "applicable" as const,
      ilave_ucret_try: 12.5,
    };
    const statusApplicable = resolveCopayIlaveStatus(applicableRow);
    expect(statusApplicable.kind).toBe("numeric");
    expect(statusApplicable.amount).toBe(12.5);
  });

  it("degrades to plain text when the clause_ref has an empty clause_key", () => {
    const unresolvedRow = {
      code: "520010",
      exemption_ground: "ek1a_muayene",
      ilave_ucret_status: "cancer_exempt" as const,
      ilave_clause_ref: {
        clause_key: "",
        clause_coordinate: "1.9.3.ç",
      },
    };
    const status = resolveCopayIlaveStatus(unresolvedRow);
    expect(status.kind).toBe("cancer_exempt");
    expect(status.labelKey).toBe("billing.copay.ilaveReasons.cancerExempt");
    // Coordinate still composes the cite, but no drawer link is possible.
    expect(status.labelParams.coordinate).toBe("§1.9.3.ç");
    expect(status.clauseKey).toBe("");
  });

  it("derives claim-scoped annex labels from clause_ref annex/coordinate", () => {
    const copay = {
      rate_corrections: [
        {
          exemption_ground: "ek1a_muayene",
          clause_ref: { clause_key: "k1", clause_coordinate: "1.8.5.(7)", annex: "EK-1/A" },
        },
        {
          exemption_ground: "inpatient_drug_1_8_5_8",
          clause_ref: { clause_key: "k2", clause_coordinate: "1.8.5.(8)", annex: "" },
        },
        {
          exemption_ground: "ek4d_drug",
          clause_ref: { clause_key: "k3", clause_coordinate: "1.8.2.(3)", annex: "EK-4/D" },
        },
        // Duplicate annex dedupes; missing clause_ref is skipped.
        {
          exemption_ground: "ek1a_muayene",
          clause_ref: { clause_key: "k1", clause_coordinate: "1.8.5.(7)", annex: "EK-1/A" },
        },
        { exemption_ground: "no_ref" },
      ],
    } as unknown as CopayOptimization;

    expect(copayClaimScopedAnnexLabels(copay)).toEqual([
      "EK-1/A",
      "§1.8.5.(8)",
      "EK-4/D",
    ]);
  });
});