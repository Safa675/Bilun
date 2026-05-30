import { createStore } from "zustand";
import type { StoreApi } from "zustand";
import {
  EMPTY_SUT_INLINE_CHAT_STATE,
  type UIStateStore,
} from "./storeInterfaces";

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

export function getDefaultSutChatState() {
  return {
    ...EMPTY_SUT_INLINE_CHAT_STATE,
    messages: [...EMPTY_SUT_INLINE_CHAT_STATE.messages],
  };
}
