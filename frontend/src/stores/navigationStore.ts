import { createStore } from "zustand";
import type { StoreApi } from "zustand";
import type { NavigationStore } from "./storeInterfaces";

export function createNavigationStore(): StoreApi<NavigationStore> {
  return createStore<NavigationStore>((set) => ({
    showHowItWorks: false,
    showAdmin: false,
    showReportProblem: false,
    aiDockPosition: "center",

    setShowHowItWorks: (showHowItWorks) => set({ showHowItWorks }),
    setShowAdmin: (showAdmin) => set({ showAdmin }),
    setShowReportProblem: (showReportProblem) => set({ showReportProblem }),
    setAiDockPosition: (aiDockPosition) => set({ aiDockPosition }),
  }));
}
