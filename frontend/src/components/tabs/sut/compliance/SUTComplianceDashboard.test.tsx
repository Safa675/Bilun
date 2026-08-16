import { describe, expect, it, vi } from "vitest";
import React from "react";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { SUTComplianceDashboard } from "./SUTComplianceDashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => "/sut",
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
  }),
  useSearchParams: () => ({
    get: (k: string) => (k === "compTab" ? "materials" : null),
    toString: () => "compTab=materials",
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
  it("renders 8 compliance subtabs correctly with default English locale", () => {
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
    );

    expect(html).toContain("SUT Mevzuat ve Fatura Uyumluluk Merkezi");
    expect(html).toContain("8 Boyutlu Denetim Aktif");
    expect(html).toContain("Copay Exemptions");
    expect(html).toContain("Surcharge Compliance");
    expect(html).toContain("Materials, UTS &amp; Pre-Auth");
    expect(html).toContain("Payment Method &amp; DRG Packages");
    expect(html).toContain("Surgical &amp; Session Modifiers");
    expect(html).toContain("Diagnostics &amp; Lab Errors");
    expect(html).toContain("Pre-Flight Docs &amp; FI");
    expect(html).toContain("MEDULA Rejection Playbook");
  });

  it("renders 8 compliance subtabs correctly with Turkish locale", () => {
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
      "tr",
    );

    expect(html).toContain("Katılım Payı Muafiyetleri");
    expect(html).toContain("İlave Ücret &amp; Tavan Sınırı");
    expect(html).toContain("Tıbbi Malzeme, ÜTS &amp; Ön Onay");
    expect(html).toContain("Fatura Yöntemi &amp; DRG Paket");
    expect(html).toContain("Cerrahi &amp; Seans Katsayıları");
    expect(html).toContain("Laboratuvar &amp; Tetkik Hataları");
    expect(html).toContain("Gönderim Evrakları &amp; FI");
    expect(html).toContain("MEDULA Red Kılavuzu");
  });

  it("renders the active materials module when compTab=materials", () => {
    const html = renderToStaticMarkupWithLocale(
      <SUTComplianceDashboard
        cohortPatientIds={new Set()}
        cohortFilterActive={false}
      />,
    );

    expect(html).toContain("Toplam Tıbbi Malzeme Riski");
    expect(html).toContain("Ön Onay Eksikliği");
    expect(html).toContain("OP1266");
    expect(html).toContain("ÜTS Bildirim Eksik");
    expect(html).toContain("Pakete Dahil Sarf");
  });
});
