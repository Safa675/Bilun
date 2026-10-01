import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "./middleware";
import { CLOSED_IDENTITY } from "./lib/auth";

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

function identityResponse(extra = {}) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ...CLOSED_IDENTITY, ...extra })));
}

describe("page authorization middleware", () => {
  it("only opens billing after the backend enables public access", async () => {
    identityResponse();
    expect((await middleware(new NextRequest("http://app/"))).headers.get("location")).toBe("http://app/login");
    identityResponse({ public_billing_enabled: true, capabilities: ["billing"] });
    for (const path of ["/", "/patient/P-1", "/patient/P-1/billing", "/?tab=reference-tools"]) {
      identityResponse({ public_billing_enabled: true, capabilities: ["billing"] });
      const response = await middleware(new NextRequest(`http://app${path}`));
      expect(response.headers.get("location")).toBeNull();
      expect(response.headers.get("cache-control")).toBe("private, no-store");
    }
  });

  it.each(["/?tab=rule-database", "/?admin=1", "/design-system"])("denies %s even with a forged browser mode", async (path) => {
    identityResponse({ public_billing_enabled: true, capabilities: ["billing"] });
    const response = await middleware(new NextRequest(`http://app${path}`, { headers: { cookie: "bilun:role=dev; bilun:session=forged" } }));
    expect(response.headers.get("location")).toBe("http://app/login?access=developer");
  });

  it("forwards the cookie to the direct backend, never trusting a browser-selected origin", async () => {
    vi.stubEnv("API_PROXY_TARGET", "http://backend.internal:8002");
    identityResponse({ authenticated: true, username: "tester", role: "dev", capabilities: ["billing", "developer"] });
    const response = await middleware(new NextRequest("http://untrusted-host/?tab=rule-database", { headers: { cookie: "bilun:session=test" } }));
    expect(response.headers.get("location")).toBeNull();
    expect(fetch).toHaveBeenCalledWith("http://backend.internal:8002/api/auth/me", expect.objectContaining({ cache: "no-store", headers: { Cookie: "bilun:session=test" } }));
  });

  it("fails closed on backend errors and never redirects APIs to login HTML", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    expect((await middleware(new NextRequest("http://app/"))).headers.get("location")).toBe("http://app/login");
    expect((await middleware(new NextRequest("http://app/api/rules"))).headers.get("location")).toBeNull();
    expect((await middleware(new NextRequest("http://app/.env"))).status).toBe(404);
  });
});
