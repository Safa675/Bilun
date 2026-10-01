import { afterEach, describe, expect, it, vi } from "vitest";
import { CLOSED_IDENTITY } from "../auth";
import { endSession, getSessionIdentity } from "./auth";

afterEach(() => vi.unstubAllGlobals());

describe("session HTTP contract", () => {
  it("bypasses caches and includes the server cookie when refreshing identity", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json(CLOSED_IDENTITY));
    vi.stubGlobal("fetch", fetch);
    await expect(getSessionIdentity()).resolves.toEqual(CLOSED_IDENTITY);
    expect(fetch).toHaveBeenCalledWith("/api/auth/me", expect.objectContaining({ credentials: "include", cache: "no-store" }));
  });

  it("does not claim sign-out when the logout endpoint fails", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("failed", { status: 500 }));
    vi.stubGlobal("fetch", fetch);
    await expect(endSession()).rejects.toThrow("Sign out failed");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("verifies logout actually removed the session", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(Response.json({ ok: true })).mockResolvedValueOnce(Response.json({ ...CLOSED_IDENTITY, authenticated: true, username: "tester" }));
    vi.stubGlobal("fetch", fetch);
    await expect(endSession()).rejects.toThrow("still active");
  });

  it("returns the public rollout state after confirmed sign-out", async () => {
    const next = { ...CLOSED_IDENTITY, public_billing_enabled: true, capabilities: ["billing"] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json({ ok: true })).mockResolvedValueOnce(Response.json(next)));
    await expect(endSession()).resolves.toEqual(next);
  });
});
