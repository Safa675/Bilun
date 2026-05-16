import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/theme", () => ({
  theme: {
    accent: "#059669",
    accentDark: "#047857",
    accentAlpha: (opacity: number) => `rgba(5, 150, 105, ${opacity})`,
  },
}));

import {
  buildSutBillingHref,
  buildSutHomeHref,
  buildSutPatientHref,
  parseSutHomeTab,
  SUT_HOME_TABS,
} from "./constants";

describe("sut constants", () => {
  it("parses home tab query parameters safely", () => {
    expect(parseSutHomeTab("analytics")).toBe("analytics");
    expect(parseSutHomeTab("optimizer")).toBe("optimizer");
    expect(parseSutHomeTab("unknown")).toBe("analytics");
    expect(parseSutHomeTab(null)).toBe("analytics");
  });

  it("builds split SUT navigation routes", () => {
    expect(buildSutHomeHref("analytics")).toBe("/?tab=analytics");
    expect(buildSutHomeHref("optimizer")).toBe("/?tab=optimizer");
    expect(buildSutPatientHref("A 123/45")).toBe("/patient/A%20123%2F45");
    expect(buildSutBillingHref("A 123/45")).toBe("/patient/A%20123%2F45/billing");
  });

  it("defines the expected split SUT tabs", () => {
    expect(SUT_HOME_TABS.map((tab) => tab.id)).toEqual(["analytics", "optimizer"]);
  });
});
