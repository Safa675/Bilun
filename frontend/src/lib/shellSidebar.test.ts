import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import {
  SHELL_SIDEBAR_COLLAPSED_KEY,
  readSidebarCollapsed,
  sidebarWidthPx,
  writeSidebarCollapsed,
  SHELL_SIDEBAR_COLLAPSED_PX,
  SHELL_SIDEBAR_EXPANDED_PX,
} from "./shellSidebar";

describe("shellSidebar", () => {
  const store = new Map<string, string>();

  beforeEach(() => {
    store.clear();
    const localStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
    };
    vi.stubGlobal("window", { localStorage });
    vi.stubGlobal("localStorage", localStorage);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps collapsed state to rail widths", () => {
    expect(sidebarWidthPx(true)).toBe(SHELL_SIDEBAR_COLLAPSED_PX);
    expect(sidebarWidthPx(false)).toBe(SHELL_SIDEBAR_EXPANDED_PX);
  });

  it("persists collapsed preference", () => {
    expect(readSidebarCollapsed()).toBe(false);
    writeSidebarCollapsed(true);
    expect(store.get(SHELL_SIDEBAR_COLLAPSED_KEY)).toBe("1");
    expect(readSidebarCollapsed()).toBe(true);
    writeSidebarCollapsed(false);
    expect(readSidebarCollapsed()).toBe(false);
  });
});
