import { afterEach, describe, expect, it } from "vitest";
import { setModuleLocale } from "@/lib/i18n/localeModule";
import {
  formatExemptionCategory,
  formatExemptionBasisSummary,
  getExemptionCategories,
  hasEk1aExemption,
} from "./copayExemption";

describe("copayExemption helpers", () => {
  afterEach(() => setModuleLocale("en"));
  it("formats known exemption categories", () => {
    setModuleLocale("en");
    expect(formatExemptionCategory("ek1a_chronic")).toBe("EK-1A");
    expect(formatExemptionCategory("yesil_kart")).toBe("Green card");
    setModuleLocale("tr");
    expect(formatExemptionCategory("yesil_kart")).toBe("Yeşil kart");
  });

  it("localizes categories without changing their source identities", () => {
    setModuleLocale("en");
    expect(formatExemptionBasisSummary(["acil_servis", "is_kazasi_meslek"])).toBe("Emergency · Work injury / occupational disease");
    expect(formatExemptionCategory("future_source_category")).toBe("future source category");
    expect(formatExemptionCategory("acil_servis", () => "Localized emergency")).toBe("Localized emergency");
  });

  it("reads categories from exemption_sources", () => {
    const categories = getExemptionCategories({
      exempt: true,
      n_qualifying: 0,
      qualifying_diagnoses: [],
      exemption_sources: [
        { category: "acil_servis" },
        { category: "yesil_kart" },
      ],
      action: null,
    });
    expect(categories).toEqual(["acil_servis", "yesil_kart"]);
    expect(hasEk1aExemption(categories)).toBe(false);
  });

  it("falls back to ek1a when only qualifying diagnoses exist", () => {
    const categories = getExemptionCategories({
      exempt: true,
      n_qualifying: 1,
      qualifying_diagnoses: [{ icd10: "E11.9", disease: "DM", range: "E10-E14" }],
      action: null,
    });
    expect(categories).toEqual(["ek1a_chronic"]);
    expect(hasEk1aExemption(categories)).toBe(true);
  });
});
