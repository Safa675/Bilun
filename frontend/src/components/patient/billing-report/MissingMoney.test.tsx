import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { BillingActionReport } from "@/lib/domains/sut";
import { BillingSummary } from "./BillingSummary";
import { CopayOptimizationSection } from "./CopayOptimizationSection";
import { LabOptimizationSection } from "./LabOptimizationSection";
import { BloodComponentUpliftSection } from "./BloodComponentUpliftSection";
import { MaterialUpliftSection } from "./MaterialUpliftSection";
import { ProcedureAddonUpliftSection } from "./ProcedureAddonUpliftSection";
import { DrgUpliftSection } from "./DrgUpliftSection";
import { ProcedureCaptureGapSection } from "./ProcedureCaptureGapSection";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

const report = (amount: number | null): BillingActionReport => ({
  patient_id: "SYNTHETIC-MONEY",
  exactness_status: "exact",
  total_recoverable_try: amount,
  sgk_uplift_try: amount,
  action_count: 0,
  priority: "low",
  copay: {
    exactness_status: "exact",
    is_exempt: true,
    exemption_disease: "",
    exemption_range: "",
    visit_copay_savings_try: amount,
    rx_copay_savings_try: amount,
    total_copay_savings_try: amount,
    patient_copay_waived_total_try: amount,
    rate_corrections: [],
  },
  lab: {
    exactness_status: "exact",
    normative_cost_try: null,
    hemogram_bundling_savings: amount,
    session_fraction_savings: amount,
    flagged_tests: [{
      test_name: "Synthetic lab", sut_code: "SYNTHETIC-LAB", gazette_price: 1,
      flag_type: "hemogram_unbundling", savings_try: null,
    }],
  },
  billing_strategy: { exactness_status: "exact", recommendations: [] },
  materials: {
    exactness_status: "exact", pre_auth_required: [], miat_restricted: [],
    gazette_ceiling_by_specialty: {},
  },
});

function headerTotal(html: string): string {
  const total = /font-mono text-sm font-semibold tabular-nums[^>]*>([^<]*)</.exec(html);
  expect(total).not.toBeNull();
  return (total as RegExpExecArray)[1];
}

describe("uncomputed backend money displays", () => {
  it.each(["en", "tr"] as const)("keeps populated summary values in container-aware tracks (%s)", (locale) => {
    const populated = {
      ...report(29039.29),
      audit_exposure_try: 53437.9,
      package_adequacy_review_try: 1,
      action_count: 26,
      copay: {
        ...report(14508.48).copay,
        ilave_ucret_total_try: 9354.77,
        line_decomposition_status: "exact" as const,
      },
    };
    const html = renderToStaticMarkupWithLocale(<BillingSummary billingReport={populated} omitPriority />, locale);
    expect(html).toContain("data-billing-summary");
    expect(html).toContain("@min-[400px]/billing-summary:basis-[calc(50%-0.75rem)]");
    expect(html).not.toMatch(/(?:md|xl):grid-cols-/);
    expect(html).toContain("@min-[220px]");
    expect(html).toContain("max-sm:p-3");
    expect(html).toContain("@min-[180px]");
    for (const value of locale === "tr"
      ? ["₺29.039,29", "₺53.437,90", "₺1,00", "₺14.508,48", "₺9.354,77"]
      : ["29,039.29 TRY", "53,437.90 TRY", "1.00 TRY", "14,508.48 TRY", "9,354.77 TRY"]) {
      expect(html).toContain(value);
    }
    expect(html).toContain(">26<");
  });

  it.each(["en", "tr"] as const)("keeps missing and zero separate in summary and copay (%s)", (locale) => {
    const zeroLabel = locale === "tr" ? "₺0,00" : "0.00 TRY";
    const missingSummary = renderToStaticMarkupWithLocale(<BillingSummary billingReport={report(null)} />, locale);
    const zeroSummary = renderToStaticMarkupWithLocale(<BillingSummary billingReport={report(0)} />, locale);
    expect(missingSummary).toContain("—");
    expect(missingSummary).not.toContain(zeroLabel);
    expect(zeroSummary).toContain(zeroLabel);
    const missingCopay = renderToStaticMarkupWithLocale(<CopayOptimizationSection copayData={report(null).copay} />, locale);
    const zeroCopay = renderToStaticMarkupWithLocale(<CopayOptimizationSection copayData={report(0).copay} />, locale);
    expect(headerTotal(missingCopay)).toBe("—");
    expect(headerTotal(zeroCopay)).toBe(zeroLabel);
  });

  it("does not display a partial lab sum as a complete total", () => {
    const lab = { ...report(20).lab, session_fraction_savings: null };
    expect(headerTotal(renderToStaticMarkupWithLocale(<LabOptimizationSection labData={lab} />, "en"))).toBe("—");
    expect(headerTotal(renderToStaticMarkupWithLocale(<LabOptimizationSection labData={report(0).lab} />, "en"))).toBe("0.00 TRY");
  });

  it.each([
    ["blood", BloodComponentUpliftSection, "bloodData"],
    ["material", MaterialUpliftSection, "materialData"],
    ["addon", ProcedureAddonUpliftSection, "addonData"],
    ["drg", DrgUpliftSection, "drgData"],
    ["capture", ProcedureCaptureGapSection, "captureData"],
  ] as const)("shows an absent %s header as a dash and a computed zero as zero", (_name, Section, prop) => {
    for (const amount of [null, 0]) {
      const data = {
        exactness_status: "exact",
        opportunities: [{ claim_id: "SYNTHETIC-CLAIM", procedure_code: "SYNTHETIC-PROC" }],
        confirmed_uplift_try: amount,
        confirmed_gap_try: amount,
        total_gap_try: amount,
      };
      const Component = Section as unknown as React.ComponentType<Record<string, unknown>>;
      const html = renderToStaticMarkupWithLocale(<Component {...{ [prop]: data }} />, "en");
      expect(headerTotal(html)).toBe(amount == null ? "—" : "0.00 TRY");
    }
  });
});
