import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { BillingActionReport } from "@/lib/domains/sut";
import {
  BillingStrategySection,
  CopayOptimizationSection,
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
    expect(html).not.toContain("katilimPayindanMuaf");
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
      <BillingStrategySection
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

    expect(html).toContain("Optional choice — §2.2.2.(2)");
    expect(html).toContain("Provider may choose method");
    expect(html).toContain("Difference if alternate method chosen");
    expect(html).toContain("compare package vs itemized");
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
});
