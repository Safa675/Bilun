"use client";

import dynamic from "next/dynamic";

// Client-only: the strip hydrates from sessionStorage, which the server
// cannot see; rendering it client-side avoids a hydration mismatch.
const WorkspaceTabStrip = dynamic(() => import("@/components/shell/WorkspaceTabStrip"), {
  ssr: false,
});

export default function WorkspaceTabStripMount() {
  return <WorkspaceTabStrip />;
}
