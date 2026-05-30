"use client";

import type { ReactNode } from "react";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { NavigationProvider } from "./navigationContext";
import { UIStateProvider } from "./uiStateContext";

export function ShellStateProviders({ children }: { children: ReactNode }) {
  return (
    <LocaleProvider>
      <NavigationProvider>
        <UIStateProvider>{children}</UIStateProvider>
      </NavigationProvider>
    </LocaleProvider>
  );
}

export { LocaleProvider };
