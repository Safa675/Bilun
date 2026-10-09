import { afterEach, describe, expect, it } from "vitest";
import { fmtTRY, fmtTRY2 } from "./formatters";
import { setModuleLocale } from "./localeModule";
import {
  fmtTRY as sharedTRY,
  fmtTRY2 as sharedTRY2,
  fmtTRY2OrUnavailable,
} from "@/components/tabs/sut/shared";

afterEach(() => setModuleLocale("en"));

describe.each([
  { locale: "en", rounded: "1,235 TRY", amount: "1,234.56 TRY", zero: "0.00 TRY", negative: "-1,234.56 TRY", unavailable: "Unavailable" },
  { locale: "tr", rounded: "₺1.235", amount: "₺1.234,56", zero: "₺0,00", negative: "₺-1.234,56", unavailable: "Kullanılamıyor" },
] as const)("canonical TRY formatting in $locale", (messages) => {
  it("keeps the established whole-money and two-decimal display contracts", () => {
    setModuleLocale(messages.locale);
    expect(fmtTRY(1234.56)).toBe(messages.rounded);
    expect(fmtTRY2(1234.56)).toBe(messages.amount);
    expect(fmtTRY2(0)).toBe(messages.zero);
    expect(fmtTRY2(-1234.56)).toBe(messages.negative);
  });

  it("uses the same formatter through the existing UI wrappers without coercing missing values", () => {
    setModuleLocale(messages.locale);
    expect(sharedTRY(1234.56)).toBe(fmtTRY(1234.56));
    expect(sharedTRY2(1234.56)).toBe(fmtTRY2(1234.56));
    expect(fmtTRY2OrUnavailable(0)).toBe(messages.zero);
    expect(fmtTRY2OrUnavailable(null)).toBe(messages.unavailable);
    expect(fmtTRY2OrUnavailable(undefined)).toBe(messages.unavailable);
  });
});
