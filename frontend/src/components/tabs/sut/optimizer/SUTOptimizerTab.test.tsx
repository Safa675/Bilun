import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

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
  KpiCard: ({ label, value }: { label: string; value: string }) => <div>{label}:{value}</div>,
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

import SUTOptimizer from "./SUTOptimizerTab";

describe("SUTOptimizer shell", () => {
  it("renders section navigation without inline provenance banner", () => {
    const html = renderToStaticMarkup(<SUTOptimizer />);

    expect(html).toContain("Compliance Alerts");
    expect(html).not.toContain("Synthetic demo claims");
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });
});
