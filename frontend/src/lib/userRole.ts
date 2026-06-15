"use client";

import { useSyncExternalStore } from "react";

export type UserRole = "billing_analyst" | "compliance_engineer" | "dev" | "admin";

export const RULE_DATABASE_ALLOWED_ROLES: UserRole[] = [
  "compliance_engineer",
  "dev",
  "admin",
];

const STORAGE_KEY = "bilun_user_role";

function getDefaultRole(): UserRole {
  if (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_USER_ROLE) {
    return process.env.NEXT_PUBLIC_USER_ROLE as UserRole;
  }
  return "dev";
}

function parseRole(value: string | null): UserRole {
  const valid: UserRole[] = ["billing_analyst", "compliance_engineer", "dev", "admin"];
  if (value && valid.includes(value as UserRole)) {
    return value as UserRole;
  }
  return getDefaultRole();
}

function getRole(): UserRole {
  if (typeof window === "undefined") return getDefaultRole();
  return parseRole(window.localStorage.getItem(STORAGE_KEY));
}

function subscribe(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};

  const handler = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) callback();
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}

export function useUserRole(): UserRole {
  return useSyncExternalStore(subscribe, getRole, getDefaultRole);
}

export function setUserRole(role: UserRole): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, role);
    if (typeof StorageEvent !== "undefined") {
      window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY }));
    } else {
      window.dispatchEvent(new Event("storage"));
    }
  }
}

export function canAccessRuleDatabase(role: UserRole): boolean {
  return RULE_DATABASE_ALLOWED_ROLES.includes(role);
}
