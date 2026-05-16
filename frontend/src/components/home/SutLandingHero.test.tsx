import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const SYNTHETIC_DEMO_COPY = vi.hoisted(
  () => "Synthetic demo claims — SUT rule calculations are exact for this generated claim-line fixture.",
);

vi.mock("@/lib/constants", () => ({
  SUT_BRAND: {
    moduleLabel: "ILAY SUT",
    heroDescription: "Standalone SUT workspace",
  },
}));

vi.mock("@/components/sut/SyntheticDemoProvenance", () => ({
  SYNTHETIC_DEMO_COPY,
  SyntheticDemoProvenance: () => <div>{SYNTHETIC_DEMO_COPY}</div>,
}));

import SutLandingHero from "./SutLandingHero";

describe("SutLandingHero provenance", () => {
  it("renders synthetic-demo provenance on the landing shell", () => {
    const html = renderToStaticMarkup(
      <SutLandingHero
        onEnter={() => undefined}
        onOpenHowItWorks={() => undefined}
        dataSource={{
          mode: "synthetic_demo",
          label: "Synthetic SUT demo claim data",
          is_synthetic: true,
          notice: "Demo data only. Rule calculations are exact for these synthetic claim lines.",
        }}
      />,
    );

    expect(html).toContain(SYNTHETIC_DEMO_COPY);
    expect(html).not.toContain("Actual reimbursement recovery");
    expect(html).not.toContain("Hospital-wide loss");
    expect(html).not.toContain("Production billing result");
    expect(html).not.toContain("Real savings");
  });
});
