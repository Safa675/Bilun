import { createStore } from "zustand";
import type { StoreApi } from "zustand";
import {
  applyWorkspaceClose,
  applyWorkspaceSync,
  readWorkspaceSession,
  type WorkspaceSessionState,
  type WorkspaceView,
} from "@/lib/workspaceTabs";

export interface WorkspaceStore extends WorkspaceSessionState {
  syncFromRoute: (view: WorkspaceView) => void;
  closeTab: (id: string) => string | null;
}

export function createWorkspaceStore(
  initial?: WorkspaceSessionState | null,
): StoreApi<WorkspaceStore> {
  const session = initial ?? readWorkspaceSession();
  return createStore<WorkspaceStore>((set, get) => ({
    tabs: session?.tabs ?? [],
    activeTabId: session?.activeTabId ?? null,

    syncFromRoute: (view) => {
      const { tabs, activeTabId } = get();
      const next = applyWorkspaceSync(tabs, activeTabId, view, Date.now());
      if (next.tabs === tabs && next.activeTabId === activeTabId) return;
      set(next);
    },

    closeTab: (id) => {
      const { tabs, activeTabId } = get();
      const next = applyWorkspaceClose(tabs, activeTabId, id);
      set({ tabs: next.tabs, activeTabId: next.activeTabId });
      return next.navigateTo;
    },
  }));
}
