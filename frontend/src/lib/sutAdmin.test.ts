import { describe, expect, it } from "vitest";

import { isSutAdminEnabled } from "./sutAdmin";

describe("isSutAdminEnabled", () => {
  it("only enables admin mode for the explicit ?admin=1 flag", () => {
    expect(isSutAdminEnabled("1")).toBe(true);
    expect(isSutAdminEnabled("0")).toBe(false);
    expect(isSutAdminEnabled("true")).toBe(false);
    expect(isSutAdminEnabled(undefined)).toBe(false);
    expect(isSutAdminEnabled(null)).toBe(false);
  });
});
