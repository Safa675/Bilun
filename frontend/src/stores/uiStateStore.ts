import { createStore } from "zustand";
import type { StoreApi } from "zustand";
import type { UIStateStore } from "./storeInterfaces";

export function createUIStateStore(): StoreApi<UIStateStore> {
  return createStore<UIStateStore>((set, get) => ({
    healthStatus: null,
    sutChatSessions: {},

    setHealthStatus: (healthStatus) => set({ healthStatus }),
    setSutChatSession: (sessionKey, state) => {
      set({
        sutChatSessions: {
          ...get().sutChatSessions,
          [sessionKey]: {
            messages: [...state.messages],
            autoText: state.autoText,
            autoFiredKey: state.autoFiredKey,
            briefedContextKeys: [...(state.briefedContextKeys ?? [])],
          },
        },
      });
    },
    clearSutChatSession: (sessionKey) => {
      const nextSessions = { ...get().sutChatSessions };
      delete nextSessions[sessionKey];
      set({ sutChatSessions: nextSessions });
    },
  }));
}
