"use client";

import { createContext, useContext, useLayoutEffect, useMemo, type ReactNode } from "react";
import { useStore } from "zustand";
import type { StoreApi } from "zustand";
import type { NavigationStore } from "./storeInterfaces";
import { readChatDock } from "@/lib/chatDockPreference";
import { createNavigationStore } from "./navigationStore";

interface NavigationContextValue {
  store: StoreApi<NavigationStore>;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

export function NavigationProvider({ children }: { children: ReactNode }) {
  const store = useMemo(() => createNavigationStore(), []);
  const value = useMemo(() => ({ store }), [store]);

  // The server and the first client render use the default dock, so hydration matches the server HTML;
  // the saved choice is applied before the first paint after hydration. setState, not the action: no write.
  useLayoutEffect(() => {
    const saved = readChatDock();
    if (saved !== store.getState().aiDockPosition) store.setState({ aiDockPosition: saved });
  }, [store]);

  return (
    <NavigationContext.Provider value={value}>
      {children}
    </NavigationContext.Provider>
  );
}

export function useNavigationStore<T>(selector: (state: NavigationStore) => T): T {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error("useNavigationStore must be used within a NavigationProvider");
  }
  return useStore(context.store, selector);
}

export function useShowHowItWorks() {
  return useNavigationStore((state) => state.showHowItWorks);
}

export function useSetShowHowItWorks() {
  return useNavigationStore((state) => state.setShowHowItWorks);
}

export function useShowAdmin() {
  return useNavigationStore((state) => state.showAdmin);
}

export function useSetShowAdmin() {
  return useNavigationStore((state) => state.setShowAdmin);
}

export function useNavigationStoreApi(): StoreApi<NavigationStore> {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error("useNavigationStore must be used within a NavigationProvider");
  }
  return context.store;
}

export function useShowReportProblem() {
  return useNavigationStore((state) => state.showReportProblem);
}

export function useSetShowReportProblem() {
  return useNavigationStore((state) => state.setShowReportProblem);
}

export function useAiDockPosition() {
  return useNavigationStore((state) => state.aiDockPosition);
}

export function useSetAiDockPosition() {
  return useNavigationStore((state) => state.setAiDockPosition);
}

