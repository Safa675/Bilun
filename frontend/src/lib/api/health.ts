import { fetchJSON } from "../apiClient";

export interface HealthStatus {
  status: "ready" | "building" | "error" | "not_started";
  patients: number;
  build_id: string;
  message?: string;
}

export async function getHealthStatus(options?: RequestInit): Promise<HealthStatus> {
  return fetchJSON<HealthStatus>("/api/health", options);
}
