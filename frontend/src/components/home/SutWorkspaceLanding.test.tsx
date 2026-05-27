import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/constants", () => ({
  SUT_BRAND: {
    moduleLabel: "BILUN",
    heroDescription: "Standalone SUT workspace",
  },
  buildSutHomeHref: (tab: string) => `/?tab=${tab}`,
}));

vi.mock("@/lib/api/sut", () => ({
  searchSutPatients: async () => ({ results: [], total: 0 }),
}));

vi.mock("@/lib/recents", () => ({
  useRecents: () => [],
}));

vi.mock("@/components/ui/PatientSearch", () => ({
  __esModule: true,
  default: ({ placeholder }: { placeholder?: string }) => (
    <input data-testid="patient-search" placeholder={placeholder} />
  ),
}));

import SutWorkspaceLanding from "./SutWorkspaceLanding";

describe("SutWorkspaceLanding", () => {
  function renderHtml() {
    return renderToStaticMarkup(
      <SutWorkspaceLanding
        onPatientSelect={() => undefined}
        onOpenBilling={() => undefined}
        onOpenTab={() => undefined}
        onOpenHowItWorks={() => undefined}
      />,
    );
  }

  it("does not render inline synthetic provenance (moved to AppTopBar chip)", () => {
    const html = renderHtml();
    expect(html).not.toContain("Synthetic demo claims");
    expect(html).not.toContain("Synthetic demo");
  });

  it("does not render the removed Billing rule intelligence hero", () => {
    const html = renderHtml();
    expect(html).not.toContain("Billing rule");
    expect(html).not.toContain("intelligence");
  });

  it("shows the recent-patients empty state when no recents are stored", () => {
    expect(renderHtml()).toContain("No recent patients yet");
    expect(renderHtml()).toContain("No recent billing reports yet");
  });

  it("does NOT render the deleted SutLandingHero marketing card copy", () => {
    const html = renderHtml();
    expect(html).not.toContain("Exact SUT rule visibility");
    expect(html).not.toContain("Exactness-aware optimization");
    expect(html).not.toContain("Product-owned SUT assistant");
    expect(html).not.toContain("Patient-first workspace");
    expect(html).not.toContain("Restore the SUT shell around exact claim-line rule work");
  });

  it("exposes Analytics, Optimizer, and How it works as tertiary nav", () => {
    const html = renderHtml();
    expect(html).toContain("SUT Analytics");
    expect(html).toContain("SUT Optimizer");
    expect(html).toContain("How it works");
  });
});
