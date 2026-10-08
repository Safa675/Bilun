import type { SutChatDockPosition } from "@/stores/storeInterfaces";

/** localStorage key of the user's chat dock choice (per browser, not per account). */
export const CHAT_DOCK_STORAGE_KEY = "bilun:chat-dock";

/** First visit and every fallback: a collapsed thin bar at the top of the page (owner decision D1). */
export const DEFAULT_CHAT_DOCK: SutChatDockPosition = "collapsed";

const CHAT_DOCK_VALUES: readonly SutChatDockPosition[] = ["collapsed", "center", "right"];

/** The stored string as a dock position, or null when it is not one of the three known values. */
export function parseChatDock(value: unknown): SutChatDockPosition | null {
  return CHAT_DOCK_VALUES.find((dock) => dock === value) ?? null;
}

/** Only the right dock is a column that pushes the page content aside; collapsed and center stay in the flow. */
export function isChatDockedRight(dock: SutChatDockPosition): boolean {
  return dock === "right";
}

/** SSR-safe. A missing, unknown or unreadable value gives the default. */
export function readChatDock(): SutChatDockPosition {
  if (typeof window === "undefined") return DEFAULT_CHAT_DOCK;
  try {
    return parseChatDock(window.localStorage.getItem(CHAT_DOCK_STORAGE_KEY)) ?? DEFAULT_CHAT_DOCK;
  } catch {
    return DEFAULT_CHAT_DOCK;
  }
}

export function writeChatDock(dock: SutChatDockPosition): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(CHAT_DOCK_STORAGE_KEY, dock);
  } catch {
    // Ignore quota / private-mode failures.
  }
}
