import { afterEach, describe, expect, it } from "vitest";
import { setModuleLocale } from "@/lib/i18n/localeModule";
import {
  formatExemptionCategory,
  formatExemptionBasisSummary,
  getCopayExemptionState,
  getExemptionCategories,
  getPrimaryExemptionGround,
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

  it("tells exempt, partial (EK-1A without a known report) and none apart", () => {
    const unmetEk1a = { category: "ek1a_chronic", counts_toward_exempt: false, missing_requirements: ["chronic_health_report"] };
    expect(getCopayExemptionState({ exempt: true, exemption_sources: [{ category: "acil_servis" }] })).toBe("exempt");
    // an exemption on another ground outranks the unmet EK-1A source
    expect(getCopayExemptionState({ exempt: true, exemption_sources: [unmetEk1a, { category: "acil_servis" }] })).toBe("exempt");
    expect(getCopayExemptionState({ exempt: false, partial_exempt: true })).toBe("partial");
    // a payload without the flag (the billing report's copay block): the EK-1A source that does not count
    expect(getCopayExemptionState({ exempt: false, exemption_sources: [unmetEk1a] })).toBe("partial");
    expect(getCopayExemptionState({ exempt: false, partial_exempt: false, exemption_sources: [] })).toBe("none");
    expect(getCopayExemptionState({ exempt: false })).toBe("none");
    // a source without the flag is an older payload: it is not read as unmet
    expect(getCopayExemptionState({ exempt: false, exemption_sources: [{ category: "ek1a_chronic" }] })).toBe("none");
    expect(getCopayExemptionState({ exempt: false, exemption_sources: [{ category: "ek4d_partial", counts_toward_exempt: false }] })).toBe("none");
  });

  it("names the ground of an exemption when the payload gives no primary category", () => {
    const unmetEk1a = { category: "ek1a_chronic", counts_toward_exempt: false };
    expect(getPrimaryExemptionGround({ exempt: true, primary_exemption_category: "yesil_kart" })).toBe("yesil_kart");
    // an alert row: the EK-1/A source that does not count is skipped
    expect(getPrimaryExemptionGround({ exempt: true, exemption_sources: [unmetEk1a, { category: "acil_servis", counts_toward_exempt: true }] })).toBe("acil_servis");
    expect(getPrimaryExemptionGround({ exempt: true, exemption_sources: [{ category: "ek1a_chronic" }] })).toBe("ek1a_chronic");
    expect(getPrimaryExemptionGround({ exempt: true, n_qualifying: 1 })).toBe("ek1a_chronic");
    expect(getPrimaryExemptionGround({ exempt: false, exemption_sources: [unmetEk1a] })).toBeNull();
    expect(getPrimaryExemptionGround({ exempt: true })).toBeNull();
  });
});
