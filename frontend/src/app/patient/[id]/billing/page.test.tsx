import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import type { BillingActionReport } from "@/lib/domains/sut";

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
  useSutChatSession: () => ({ messages: [], autoText: "", autoFiredKey: "", briefedContextKeys: [] }),
  useSetSutChatSession: () => vi.fn(),
}));

vi.mock("@/components/skeletons/SutSkeletons", () => ({
  SutBillingReportSkeleton: () => null,
}));

vi.mock("@/lib/constants", () => ({
  buildSutBillingHref: (patientId: string) => `/patient/${patientId}/billing`,
  buildSutHomeHref: () => "/?tab=compliance",
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

import { BillingSummary } from "@/components/patient/SutBillingReportSections";

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
  total_recoverable_try: 0,
  action_count: 0,
  priority: "low",
  exactness_status: "exact",
};

describe("BillingSummary", () => {
  it("shows exact billing state without inline provenance banner", () => {
    const html = renderToStaticMarkupWithLocale(<BillingSummary billingReport={baseReport} />);

    expect(html).toContain("SGK uplift (Kurum ödemesi)");
    expect(html).not.toContain("Synthetic demo claims");
    expect(html).not.toContain("Billing totals remain unavailable");
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });

  it("keeps unavailable billing state independent of provenance placement", () => {
    const unavailableReport: BillingActionReport = {
      ...baseReport,
      exactness_status: "missing_exact_inputs",
      unavailable_reason: "Needs exact claim sections.",
      required_inputs_missing: ["billing_sections"],
    };
    const html = renderToStaticMarkupWithLocale(<BillingSummary billingReport={unavailableReport} />);

    expect(html).toContain("Needs exact claim sections.");
    expect(html).toContain("Unavailable");
    expect(html).not.toContain("Synthetic demo claims");
  });

  it("applies the italic-gold serif treatment to the primary KPI money amount", () => {
    const exactReport: BillingActionReport = {
      ...baseReport,
      exactness_status: "exact",
      total_recoverable_try: 18450.5,
      action_count: 12,
      priority: "high",
    };
    const html = renderToStaticMarkupWithLocale(<BillingSummary billingReport={exactReport} />);

    // Italic-gold serif on the primary money amount (Stat display="gold")
    expect(html).toMatch(/italic[^>]*var\(--gold\)[\s\S]*?18450\.50 TRY/);
    expect(html).toContain("SGK uplift (Kurum ödemesi)");
    // legacy chrome must be absent
    expect(html).not.toContain("frost-panel");
    expect(html).not.toContain("sut-premium-panel");
    expect(html).not.toContain("sut-patient-id-title");
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
    const html = renderToStaticMarkupWithLocale(<BillingSummary billingReport={partialReport} />);

    expect(html).toContain("22552.44 TRY");
    expect(html).toContain("Partial exact");
    expect(html).not.toContain("Rule-calculated opportunity:Unavailable");
  });
});
