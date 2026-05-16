"use client";

import type { ReactNode } from "react";
import { NavigationProvider } from "./navigationContext";
import { UIStateProvider } from "./uiStateContext";

export function ShellStateProviders({ children }: { children: ReactNode }) {
  return (
    <NavigationProvider>
      <UIStateProvider>{children}</UIStateProvider>
    </NavigationProvider>
  );
}
