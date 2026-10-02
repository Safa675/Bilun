import { afterEach, describe, expect, it } from "vitest";
import { fmtDate, fmtDateTime } from "./formatters";
import { setModuleLocale } from "./localeModule";
afterEach(() => setModuleLocale("en"));
describe.each(["UTC", "Europe/Istanbul", "America/Los_Angeles"])("civil dates with requested zone %s", zone => {
  it.each(["2026-09-01", "2024-02-29", "2026-01-01", "2026-12-31"])("preserves %s", value => {
    expect(fmtDate(value, { year: "numeric", month: "2-digit", day: "2-digit", timeZone: zone }))
      .toBe(new Date(value).toLocaleDateString("en-US", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: "UTC" }));
  });
  it("keeps timestamp instant semantics", () => {
    const value = "2026-01-01T00:30:00Z";
    const options = { year: "numeric", month: "2-digit", day: "2-digit", timeZone: zone } as const;
    expect(fmtDate(value, options)).toBe(new Date(value).toLocaleDateString("en-US", options));
    expect(fmtDateTime(value, { timeZone: zone })).toBe(new Date(value).toLocaleString("en-US", { timeZone: zone }));
  });
});
it("preserves the date in Turkish and keeps invalid/empty fallbacks", () => {
  setModuleLocale("tr"); expect(fmtDate("2024-02-29")).toBe("29 Şub 2024");
  expect(fmtDate(null)).toBe("—"); expect(fmtDate("")).toBe("—"); expect(fmtDate("bad-date-value")).toBe("bad-date-v");
  expect(fmtDate("2026-02-30")).toBe("2026-02-30");
});
