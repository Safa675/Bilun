import { afterEach, expect, it, vi } from "vitest";
import { getHealthStatus } from "./health";
const healthy = { status: "ok", service: "bilun", database_reachable: true, cache_ready: true, active_build: "build-1" };
function respond(body: unknown, status = 200) {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", mock); return mock;
}
afterEach(() => vi.unstubAllGlobals());
it("uses the authenticated supported endpoint and adapts the actual backend DTO", async () => {
  const mock = respond(healthy);
  await expect(getHealthStatus()).resolves.toEqual({ status: "ready", patients: null, build_id: "build-1" });
  expect(mock).toHaveBeenCalledWith("http://localhost:8000/api/health", expect.objectContaining({ credentials: "include", cache: "no-store" }));
});
it.each([null, "", "build-old"])("retains valid degraded 503 diagnostics with build %s", async active_build => {
  respond({ ...healthy, status: "degraded", cache_ready: false, active_build }, 503);
  await expect(getHealthStatus()).resolves.toEqual({ status: "degraded", patients: null, build_id: active_build || null });
});
it.each([401, 403, 404, 500])("rejects HTTP %s rather than treating it as health", async status => {
  respond(healthy, status); await expect(getHealthStatus()).rejects.toMatchObject({ code: "http_error", status });
});
it.each([null, [], {}, { ...healthy, active_build: undefined }, { ...healthy, active_build: "" }, { ...healthy, active_build: "   " }, { ...healthy, cache_ready: "true" }, { ...healthy, status: "ready" }])("rejects malformed/legacy health body %j", async body => {
  respond(body); await expect(getHealthStatus()).rejects.toMatchObject({ code: "invalid_json" });
});
it("rejects a proxy 503 or a contradictory ok 503 body", async () => {
  respond(healthy, 503); await expect(getHealthStatus()).rejects.toMatchObject({ code: "invalid_json" });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>unavailable</html>", { status: 503 })));
  await expect(getHealthStatus()).rejects.toMatchObject({ code: "invalid_json" });
});
it("distinguishes transport failure and cancellation", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
  await expect(getHealthStatus()).rejects.toMatchObject({ code: "network_error", isNetworkError: true });
  const abort = new DOMException("aborted", "AbortError"); vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
  await expect(getHealthStatus()).rejects.toBe(abort);
});
