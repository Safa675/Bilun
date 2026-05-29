import { SUT_INLINE_CHAT_PANEL_WIDTH } from "@/components/chat/SutInlineAIPanel";
import type { SutChatDockPosition } from "@/stores/storeInterfaces";

/** Breathing room between docked chat panel edge and page content. */
export const CHAT_DOCK_MARGIN_PX = 32;

export const CHAT_DOCK_INSET_PX = SUT_INLINE_CHAT_PANEL_WIDTH + CHAT_DOCK_MARGIN_PX;

export function isChatDockEligiblePath(pathname: string): boolean {
  return pathname === "/" || pathname.startsWith("/patient/");
}

export function getChatDockInsets(
  dock: SutChatDockPosition,
  eligible: boolean,
): { left: string; right: string } {
  if (!eligible || dock === "center") {
    return { left: "0px", right: "0px" };
  }

  const inset = `${CHAT_DOCK_INSET_PX}px`;
  return {
    left: dock === "left" ? inset : "0px",
    right: dock === "right" ? inset : "0px",
  };
}
