import { createStore } from "zustand";
import type { StoreApi } from "zustand";
import {
  applyWorkspaceClose,
  applyWorkspaceSync,
  ensureWorkspaceTab,
  readWorkspaceSession,
  type WorkspaceSessionState,
  type WorkspaceView,
} from "@/lib/workspaceTabs";

export interface WorkspaceStore extends WorkspaceSessionState {
  syncFromRoute: (view: WorkspaceView) => void;
  closeTab: (id: string) => string | null;
  /** Open a patient in split pane B without leaving the current view. */
  openSplit: (view: WorkspaceView) => void;
  setPaneB: (tabId: string | null) => void;
  closeSplit: () => void;
  /** Ctrl+K quick-open palette visibility (UI-only, not persisted). */
  quickOpen: boolean;
  setQuickOpen: (open: boolean) => void;
}

export function createWorkspaceStore(
  initial?: Partial<WorkspaceSessionState> | null,
): StoreApi<WorkspaceStore> {
  const session = initial ?? readWorkspaceSession();
  return createStore<WorkspaceStore>((set, get) => ({
    tabs: session?.tabs ?? [],
    activeTabId: session?.activeTabId ?? null,
    paneBTabId: session?.paneBTabId ?? null,

    syncFromRoute: (view) => {
      const { tabs, activeTabId, paneBTabId } = get();
      const next = applyWorkspaceSync(tabs, activeTabId, view, Date.now());
      const paneBCleared = paneBTabId !== null && next.activeTabId === paneBTabId;
      if (
        next.tabs === tabs &&
        next.activeTabId === activeTabId &&
        !paneBCleared
      ) {
        return;
      }
      set({
        tabs: next.tabs,
        activeTabId: next.activeTabId,
        ...(paneBCleared ? { paneBTabId: null } : {}),
      });
    },

    closeTab: (id) => {
      const { tabs, activeTabId, paneBTabId } = get();
      const next = applyWorkspaceClose(tabs, activeTabId, id);
      set({
        tabs: next.tabs,
        activeTabId: next.activeTabId,
        ...(paneBTabId === id ? { paneBTabId: null } : {}),
      });
      return next.navigateTo;
    },

    openSplit: (view) => {
      if (view.kind !== "patient") return;
      const { tabs, activeTabId } = get();
      const next = ensureWorkspaceTab(tabs, activeTabId, view, Date.now());
      set({ tabs: next.tabs, paneBTabId: next.tabId });
    },

    setPaneB: (tabId) => {
      if (tabId === null) {
        set({ paneBTabId: null });
        return;
      }
      const { tabs } = get();
      const tab = tabs.find((entry) => entry.id === tabId);
      set({ paneBTabId: tab && tab.kind === "patient" ? tabId : null });
    },

    closeSplit: () => {
      set({ paneBTabId: null });
    },

    quickOpen: false,
    setQuickOpen: (open) => {
      set({ quickOpen: open });
    },
  }));
}
