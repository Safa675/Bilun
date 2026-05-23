import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { BillingActionReport } from "@/lib/domains/sut";

const SYNTHETIC_DEMO_COPY = vi.hoisted(
  () => "Synthetic demo claims — SUT rule calculations are exact for this generated claim-line fixture.",
);

vi.mock("next/link", () => ({
  default: ({ children }: { children: unknown }) => children,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "P-001" }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/components/ui/PatientSearch", () => ({
  default: () => null,
}));

vi.mock("@/components/chat/SutInlineAIPanel", () => ({
  default: () => null,
  SUT_INLINE_CHAT_PANEL_WIDTH: 380,
}));

vi.mock("@/stores/index", () => ({
  useAiDockPosition: () => "center",
  useSetAiDockPosition: () => vi.fn(),
  useSutChatSession: () => ({ messages: [], autoText: "", autoFiredKey: "" }),
  useSetSutChatSession: () => vi.fn(),
}));

vi.mock("@/components/skeletons/SutSkeletons", () => ({
  SutBillingReportSkeleton: () => null,
}));

vi.mock("@/components/sut/SyntheticDemoProvenance", () => ({
  SYNTHETIC_DEMO_COPY,
  SyntheticDemoProvenance: () => <div>{SYNTHETIC_DEMO_COPY}</div>,
}));

vi.mock("@/lib/constants", () => ({
  buildSutBillingHref: (patientId: string) => `/patient/${patientId}/billing`,
  buildSutHomeHref: () => "/?tab=optimizer",
  SUT_BRAND: {
    moduleLabel: "BILUN",
    billingTitle: "Patient billing report",
    billingDescription: "Per-patient SUT rule review.",
  },
}));

vi.mock("@/lib/sutLabels", () => ({
  SUT_ALERT_BADGE_LABELS: {
    clear: "Clear",
    unavailable: "Unavailable",
    exempt: "Exempt",
    notExempt: "Not exempt",
  },
}));

vi.mock("@/lib/sutExactness", () => ({
  isExactOutput: (block: { exactness_status?: string | null; pricing_status?: string | null } | null | undefined) =>
    block?.exactness_status === "exact" || block?.pricing_status === "exact",
  hasRecoverableBillingTotals: (block: { exactness_status?: string | null; pricing_status?: string | null } | null | undefined) =>
    block?.exactness_status === "exact" ||
    block?.pricing_status === "exact" ||
    block?.exactness_status === "partial_exact",
  getUnavailableMessage: (
    block: { unavailable_reason?: string | null } | null | undefined,
    fallback: string,
  ) => block?.unavailable_reason ?? fallback,
}));

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
    accentAlpha: (opacity: number) => `rgba(5, 150, 105, ${opacity})`,
  },
}));

vi.mock("@/components/tabs/sut/shared", () => ({
  fmtLabel: (value: string) => value,
  fmtNum: (value: number) => String(value),
  fmtPriorityLabel: (value: string) => value,
  fmtRiskLabel: (value: string) => value,
  fmtTRY2: (value: number) => `${value.toFixed(2)} TRY`,
  fmtTRY2OrUnavailable: (value: number | null | undefined) => value == null ? "Unavailable" : `${value.toFixed(2)} TRY`,
  KpiCard: ({ label, value }: { label: string; value: string }) => <div>{label}:{value}</div>,
}));

vi.mock("@/lib/api/sut", () => ({
  getPatientBillingReport: vi.fn(),
  getPatientOptimization: vi.fn(),
  searchSutPatients: vi.fn(),
}));

import { BillingSummary } from "./page";

const baseReport: BillingActionReport = {
  patient_id: "P-001",
  data_source: {
    mode: "synthetic_demo",
    label: "Synthetic SUT demo claim data",
    is_synthetic: true,
    notice: "Demo data only. Rule calculations are exact for these synthetic claim lines.",
  },
  lab: {
    exactness_status: "exact",
    normative_cost_try: 0,
    hemogram_bundling_savings: 0,
    duplicate_test_savings: 0,
    flagged_tests: [],
  },
  drug: {
    exactness_status: "exact",
    generic_substitution_savings: 0,
    n_generics_available: 0,
    passivated_drug_count: 0,
    drug_recommendations: [],
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
  total_recoverable_try: 0,
  action_count: 0,
  priority: "low",
  exactness_status: "exact",
};

describe("BillingSummary provenance", () => {
  it("shows synthetic-demo provenance while preserving exact billing state", () => {
    const html = renderToStaticMarkup(<BillingSummary billingReport={baseReport} />);

    expect(html).toContain(SYNTHETIC_DEMO_COPY);
    expect(html).toContain("Rule-calculated opportunity");
    expect(html).not.toContain("Billing totals remain unavailable");
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });

  it("keeps unavailable billing state independent of synthetic provenance", () => {
    const unavailableReport: BillingActionReport = {
      ...baseReport,
      exactness_status: "missing_exact_inputs",
      unavailable_reason: "Needs exact claim sections.",
      required_inputs_missing: ["billing_sections"],
    };
    const html = renderToStaticMarkup(<BillingSummary billingReport={unavailableReport} />);

    expect(html).toContain(SYNTHETIC_DEMO_COPY);
    expect(html).toContain("Needs exact claim sections.");
    expect(html).toContain("Unavailable");
  });

  it("shows recoverable totals for partial exact reports", () => {
    const partialReport: BillingActionReport = {
      ...baseReport,
      exactness_status: "partial_exact",
      unavailable_reason: "Some sections are still partial.",
      required_inputs_missing: ["exactness_status"],
      total_recoverable_try: 22552.44,
      action_count: 28,
      priority: "medium",
    };
    const html = renderToStaticMarkup(<BillingSummary billingReport={partialReport} />);

    expect(html).toContain("22552.44 TRY");
    expect(html).toContain("Partial exact");
    expect(html).not.toContain("Rule-calculated opportunity:Unavailable");
  });
});
