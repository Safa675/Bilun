import { afterEach, describe, expect, it, vi } from "vitest";
import { CLOSED_IDENTITY } from "@/lib/auth";
import { POST } from "./route";

afterEach(() => vi.unstubAllGlobals());

describe("local feedback access boundary", () => {
  it("does not send or accept feedback without billing permission", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(CLOSED_IDENTITY)));
    const response = await POST(new Request("http://app/api/feedback", { method: "POST", body: "{}" }));
    expect(response.status).toBe(401);
  });

  it("bounds anonymous feedback before JSON parsing or email work", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ...CLOSED_IDENTITY, public_billing_enabled: true, capabilities: ["billing"] })));
    const response = await POST(new Request("http://app/api/feedback", { method: "POST", body: "x".repeat(16385) }));
    expect(response.status).toBe(413);
  });

  it("preserves the honeypot without sending email", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ...CLOSED_IDENTITY, public_billing_enabled: true, capabilities: ["billing"] })));
    const response = await POST(new Request("http://app/api/feedback", { method: "POST", body: JSON.stringify({ website: "spam" }) }));
    expect(await response.json()).toEqual({ ok: true });
  });
});
