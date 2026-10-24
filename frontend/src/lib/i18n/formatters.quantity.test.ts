import { afterEach, describe, expect, it } from "vitest";
import { fmtNum, fmtQuantity } from "./formatters";
import { fmtQuantity as barrelQuantity } from "./index";
import { setModuleLocale } from "./localeModule";

afterEach(() => setModuleLocale("en"));

// A drug quantity is a decimal box count since #302 (MEDULA keys 0.5 kutu).
describe.each([
  { locale: "en", half: "0.5", oneAndHalf: "1.5", two: "2", grouped: "4,000", groupedDecimal: "1,234.5", sixteenth: "0.0625", nearMax: "998.125", tenth: "0.3", negative: "-0.5", rounded: "1,235" },
  { locale: "tr", half: "0,5", oneAndHalf: "1,5", two: "2", grouped: "4.000", groupedDecimal: "1.234,5", sixteenth: "0,0625", nearMax: "998,125", tenth: "0,3", negative: "-0,5", rounded: "1.235" },
] as const)("line quantity formatting in $locale", (messages) => {
  it("shows a decimal quantity with its decimals in the locale", () => {
    setModuleLocale(messages.locale);
    expect(fmtQuantity(0.5)).toBe(messages.half);
    expect(fmtQuantity(1.5)).toBe(messages.oneAndHalf);
    expect(fmtQuantity(1234.5)).toBe(messages.groupedDecimal);
    expect(fmtQuantity(-0.5)).toBe(messages.negative);
  });

  it("keeps every decimal a hospital keys, not three, and no binary noise", () => {
    setModuleLocale(messages.locale);
    expect(fmtQuantity(0.0625)).toBe(messages.sixteenth);
    expect(fmtQuantity(998.125)).toBe(messages.nearMax);
    expect(fmtQuantity(0.3)).toBe(messages.tenth);
    expect(fmtQuantity(0.1 + 0.2)).toBe(messages.tenth);
  });

  it("shows an integer without decimals, exactly as the whole-number formatter does", () => {
    setModuleLocale(messages.locale);
    expect(fmtQuantity(2)).toBe(messages.two);
    expect(fmtQuantity(2.0)).toBe(messages.two);
    expect(fmtQuantity(4000)).toBe(messages.grouped);
    for (const whole of [0, 1, 2, 3, 30, 999, 4000, 123456, -2]) {
      expect(fmtQuantity(whole)).toBe(fmtNum(whole));
    }
  });

  it("leaves the whole-number formatter rounding for its other callers", () => {
    setModuleLocale(messages.locale);
    expect(fmtNum(0.5)).toBe("1");
    expect(fmtNum(1.5)).toBe("2");
    expect(fmtNum(1234.56)).toBe(messages.rounded);
  });

  it("is exported from the i18n barrel", () => {
    setModuleLocale(messages.locale);
    expect(barrelQuantity(0.5)).toBe(messages.half);
  });
});
