"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { deriveWorkspaceView } from "@/lib/workspaceTabs";
import { useWorkspaceStoreApi } from "@/stores/workspaceContext";

/**
 * Keeps the workspace tab store in sync with the route: the URL is the source
 * of truth, so any navigation (sidebar links, patient rows, tabs, back/forward)
 * opens and activates the matching tab.
 */
export default function WorkspaceRouteSync() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const store = useWorkspaceStoreApi();

  const view = deriveWorkspaceView(pathname, searchParams.get("tab"));
  const viewKind = view?.kind ?? null;
  const viewRefId = view?.refId ?? null;
  const viewQuery = view ? searchParams.toString() : null;

  useEffect(() => {
    if (viewKind && viewRefId) {
      store
        .getState()
        .syncFromRoute({ kind: viewKind, refId: viewRefId, query: viewQuery ?? undefined });
    }
  }, [viewKind, viewRefId, viewQuery, store]);

  return null;
}
