"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useStore } from "zustand";
import type { StoreApi } from "zustand";
import type {
  SutInlineChatState,
  UIStateStore,
} from "./storeInterfaces";
import { EMPTY_SUT_INLINE_CHAT_STATE } from "./storeInterfaces";
import { createUIStateStore } from "./uiStateStore";

interface UIStateContextValue {
  store: StoreApi<UIStateStore>;
}

const UIStateContext = createContext<UIStateContextValue | null>(null);

export function UIStateProvider({ children }: { children: ReactNode }) {
  const store = useMemo(() => createUIStateStore(), []);
  const value = useMemo(() => ({ store }), [store]);

  return (
    <UIStateContext.Provider value={value}>
      {children}
    </UIStateContext.Provider>
  );
}

export function useUIStateStore<T>(selector: (state: UIStateStore) => T): T {
  const context = useContext(UIStateContext);
  if (!context) {
    throw new Error("useUIStateStore must be used within a UIStateProvider");
  }
  return useStore(context.store, selector);
}

export function useHealthStatus() {
  return useUIStateStore((state) => state.healthStatus);
}

export function useSetHealthStatus() {
  return useUIStateStore((state) => state.setHealthStatus);
}

export function useSutChatSession(sessionKey: string): SutInlineChatState {
  return useUIStateStore(
    (state) => state.sutChatSessions[sessionKey] ?? EMPTY_SUT_INLINE_CHAT_STATE,
  );
}

export function useSetSutChatSession() {
  return useUIStateStore((state) => state.setSutChatSession);
}
