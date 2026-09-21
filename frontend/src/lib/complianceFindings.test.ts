import { describe, expect, it } from "vitest";
import type { BillingActionReport } from "@/lib/domains/sut";
import {
  buildUnifiedComplianceFindings,
  type UnifiedComplianceFindingRow,
} from "./complianceFindings";

describe("buildUnifiedComplianceFindings", () => {
  it("projects four compliance actions and zero canonical findings into four rows", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [
        { action_id: "a1", surface: "materials", kind: "material_pre_auth", finding_type: "compliance", billed_try: 120 },
        { action_id: "a2", surface: "materials", kind: "material_miat", finding_type: "compliance", billed_try: 80 },
        { action_id: "a3", surface: "lab", kind: "hemogram_unbundling", finding_type: "compliance", compliance_savings_try: 45 },
        { action_id: "a4", surface: "billing_strategy", kind: "mandatory_compliance", finding_type: "compliance" },
      ],
      claim_compliance: {
        findings: [],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(4);
    expect(rows.map((r) => r.rowId)).toEqual([
      "action:a1",
      "action:a2",
      "action:a3",
      "action:a4",
    ]);
    expect(rows.every((r) => r.sourceKind === "recommended_action")).toBe(true);
  });

  it("classifies canonical finding with status 'violation' as confirmed_violation", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [],
      claim_compliance: {
        findings: [
          {
            finding_id: "canonical-viol-1",
            patient_id: "P-1",
            rule_id: "tablo15_8_missing_diagnosis",
            status: "violation",
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe("confirmed_violation");
    expect(rows[0].sourceKind).toBe("claim_compliance");
    expect(rows[0].canonicalFindingId).toBe("canonical-viol-1");
  });

  it("classifies generic compliance action as review_risk", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "act-generic",
          surface: "materials",
          kind: "material_pre_auth",
          finding_type: "compliance",
          billed_try: 250,
        },
      ],
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe("review_risk");
  });

  it("classifies action with kind 'compliance_violation' as confirmed_violation", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "act-viol",
          surface: "billing_strategy",
          kind: "compliance_violation",
          finding_type: "compliance",
        },
      ],
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe("confirmed_violation");
  });

  it("classifies drug indication action as confirmed_violation only when matching finding_id exists in drug_indication.violations", () => {
    const reportWithViolation = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "act-drug-1",
          finding_id: "drug-viol-1",
          surface: "drug_indication",
          kind: "drug_indication",
          finding_type: "compliance",
        },
      ],
      drug_indication: {
        violations: [
          { finding_id: "drug-viol-1", drug_code: "D-100" },
        ],
      },
    } as unknown as BillingActionReport;

    const rowsViol = buildUnifiedComplianceFindings(reportWithViolation);
    expect(rowsViol).toHaveLength(1);
    expect(rowsViol[0].status).toBe("confirmed_violation");

    const reportWithoutViolation = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "act-drug-2",
          finding_id: "drug-risk-2",
          surface: "drug_indication",
          kind: "drug_indication",
          finding_type: "compliance",
        },
      ],
      drug_indication: {
        violations: [
          { finding_id: "other-drug-id", drug_code: "D-200" },
        ],
      },
    } as unknown as BillingActionReport;

    const rowsRisk = buildUnifiedComplianceFindings(reportWithoutViolation);
    expect(rowsRisk).toHaveLength(1);
    expect(rowsRisk[0].status).toBe("review_risk");
  });

  it("deduplicates action and canonical finding when both share the same non-empty finding_id into one row with two sources", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "act-shared",
          finding_id: "canonical-shared-99",
          surface: "materials",
          kind: "material_bundling",
          finding_type: "compliance",
          billed_try: 500,
          procedure_code: "P-123",
        },
      ],
      claim_compliance: {
        findings: [
          {
            finding_id: "canonical-shared-99",
            action_id: "canonical-shared-99",
            patient_id: "P-1",
            rule_id: "tablo15_5_material_identity_error",
            status: "violation",
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].canonicalFindingId).toBe("canonical-shared-99");
    expect(rows[0].action?.action_id).toBe("act-shared");
    expect(rows[0].finding?.finding_id).toBe("canonical-shared-99");
    expect(rows[0].sourceLabels).toHaveLength(2);
    expect(rows[0].status).toBe("confirmed_violation");
  });

  it("preserves two rows when similar claim/code/sut are present without a shared canonical finding_id", () => {
    const report = {
      patient_id: "P-1",
      claim_id: "C-1",
      recommended_actions: [
        {
          action_id: "act-similar",
          surface: "materials",
          kind: "material_bundling",
          finding_type: "compliance",
          claim_id: "C-1",
          procedure_code: "P-999",
          sut_section_id: "3.1",
        },
      ],
      claim_compliance: {
        findings: [
          {
            patient_id: "P-1",
            claim_id: "C-1",
            procedure_code: "P-999",
            sut_section_id: "3.1",
            rule_id: "tablo15_5_material_identity_error",
            status: "violation",
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(2);
    expect(rows[0].action?.action_id).toBe("act-similar");
    expect(rows[1].finding?.rule_id).toBe("tablo15_5_material_identity_error");
  });

  it("continues to support legacy action fallback through viewActions", () => {
    const report = {
      patient_id: "P-LEGACY",
      lab: {
        flagged_tests: [
          {
            sut_code: "L-901230",
            test_name: "Hemogram unbundling test",
            flag_type: "lab_flag",
            savings_try: 60,
          },
        ],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].code).toBe("L-901230");
    expect(rows[0].action?.surface).toBe("lab");
  });

  it("leaves amountValue as null for unpriced canonical findings", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [],
      claim_compliance: {
        findings: [
          {
            finding_id: "f-unpriced",
            patient_id: "P-1",
            rule_id: "unpriced_rule",
            status: "review",
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].amountValue).toBeNull();
  });

  it("does not mutate the input report or its nested arrays", () => {
    const report = Object.freeze({
      patient_id: "P-FROZEN",
      recommended_actions: Object.freeze([
        Object.freeze({
          action_id: "a-frozen",
          surface: "materials",
          kind: "material_pre_auth",
          finding_type: "compliance",
          billed_try: 100,
        }),
      ]),
      claim_compliance: Object.freeze({
        findings: Object.freeze([
          Object.freeze({
            finding_id: "f-frozen",
            patient_id: "P-FROZEN",
            rule_id: "rule-frozen",
            status: "violation",
          }),
        ]),
        evaluations: Object.freeze([]),
      }),
    }) as unknown as BillingActionReport;

    expect(() => buildUnifiedComplianceFindings(report)).not.toThrow();
  });

  it("preserves legacy action_id as canonical navigation identity for standalone findings without finding_id", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [],
      claim_compliance: {
        findings: [
          {
            patient_id: "P-1",
            action_id: "legacy-canonical-1",
            rule_id: "legacy_rule",
            status: "violation",
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].canonicalFindingId).toBe("legacy-canonical-1");
    expect(rows[0].rowId).toContain("legacy-canonical-1");
  });

  it("emits a single row when two actions share one explicit canonical finding_id with one finding", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "act-first",
          finding_id: "canonical-1",
          surface: "materials",
          kind: "material_bundling",
          finding_type: "compliance",
          billed_try: 500,
          procedure_code: "P-123",
        },
        {
          action_id: "act-second",
          finding_id: "canonical-1",
          surface: "lab",
          kind: "hemogram_unbundling",
          finding_type: "compliance",
          compliance_savings_try: 45,
        },
      ],
      claim_compliance: {
        findings: [
          {
            finding_id: "canonical-1",
            action_id: "canonical-1",
            patient_id: "P-1",
            rule_id: "tablo15_5_material_identity_error",
            status: "violation",
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].canonicalFindingId).toBe("canonical-1");
    expect(rows[0].action?.action_id).toBe("act-first");
    expect(rows[0].finding?.finding_id).toBe("canonical-1");
    // Stable-order unique source labels: both action surfaces + canonical label once.
    expect(rows[0].sourceLabels.length).toBeGreaterThanOrEqual(3);
    expect(new Set(rows[0].sourceLabels).size).toBe(rows[0].sourceLabels.length);
  });

  it("keeps two rows with distinct rowIds when action_id equals finding_id without shared explicit finding_id", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "same-id",
          surface: "materials",
          kind: "material_bundling",
          finding_type: "compliance",
        },
      ],
      claim_compliance: {
        findings: [
          {
            finding_id: "same-id",
            patient_id: "P-1",
            rule_id: "tablo15_5_material_identity_error",
            status: "violation",
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(2);
    expect(rows[0].action?.action_id).toBe("same-id");
    expect(rows[0].finding).toBeNull();
    expect(rows[1].finding?.finding_id).toBe("same-id");
    expect(rows[0].rowId).not.toBe(rows[1].rowId);
  });

  it("preserves explicit zero billed_try on standalone canonical findings", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [],
      claim_compliance: {
        findings: [
          {
            finding_id: "f-zero",
            patient_id: "P-1",
            rule_id: "zero_rule",
            status: "review",
            billed_try: 0,
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].amountValue).toBe(0);
    expect(rows[0].amountLabel).not.toBeNull();
  });

  it("preserves zero billed_try fallback on merged canonical findings when the action has no amount", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "act-no-amount",
          finding_id: "canonical-zero",
          surface: "billing_strategy",
          kind: "mandatory_compliance",
          finding_type: "compliance",
        },
      ],
      claim_compliance: {
        findings: [
          {
            finding_id: "canonical-zero",
            action_id: "canonical-zero",
            patient_id: "P-1",
            rule_id: "zero_rule",
            status: "violation",
            billed_try: 0,
          },
        ],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(1);
    expect(rows[0].amountValue).toBe(0);
  });

  it("keeps unique rowIds for duplicate action_ids without canonical identity", () => {
    const report = {
      patient_id: "P-1",
      recommended_actions: [
        {
          action_id: "dup-action",
          surface: "materials",
          kind: "material_pre_auth",
          finding_type: "compliance",
          billed_try: 100,
        },
        {
          action_id: "dup-action",
          surface: "lab",
          kind: "hemogram_unbundling",
          finding_type: "compliance",
          compliance_savings_try: 50,
        },
      ],
      claim_compliance: {
        findings: [],
        evaluations: [],
      },
    } as unknown as BillingActionReport;

    const rows = buildUnifiedComplianceFindings(report);
    expect(rows).toHaveLength(2);
    expect(new Set(rows.map((r) => r.rowId)).size).toBe(2);
  });
});
