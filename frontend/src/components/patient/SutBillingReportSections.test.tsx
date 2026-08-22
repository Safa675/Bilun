import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtTRY2Fixture } from "@/test/fmtMoney";
import type { BillingActionReport } from "@/lib/domains/sut";
import {
  BillingStrategySection,
  BillingSummary,
  CopayOptimizationSection,
  DrgUpliftSection,
  MaterialsPreCheckSection,
  MedulaRejectionPlaybookSection,
  DrugIndicationReviewSection,
  OptionalOverrideSection,
  RecommendedActionsPanel,
} from "./SutBillingReportSections";

vi.mock("@/lib/sutLabels", () => ({
  getSutAlertBadgeLabel: (key: string) => key,
  getSutSeverityLabel: (value: string | null | undefined) => value ?? "",
  getPaymentMethodKindLabel: (value: string | null | undefined) => value ?? "",
}));

vi.mock("@/lib/theme", () => ({
  theme: { accent: "#059669" },
}));

vi.mock("@/components/tabs/sut/shared", () => ({
  fmtLabel: (value: string) => value,
  fmtNum: (value: number) => String(value),
  fmtPriorityLabel: (value: string) => value,
  fmtRiskLabel: (value: string) => value,
  fmtTRY2: (value: number) => `${value.toFixed(2)} TRY`,
  fmtTRY2OrUnavailable: (value: number | null | undefined) =>
    value == null ? "Unavailable" : `${value.toFixed(2)} TRY`,
  KpiCard: ({ label, value }: { label: string; value: string }) => (
    <div>
      {label}:{value}
    </div>
  ),
}));

describe("SutBillingReportSections honest gaps", () => {

  it("shows copay exemption insight when section is not exact", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayOptimizationSection
        copayData={{
          exactness_status: "missing_exact_inputs",
          is_exempt: true,
          exemption_disease: "Diabetes",
          exemption_range: "E10-E14",
          visit_copay_savings_try: 0,
          rx_copay_savings_try: 0,
          total_copay_savings_try: 0,
          rate_corrections: [
            {
              detail: "EK-1A exemption may apply for Diabetes (E10-E14).",
            },
          ],
        }}
      />,
    );

    expect(html).toContain("exempt");
    expect(html).toContain("EK-1A exemption may apply");
    expect(html).not.toContain("exemption gap");
  });

  it("shows copay rule_source annex chips in billing copay section", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayOptimizationSection
        copayData={{
          exactness_status: "exact",
          rule_source:
            "SUT §1.8.5(7)+EK-1/A exemptions; §1.8.2(3)+EK-4/D drug exemptions",
          is_exempt: true,
          exemption_disease: "Diabetes",
          exemption_range: "E10-E14",
          visit_copay_savings_try: 10,
          rx_copay_savings_try: 0,
          total_copay_savings_try: 10,
          rate_corrections: [],
        }}
      />,
    );

    expect(html).toContain("EK-1A");
    expect(html).toContain("EK-4D");
  });

  it("shows exemption gap KPIs, MEDULA chip, and dual-benefit footnote when exact and exempt", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayOptimizationSection
        copayData={{
          exactness_status: "exact",
          is_exempt: true,
          exemption_disease: "Diabetes",
          exemption_range: "E10-E14",
          savings_beneficiary: "patient_and_sgk",
          gap_kind: "exemption_correction",
          visit_copay_savings_try: 100,
          rx_copay_savings_try: 10,
          total_copay_savings_try: 100,
          patient_copay_waived_total_try: 110,
          rate_corrections: [
            {
              code: "704100",
              name: "Ear exam",
              billed_try: 50,
              payable_try: 40,
              copay_component_try: 10,
            },
          ],
        }}
      />,
    );

    expect(html).toContain("katilimPayindanMuaf=E");
    expect(html).toContain("Procedure exemption gap");
    expect(html).toContain("Total exemption gap");
    expect(html).toContain(fmtTRY2Fixture(110.00));
    expect(html).toContain("Compliance correction");
    expect(html).toContain("Copay (participation fee)");
  });

  it("shows ilave column and KPI when line decomposition is exact", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayOptimizationSection
        copayData={{
          exactness_status: "exact",
          is_exempt: true,
          exemption_disease: "Diabetes",
          exemption_range: "E10-E14",
          visit_copay_savings_try: 80,
          rx_copay_savings_try: 0,
          total_copay_savings_try: 80,
          patient_copay_waived_total_try: 80,
          ilave_ucret_total_try: 25,
          line_decomposition_status: "exact",
          rate_corrections: [
            {
              code: "704100",
              name: "Ear exam",
              billed_try: 100,
              payable_try: 70,
              copay_component_try: 20,
              ilave_ucret_try: 10,
            },
            {
              code: "704200",
              name: "Hearing test",
              billed_try: 50,
              payable_try: 35,
              copay_component_try: 10,
              ilave_ucret_try: 5,
            },
          ],
        }}
      />,
    );

    expect(html).toContain("Ilave ücret");
    expect(html).toContain("Ilave ücret total");
    expect(html).toContain(fmtTRY2Fixture(25.00));
    expect(html).toContain(fmtTRY2Fixture(10.00));
    expect(html).toContain("exemption does not waive ilave");
  });

  it("hides ilave column when line decomposition is copay_only", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayOptimizationSection
        copayData={{
          exactness_status: "exact",
          is_exempt: true,
          exemption_disease: "Diabetes",
          exemption_range: "E10-E14",
          visit_copay_savings_try: 20,
          rx_copay_savings_try: 0,
          total_copay_savings_try: 20,
          patient_copay_waived_total_try: 20,
          line_decomposition_status: "copay_only",
          rate_corrections: [
            {
              code: "704100",
              name: "Ear exam",
              billed_try: 50,
              payable_try: 30,
              copay_component_try: 20,
            },
          ],
        }}
      />,
    );

    expect(html).not.toContain("Ilave ücret total");
    expect(html).toContain("surcharge rates are missing");
    expect(html).toContain("Copay (participation fee)");
  });

  it("renders backend ilave reasons with clause drawer links when resolvable", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayOptimizationSection
        copayData={{
          exactness_status: "exact",
          is_exempt: true,
          exemption_disease: "Multiple Miyelom ve Malign Plazma",
          exemption_range: "C90",
          visit_copay_savings_try: 0,
          rx_copay_savings_try: 31.24,
          total_copay_savings_try: 0,
          patient_copay_waived_total_try: 31.24,
          ilave_ucret_total_try: 25,
          line_decomposition_status: "exact",
          rate_corrections: [
            {
              code: "A11925",
              name: "MONOVAS 5 MG",
              exemption_ground: "inpatient_drug_1_8_5_8",
              billed_try: 111.55,
              payable_try: 80.32,
              copay_component_try: 31.24,
              clause_ref: {
                clause_key: "1.8.5.(8)#abc123",
                clause_coordinate: "1.8.5.(8)",
              },
              ilave_ucret_status: "drug_prohibited",
              ilave_clause_ref: {
                clause_key: "1.9.1#52ade285",
                clause_coordinate: "1.9.1",
                statutory_law: "5510 Sayılı Kanun Madde 73",
              },
            },
          ],
        }}
      />,
    );

    // Backend-driven reason label composed from the §1.9.1 clause ref.
    expect(html).toContain("Prohibited (§1.9.1 Drug)");
    // Ilave cell links the surcharge clause; ground cell links the waiver clause.
    expect(html).toContain('data-clause-link="1.9.1#52ade285"');
    expect(html).toContain('data-clause-link="1.8.5.(8)#abc123"');
    // In-flight affordances kept.
    expect(html).toContain("Corrected SGK payable (100%)");
    expect(html).toContain("Cashier Refund Notice");
  });

  it("renders unresolved ilave reasons as plain text without a drawer link", () => {
    const html = renderToStaticMarkupWithLocale(
      <CopayOptimizationSection
        copayData={{
          exactness_status: "exact",
          is_exempt: true,
          exemption_disease: "Multiple Miyelom",
          exemption_range: "C90",
          visit_copay_savings_try: 10,
          rx_copay_savings_try: 0,
          total_copay_savings_try: 10,
          patient_copay_waived_total_try: 10,
          ilave_ucret_total_try: 5,
          line_decomposition_status: "exact",
          rate_corrections: [
            {
              code: "520010",
              name: "Muayene",
              billed_try: 100,
              payable_try: 80,
              copay_component_try: 10,
              ilave_ucret_status: "cancer_exempt",
              ilave_clause_ref: {
                clause_key: "",
                clause_coordinate: "1.9.3.ç",
              },
            },
          ],
        }}
      />,
    );

    // Cite is still composed from the coordinate, but clause_key is empty →
    // graceful degradation to plain text (no drawer link anywhere).
    expect(html).toContain("Exempt (§1.9.3.ç Oncology)");
    expect(html).not.toContain("data-clause-link");
  });

  it("shows ilave info stat in billing summary when decomposition is exact", () => {
    const html = renderToStaticMarkupWithLocale(
      <BillingSummary
        billingReport={{
          patient_id: "SENTETIK-HASTA-0042",
          claim_id: "F-SENTETIK-HASTA-0042-072",
          scope: "bill",
          exactness_status: "exact",
          priority: "low",
          total_recoverable_try: 0,
          action_count: 0,
          sgk_uplift_try: 0,
          recommended_actions: [],
          copay: {
            exactness_status: "exact",
            is_exempt: true,
            visit_copay_savings_try: 50,
            rx_copay_savings_try: 0,
            patient_copay_waived_total_try: 50,
            ilave_ucret_total_try: 15,
            line_decomposition_status: "exact",
            rate_corrections: [],
          },
        } as unknown as BillingActionReport}
      />,
    );

    expect(html).toContain("Ilave ücret (informational)");
    expect(html).toContain(fmtTRY2Fixture(15.00));
    expect(html).toContain("exemption does not waive ilave");
  });

  it("shows strategy chapter review flags without TRY", () => {
    const html = renderToStaticMarkupWithLocale(
      <BillingStrategySection
        strategyData={{
          exactness_status: "missing_exact_inputs",
          unavailable_reason: "Needs claim lines.",
          recommendations: [
            {
              chapter: "I",
              recommendation: "review_package_eligibility",
              savings_try: null,
              detail: "Review EK-2C package vs itemized billing eligibility for ICD-10 chapter I.",
            },
          ],
        }}
      />,
    );

    expect(html).toContain("Review package eligibility");
    expect(html).toContain("ICD-10 chapter I");
    expect(html).toContain("Unavailable");
  });

  it("shows SUT rule badges and compliant savings for claim-level strategy", () => {
    const html = renderToStaticMarkupWithLocale(
      <BillingStrategySection
        strategyData={{
          exactness_status: "exact",
          recommendations: [
            {
              claim_id: "F-SENTETIK-HASTA-0003-011",
              recommendation: "package",
              recommendation_kind: "mandatory_compliance",
              payment_method_kind: "DRG_MANDATORY",
              sut_section_id: "2.2.2.(1)",
              package_total_try: 14637.06,
              itemized_total_try: 208.7,
              savings_try: 0,
              detail: "SUT §2.2 mandates package billing for claim F-SENTETIK-HASTA-0003-011.",
            },
            {
              type: "compliance_violation",
              claim_id: "F-SENTETIK-HASTA-0003-011",
              procedure_code: "P603430",
              procedure_name: "Package procedure",
              mandated_method: "package",
              payment_method_kind: "DRG_MANDATORY",
              sut_section_id: "2.2.2.(1)",
              detail: "Procedure must use package billing.",
            },
          ],
        }}
      />,
    );

    expect(html).toContain("Mandatory billing — §2.2.2.(1)");
    expect(html).toContain("Mandatory billing rule");
    expect(html).toContain("DRG mandatory");
    expect(html).toContain("Compliant");
    expect(html).toContain("Violation");
    expect(html).toContain("Package procedure");
    expect(html).toContain(fmtTRY2Fixture(14637.06));
    expect(html).not.toContain("0.00 TRY");
    // Single merged table — no separate red compliance-violations subheading.
    expect(html).not.toContain("Payment method compliance issues");
    // Violation row appears before compliant claim-level content in markup order.
    expect(html.indexOf("Violation")).toBeLessThan(html.indexOf("Mandatory billing rule"));
  });

  it("shows override badge and optional savings header", () => {
    const html = renderToStaticMarkupWithLocale(
      <OptionalOverrideSection
        strategyData={{
          exactness_status: "exact",
          recommendations: [
            {
              claim_id: "CLM-T3",
              recommendation: "itemized",
              recommendation_kind: "optional_override",
              payment_method_kind: "DRG_OVERRIDABLE",
              sut_section_id: "2.2.2.(2)",
              package_total_try: 5000,
              itemized_total_try: 6200,
              savings_try: 1200,
              detail: "Optional §2.2.2(2) override.",
            },
          ],
        }}
      />,
    );

    expect(html).toContain("§2.2.2(2) optional billing method");
    expect(html).toContain("compare package vs itemized");
    expect(html).toContain("Recoverable uplift");
    expect(html).toContain(fmtTRY2Fixture(1200.00));
  });

  it("shows catalog as-of footnote for claim-level strategy", () => {
    const html = renderToStaticMarkupWithLocale(
      <BillingStrategySection
        strategyData={{
          exactness_status: "exact",
          recommendations: [
            {
              claim_id: "CLM-DATE",
              recommendation: "package",
              recommendation_kind: "mandatory_compliance",
              payment_method_kind: "DRG_MANDATORY",
              sut_section_id: "2.2.2.(1)",
              package_total_try: 1000,
              itemized_total_try: 800,
              savings_try: 0,
              catalog_as_of_date: "2024-03-10",
            },
          ],
        }}
      />,
    );

    expect(html).toContain("2024-03-10");
    expect(html).toContain("catalog membership");
  });

  it("shows EK annex chips in DRG uplift rows", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrgUpliftSection
        drgData={{
          exactness_status: "exact",
          rule_source:
            "SUT §2.2 prose rules (payment_method_2_2) + EK-2B/EK-2C catalog membership",
          opportunities: [
            {
              claim_id: "CLM-DRG",
              itemized_total_try: 900,
              package_total_try: 1200,
              recoverable_uplift_try: 300,
              savings_basis: "package_vs_itemized",
              sut_section_id: "2.2.2.(1)",
            },
          ],
          confirmed_uplift_try: 300,
        }}
      />,
    );

    expect(html).toContain("Source (EK)");
    expect(html).toContain("EK-2B");
    expect(html).toContain("EK-2C");
  });

  it("renders multiple prose violations that share the same rule_id", () => {
    const html = renderToStaticMarkupWithLocale(
      <MaterialsPreCheckSection
        materialsData={{
          exactness_status: "exact",
          pre_auth_required: [],
          miat_restricted: [],
          prose_bundling_violations: [
            {
              rule_id: "3.1.2.(2).not_in_ek3c",
              material_code: "MAL-A",
              material_name: "Material A",
              message: "Not in EK-3C",
              risk_amount: 100,
            },
            {
              rule_id: "3.1.2.(2).not_in_ek3c",
              material_code: "MAL-B",
              material_name: "Material B",
              message: "Not in EK-3C",
              risk_amount: 200,
            },
          ],
          gazette_ceiling_by_specialty: {},
        }}
      />,
    );

    expect(html).toContain("MAL-A");
    expect(html).toContain("MAL-B");
    expect(html).toContain("Material A");
    expect(html).toContain("Material B");
  });

  it("renders specialty prose and KDV price review tables", () => {
    const html = renderToStaticMarkupWithLocale(
      <MaterialsPreCheckSection
        materialsData={{
          exactness_status: "exact",
          pre_auth_required: [],
          miat_restricted: [],
          specialty_prose_violations: [
            {
              rule_id: "3.3.3.A.(4).ek3d_lens_upgrade_difference",
              material_code: "GZ2035",
              material_name: "Gözlük camı",
              message: "Lens upgrade difference not payable",
              risk_amount: 450,
            },
          ],
          kdv_price_reviews: [
            {
              sut_code: "OP1592",
              material_name: "ICD",
              billed_try: 999999,
              gazette_ceiling_try: 1200,
              kdv_applied: true,
              note: "Billed amount exceeds EK-3 list price + KDV (§3.1.1(12)).",
            },
          ],
          gazette_ceiling_by_specialty: {},
        }}
      />,
    );

    expect(html).toContain("GZ2035");
    expect(html).toContain("OP1592");
    expect(html).toContain("Lens upgrade difference not payable");
  });
});

describe("MedulaRejectionPlaybookSection", () => {
  it("renders nothing when exactness_status is not_applicable", () => {
    const html = renderToStaticMarkupWithLocale(
      <MedulaRejectionPlaybookSection
        playbookData={{
          exactness_status: "not_applicable",
          entries: [],
          entry_count: 0,
          rebill_permitted_count: 0,
        }}
      />,
    );
    expect(html).toBe("");
  });

  it("renders nothing when exact with no entries", () => {
    const html = renderToStaticMarkupWithLocale(
      <MedulaRejectionPlaybookSection
        playbookData={{
          exactness_status: "exact",
          entries: [],
          entry_count: 0,
          rebill_permitted_count: 0,
        }}
      />,
    );
    expect(html).toBe("");
  });

  it("renders the playbook table when entries exist", () => {
    const html = renderToStaticMarkupWithLocale(
      <MedulaRejectionPlaybookSection
        playbookData={{
          exactness_status: "exact",
          entries: [
            {
              playbook_id: "1688_molecular_microbiology",
              rejection_event_id: "MEDULA-F-001-001",
              claim_id: "F-001",
              medula_stage: "fatura_kayit",
              sonuc_kodu: "1688",
              hata_kodu: "1688",
              hata_mesaji:
                "Moleküler mikrobiyoloji işlemi için zorunlu rapor eksik",
              related_procedure_code: "700390",
              related_procedure_line_id: "ISL-001",
              related_line_type: "procedure",
              related_line_id: "ISL-001",
              sut_anchor: "EK-2 / moleküler mikrobiyoloji rapor gerekliliği",
              problem_summary_tr: "Rapor eksik.",
              problem_summary_en: "Report missing.",
              corrective_steps_tr: ["Adım 1", "Adım 2"],
              corrective_steps_en: ["Step 1", "Step 2"],
              rebill_permitted: true,
              rebill_stage: "fatura_kayit",
            },
          ],
          entry_count: 1,
          rebill_permitted_count: 1,
        }}
      />,
    );
    expect(html).toContain("1688");
    expect(html).toContain("Moleküler mikrobiyoloji");
    expect(html).toContain("Step 1");
  });
});

describe("DrugIndicationReviewSection", () => {
  it("renders nothing when there are no violations", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection
        reviewData={{
          exactness_status: "exact",
          violations: [],
          violation_count: 0,
          error_count: 0,
        }}
      />,
    );
    expect(html).toBe("");
  });

  it("renders violation table when entries exist", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection
        reviewData={{
          exactness_status: "exact",
          violations: [
            {
              claim_id: "F-DEMO-001",
              drug_name: "AVASTIN (BEVACIZUMAB)",
              violation_kind: "missing_board_report",
              severity: "error",
              primary_icd10: "C34.9",
              rule_id: "4.2.14.C.(1).bevacizumab_oncology_board",
              sut_section: "4.2.14.C",
              message_tr: "Uzmanlık sağlık kurulu raporu eksik",
            },
          ],
          violation_count: 1,
          error_count: 1,
        }}
      />,
    );
    expect(html).toContain("missing_board_report");
    expect(html).toContain("AVASTIN");
    expect(html).toContain("C34.9");
  });

  it("lists itemized recommended actions in the actions panel", () => {
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel
        billingReport={{
          patient_id: "SENTETIK-HASTA-0003",
          claim_id: "F-SENTETIK-HASTA-0003-015",
          scope: "bill",
          exactness_status: "exact",
          priority: "low",
          total_recoverable_try: 0,
          action_count: 4,
          sgk_uplift_try: 0,
          recommended_actions: [
            {
              action_id: "strategy:608870",
              surface: "billing_strategy",
              kind: "compliance_violation",
              procedure_code: "608870",
              procedure_name: "Torakotomi",
              detail: "must use package",
              sut_section_id: "2.2.1.B-1.a",
            },
            {
              action_id: "copay:ek1a",
              surface: "copay",
              kind: "exemption_review",
              // Backend emits the canonical dot form (never legacy "1.8.5(7)").
              sut_section_id: "1.8.5.(7)",
              clause_ref: {
                clause_key: "1.8.5.(7)#9f2c41de",
                clause_coordinate: "1.8.5.(7)",
                annex: "EK-1/A",
              },
              finding_type: "opportunity",
            },
          ],
          copay: {
            is_exempt: false,
            visit_copay_savings_try: 0,
            rx_copay_savings_try: 0,
          },
        } as BillingActionReport}
      />,
    );

    expect(html).toContain("608870");
    expect(html).toContain("Torakotomi");
    // Both recommended actions render as separate rows in the itemized table.
    expect(html).toContain("§2.2.1.B-1.a");
    expect(html).toContain("§1.8.5.(7)");
  });

  it("renders material recommended actions with SUT, billed amount, and detail", () => {
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel
        billingReport={{
          patient_id: "SENTETIK-HASTA-0042",
          claim_id: "F-SENTETIK-HASTA-0042-072",
          scope: "bill",
          exactness_status: "exact",
          priority: "low",
          total_recoverable_try: 0,
          action_count: 1,
          sgk_uplift_try: 0,
          recommended_actions: [
            {
              action_id: "materials:material_pre_auth:F-1:0",
              surface: "materials",
              kind: "material_pre_auth",
              material_code: "OP1198",
              material_name: "Ortez",
              billed_try: 1250,
              detail: "EK-3C-1 — pre-auth required",
              sut_section_id: "3.1.2",
            },
          ],
          copay: {
            is_exempt: false,
            visit_copay_savings_try: 0,
            rx_copay_savings_try: 0,
          },
        } as BillingActionReport}
      />,
    );

    expect(html).toContain("OP1198");
    expect(html).toContain("Ortez");
    expect(html).toContain("§3.1.2");
    expect(html).toContain(fmtTRY2Fixture(1250.00));
    expect(html).toContain("EK-3C-1 — pre-auth required");
  });
});

describe("RecommendedActionsPanel workspace-view integration", () => {
  const panelReport = {
    patient_id: "P-VIEWS",
    exactness_status: "exact",
    priority: "low",
    total_recoverable_try: 150,
    action_count: 3,
    recommended_actions: [
      {
        action_id: "a1",
        surface: "materials",
        kind: "material_pre_auth",
        finding_type: "compliance",
        billed_try: 100,
        sut_section_id: "3.1.2",
        clause_ref: {
          clause_key: "3.1.2#abc123",
          clause_coordinate: "3.1.2",
          source_type: "sut_clause",
        },
        detail: "PRE-AUTH-DETAIL",
      },
      {
        action_id: "a2",
        surface: "yatak_puani",
        kind: "yatak_puani_standard_bed",
        finding_type: "opportunity",
        sgk_uplift_try: 50,
        sut_section_id: "2.2.2",
        detail: "BED-DAY-DETAIL",
      },
      {
        action_id: "a3",
        surface: "claim_checklist",
        kind: "documentation_requirement",
        finding_type: "informational",
        detail: "CHECKLIST-DETAIL",
      },
    ],
  } as unknown as BillingActionReport;

  it("renders all rows without a finding filter", () => {
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel billingReport={panelReport} />,
    );

    expect(html).toContain("PRE-AUTH-DETAIL");
    expect(html).toContain("BED-DAY-DETAIL");
    expect(html).toContain("CHECKLIST-DETAIL");
  });

  it("filters rows to one finding class", () => {
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel billingReport={panelReport} findingFilter="compliance" />,
    );

    expect(html).toContain("PRE-AUTH-DETAIL");
    expect(html).not.toContain("BED-DAY-DETAIL");
    expect(html).not.toContain("CHECKLIST-DETAIL");
  });

  it("renders the SUT section cell as a clause-inspect button when onOpenClause is given", () => {
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel
        billingReport={panelReport}
        findingFilter="compliance"
        onOpenClause={() => {}}
      />,
    );

    expect(html).toContain('<button');
    expect(html).toContain('aria-label="Inspect clause: 3.1.2"');
    expect(html).toContain("§3.1.2");
  });

  it("keeps the SUT section cell as plain text without onOpenClause", () => {
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel billingReport={panelReport} findingFilter="compliance" />,
    );

    expect(html).not.toContain('<button');
    expect(html).toContain("§3.1.2");
  });
});
