import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CHAT_DOCK_STORAGE_KEY,
  DEFAULT_CHAT_DOCK,
  isChatDockedRight,
  parseChatDock,
  readChatDock,
  writeChatDock,
} from "./chatDockPreference";

describe("chatDockPreference", () => {
  const store = new Map<string, string>();

  beforeEach(() => {
    store.clear();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => {
          store.set(key, value);
        },
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses the key bilun:chat-dock and a collapsed first-visit default", () => {
    expect(CHAT_DOCK_STORAGE_KEY).toBe("bilun:chat-dock");
    expect(DEFAULT_CHAT_DOCK).toBe("collapsed");
    expect(readChatDock()).toBe("collapsed");
  });

  it("round-trips the three dock positions", () => {
    for (const dock of ["center", "right", "collapsed"] as const) {
      writeChatDock(dock);
      expect(store.get(CHAT_DOCK_STORAGE_KEY)).toBe(dock);
      expect(readChatDock()).toBe(dock);
    }
  });

  it("falls back to the default for unknown stored values", () => {
    for (const value of ["", "left", "CENTER", "1", "null", "{}"]) {
      store.set(CHAT_DOCK_STORAGE_KEY, value);
      expect(readChatDock()).toBe("collapsed");
    }
    expect(parseChatDock("right")).toBe("right");
    expect(parseChatDock(undefined)).toBeNull();
  });

  it("does not throw when storage is blocked (private mode, disabled site data)", () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => {
          throw new Error("blocked");
        },
        setItem: () => {
          throw new Error("blocked");
        },
      },
    });
    expect(readChatDock()).toBe("collapsed");
    expect(() => writeChatDock("right")).not.toThrow();
  });

  it("is safe on the server (no window)", () => {
    vi.unstubAllGlobals();
    expect(readChatDock()).toBe("collapsed");
    expect(() => writeChatDock("center")).not.toThrow();
  });

  it("treats only the right dock as a column that pushes the page aside", () => {
    expect(isChatDockedRight("right")).toBe(true);
    expect(isChatDockedRight("center")).toBe(false);
    expect(isChatDockedRight("collapsed")).toBe(false);
  });
});
