export type UserRole = "billing_officer" | "dev";

export const ROLE_STORAGE_KEY = "bilun_user_role";
export const ROLE_COOKIE_KEY = "bilun:role";

function getDefaultRole(): UserRole {
  if (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_USER_ROLE) {
    const envRole = process.env.NEXT_PUBLIC_USER_ROLE as UserRole;
    if (isValidRole(envRole)) return envRole;
  }
  return "dev";
}

function isValidRole(value: string): value is UserRole {
  return value === "billing_officer" || value === "dev";
}

export function parseRole(value: string | null | undefined): UserRole {
  if (value && isValidRole(value)) return value;
  return getDefaultRole();
}

export function setUserRole(role: UserRole): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(ROLE_STORAGE_KEY, role);
    if (typeof StorageEvent !== "undefined") {
      window.dispatchEvent(new StorageEvent("storage", { key: ROLE_STORAGE_KEY }));
    } else {
      window.dispatchEvent(new Event("storage"));
    }
  }
}
