import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { BillingActionReport } from "@/lib/domains/sut";
import {
  BillingStrategySection,
  CopayOptimizationSection,
  DrgUpliftSection,
  MaterialsPreCheckSection,
  OptionalOverrideSection,
} from "./SutBillingReportSections";

vi.mock("@/lib/sutLabels", () => ({
  getSutAlertBadgeLabel: (key: string) => key,
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
    expect(html).toContain("110.00 TRY");
    expect(html).toContain("Compliance correction");
    expect(html).toContain("Exemption gap");
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
    expect(html).toContain("Payment method compliance issues");
    expect(html).toContain("14637.06 TRY");
    expect(html).not.toContain("0.00 TRY");
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
    expect(html).toContain("1200.00 TRY");
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
});
