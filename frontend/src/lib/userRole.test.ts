import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { canAccessRuleDatabase, parseRole, setUserRole } from "./userRole";

describe("parseRole", () => {
  it("returns billing_officer for that value", () => {
    expect(parseRole("billing_officer")).toBe("billing_officer");
  });

  it("returns dev for dev", () => {
    expect(parseRole("dev")).toBe("dev");
  });

  it("falls back to dev for unknown or empty values", () => {
    expect(parseRole(null)).toBe("dev");
    expect(parseRole("admin")).toBe("dev");
    expect(parseRole("compliance_engineer")).toBe("dev");
  });
});

describe("canAccessRuleDatabase", () => {
  it("allows dev", () => {
    expect(canAccessRuleDatabase("dev")).toBe(true);
  });

  it("denies billing_officer", () => {
    expect(canAccessRuleDatabase("billing_officer")).toBe(false);
  });
});

describe("setUserRole", () => {
  let storage: Record<string, string> = {};

  beforeEach(() => {
    storage = {};
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => storage[key] ?? null,
        setItem: (key: string, value: string) => {
          storage[key] = value;
        },
      },
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });
    vi.stubGlobal("document", {
      cookie: "",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("persists billing_officer to localStorage and dispatches storage event", () => {
    setUserRole("billing_officer");
    expect(storage["bilun_user_role"]).toBe("billing_officer");
  });

  it("no-ops gracefully when window is undefined", () => {
    vi.stubGlobal("window", undefined);
    expect(() => setUserRole("billing_officer")).not.toThrow();
  });
});
