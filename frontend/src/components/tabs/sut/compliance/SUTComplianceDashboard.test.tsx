import { describe, expect, it, vi } from "vitest";
import React from "react";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { SUTComplianceDashboard } from "./SUTComplianceDashboard";

const searchGet = vi.fn<(key: string) => string | null>(() => null);

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
  }),
  useSearchParams: () => ({
    get: (key: string) => searchGet(key),
    toString: () => "",
  }),
}));

vi.mock("@/lib/api/sut", () => ({
  getPatientAlerts: vi.fn().mockResolvedValue({
    patients: [],
    pagination: { total_matching: 0, limit: 50, offset: 0, has_more: false },
    metrics: {},
  }),
}));

describe("SUTComplianceDashboard", () => {
  it("renders only live exemption and surcharge subtabs", () => {
    searchGet.mockImplementation(() => null);
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
    );

    expect(html).toContain("Copay Exemptions");
    expect(html).toContain("Surcharge Compliance");
    expect(html).not.toContain("8 Boyutlu Denetim Aktif");
    expect(html).not.toContain("SUT Mevzuat ve Fatura Uyumluluk Merkezi");
    expect(html).not.toContain("Materials, UTS &amp; Pre-Auth");
    expect(html).not.toContain("MEDULA Rejection Playbook");
    expect(html).not.toContain("%98,4");
    expect(html).not.toContain("121.714");
  });

  it("renders live subtabs in Turkish", () => {
    searchGet.mockImplementation(() => null);
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
      "tr",
    );

    expect(html).toContain("Katılım Payı Muafiyetleri");
    expect(html).toContain("İlave Ücret &amp; Tavan Sınırı");
    expect(html).not.toContain("Tıbbi Malzeme");
    expect(html).not.toContain("MEDULA Red Kılavuzu");
  });

  it("falls back to exemptions when compTab is an unknown demo id", () => {
    searchGet.mockImplementation((key: string) => (key === "compTab" ? "materials" : null));
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
    );

    expect(html).toContain("Copay Exemptions");
    expect(html).not.toContain("OP1266");
    expect(html).not.toContain("Toplam Tıbbi Malzeme Riski");
  });
});
