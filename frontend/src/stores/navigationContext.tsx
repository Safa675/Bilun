"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useStore } from "zustand";
import type { StoreApi } from "zustand";
import type { NavigationStore } from "./storeInterfaces";
import { createNavigationStore } from "./navigationStore";

interface NavigationContextValue {
  store: StoreApi<NavigationStore>;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

export function NavigationProvider({ children }: { children: ReactNode }) {
  const store = useMemo(() => createNavigationStore(), []);
  const value = useMemo(() => ({ store }), [store]);

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

export function useAiDockPosition() {
  return useNavigationStore((state) => state.aiDockPosition);
}

export function useSetAiDockPosition() {
  return useNavigationStore((state) => state.setAiDockPosition);
}
