import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtTRY2Fixture } from "@/test/fmtMoney";
import enBilling from "@/messages/en/billing";
import trBilling from "@/messages/tr/billing";
import type { BillingActionReport, DrugIndicationFinding, PatientOptimization } from "@/lib/domains/sut";
import {
  BillingStrategySection,
  BillingSectionShell,
  BillingSummary,
  CopayOptimizationSection,
  DrgUpliftSection,
  MaterialsPreCheckSection,
  MedulaRejectionPlaybookSection,
  DrugIndicationReviewSection,
  OptionalOverrideSection,
  RecommendedActionsPanel,
  SutOptimizationSection,
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

  it("separates a collapsed row count from a known zero monetary total in visible text", () => {
    const html = renderToStaticMarkupWithLocale(
      <BillingSectionShell title="SUT review" collapsed count={1} total="0.00 TRY" exactness={{ exactness_status: "exact" }}>
        <p>Details</p>
      </BillingSectionShell>,
    );
    const summaryText = html.match(/<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1].replace(/<[^>]+>/g, "");
    expect(summaryText).toContain("SUT review · 1 0.00 TRY");
    expect(summaryText).not.toContain("10.00 TRY");
  });

  it.each(["en", "tr"] as const)("keeps implemented but partial material prose coverage visible in the collapsed %s header", (locale) => {
    const html = renderToStaticMarkupWithLocale(
      <MaterialsPreCheckSection collapsed materialsData={{
        exactness_status: "exact",
        pre_auth_required: [], miat_restricted: [], gazette_ceiling_by_specialty: {},
        prose_bundling_violations: [{ material_code: "MAL-A", material_name: "Material A", risk_amount: 100 }],
        coverage_scope: {
          prose_engine_status: "implemented", prose_coverage_tier: "partial", prose_rules_implemented: 1,
          prose_section_prefixes: ["3.1"], implemented_annexes: ["EK-3B-1", "EK-3B-2"],
          ek3b1_row_count: 10, ek3b2_row_count: 20,
        },
      }} />,
      locale,
    );
    const summary = html.match(/<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1];
    expect(summary).toContain(locale === "en" ? "Exact" : "Kesin");
    expect(summary).toContain(locale === "en" ? "Partial coverage" : "Kısmi kapsam");
  });

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
        onOpenClause={() => {}}
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

    expect(html).toContain("Surcharge (informational)");
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
              note: "Billed amount exceeds EK-3 list price + KDV (§3.1.1(10)).",
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
  it.each(["en", "tr"] as const)("keeps each %s drug and certainty with one shared summary risk and unchanged card risks", (locale) => {
    const labels = (locale === "en" ? enBilling : trBilling).drugIndication;
    const findings: DrugIndicationFinding[] = ["evaluated", "missing_inputs", "unavailable"].map((evaluation_status, index) => ({
      finding_id: `drug-${index}`, patient_id: "P-DRUG", claim_id: "C-DRUG", drug_claim_line_id: `D-${index}`,
      drug_name: index === 2 ? undefined : `Medicine ${index}`, drug_code: `CODE-${index}`,
      finding_kind: "indication_mismatch", severity: "review", applicability_status: "indication_mismatch",
      evaluation_status, observed_icd10_codes: [], matched_icd10_codes: [], unmatched_icd10_codes: [], eligible_routes: [],
      explanation_tr: `Distinct explanation ${index}`, recommended_action_tr: `Distinct action ${index}`,
    } as DrugIndicationFinding));
    const html = renderToStaticMarkupWithLocale(<DrugIndicationReviewSection reviewData={{
      exactness_status: "partial_exact", unavailable_reason: "Distinct partial reason", violations: [], findings,
      violation_count: 3, error_count: 0,
    }} />, locale);
    const header = html.match(/<details id="drug-indication"[^>]*>\s*<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1] ?? "";
    const lines = [...header.matchAll(/<span class="mt-1 block text-xs font-normal text-\[var\(--text-secondary\)\]">([\s\S]*?)<\/span>/g)]
      .map((match) => match[1]);

    expect(header.split(labels.riskNotice)).toHaveLength(2);
    expect(header).toContain("Distinct partial reason");
    expect(header).toContain("· 3");
    expect(lines).toEqual([`Medicine 0 · ${labels.certaintyLabels.evaluated}`, `Medicine 1 · ${labels.certaintyLabels.missing_inputs}`,
      `CODE-2 · ${labels.certaintyLabels.unavailable}`]);
    expect(html).not.toContain('<details id="drug-indication" open=');
    const cards = [...html.matchAll(/<article\b[^>]*>([\s\S]*?)<\/article>/g)].map((match) => match[1]);
    expect(cards).toHaveLength(3);
    cards.forEach((card, index) => {
      expect(card.split(labels.riskNotice)).toHaveLength(2);
      expect(card).toContain(`CODE-${index}`);
      expect(card).toContain(`Distinct explanation ${index}`);
      expect(card).toContain(`Distinct action ${index}`);
    });
  });

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

  it("renders nothing for a genuinely not-applicable empty block", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection
        reviewData={{
          exactness_status: "not_applicable",
          violations: [],
          findings: [],
          evaluations: [],
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
    expect(html).not.toContain("<details open");
  });

  it("renders structured findings as an actionable summary with technical disclosure", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection
        reviewData={{
          exactness_status: "exact",
          violations: [],
          findings: [
            {
              finding_id: "drug_indication:P1:C1:D1:indication_mismatch",
              patient_id: "P1",
              claim_id: "C1",
              drug_claim_line_id: "D1",
              drug_name: "ORENCIA 250 MG",
              finding_kind: "indication_mismatch",
              severity: "error",
              applicability_status: "indication_mismatch",
              evaluation_status: "evaluated",
              observed_icd10_codes: ["E66.9"],
              observed_icd10_count: 65,
              observed_icd10_truncated: true,
              matched_icd10_codes: [],
              unmatched_icd10_codes: ["E66.9"],
              eligible_routes: [
                {
                  rule_id: "4.2.1.abatacept_ra_board",
                  sut_section: "4.2.1",
                  icd10_codes: ["M05", "M06"],
                  icd10_code_count: 23,
                  icd10_codes_truncated: true,
                  icd10_ranges: ["M08"],
                  icd10_range_count: 1,
                  icd10_ranges_truncated: false,
                  regulatory_summary_tr: "RA/JIA route evidence",
                },
              ],
              explanation_tr: "E66.9 tanısı kodlanmış endikasyon yollarıyla eşleşmedi.",
              recommended_action_tr: "Tanı kodunu ve sağlık kurulu raporunu doğrulayın.",
              selected_rule_id: null,
            },
          ],
          violation_count: 1,
          error_count: 1,
        }}
      />,
      "tr",
    );

    expect(html).toContain("Tanı–ilaç eşleşmesi bulunamadı");
    expect(html).toContain("Geri ödeme koşulu doğrulanamadı — MEDULA reddi riski");
    expect(html).toContain("E66.9");
    expect(html).toContain("M05, M06, M08");
    expect(html).toContain("Tanı kodunu ve sağlık kurulu raporunu doğrulayın.");
    expect(html).toContain("Teknik ayrıntılar");
    expect(html).toContain("4.2.1.abatacept_ra_board");
    expect(html).toContain("Gözlenen tanıların yalnızca sınırlı bir önizlemesi gösteriliyor.");
    expect(html).toContain("Gösterilen yol kodları/aralıkları sınırlı bir önizlemedir");
    expect(html).toContain("Çok sayıda aday yol bulundu; teknik liste sınırlandı.");
    expect(html).not.toContain('<details id="drug-indication" open=');
    const header = html.match(/<details id="drug-indication"[^>]*>\s*<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1];
    expect(header).toContain("· 1");
    expect(header).toContain("ORENCIA 250 MG");
    expect(header).toContain("Geri ödeme koşulu doğrulanamadı — MEDULA reddi riski");
  });

  it("renders missing diagnosis as unevaluable rather than a confirmed mismatch", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection
        reviewData={{
          exactness_status: "missing_exact_inputs",
          violations: [],
          findings: [
            {
              finding_id: "drug_indication:P2:C2:D2:missing_diagnosis",
              patient_id: "P2",
              claim_id: "C2",
              drug_claim_line_id: "D2",
              drug_name: "ORENCIA 250 MG",
              finding_kind: "missing_diagnosis",
              severity: "review",
              applicability_status: "missing_diagnosis",
              evaluation_status: "missing_inputs",
              observed_icd10_codes: [],
              matched_icd10_codes: [],
              unmatched_icd10_codes: [],
              missing_inputs: ["claim_diagnoses", "primary_icd10"],
              eligible_routes: [
                {
                  rule_id: "4.2.1.abatacept_ra_board",
                  sut_section: "4.2.1",
                  icd10_codes: ["M05", "M06"],
                  icd10_ranges: ["M08"],
                },
              ],
              explanation_tr: "Tanı kodu bulunamadığı için endikasyon eşleştirmesi tamamlanamadı.",
              recommended_action_tr: "Tanı kayıtlarını tamamlayıp yeniden kontrol edin.",
              selected_rule_id: null,
            },
          ],
          violation_count: 1,
          error_count: 0,
        }}
      />,
      "tr",
    );

    expect(html).toContain("Tanı bilgisi eksik");
    expect(html).toContain("Eksik girdi — manuel doğrulama");
    expect(html).toContain("Tanı kodu yok");
    expect(html).toContain("Tanı kayıtlarını tamamlayıp yeniden kontrol edin.");
    expect(html).not.toContain("Tanı–ilaç eşleşmesi bulunamadı");
    const header = html.match(/<details id="drug-indication"[^>]*>\s*<summary[^>]*>([\s\S]*?)<\/summary>/)?.[1];
    expect(header).toContain("Eksik girdi — manuel doğrulama");
  });

  it("selects exactly the requested canonical finding across drug lines", () => {
    const finding = {
      patient_id: "P-DEEP",
      claim_id: "C-DEEP",
      drug_name: "ORENCIA",
      finding_kind: "indication_mismatch",
      severity: "error",
      applicability_status: "indication_mismatch",
      evaluation_status: "evaluated",
      observed_icd10_codes: ["E66.9"],
      matched_icd10_codes: [],
      unmatched_icd10_codes: ["E66.9"],
      eligible_routes: [],
      explanation_tr: "İlk bulgu",
      recommended_action_tr: "Kontrol edin.",
    } satisfies DrugIndicationFinding;
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection
        selectedFindingId="drug_indication:P-DEEP:C-DEEP:D2:indication_mismatch"
        reviewData={{
          exactness_status: "exact",
          violations: [],
          findings: [
            {
              ...finding,
              finding_id: "drug_indication:P-DEEP:C-DEEP:D1:indication_mismatch",
              drug_claim_line_id: "D1",
            },
            {
              ...finding,
              finding_id: "drug_indication:P-DEEP:C-DEEP:D2:indication_mismatch",
              drug_claim_line_id: "D2",
            },
          ],
          violation_count: 2,
          error_count: 2,
        }}
      />,
    );

    expect(html.match(/data-selected="true"/g)).toHaveLength(1);
    expect(html).toContain('<details id="drug-indication" open=""');
    expect(html).toContain(
      'data-finding-id="drug_indication:P-DEEP:C-DEEP:D2:indication_mismatch"',
    );
  });

  it("opens drug detail from its section anchor without a selected finding", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection selectedSection="drug-indication" reviewData={{
        exactness_status: "exact",
        violations: [{ claim_id: "C-1", drug_name: "Drug", violation_kind: "missing_board_report" }],
        violation_count: 1,
        error_count: 0,
      }} />,
      "en",
    );
    expect(html).toContain('<details id="drug-indication" open=""');
  });

  it("renders structured corpus noncoverage without calling it legacy", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugIndicationReviewSection
        reviewData={{
          exactness_status: "partial_exact",
          unavailable_reason: "Kodlanmış kural kapsamı dışında.",
          required_inputs_missing: [],
          violations: [],
          findings: [],
          evaluations: [
            {
              patient_id: "P-UNCODED",
              claim_id: "C-UNCODED",
              drug_claim_line_id: "D-UNCODED",
              drug_name: "UNENCODED MEDICINE",
              applicability_status: "not_in_encoded_corpus",
              evaluation_status: "unavailable",
              observed_icd10_codes: ["E66.9"],
              matched_icd10_codes: [],
              unmatched_icd10_codes: ["E66.9"],
              eligible_routes: [],
              required_inputs: [],
              missing_inputs: [],
            },
          ],
          violation_count: 0,
          error_count: 0,
        }}
      />,
      "tr",
    );

    expect(html).toContain("Kodlanmış kural derlemi bu ilacı değerlendiremiyor");
    expect(html).toContain("SUT metnini manuel inceleyin");
    expect(html).not.toContain("Legacy payload");
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

  it.each(["en", "tr"] as const)("shows the three highest existing amounts with their source exactness in the compact %s container", (locale) => {
    const report = {
      ...panelReport,
      materials: { exactness_status: "partial_exact" },
      yatak_puani: { exactness_status: "exact" },
      recommended_actions: [
        ...panelReport.recommended_actions!,
        { action_id: "a4", surface: "lab", kind: "hemogram_unbundling", compliance_savings_try: 25 },
      ],
    } as unknown as BillingActionReport;
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel billingReport={report} compact onOpenClause={() => {}} />,
      locale,
    );
    expect(html).toContain(locale === "en" ? "Next actions" : "Sonraki işlemler");
    expect(html).toContain(locale === "en" ? "Show all (4)" : "Tümünü göster (4)");
    expect(html).toContain(locale === "en" ? "Partial exact" : "Kısmi kesin");
    expect(html).toContain(locale === "en" ? ">Exact<" : ">Kesin<");
    expect(html.indexOf('data-action-id="a1"')).toBeLessThan(html.indexOf('data-action-id="a2"'));
    expect(html.indexOf('data-action-id="a2"')).toBeLessThan(html.indexOf('data-action-id="a4"'));
    expect(html).not.toContain('data-action-id="a3"');
    expect(html).toContain("SUT §3.1.2");
    expect(html.match(locale === "en" ? /aria-label="Inspect clause:/g : /aria-label="Fıkrayı incele:/g)).toHaveLength(1);
    expect(html).toContain("100.00 TRY");
    expect(html).toContain("50.00 TRY");
    expect(html).toContain("25.00 TRY");
    expect(html).toContain("@min-[420px]:grid-cols-[minmax(0,1fr)_auto_auto]");
    expect(html).toContain("@min-[420px]:col-span-1");
    expect(html).toContain("@min-[420px]:text-right");
    expect(html).toContain("@min-[300px]:col-span-2");
    expect(html).not.toContain("@min-[560px]");
  });

  it.each(["en", "tr"] as const)("preserves a missing exactness and disabled Source for a null compact %s action", (locale) => {
    const report = {
      ...panelReport,
      recommended_actions: [{
        action_id: "unpriced-material",
        surface: "materials",
        kind: "material_pre_auth",
        billed_try: null,
        material_name: "UNPRICED-MATERIAL",
      }],
    } as unknown as BillingActionReport;
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel billingReport={report} compact onOpenClause={() => {}} />,
      locale,
    );
    expect(html).toContain('data-action-id="unpriced-material"');
    expect(html).toContain(locale === "en" ? "Pre-authorization required" : "Ön onay gerekli");
    expect(html).toContain(locale === "en" ? "Unavailable" : "Kullanılamıyor");
    expect(html).toContain("disabled=\"\"");
    expect(html).not.toMatch(/aria-label="(?:Inspect clause|Fıkrayı incele):/);
    expect(html).not.toMatch(/0(?:[.,]00)?\s*TRY\b/);
  });

  it.each([
    ["en", "Verify exemption", "Partial exact", "Inspect clause: 1.8.5.(7)"],
    ["tr", "Muafiyeti doğrula", "Kısmi kesin", "Fıkrayı incele: 1.8.5.(7)"],
  ] as const)("keeps a null copay review amount unpriced in the compact %s panel", (locale, label, exactness, clauseLabel) => {
    const report = {
      ...panelReport,
      copay: { exactness_status: "partial_exact" },
      recommended_actions: [{
        action_id: "unpriced-copay",
        surface: "copay",
        kind: "exemption_review",
        billed_try: null,
        sgk_uplift_try: null,
        clause_ref: { clause_key: "1.8.5.(7)#real-source", clause_coordinate: "1.8.5.(7)" },
      }],
    } as unknown as BillingActionReport;
    const html = renderToStaticMarkupWithLocale(
      <RecommendedActionsPanel billingReport={report} compact onOpenClause={() => {}} />,
      locale,
    );
    expect(html).toContain(label);
    expect(html).not.toMatch(/₺\s*0\b|0(?:[.,]00)?\s*TRY\b/);
    expect(html).toContain(exactness);
    expect(html).toContain(`aria-label="${clauseLabel}"`);
    expect(html).toContain("SUT §1.8.5.(7)");
  });

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

describe("SutOptimizationSection container layout", () => {
  it.each(["en", "tr"] as const)("keeps the open %s metric rows and their separate uncertainty inside component-width rows", (locale) => {
    const optimization: PatientOptimization = {
      patient_id: "P-CONTAINER",
      n_diagnoses: 0,
      diagnoses: [],
      icd10_chapters: [],
      copay_exemptions: { exempt: false, n_qualifying: 0, qualifying_diagnoses: [] },
      surcharge_exposure: {
        exactness_status: "exact", n_applicable_procedures: 2,
        n_total_ek2g: 3, exposure_rate: 2 / 3, applicable_rules: [],
      },
      copay_rate_exposure: {
        exactness_status: "partial_exact", unavailable_reason: "RATE-INPUT-MISSING",
        n_applicable_procedures: null, n_total_ek2c1: null,
        procedures_with_rates: [], mean_rate: null, rate_distribution: {},
      },
      drg_unbundling: {
        exactness_status: "exact", has_unbundling_risk: true,
        n_chapters_analyzed: 1, chapter_analysis: [], total_potential_savings: null,
      },
    };
    const html = renderToStaticMarkupWithLocale(
      <SutOptimizationSection optimization={optimization} />,
      locale,
    );
    expect(html).toContain('<dl data-sut-optimization-summary="true" class="@container/optimization space-y-3">');
    expect([...html.matchAll(/data-optimization-metric="([^"]+)"/g)].map((match) => match[1])).toEqual(["copay", "surcharge", "copay-rate", "drg"]);
    expect(html.match(/@min-\[400px\]\/optimization:grid-cols-\[minmax\(0,1fr\)_auto\]/g)).toHaveLength(4);
    expect(html).not.toContain("md:grid-cols");
    expect(html).not.toContain("xl:grid-cols");
    expect(html).not.toContain("<details");
    expect(html).toContain("RATE-INPUT-MISSING");
    expect(html).toContain('role="status">RATE-INPUT-MISSING');
    expect(html).toContain(locale === "en" ? "2 flags" : "2 bayrak");
    expect(html).toContain("Unavailable");
    expect(html).not.toContain("0.00 TRY");
    expect(html).toContain("whitespace-nowrap tabular-nums");
    const rate = html.match(/data-optimization-metric="copay-rate"([\s\S]*?)(?=<div data-optimization-metric=|<\/dl>)/)?.[1];
    expect(rate).toContain("RATE-INPUT-MISSING");
    const drg = html.match(/data-optimization-metric="drg"([\s\S]*?)<\/dl>/)?.[1];
    expect(drg).not.toContain("RATE-INPUT-MISSING");
  });

  it.each(["en", "tr"] as const)("retains qualification, both savings and independent unavailable owners in %s", (locale) => {
    const labels = (locale === "en" ? enBilling : trBilling).sutOptimization;
    const optimization = {
      patient_id: "P-METRIC", n_diagnoses: 2, diagnoses: [], icd10_chapters: [],
      copay_exemptions: { exempt: true, n_qualifying: 2, qualifying_diagnoses: [{}, {}] },
      surcharge_exposure: { exactness_status: "exact", n_applicable_procedures: 3, n_total_ek2g: 3, exposure_rate: 1, applicable_rules: [] },
      copay_rate_exposure: { exactness_status: "exact", n_applicable_procedures: 4, n_total_ek2c1: 4, procedures_with_rates: [], mean_rate: 1, rate_distribution: {} },
      drg_unbundling: { exactness_status: "exact", has_unbundling_risk: true, n_chapters_analyzed: 1, chapter_analysis: [], total_potential_savings: 600, total_sourced_savings: 700 },
    } as unknown as PatientOptimization;
    const html = renderToStaticMarkupWithLocale(<SutOptimizationSection optimization={optimization} />, locale);
    for (const label of [labels.copayEyebrow, labels.surchargeEyebrow, labels.copayRateEyebrow, labels.drgEyebrow]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("EK-1A");
    expect(html).toContain(labels.ek1aQualifying.replace("{count}", "2"));
    expect(html).toContain(labels.flags.replace("{count}", "3"));
    expect(html).toContain(labels.cappedProcedures.replace("{count}", "4"));
    expect(html).toContain("high");
    expect(html).toContain("600.00 TRY");
    expect(html).toContain("700.00 TRY");
    expect(html).not.toContain('role="status"');
    for (const status of ["partial_exact", "missing_exact_inputs"] as const) {
      const unavailable = renderToStaticMarkupWithLocale(<SutOptimizationSection optimization={{
        ...optimization,
        surcharge_exposure: { ...optimization.surcharge_exposure, exactness_status: status, unavailable_reason: "SURCHARGE-MISSING" },
        copay_rate_exposure: { ...optimization.copay_rate_exposure, exactness_status: status, unavailable_reason: "RATE-MISSING" },
        drg_unbundling: { ...optimization.drg_unbundling!, exactness_status: status, unavailable_reason: "DRG-MISSING" },
      }} />, locale);
      for (const [key, reason] of [["surcharge", "SURCHARGE-MISSING"], ["copay-rate", "RATE-MISSING"], ["drg", "DRG-MISSING"]]) {
        const row = unavailable.match(new RegExp(`data-optimization-metric="${key}"([\\s\\S]*?)(?=<div data-optimization-metric=|</dl>)`))?.[1];
        expect(row).toContain(`role="status">${reason}`);
        expect(row?.match(/role="status"/g)).toHaveLength(1);
      }
      expect(unavailable).not.toContain("600.00 TRY");
      expect(unavailable).not.toContain("700.00 TRY");
      expect(unavailable).not.toContain("<details");
    }
  });
});

describe("BillingSummary open metric ownership", () => {
  it.each([
    ["en", "patient"], ["en", "bill"], ["tr", "patient"], ["tr", "bill"],
  ] as const)("omits only opted-in duplicate %s/%s identity and copy while keeping all unique content", (locale, scope) => {
    const labels = (locale === "en" ? enBilling : trBilling).summary;
    const base = {
      patient_id: "P-LONG-CONTEXT-IDENTITY-0001", claim_id: scope === "bill" ? "C-LONG-CONTEXT-IDENTITY-0001" : undefined,
      scope: scope === "bill" ? "bill" : undefined, exactness_status: "exact", priority: "high", total_recoverable_try: 10, sgk_uplift_try: 123456789012.34,
      compliance_adjustment_try: 20, audit_exposure_try: 30, capture_gap_try: 40, package_adequacy_review_try: 50,
      medula_playbook_entry_count: 6, drug_indication_violation_count: 7, action_count: 8, recommended_actions: [],
      copay: { exactness_status: "exact", is_exempt: true, patient_copay_waived_total_try: 90,
        ilave_ucret_total_try: 100, line_decomposition_status: "exact", rate_corrections: [] },
    } as unknown as BillingActionReport;
    for (const report of [base,
      { ...base, exactness_status: "partial_exact", unavailable_reason: "CONTEXT-PARTIAL",
        copay: { ...base.copay, line_decomposition_status: "copay_only" } },
      { ...base, total_recoverable_try: 0, sgk_uplift_try: 0 },
      { ...base, total_recoverable_try: null, sgk_uplift_try: null },
      { ...base, exactness_status: "missing_exact_inputs", unavailable_reason: "CONTEXT-MISSING" },
    ] as BillingActionReport[]) {
      const full = renderToStaticMarkupWithLocale(<BillingSummary billingReport={report} omitPriority />, locale);
      const compact = renderToStaticMarkupWithLocale(<BillingSummary billingReport={report} omitPriority omitHeaderContext />, locale);
      const fullClasses = full.match(/<div\b[^>]*data-billing-summary="true"[^>]*>/)?.[0].match(/class="([^"]+)"/)?.[1].split(" ");
      const compactClasses = compact.match(/<div\b[^>]*data-billing-summary="true"[^>]*>/)?.[0].match(/class="([^"]+)"/)?.[1].split(" ");
      expect(fullClasses).toContain("p-6");
      expect(fullClasses).not.toContain("p-4");
      expect(compactClasses).toContain("p-4");
      expect(compactClasses).not.toContain("p-6");
      expect(fullClasses).toContain("max-sm:p-3");
      expect(compactClasses).toContain("max-sm:p-3");
      const title = scope === "bill" ? labels.billTitle : labels.title;
      const description = scope === "bill" ? labels.billDescription : labels.description;
      const identity = scope === "bill" ? report.claim_id : report.patient_id;
      expect(full).toContain(identity);
      expect(full).toContain(description);
      expect(compact).not.toContain(identity);
      expect(compact).not.toContain(description);
      expect(compact).toContain(title);
      const chip = full.match(/<span class="inline-flex items-center[^"]*"[^>]*><span>[\s\S]*?<\/span><\/span>/)?.[0];
      expect(chip).toBeDefined();
      expect(compact.match(/<span class="inline-flex items-center[^"]*"[^>]*><span>[\s\S]*?<\/span><\/span>/)?.[0]).toBe(chip);
      expect(compact.match(/<dl\b[\s\S]*?<\/dl>/)?.[0]).toBe(full.match(/<dl\b[\s\S]*?<\/dl>/)?.[0]);
      expect(compact.slice(compact.indexOf("</dl>") + 5)).toBe(full.slice(full.indexOf("</dl>") + 5));
      expect(compact).not.toContain("<details");
    }
  });

  it.each(["en", "tr"] as const)("retains every label, amount, count, condition and report reason in %s", (locale) => {
    const labels = (locale === "en" ? enBilling : trBilling).summary;
    const report = {
      patient_id: "P-METRIC", claim_id: "C-METRIC", scope: "bill",
      exactness_status: "exact", priority: "high", total_recoverable_try: 10,
      sgk_uplift_try: 123456789012.34, compliance_adjustment_try: 20,
      audit_exposure_try: 30, capture_gap_try: 40, package_adequacy_review_try: 50,
      medula_playbook_entry_count: 6, drug_indication_violation_count: 7,
      action_count: 8, recommended_actions: [],
      copay: {
        exactness_status: "exact", is_exempt: true,
        patient_copay_waived_total_try: 90, ilave_ucret_total_try: 100,
        line_decomposition_status: "exact", rate_corrections: [],
      },
    } as unknown as BillingActionReport;
    const html = renderToStaticMarkupWithLocale(<BillingSummary billingReport={report} />, locale);
    const metrics = [
      ["sgk-uplift", labels.ruleCalculatedOpportunity, "123456789012.34 TRY"],
      ["compliance-adjustment", labels.complianceAdjustment, "20.00 TRY"],
      ["audit-exposure", labels.auditExposure, "30.00 TRY"],
      ["capture-gap", labels.captureGap, "40.00 TRY"],
      ["package-adequacy", labels.packageAdequacyReview, "50.00 TRY"],
      ["medula-playbook", labels.medulaPlaybook, "6"],
      ["drug-indication", labels.drugIndicationReview, "7"],
      ["exemption-gap", labels.exemptionGapCorrective, "90.00 TRY"],
      ["ilave-ucret", labels.ilaveUcretInfo, "100.00 TRY"],
      ["recommended-actions", labels.recommendedActions, "8"],
      ["priority", labels.priorityTier, "high"],
    ];
    expect([...html.matchAll(/data-billing-metric="([^"]+)"/g)].map((match) => match[1])).toEqual(metrics.map(([key]) => key));
    for (const [key, label, value] of metrics) {
      const row = html.match(new RegExp(`data-billing-metric="${key}"[^>]*>(.*?)</div>`))?.[1];
      expect(row).toContain(`<dt class=`);
      expect(row).toContain(label);
      expect(row).toContain(`<dd class=`);
      expect(row).toContain(value);
    }
    expect(html).toContain('data-billing-summary="true"');
    expect(html).toContain("@container/billing-summary");
    expect(html).toContain('<dl class="flex flex-wrap gap-x-6 gap-y-3">');
    expect(html.match(/@min-\[400px\]\/billing-summary:min-w-min/g)).toHaveLength(11);
    expect(html.match(/@min-\[400px\]\/billing-summary:basis-\[calc\(50%-0\.75rem\)\]/g)).toHaveLength(11);
    expect(html).not.toContain("overflow-x-auto");
    expect(html).not.toContain("overflow-hidden");
    expect(html).not.toContain("minmax(0,1fr)_auto");
    expect(html).toContain("C-METRIC");
    expect(html).toContain(labels.billDescription);
    expect(html).toContain(labels.dualTotalsFootnote);
    expect(html).toContain((locale === "en" ? enBilling : trBilling).copay.ilaveUcretFootnote);
    expect(html).not.toContain("<details");

    const partial = renderToStaticMarkupWithLocale(<BillingSummary billingReport={{
      ...report, exactness_status: "partial_exact", unavailable_reason: "REPORT-PARTIAL",
      copay: { ...report.copay, line_decomposition_status: "copay_only" },
    }} omitPriority />, locale);
    expect(partial).toContain('role="status">REPORT-PARTIAL');
    expect(partial).toContain((locale === "en" ? enBilling : trBilling).copay.partialDecompositionNotice);
    expect(partial).not.toContain('data-billing-metric="priority"');
    expect(partial).not.toContain('data-billing-metric="ilave-ucret"');
  });

  it.each(["en", "tr"] as const)("keeps exact zero, unknown and unavailable values separate in %s", (locale) => {
    for (const state of ["zero", "null", "unavailable"] as const) {
      const report = {
        patient_id: "P-METRIC", exactness_status: state === "unavailable" ? "missing_exact_inputs" : "exact",
        unavailable_reason: state === "unavailable" ? "TOTALS-MISSING" : undefined,
        priority: "low", total_recoverable_try: state === "zero" ? 0 : null,
        sgk_uplift_try: state === "zero" ? 0 : null,
        action_count: 0, recommended_actions: [],
        copay: { exactness_status: state === "unavailable" ? "missing_exact_inputs" : "exact",
          is_exempt: false, visit_copay_savings_try: state === "zero" ? 0 : null,
          rx_copay_savings_try: state === "zero" ? 0 : null, rate_corrections: [] },
      } as unknown as BillingActionReport;
      const html = renderToStaticMarkupWithLocale(<BillingSummary billingReport={report} />, locale);
      const metric = html.match(/data-billing-metric="sgk-uplift"[^>]*>(.*?)<\/div>/)?.[1];
      expect(metric).toContain(state === "zero" ? "0.00 TRY" : state === "null" ? ">—<" : locale === "en" ? "Unavailable" : "Kullanılamıyor");
      expect(html.match(/data-billing-metric=/g)).toHaveLength(4);
      if (state === "unavailable") {
        expect(html).toContain('role="status">TOTALS-MISSING');
        expect(html).toContain((locale === "en" ? enBilling : trBilling).summary.reviewSections);
        expect(html).not.toContain("0.00 TRY");
      }
    }
  });
});
