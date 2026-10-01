import type { UserRole } from "./userRole";

export interface SessionIdentity {
  authenticated: boolean;
  username: string | null;
  role: UserRole;
  capabilities: string[];
  public_billing_enabled: boolean;
  expires_at: number | null;
}

export const CLOSED_IDENTITY: SessionIdentity = {
  authenticated: false,
  username: null,
  role: "billing_officer",
  capabilities: [],
  public_billing_enabled: false,
  expires_at: null,
};

/** Accept this shape only from the identity endpoint, never from browser storage. */
export function parseSessionIdentity(value: unknown): SessionIdentity {
  if (!value || typeof value !== "object") throw new Error("Invalid session response");
  const data = value as Record<string, unknown>;
  if (
    typeof data.authenticated !== "boolean" ||
    typeof data.public_billing_enabled !== "boolean" ||
    (data.role !== "billing_officer" && data.role !== "dev") ||
    !(data.username === null || typeof data.username === "string") ||
    !Array.isArray(data.capabilities) ||
    !data.capabilities.every((item) => typeof item === "string") ||
    !(data.expires_at === null || (typeof data.expires_at === "number" && Number.isFinite(data.expires_at)))
  ) throw new Error("Invalid session response");
  if (!data.authenticated && (data.role === "dev" || data.username !== null)) {
    throw new Error("Invalid anonymous session response");
  }
  return data as unknown as SessionIdentity;
}

export function canUseDeveloper(identity: SessionIdentity): boolean {
  return identity.authenticated && identity.role === "dev" && identity.capabilities.includes("developer");
}

export function canUseBilling(identity: SessionIdentity): boolean {
  return (identity.authenticated || identity.public_billing_enabled) && identity.capabilities.includes("billing");
}

export function identityKey(identity: SessionIdentity): string {
  return JSON.stringify([identity.authenticated, identity.username, identity.role, identity.capabilities, identity.public_billing_enabled]);
}

export function requestsDeveloper(pathname: string, query: Pick<URLSearchParams, "get">): boolean {
  return pathname === "/design-system" || query.get("tab") === "rule-database" || query.get("admin") === "1";
}

export function isBillingPage(pathname: string): boolean {
  return pathname === "/" || /^\/patient\/[^/]+(?:\/billing)?\/?$/.test(pathname);
}
