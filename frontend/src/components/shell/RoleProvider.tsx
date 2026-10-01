"use client";

import { createContext, Fragment, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { canUseDeveloper, CLOSED_IDENTITY, identityKey, type SessionIdentity } from "@/lib/auth";
import { getSessionIdentity } from "@/lib/api/auth";
import { AUTH_CHANGE_KEY, clearProtectedBrowserState, removeLegacyRolePreferences } from "@/lib/authBrowser";
import type { UserRole } from "@/lib/userRole";

const RoleContext = createContext<SessionIdentity | null>(null);

export function RoleProvider({ children, initialIdentity = CLOSED_IDENTITY }: {
  children: ReactNode;
  initialIdentity?: SessionIdentity;
}) {
  const [identity, setIdentity] = useState(initialIdentity);
  const current = useRef(initialIdentity);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    removeLegacyRolePreferences();
    let active = true;
    let requestVersion = 0;
    const refresh = async (conceal = false) => {
      const version = ++requestVersion;
      if (conceal) setChecking(true);
      try {
        const next = await getSessionIdentity();
        if (!active || version !== requestVersion) return;
        if (identityKey(next) !== identityKey(current.current)) {
          clearProtectedBrowserState();
          current.current = next;
          setIdentity(next);
          // A document navigation discards all old React, fetch and chat state.
          window.location.replace(next.capabilities.includes("billing") ? "/" : "/login");
          return;
        }
        setChecking(false);
      } catch {
        if (!active || version !== requestVersion) return;
        // Never retain a privileged screen when its identity cannot be verified.
        current.current = CLOSED_IDENTITY;
        setIdentity(CLOSED_IDENTITY);
        clearProtectedBrowserState();
        if (window.location.pathname !== "/login") window.location.replace("/login");
        else setChecking(false);
      }
    };
    const onFocus = () => { void refresh(); };
    const onVisibility = () => { if (document.visibilityState === "visible") void refresh(); };
    const onStorage = (event: StorageEvent) => { if (event.key === AUTH_CHANGE_KEY) void refresh(true); };
    const onPageShow = (event: PageTransitionEvent) => { if (event.persisted) void refresh(true); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("storage", onStorage);
    window.addEventListener("pageshow", onPageShow);
    const poll = window.setInterval(() => { void refresh(); }, 30_000);
    const delay = identity.expires_at == null ? null : Math.max(0, identity.expires_at * 1000 - Date.now() + 100);
    const expiry = delay == null ? null : window.setTimeout(() => { void refresh(true); }, Math.min(delay, 2_147_483_647));
    return () => {
      active = false;
      window.clearInterval(poll);
      if (expiry !== null) window.clearTimeout(expiry);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("pageshow", onPageShow);
    };
  }, [identity.expires_at]);

  return <RoleContext.Provider value={identity}>
    {checking ? <div aria-busy="true" /> : <Fragment key={identityKey(identity)}>{children}</Fragment>}
  </RoleContext.Provider>;
}

export function useSessionIdentity(): SessionIdentity {
  const identity = useContext(RoleContext);
  if (!identity) throw new Error("useSessionIdentity must be used within RoleProvider");
  return identity;
}

export function useUserRole(): UserRole {
  return canUseDeveloper(useSessionIdentity()) ? "dev" : "billing_officer";
}
