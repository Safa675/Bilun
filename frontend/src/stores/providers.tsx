"use client";

import type { ReactNode } from "react";
import { RoleProvider } from "@/components/shell/RoleProvider";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import type { Locale } from "@/lib/i18n/types";
import type { UserRole } from "@/lib/userRole";
import { NavigationProvider } from "./navigationContext";
import { UIStateProvider } from "./uiStateContext";
import { WorkspaceProvider } from "./workspaceContext";

export function ShellStateProviders({
  children,
  initialLocale,
  initialRole,
}: {
  children: ReactNode;
  initialLocale?: Locale;
  initialRole?: UserRole;
}) {
  return (
    <LocaleProvider initialLocale={initialLocale}>
      <RoleProvider initialRole={initialRole}>
        <NavigationProvider>
          <WorkspaceProvider>
            <UIStateProvider>{children}</UIStateProvider>
          </WorkspaceProvider>
        </NavigationProvider>
      </RoleProvider>
    </LocaleProvider>
  );
}

export { LocaleProvider };
