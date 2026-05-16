import { describe, expect, it } from "vitest";

import {
  buildPatientAlertsQuery,
  clampAlertPage,
  parseAlertPageInput,
} from "./sutOptimizerHelpers";

describe("sutOptimizerHelpers", () => {
  it("builds offset-based patient alert queries", () => {
    expect(buildPatientAlertsQuery({
      category: "exemptions",
      status: "all",
      search: " 12345 ",
      page: 3,
    })).toEqual({
      category: "exemptions",
      status: "all",
      search: "12345",
      limit: 100,
      offset: 200,
    });
  });

  it("parses page jump input safely", () => {
    expect(parseAlertPageInput("42")).toBe(42);
    expect(parseAlertPageInput(" 004 ")).toBe(4);
    expect(parseAlertPageInput("2,727")).toBe(2727);
    expect(parseAlertPageInput("page")).toBeNull();
  });

  it("clamps page jumps into the valid range", () => {
    expect(clampAlertPage(0, 25)).toBe(1);
    expect(clampAlertPage(999, 25)).toBe(25);
    expect(clampAlertPage(8, 25)).toBe(8);
  });
});
