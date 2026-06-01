import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { BillingActionReport } from "@/lib/domains/sut";
import {
  BillingStrategySection,
  CopayOptimizationSection,
  DrugOptimizationSection,
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
  it("shows drug recommendations without TRY when section is not exact", () => {
    const html = renderToStaticMarkupWithLocale(
      <DrugOptimizationSection
        drugData={{
          exactness_status: "missing_exact_inputs",
          unavailable_reason: "Needs claim lines.",
          generic_substitution_savings: 0,
          n_generics_available: 1,
          passivated_drug_count: 0,
          drug_recommendations: [
            {
              drug_name: "Brand-X",
              issue: "generic_available",
              alternative: "Generic-X",
              savings_try: null,
            },
          ],
        }}
      />,
    );

    expect(html).toContain("Brand-X");
    expect(html).toContain("Generic-X");
    expect(html).toContain("Unavailable");
    expect(html).not.toContain("70.00 TRY");
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
    expect(html).not.toContain("Visit copay savings");
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
});
