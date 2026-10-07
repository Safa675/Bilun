import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtTRY2Fixture } from "@/test/fmtMoney";

vi.mock("@/components/tabs/sut/shared", () => ({
  fmtNum: (value: number) => String(value),
  fmtTRY2: (value: number) => `${value.toFixed(2)} TRY`,
  fmtPriorityLabel: (value: string) => value,
}));

vi.mock("@/lib/theme", () => ({
  theme: { accent: "#059669" },
}));

vi.mock("@/lib/sutExactness", () => ({
  isExactOutput: (block: { exactness_status?: string | null } | null | undefined) =>
    block?.exactness_status === "exact",
  hasRecoverableBillingTotals: (block: { exactness_status?: string | null } | null | undefined) =>
    block?.exactness_status === "exact" || block?.exactness_status === "partial_exact",
}));

import { PatientFinancialSummary } from "./PatientFinancialSummary";
import type { BillingActionReport, SutPatientOutcomeData } from "@/lib/domains/sut";

const baseBillingReport: BillingActionReport = {
  patient_id: "P-001",
  lab: {
    exactness_status: "exact",
    normative_cost_try: 0,
    hemogram_bundling_savings: 0,
    flagged_tests: [],
  },
  copay: {
    exactness_status: "exact",
    is_exempt: false,
    exemption_disease: "",
    exemption_range: "",
    visit_copay_savings_try: 0,
    rx_copay_savings_try: 0,
    total_copay_savings_try: 0,
    rate_corrections: [],
  },
  billing_strategy: {
    exactness_status: "exact",
    recommendations: [],
  },
  materials: {
    exactness_status: "exact",
    pre_auth_required: [],
    miat_restricted: [],
    gazette_ceiling_by_specialty: {},
  },
  total_recoverable_try: 1750,
  sgk_uplift_try: 1750,
  action_count: 5,
  priority: "high",
  exactness_status: "exact",
};

describe("PatientFinancialSummary", () => {
  it("renders all-bills totals and recoverable priority", () => {
    const claimTotals = {
      exactness_status: "exact" as const,
      patient_id: "P-001",
      total_billed_try: 12000,
      total_expected_payable_try: 9600,
      claim_count: 3,
      procedure_line_count: 10,
      material_line_count: 2,
      drug_line_count: 1,
      lab_billed_line_count: 4,
    };
    const outcome: SutPatientOutcomeData = {
      sut_claim_totals: claimTotals,
    };

    const html = renderToStaticMarkupWithLocale(
      <PatientFinancialSummary outcome={outcome} billingReport={baseBillingReport} />,
    );

    expect(html).toContain("All bills at a glance");
    expect(html).toContain(fmtTRY2Fixture(claimTotals.total_billed_try));
    expect(html).toContain(fmtTRY2Fixture(claimTotals.total_expected_payable_try));
    expect(html).toContain(fmtTRY2Fixture(baseBillingReport.total_recoverable_try!));
    expect(html).toContain("3");
    expect(html).toContain("high");
  });

  it("returns null when no financial inputs are available", () => {
    const html = renderToStaticMarkupWithLocale(
      <PatientFinancialSummary outcome={null} billingReport={null} />,
    );

    expect(html).toBe("");
  });
});
