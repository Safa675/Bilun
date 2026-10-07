import { SUT_INLINE_CHAT_PANEL_WIDTH } from "@/components/chat/SutInlineAIPanel";
import { isChatDockedRight } from "@/lib/chatDockPreference";
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
  if (!eligible || !isChatDockedRight(dock)) {
    return { left: "0px", right: "0px" };
  }

  return { left: "0px", right: `${CHAT_DOCK_INSET_PX}px` };
}
