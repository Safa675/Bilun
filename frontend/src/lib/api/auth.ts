import { parseSessionIdentity, type SessionIdentity } from "../auth";

export async function getSessionIdentity(): Promise<SessionIdentity> {
  const response = await fetch("/api/auth/me", {
    credentials: "include",
    cache: "no-store",
    signal: AbortSignal.timeout(5_000),
  });
  if (!response.ok) throw new Error("Session could not be verified");
  return parseSessionIdentity(await response.json());
}

export async function endSession(): Promise<SessionIdentity> {
  const response = await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Sign out failed");
  const identity = await getSessionIdentity();
  if (identity.authenticated) throw new Error("Session is still active");
  return identity;
}
