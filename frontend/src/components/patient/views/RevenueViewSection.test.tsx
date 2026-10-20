import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { WorkspaceProvider } from "@/stores/workspaceContext";
import type { BillingActionReport } from "@/lib/domains/sut";
import RevenueViewSection from "./RevenueViewSection";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

const off = { available: false, unavailable_reason: "wavea_capability_unavailable", total_rows: null, rows: [], has_more: false };
const report = {
  patient_id: "P-REV",
  priority: "low",
  total_recoverable_try: 0,
  action_count: 0,
  recommended_actions: [],
  copay: { is_exempt: false, rate_corrections: [] },
  financial_findings: off,
} as unknown as BillingActionReport;

describe("RevenueViewSection extended financial evidence", () => {
  it.each([
    ["tr", "Genişletilmiş kanıt katmanı bu derlemede etkin değil; bu katmanın kayıtları ve kapsam sayıları gösterilemiyor. Bu, sıfır bulgu olduğu anlamına gelmez."],
    ["en", "The extended evidence layer is not active in this build, so its records and coverage counts cannot be shown. This does not mean zero findings."],
  ] as const)("shows the layer-off notice once and no count (%s)", (locale, notice) => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider><RevenueViewSection billingReport={report} /></WorkspaceProvider>,
      locale,
    );
    expect(html.split(notice)).toHaveLength(2);
    expect(html).not.toContain("Wave A");
    expect(html).not.toContain('id="wavea-financial"');
  });

  it("keeps the section when the financial evidence is there", () => {
    const html = renderToStaticMarkupWithLocale(
      <WorkspaceProvider>
        <RevenueViewSection billingReport={{
          ...report,
          financial_findings: { available: true, unavailable_reason: null, total_rows: 0, rows: [], has_more: false },
        } as unknown as BillingActionReport} />
      </WorkspaceProvider>,
      "en",
    );
    expect(html).toContain('id="wavea-financial"');
    expect(html).not.toContain('id="wavea-unavailable"');
  });
});
