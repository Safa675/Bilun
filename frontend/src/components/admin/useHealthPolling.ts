"use client";

import { useEffect } from "react";
import { getHealthStatus, type HealthStatus } from "@/lib/api/health";

export function useHealthPolling(enabled: boolean, setStatus: (status: HealthStatus | null) => void) {
  useEffect(() => {
    if (!enabled) return;
    let controller: AbortController | null = null;
    const poll = () => {
      controller?.abort();
      const current = new AbortController();
      controller = current;
      getHealthStatus({ signal: current.signal })
        .then(status => {
          if (!current.signal.aborted && controller === current) setStatus(status);
        })
        .catch(() => {
          // A failed current poll must not leave an old green readiness result.
          if (!current.signal.aborted && controller === current) setStatus(null);
        });
    };
    poll();
    const timer = window.setInterval(poll, 30_000);
    return () => {
      controller?.abort();
      window.clearInterval(timer);
    };
  }, [enabled, setStatus]);
}
