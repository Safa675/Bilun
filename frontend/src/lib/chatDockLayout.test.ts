import { describe, expect, it } from "vitest";
import {
  CHAT_DOCK_INSET_PX,
  getChatDockInsets,
  isChatDockEligiblePath,
} from "./chatDockLayout";

describe("chatDockLayout", () => {
  it("detects chat-eligible routes", () => {
    expect(isChatDockEligiblePath("/")).toBe(true);
    expect(isChatDockEligiblePath("/patient/P-001")).toBe(true);
    expect(isChatDockEligiblePath("/design-system")).toBe(false);
  });

  it("returns zero insets for center dock or ineligible routes", () => {
    expect(getChatDockInsets("center", true)).toEqual({ left: "0px", right: "0px" });
    expect(getChatDockInsets("right", false)).toEqual({ left: "0px", right: "0px" });
  });

  it("offsets content away from a right-docked panel", () => {
    expect(getChatDockInsets("right", true)).toEqual({
      left: "0px",
      right: `${CHAT_DOCK_INSET_PX}px`,
    });
  });
});
