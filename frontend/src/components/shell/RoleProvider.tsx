"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { setCookie } from "@/lib/cookies";
import {
  parseRole,
  ROLE_COOKIE_KEY,
  ROLE_STORAGE_KEY,
  setUserRole as setUserRoleRaw,
  type UserRole,
} from "@/lib/userRole";

interface RoleContextValue {
  role: UserRole;
  setRole: (role: UserRole) => void;
}

const RoleContext = createContext<RoleContextValue | null>(null);

export function RoleProvider({
  children,
  initialRole,
}: {
  children: ReactNode;
  initialRole?: UserRole;
}) {
  const [role, setRoleState] = useState<UserRole>(() => initialRole ?? parseRole(undefined));

  useEffect(() => {
    if (initialRole !== undefined) return;
    const stored =
      typeof window !== "undefined"
        ? parseRole(window.localStorage.getItem(ROLE_STORAGE_KEY))
        : parseRole(undefined);
    setRoleState(stored);
  }, [initialRole]);

  const setRole = useCallback((next: UserRole) => {
    setRoleState(next);
    setUserRoleRaw(next);
    setCookie(ROLE_COOKIE_KEY, next);
  }, []);

  return <RoleContext.Provider value={{ role, setRole }}>{children}</RoleContext.Provider>;
}

export function useUserRole(): UserRole {
  const context = useContext(RoleContext);
  if (!context) {
    throw new Error("useUserRole must be used within RoleProvider");
  }
  return context.role;
}

export function useSetUserRole(): (role: UserRole) => void {
  const context = useContext(RoleContext);
  if (!context) {
    throw new Error("useSetUserRole must be used within RoleProvider");
  }
  return context.setRole;
}
