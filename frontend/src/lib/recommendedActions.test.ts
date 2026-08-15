import { describe, expect, it } from "vitest";
import {
  findingTypeChipVariant,
  getFindingType,
  getRecommendedActions,
  recommendedActionAmountParts,
  recommendedActionKindLabel,
  recommendedActionLineCodes,
  recommendedActionSurfaceLabel,
  recommendedActionTitle,
} from "@/lib/recommendedActions";
import type { BillingActionReport, RecommendedActionItem } from "@/lib/domains/sut";

const t = (key: string, params?: Record<string, string | number>) => {
  if (params) {
    return `${key}:${JSON.stringify(params)}`;
  }
  return key;
};

describe("getFindingType", () => {
  const cases: Array<["compliance" | "opportunity" | "informational"]> = [
    ["compliance"],
    ["opportunity"],
    ["informational"],
  ];

  it.each(cases)("passes through backend finding_type %s", (findingType) => {
    expect(
      getFindingType({
        action_id: "x",
        surface: "materials",
        kind: "material_pre_auth",
        finding_type: findingType,
      }),
    ).toBe(findingType);
  });

  it("defaults to informational when finding_type is absent", () => {
    expect(
      getFindingType({ action_id: "x", surface: "materials", kind: "material_pre_auth" }),
    ).toBe("informational");
    expect(
      getFindingType({
        action_id: "x",
        surface: "billing_strategy",
        kind: "compliance_violation",
        finding_type: null,
      }),
    ).toBe("informational");
  });

  it("maps finding types to chip variants", () => {
    expect(findingTypeChipVariant("compliance")).toBe("danger");
    expect(findingTypeChipVariant("opportunity")).toBe("success");
    expect(findingTypeChipVariant("informational")).toBe("neutral");
  });
});

describe("recommendedAction labels", () => {
  it("labels material and yatak kinds instead of Unknown", () => {
    expect(
      recommendedActionKindLabel(t, "material_pre_auth"),
    ).toBe("billing.recommendedActions.kinds.materialPreAuth");
    expect(
      recommendedActionKindLabel(t, "material_bundling"),
    ).toBe("billing.recommendedActions.kinds.materialBundling");
    expect(
      recommendedActionSurfaceLabel(t, "yatak_puani"),
    ).toBe("billing.recommendedActions.surfaces.yatakPuani");
  });

  it("humanizes unmapped snake_case kinds instead of Unknown", () => {
    expect(recommendedActionKindLabel(t, "brand_new_detector")).toBe(
      "Brand New Detector",
    );
  });
});

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
    // Fallback rows carry finding_type and the canonical dot-form section id.
    const copayRow = actions.find((row) => row.surface === "copay")!;
    expect(copayRow.finding_type).toBe("opportunity");
    expect(copayRow.sut_section_id).toBe("1.8.5.(7)");
    expect(
      actions.find((row) => row.surface === "billing_strategy")!.finding_type,
    ).toBe("compliance");
  });

  it("classifies fallback lab and uplift rows", () => {
    const report = {
      copay: { is_exempt: false },
      lab: {
        flagged_tests: [
          { test_name: "Hemogram", flag_type: "hemogram_unbundling", savings_try: 5 },
        ],
      },
      billing_strategy: { recommendations: [] },
      session_uplift: {
        opportunities: [{ claim_id: "F-2", procedure_code: "908110" }],
      },
    } as unknown as BillingActionReport;

    const actions = getRecommendedActions(report);
    const lab = actions.find((row) => row.surface === "lab")!;
    expect(lab.finding_type).toBe("compliance");
    const uplift = actions.find((row) => row.surface === "session_uplift")!;
    expect(uplift.finding_type).toBe("opportunity");
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
    expect(recommendedActionTitle(t, action)).not.toContain("P611132");

    const amount = recommendedActionAmountParts(t, action);
    expect(amount?.label).toBe("billing.recommendedActions.amountBilledAtRisk");
    expect(amount?.value).toBe(1250);
  });

  it("prefers material code over package procedure code on material precheck rows", () => {
    const action: RecommendedActionItem = {
      action_id: "materials:material_bundling:F-1:0",
      surface: "materials",
      kind: "material_bundling",
      procedure_code: "P700930",
      procedure_name: "Perkütan balon valvüloplasti, mitral kapak için",
      material_code: "GHC1390",
      material_name: "STENT, SİLİKON, FİSTÜL",
      billed_try: 12969.69,
      detail: "Bundled material billed separately",
      sut_section_id: "EK-3B-1",
    };

    const title = recommendedActionTitle(t, action);
    expect(title).toContain("GHC1390");
    expect(title).toContain("STENT, SİLİKON, FİSTÜL");
    expect(title).not.toContain("P700930");
  });

  it("shows missing billable material code on material uplift rows", () => {
    const action: RecommendedActionItem = {
      action_id: "material_uplift:F-1:0",
      surface: "material_uplift",
      kind: "missing_billable_material",
      procedure_code: "P700930",
      procedure_name: "Perkütan balon valvüloplasti, mitral kapak için",
      material_code: "KR1152",
      material_name: "STENT, KORONER, BALONA MONTE EDİLMİŞ GRAFT STENT",
      sgk_uplift_try: 10134.14,
      detail: "EK-3H ilac salinimli stent (KR1152) ayri faturalandirilmamis.",
      sut_section_id: "3.3.1",
    };

    const title = recommendedActionTitle(t, action);
    expect(title).toContain("KR1152");
    expect(title).toContain("STENT, KORONER");
    expect(title).not.toContain("P700930");
  });

  it("maps recommended actions to per-section invoice-line codes for highlighting", () => {
    const lab = recommendedActionLineCodes({
      action_id: "lab:1",
      surface: "lab",
      kind: "lab_flag",
      procedure_code: "907450",
    });
    expect(lab.labs).toEqual(["907450"]);
    expect(lab.procedures).toEqual([]);

    // Material-anchored: material_code → materials, procedure_code (package) → procedures.
    const material = recommendedActionLineCodes({
      action_id: "material_uplift:1",
      surface: "material_uplift",
      kind: "missing_billable_material",
      procedure_code: "P700930",
      material_code: "KR1152",
    });
    expect(material.materials).toEqual(["KR1152"]);
    expect(material.procedures).toEqual(["P700930"]);

    // Drug indication → drugs.
    const drug = recommendedActionLineCodes({
      action_id: "drug:1",
      surface: "drug_indication",
      kind: "drug_indication",
      drug_code: "A10AB05",
    });
    expect(drug.drugs).toEqual(["A10AB05"]);

    // Generic procedure-anchored surface → procedures.
    const proc = recommendedActionLineCodes({
      action_id: "session_uplift:1",
      surface: "session_uplift",
      kind: "session_uplift",
      procedure_code: "908110",
    });
    expect(proc.procedures).toEqual(["908110"]);

    // No code (e.g. copay exemption) → graceful no-op, all sections empty.
    const copay = recommendedActionLineCodes({
      action_id: "copay:ek1a",
      surface: "copay",
      kind: "exemption_review",
    });
    expect(copay).toEqual({ procedures: [], labs: [], materials: [], drugs: [] });
  });
});
