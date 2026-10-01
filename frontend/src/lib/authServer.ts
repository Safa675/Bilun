import { CLOSED_IDENTITY, parseSessionIdentity, type SessionIdentity } from "./auth";

/** Calls the backend directly: going through this Next server would recurse into middleware. */
export async function getServerIdentity(cookie: string): Promise<SessionIdentity> {
  const origin = (process.env.API_PROXY_TARGET ?? "http://localhost:8001").replace(/\/$/, "");
  try {
    const response = await fetch(`${origin}/api/auth/me`, {
      headers: cookie ? { Cookie: cookie } : {},
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) return CLOSED_IDENTITY;
    return parseSessionIdentity(await response.json());
  } catch {
    return CLOSED_IDENTITY;
  }
}
