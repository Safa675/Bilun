"use client";

import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import { useStore } from "zustand";
import type { StoreApi } from "zustand";
import { writeWorkspaceSession } from "@/lib/workspaceTabs";
import { createWorkspaceStore, type WorkspaceStore } from "./workspaceStore";

const WorkspaceContext = createContext<{ store: StoreApi<WorkspaceStore> } | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const store = useMemo(() => createWorkspaceStore(), []);

  useEffect(() => {
    const unsubscribe = store.subscribe((state) => {
      writeWorkspaceSession({ tabs: state.tabs, activeTabId: state.activeTabId });
    });
    return unsubscribe;
  }, [store]);

  const value = useMemo(() => ({ store }), [store]);
  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaceStoreApi(): StoreApi<WorkspaceStore> {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspaceStoreApi must be used within a WorkspaceProvider");
  }
  return context.store;
}

export function useWorkspaceTabs() {
  const store = useWorkspaceStoreApi();
  return useStore(store, (state) => state.tabs);
}

export function useWorkspaceActiveTabId() {
  const store = useWorkspaceStoreApi();
  return useStore(store, (state) => state.activeTabId);
}
