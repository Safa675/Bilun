import { describe, expect, it } from "vitest";
import {
  normalizeEkCatalogHint,
  parseEkAnnexLabels,
  resolveBillingEkAnnexLabels,
} from "./sutRegulatorySources";

describe("sutRegulatorySources", () => {
  it("parses multiple annex labels from rule_source text", () => {
    expect(
      parseEkAnnexLabels(
        "SUT §2.2 prose rules (payment_method_2_2) + EK-2B/EK-2C catalog membership",
      ),
    ).toEqual(["EK-2B", "EK-2C"]);
  });

  it("normalizes EK-1/A style references", () => {
    expect(parseEkAnnexLabels("SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions")).toEqual([
      "EK-1A",
    ]);
  });

  it("prefers per-row catalog hints for billing rows", () => {
    expect(resolveBillingEkAnnexLabels("EK-2B/EK-2C gazette repricing", "ek2b")).toEqual([
      "EK-2B",
    ]);
    expect(normalizeEkCatalogHint("ek2c")).toBe("EK-2C");
  });
});
