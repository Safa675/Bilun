import { createStore } from "zustand";
import type { StoreApi } from "zustand";
import { DEFAULT_CHAT_DOCK, writeChatDock } from "@/lib/chatDockPreference";
import type { NavigationStore } from "./storeInterfaces";

export function createNavigationStore(): StoreApi<NavigationStore> {
  return createStore<NavigationStore>((set) => ({
    showHowItWorks: false,
    showAdmin: false,
    showReportProblem: false,
    aiDockPosition: DEFAULT_CHAT_DOCK,

    setShowHowItWorks: (showHowItWorks) => set({ showHowItWorks }),
    setShowAdmin: (showAdmin) => set({ showAdmin }),
    setShowReportProblem: (showReportProblem) => set({ showReportProblem }),
    // A user choice: remembered in this browser. Layout-forced changes use setState and are not remembered.
    setAiDockPosition: (aiDockPosition) => {
      writeChatDock(aiDockPosition);
      set({ aiDockPosition });
    },
  }));
}
