"use client";

import SUTAnalyticsShell, { type SUTAnalyticsProps } from "./sut/SUTAnalyticsShell";

export type { SUTAnalyticsProps };

export default function SUTAnalytics(props: SUTAnalyticsProps) {
  return <SUTAnalyticsShell {...props} />;
}