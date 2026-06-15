import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { canAccessRuleDatabase, setUserRole, UserRole } from "./userRole";

describe("canAccessRuleDatabase", () => {
  it("allows compliance_engineer, dev, and admin", () => {
    expect(canAccessRuleDatabase("compliance_engineer")).toBe(true);
    expect(canAccessRuleDatabase("dev")).toBe(true);
    expect(canAccessRuleDatabase("admin")).toBe(true);
  });

  it("denies billing_analyst", () => {
    expect(canAccessRuleDatabase("billing_analyst")).toBe(false);
  });
});

describe("setUserRole", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("persists role to localStorage and dispatches storage event", () => {
    const storage: Record<string, string> = {};
    const dispatchSpy = vi.fn(() => true);
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => storage[key] ?? null,
        setItem: (key: string, value: string) => {
          storage[key] = value;
        },
      },
      dispatchEvent: dispatchSpy,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });

    const role: UserRole = "billing_analyst";
    setUserRole(role);
    expect(storage["bilun_user_role"]).toBe("billing_analyst");
    expect(dispatchSpy).toHaveBeenCalled();
  });

  it("no-ops gracefully when window is undefined", () => {
    vi.stubGlobal("window", undefined);
    expect(() => setUserRole("billing_analyst")).not.toThrow();
  });
});
