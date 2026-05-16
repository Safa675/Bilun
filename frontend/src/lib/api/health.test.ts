import { afterEach, describe, expect, it, vi } from "vitest";

import { getHealthStatus, rollbackCache } from "./health";

describe("SUT health API wrappers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches SUT health status from the shared health endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ready", patients: 24, build_id: "sut-build" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getHealthStatus()).resolves.toEqual({
      status: "ready",
      patients: 24,
      build_id: "sut-build",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/health",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("posts rollback requests to the admin endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", build_id: "previous-build" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(rollbackCache()).resolves.toEqual({
      status: "ok",
      build_id: "previous-build",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/admin/rollback",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
});
