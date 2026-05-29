"use client";

import { useLayoutEffect } from "react";
import { usePathname } from "next/navigation";
import { getChatDockInsets, isChatDockEligiblePath } from "@/lib/chatDockLayout";
import { useAiDockPosition } from "@/stores/index";

/**
 * Keeps `--chat-dock-inset-left/right` in sync so AppTopBar tabs and main
 * content shift away from a fixed docked chat panel.
 */
export default function ChatDockInsetSync() {
  const pathname = usePathname();
  const chatDock = useAiDockPosition();
  const eligible = isChatDockEligiblePath(pathname);
  const { left, right } = getChatDockInsets(chatDock, eligible);

  useLayoutEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--chat-dock-inset-left", left);
    root.style.setProperty("--chat-dock-inset-right", right);
    return () => {
      root.style.setProperty("--chat-dock-inset-left", "0px");
      root.style.setProperty("--chat-dock-inset-right", "0px");
    };
  }, [left, right]);

  return null;
}
