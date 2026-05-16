"use client";

import type { HealthStatus } from "@/lib/api/health";
import { theme } from "@/lib/theme";

function statusColor(status: HealthStatus["status"] | "unavailable"): string {
  switch (status) {
    case "ready":
      return theme.accent;
    case "building":
      return "#B45309";
    case "error":
    case "not_started":
    case "unavailable":
    default:
      return "#B91C1C";
  }
}

export default function SutHealthPanel({ healthStatus }: { healthStatus: HealthStatus | null }) {
  const resolvedStatus = healthStatus?.status ?? "unavailable";

  return (
    <div className="frost-panel" style={{ padding: 16, display: "flex", alignItems: "center", gap: 16, fontSize: 12 }}>
      <span style={{ fontWeight: 700, color: "#71717A", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        Admin
      </span>
      <span style={{ color: "#71717A" }}>
        Status:{" "}
        <strong style={{ color: statusColor(resolvedStatus) }}>
          {resolvedStatus}
        </strong>
      </span>
      <span style={{ color: "#71717A" }}>
        Patients: {healthStatus?.patients ?? "—"}
      </span>
      <span style={{ color: "#71717A" }}>
        Build: <code style={{ fontSize: 11 }}>{healthStatus?.build_id ?? "—"}</code>
      </span>
      {healthStatus?.message && (
        <span style={{ color: "#71717A" }}>{healthStatus.message}</span>
      )}
    </div>
  );
}
