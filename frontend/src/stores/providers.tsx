"use client";

import type { ReactNode } from "react";
import { RoleProvider, useSessionIdentity } from "@/components/shell/RoleProvider";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import type { Locale } from "@/lib/i18n/types";
import { canUseDeveloper, type SessionIdentity } from "@/lib/auth";
import { ConfigProvider } from "@/lib/configContext";
import { NavigationProvider } from "./navigationContext";
import { UIStateProvider } from "./uiStateContext";
import { WorkspaceProvider } from "./workspaceContext";

export function ShellStateProviders({
  children,
  initialLocale,
  initialIdentity,
}: {
  children: ReactNode;
  initialLocale?: Locale;
  initialIdentity?: SessionIdentity;
}) {
  return (
    <LocaleProvider initialLocale={initialLocale}>
      <RoleProvider initialIdentity={initialIdentity}>
        <SessionStores>{children}</SessionStores>
      </RoleProvider>
    </LocaleProvider>
  );
}

function SessionStores({ children }: { children: ReactNode }) {
  const developer = canUseDeveloper(useSessionIdentity());
  return (
        <ConfigProvider>
          <NavigationProvider>
          <WorkspaceProvider developer={developer}>
            <UIStateProvider>{children}</UIStateProvider>
          </WorkspaceProvider>
          </NavigationProvider>
        </ConfigProvider>
  );
}

export { LocaleProvider };
