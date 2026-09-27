import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { fmtDate } from "@/lib/i18n/formatters";

vi.mock("../useSutApi", () => ({
  useSutApi: () => ({ loading: false, error: null, data: {
    bundled_consumables: { count: 1, items: [{
      item_name: "Eldiven (cerrahi steril eldiven hariç)", description: "EK-3B-1",
      bundled_in: "EK-3B-1", effective_date: "2026-01-31", evaluation_status: "not_evaluated",
    }] },
    exclusion_categories: { count: 1, categories: [{
      section: "EK-3B-2 Madde 1", material_name: "Viskosüplemantasyon (SUT ekleri hariç)",
      description: "SUT ekleri hariç", effective_date: "2026-01-31", evaluation_status: "not_evaluated",
    }] },
  } }),
}));

import { BundledConsumablesSection } from "./BundledConsumablesSection";

describe("annex source catalog", () => {
  it("shows source conditions without a blanket denial or stale effective date", () => {
    const html = renderToStaticMarkupWithLocale(<BundledConsumablesSection />);
    expect(html).toContain("EK-3B-2 Source Catalog");
    expect(html).toContain("Claim not evaluated");
    expect(html).toContain("cerrahi steril eldiven hariç");
    expect(html).toContain("SUT ekleri hariç");
    expect(html).not.toContain("Non-Reimbursable");
    expect(html).not.toContain("Effective Date");
    expect(html).not.toContain(fmtDate("2026-01-31"));
  });

  it("preserves the same source-only distinction in Turkish", () => {
    const html = renderToStaticMarkupWithLocale(<BundledConsumablesSection />, "tr");
    expect(html).toContain("EK-3B-2 Kaynak Kataloğu");
    expect(html).toContain("Fatura değerlendirilmedi");
    expect(html).not.toContain("Yürürlük Tarihi");
    expect(html).not.toContain(fmtDate("2026-01-31"));
  });
});
