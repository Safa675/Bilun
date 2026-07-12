/** Shell sidebar layout constants and collapse persistence. */

export const SHELL_SIDEBAR_EXPANDED_PX = 220;
export const SHELL_SIDEBAR_COLLAPSED_PX = 64;
export const SHELL_SIDEBAR_COLLAPSED_KEY = "bilun:sidebar-collapsed";

export function readSidebarCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(SHELL_SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeSidebarCollapsed(collapsed: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SHELL_SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
  } catch {
    // Ignore quota / private-mode failures.
  }
}

export function sidebarWidthPx(collapsed: boolean): number {
  return collapsed ? SHELL_SIDEBAR_COLLAPSED_PX : SHELL_SIDEBAR_EXPANDED_PX;
}
