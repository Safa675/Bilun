import { ApiRequestError, buildApiUrl } from "../apiClient";

export interface HealthStatus {
  status: "ready" | "degraded";
  patients: number | null;
  build_id: string | null;
  message?: string;
}

/** Adapt the protected backend readiness contract, including a useful 503 body. */
export async function getHealthStatus(options?: RequestInit): Promise<HealthStatus> {
  let response: Response;
  try {
    response = await fetch(buildApiUrl("/api/health"), {
      ...options,
      credentials: "include",
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiRequestError("Health service unavailable", { code: "network_error", isNetworkError: true });
  }
  if (response.status !== 200 && response.status !== 503) {
    throw new ApiRequestError("Health request failed", { code: "http_error", status: response.status });
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiRequestError("Invalid health response", { code: "invalid_json" });
  }
  if (!payload || typeof payload !== "object") {
    throw new ApiRequestError("Invalid health response", { code: "invalid_json" });
  }
  const body = payload as Record<string, unknown>;
  if (
    body.service !== "bilun" ||
    body.status !== (response.status === 200 ? "ok" : "degraded") ||
    typeof body.database_reachable !== "boolean" || typeof body.cache_ready !== "boolean" ||
    !(body.active_build === null || typeof body.active_build === "string") ||
    (body.status === "ok" && (!body.database_reachable || !body.cache_ready || typeof body.active_build !== "string" || !body.active_build.trim()))
  ) {
    throw new ApiRequestError("Invalid health response", { code: "invalid_json" });
  }
  return {
    status: body.status === "ok" ? "ready" : "degraded",
    build_id: typeof body.active_build === "string" && body.active_build.trim() ? body.active_build : null,
    // Readiness does not currently expose a patient count. Never imply zero.
    patients: null,
  };
}
