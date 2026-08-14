import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtTRYFixture } from "@/test/fmtMoney";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/hooks/useStaggeredReveal", () => ({
  default: () => ({
    getRevealProps: () => ({
      staggerAttrs: {},
      staggerClass: "",
      staggerStyle: undefined,
    }),
  }),
}));

vi.mock("@/lib/configContext", () => ({
  useConfig: () => ({
    regulatory: {
      ek1a_exemption_count: 1,
      ek2g_procedure_count: 1,
      ek2c1_procedure_count: 1,
    },
    sut_data_source: {
      mode: "synthetic_demo",
      label: "Synthetic SUT demo claim data",
      is_synthetic: true,
      notice: "Demo data only. Rule calculations are exact for these synthetic claim lines.",
    },
  }),
}));

vi.mock("@/components/ui/PatientSearch", () => ({
  default: () => null,
}));

vi.mock("@/components/skeletons/SutSkeletons", () => ({
  SutAlertTableSkeleton: () => null,
}));

vi.mock("@/lib/apiClient", () => ({
  ApiRequestError: class ApiRequestError extends Error {
    isNetworkError = false;
  },
}));

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
    accentAlpha: (opacity: number) => `rgba(5, 150, 105, ${opacity})`,
  },
}));

vi.mock("@/lib/sutExactness", () => ({
  isExactOutput: (block: { exactness_status?: string | null; pricing_status?: string | null } | null | undefined) =>
    block?.exactness_status === "exact" || block?.pricing_status === "exact",
  getUnavailableMessage: (
    block: { unavailable_reason?: string | null } | null | undefined,
    fallback: string,
  ) => block?.unavailable_reason ?? fallback,
}));

vi.mock("@/lib/sutLabels", () => ({
  SUT_ACTION_LABELS: { noActionNeeded: "No action needed" },
  SUT_ALERT_BADGE_LABELS: {
    clear: "Clear",
    unavailable: "Unavailable",
    exempt: "Exempt",
    notExempt: "Not exempt",
    flagged: "Flagged",
  },
}));

vi.mock("@/components/tabs/sut/shared", () => ({
  fmtLabel: (value: string) => value,
  fmtNum: (value: number) => String(value),
  fmtNumOrUnavailable: (value: number | null | undefined) => value == null ? "Unavailable" : String(value),
  fmtPctRatio: (value: number) => `${(value * 100).toFixed(0)}%`,
  fmtPriorityLabel: (value: string) => value,
  fmtTRY: (value: number) => `${value} TRY`,
  fmtTRYOrUnavailable: (value: number | null | undefined) => value == null ? "Unavailable" : `${value} TRY`,
  fmtTRY2OrUnavailable: (value: number | null | undefined) => value == null ? "Unavailable" : `${value.toFixed(2)} TRY`,
  KpiCard: ({ label, value }: { label: string; value: string; sub?: string }) => <div>{label}:{value}</div>,
}));

vi.mock("@/lib/constants", () => ({
  buildSutBillingHref: (patientId: string) => `/patient/${patientId}/billing`,
}));

vi.mock("@/lib/api/sut", () => ({
  getPatientAlerts: vi.fn(),
  getRevenueRecovery: vi.fn(),
  getOptimizationSummary: vi.fn(),
  searchSutPatients: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ children }: { children: unknown }) => children,
}));

vi.mock("@/hooks/useCohortFilter", () => ({
  useCohortFilter: () => ({
    filter: { q: "", sex: "", ageMin: null, ageMax: null, doctor: "" },
    isActive: false,
    activeTab: "compliance",
    setFilter: vi.fn(),
    clearFilter: vi.fn(),
  }),
}));

import SUTOptimizer, { DrgUnbundlingInline } from "./SUTOptimizerTab";
import type { OptimizationSummary } from "@/lib/domains/sut";

describe("SUTOptimizer shell", () => {
  it("renders section navigation without inline provenance banner", () => {
    const html = renderToStaticMarkupWithLocale(<SUTOptimizer />);

    expect(html).toContain("Copay Exemptions");
    expect(html).toContain("Surcharge Compliance");
    expect(html).not.toContain("EK-2C-1 Copay Rate Compliance");
    expect(html).not.toContain("Synthetic demo claims");
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });
});

describe("Revenue recovery optimization panels", () => {
  it("shows methodology for exact DRG unbundling instead of unavailable banner", () => {
    const totalPotentialSavings = 121738.79;
    const data = {
      drg_unbundling: {
        exactness_status: "exact",
        n_patients_checked: 50,
        n_patients_with_risk: 19,
        risk_rate: 0.38,
        total_potential_savings: totalPotentialSavings,
        top_risky_chapters: [{ chapter: "I", count: 3 }],
        methodology: "Aggregated per-patient DRG unbundling findings from exact claim lines.",
      },
    } as unknown as OptimizationSummary;

    const html = renderToStaticMarkupWithLocale(<DrgUnbundlingInline data={data} />);

    expect(html).toContain("Aggregated per-patient DRG unbundling findings from exact claim lines.");
    expect(html).not.toContain("Unavailable:DRG unbundling risk is unavailable");
    expect(html).toContain("Patients With Risk:19");
    expect(html).toContain(`Claim-backed savings:${fmtTRYFixture(totalPotentialSavings)}`);
  });

  it("shows unavailable banner for missing DRG inputs", () => {
    const data = {
      drg_unbundling: {
        exactness_status: "missing_exact_inputs",
        unavailable_reason: "Missing itemized billed procedure lines.",
        n_patients_checked: 50,
        n_patients_with_risk: null,
        risk_rate: null,
        total_potential_savings: null,
        top_risky_chapters: [],
        methodology: "",
      },
    } as unknown as OptimizationSummary;

    const html = renderToStaticMarkupWithLocale(<DrgUnbundlingInline data={data} />);

    expect(html).toContain("Missing itemized billed procedure lines.");
    expect(html).toContain("Unavailable");
    expect(html).toContain("Patients With Risk:Unavailable");
  });

});
