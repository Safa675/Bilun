import { createStore } from "zustand";
import type { StoreApi } from "zustand";
import type { NavigationStore } from "./storeInterfaces";

export function createNavigationStore(): StoreApi<NavigationStore> {
  return createStore<NavigationStore>((set) => ({
    showHowItWorks: false,
    showAdmin: false,
    aiDockPosition: "center",
    workspaceEntered: false,

    setShowHowItWorks: (showHowItWorks) => set({ showHowItWorks }),
    setShowAdmin: (showAdmin) => set({ showAdmin }),
    setAiDockPosition: (aiDockPosition) => set({ aiDockPosition }),
    setWorkspaceEntered: (workspaceEntered) => set({ workspaceEntered }),
  }));
}
