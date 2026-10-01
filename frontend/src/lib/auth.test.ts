import { describe, expect, it } from "vitest";
import { canUseBilling, canUseDeveloper, CLOSED_IDENTITY, parseSessionIdentity, requestsDeveloper } from "./auth";

describe("server session identity", () => {
  it("keeps anonymous billing closed until explicitly granted by the backend", () => {
    expect(canUseBilling(CLOSED_IDENTITY)).toBe(false);
    expect(canUseBilling({ ...CLOSED_IDENTITY, capabilities: ["billing"] })).toBe(false);
    expect(canUseBilling({ ...CLOSED_IDENTITY, public_billing_enabled: true, capabilities: ["billing"] })).toBe(true);
  });

  it("requires authentication, developer role and developer capability together", () => {
    const developer = { ...CLOSED_IDENTITY, authenticated: true, username: "tester", role: "dev" as const, capabilities: ["billing", "developer"] };
    expect(canUseDeveloper(developer)).toBe(true);
    expect(canUseDeveloper({ ...developer, authenticated: false })).toBe(false);
    expect(canUseDeveloper({ ...developer, role: "billing_officer" })).toBe(false);
    expect(canUseDeveloper({ ...developer, capabilities: ["billing"] })).toBe(false);
  });

  it("rejects incomplete or contradictory identity responses", () => {
    expect(parseSessionIdentity(CLOSED_IDENTITY)).toEqual(CLOSED_IDENTITY);
    for (const value of [null, { role: "dev" }, { ...CLOSED_IDENTITY, role: "dev" }, { ...CLOSED_IDENTITY, capabilities: "developer" }]) {
      expect(() => parseSessionIdentity(value)).toThrow();
    }
  });

  it("recognizes developer entry points independently of sidebar visibility", () => {
    expect(requestsDeveloper("/", new URLSearchParams("tab=rule-database"))).toBe(true);
    expect(requestsDeveloper("/", new URLSearchParams("admin=1"))).toBe(true);
    expect(requestsDeveloper("/design-system", new URLSearchParams())).toBe(true);
    expect(requestsDeveloper("/", new URLSearchParams("tab=reference-tools"))).toBe(false);
  });
});
