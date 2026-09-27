import { afterEach, describe, expect, it, vi } from "vitest";

import { validateSutClaim } from "./sut";

const claim = { claim_id: "C1", procedure_code: "", materials: [] };

afterEach(() => vi.unstubAllGlobals());

describe("validator response version boundary", () => {
  it("marks new requests explicitly and preserves caller headers and cancellation", async () => {
    const payload = { contract_version: 2, is_valid: null, violations: [], advisories: [] };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    const result = await validateSutClaim(claim, {
      signal: controller.signal,
      headers: new Headers({ "X-Test": "preserved", "X-Bilun-Validation-Contract": "1" }),
    });
    expect(result).toEqual(payload);
    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.get("X-Bilun-Validation-Contract")).toBe("2");
    expect(headers.get("X-Test")).toBe("preserved");
    expect(options.signal).toBe(controller.signal);
  });

  it.each([undefined, 1, 3])("rejects an old or unknown backend contract %s", async (version) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      contract_version: version, is_valid: true, violations: [],
    }), { status: 200 })));
    await expect(validateSutClaim(claim)).rejects.toThrow(/upgrade|yenileyin/i);
  });

  it("shows the server upgrade error without retrying or silently using legacy", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "Sayfayı yenileyin / Reload or upgrade this client.",
    }), { status: 409 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(validateSutClaim(claim)).rejects.toThrow("Sayfayı yenileyin");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
