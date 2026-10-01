import { ROLE_COOKIE_KEY, ROLE_STORAGE_KEY } from "./userRole";

export const AUTH_CHANGE_KEY = "bilun:auth-change";

export function removeLegacyRolePreferences(): void {
  try { window.localStorage.removeItem(ROLE_STORAGE_KEY); } catch { /* Storage can be disabled. */ }
  document.cookie = `${ROLE_COOKIE_KEY}=; Max-Age=0; Path=/; SameSite=Lax`;
}

export function clearProtectedBrowserState(): void {
  removeLegacyRolePreferences();
  try { window.sessionStorage.removeItem("bilun:workspace-tabs"); } catch { /* Storage can be disabled. */ }
}

/** A notification only. Receivers must recheck the server before granting permission. */
export function announceSessionChange(): void {
  try { window.localStorage.setItem(AUTH_CHANGE_KEY, `${Date.now()}:${Math.random()}`); } catch { /* Focus/expiry checks still work. */ }
}
