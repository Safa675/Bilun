"use client";

import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeftRight, X } from "lucide-react";
import { SutPatientPageContent } from "@/app/patient/[id]/page";
import { useT } from "@/lib/i18n/useTranslations";
import { workspaceTabHref } from "@/lib/workspaceTabs";
import {
  useAiDockPosition,
  useNavigationStoreApi,
  useWorkspacePaneB,
  useWorkspaceStoreApi,
} from "@/stores/index";

/**
 * Two-pane workspace: pane A is the routed view (children); pane B renders a
 * second patient workspace for side-by-side comparison. Pane B is store-only
 * (not in the URL) per the workspace-shell plan.
 */
const noopSubscribe = () => () => {};

export default function WorkspaceSplitLayout({ children }: { children: ReactNode }) {
  const t = useT();
  const router = useRouter();
  const paneB = useWorkspacePaneB();
  const store = useWorkspaceStoreApi();
  const chatDock = useAiDockPosition();
  const navigationStore = useNavigationStoreApi();
  // The split state hydrates from sessionStorage, which the server cannot
  // see; gate it behind a mounted flag so hydration matches the SSR tree.
  const mounted = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const effectivePaneB = mounted ? paneB : null;

  // Right-docked chat is disabled while split is active (v1 scope).
  // setState, not the action: a layout rule must not overwrite the dock the user saved.
  useEffect(() => {
    if (paneB && chatDock === "right") navigationStore.setState({ aiDockPosition: "center" });
  }, [paneB, chatDock, navigationStore]);

  if (!effectivePaneB) {
    return <>{children}</>;
  }

  const handleSwap = () => {
    const { tabs, activeTabId, setPaneB } = store.getState();
    const activeTab = tabs.find((tab) => tab.id === activeTabId);
    router.push(workspaceTabHref(effectivePaneB));
    setPaneB(
      activeTab && activeTab.kind === "patient" && activeTab.id !== effectivePaneB.id
        ? activeTab.id
        : null,
    );
  };

  return (
    <div className="flex items-start" data-workspace-split>
      <div className="min-w-0 flex-1">{children}</div>
      <div
        className="min-w-0 flex-1 border-l border-[var(--border-subtle)]"
        data-workspace-pane="b"
      >
        <div className="sticky top-10 z-20 flex items-center justify-between gap-2 border-b border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-1.5">
          <span className="truncate font-mono text-xs font-medium text-[var(--text-secondary)]">
            {effectivePaneB.refId}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleSwap}
              aria-label={t("shell.workspaceTabs.swapPanes")}
              title={t("shell.workspaceTabs.swapPanes")}
              className="inline-flex h-6 w-6 items-center justify-center rounded-[var(--r-md)] text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-primary)] transition-colors"
            >
              <ArrowLeftRight className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => store.getState().closeSplit()}
              aria-label={t("shell.workspaceTabs.closeSplit")}
              title={t("shell.workspaceTabs.closeSplit")}
              className="inline-flex h-6 w-6 items-center justify-center rounded-[var(--r-md)] text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-primary)] transition-colors"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
        <SutPatientPageContent patientId={effectivePaneB.refId} embedded />
      </div>
    </div>
  );
}
