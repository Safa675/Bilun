import { describe, expect, it } from "vitest";
import { createWorkspaceStore } from "@/stores/workspaceStore";
import {
  applyWorkspaceClose,
  applyWorkspaceSync,
  deriveWorkspaceView,
  ensureWorkspaceTab,
  workspaceTabHref,
  workspaceTabId,
  type WorkspaceTab,
} from "./workspaceTabs";

function tab(kind: "section" | "patient", refId: string, lastActivatedAt: number): WorkspaceTab {
  return { id: workspaceTabId(kind, refId), kind, refId, lastActivatedAt };
}

describe("deriveWorkspaceView", () => {
  it("maps the home route to a section tab", () => {
    expect(deriveWorkspaceView("/", null)).toEqual({ kind: "section", refId: "patients" });
    expect(deriveWorkspaceView("/", "revenue")).toEqual({ kind: "section", refId: "revenue" });
  });

  it("maps patient routes to patient tabs", () => {
    expect(deriveWorkspaceView("/patient/P-001", null)).toEqual({
      kind: "patient",
      refId: "P-001",
    });
  });

  it("ignores non-workspace routes", () => {
    expect(deriveWorkspaceView("/login", null)).toBeNull();
    expect(deriveWorkspaceView("/patient/", null)).toBeNull();
  });
});

describe("workspaceTabHref", () => {
  it("builds section and patient hrefs", () => {
    expect(workspaceTabHref(tab("section", "compliance", 1))).toBe("/?tab=compliance");
    expect(workspaceTabHref(tab("patient", "P-001", 1))).toBe("/patient/P-001");
  });
});

describe("applyWorkspaceSync", () => {
  it("opens a new tab and activates it when the strip is empty", () => {
    const next = applyWorkspaceSync([], null, { kind: "section", refId: "patients" }, 10);
    expect(next.activeTabId).toBe("section:patients");
    expect(next.tabs).toHaveLength(1);
  });

  it("is a no-op when the view is already active", () => {
    const tabs = [tab("section", "patients", 10)];
    const next = applyWorkspaceSync(tabs, "section:patients", { kind: "section", refId: "patients" }, 99);
    expect(next.tabs).toBe(tabs);
    expect(next.activeTabId).toBe("section:patients");
  });

  it("replaces the active tab when navigating to a new view", () => {
    const opened = applyWorkspaceSync([], null, { kind: "section", refId: "patients" }, 10);
    const next = applyWorkspaceSync(
      opened.tabs,
      "section:patients",
      { kind: "patient", refId: "P-001" },
      20,
    );
    expect(next.tabs).toHaveLength(1);
    expect(next.tabs[0].id).toBe("patient:P-001");
    expect(next.activeTabId).toBe("patient:P-001");
  });

  it("re-activates an existing tab and leaves siblings in place", () => {
    const tabs = [tab("section", "patients", 10), tab("patient", "P-001", 20)];
    const next = applyWorkspaceSync(tabs, "section:patients", { kind: "patient", refId: "P-001" }, 30);
    expect(next.activeTabId).toBe("patient:P-001");
    expect(next.tabs).toHaveLength(2);
    expect(next.tabs.find((t) => t.id === "section:patients")?.lastActivatedAt).toBe(10);
    expect(next.tabs.find((t) => t.id === "patient:P-001")?.lastActivatedAt).toBe(30);
  });

  it("remembers each tab's query so list state survives switching back", () => {
    const opened = applyWorkspaceSync([], null, { kind: "section", refId: "patients", query: "tab=patients&p=2" }, 10);
    const background = ensureWorkspaceTab(
      opened.tabs,
      "section:patients",
      { kind: "patient", refId: "P-001" },
      15,
    );
    const switched = applyWorkspaceSync(
      background.tabs,
      "section:patients",
      { kind: "patient", refId: "P-001" },
      20,
    );
    const back = applyWorkspaceSync(
      switched.tabs,
      "patient:P-001",
      { kind: "section", refId: "patients", query: "tab=patients&p=2" },
      30,
    );
    expect(workspaceTabHref(back.tabs.find((t) => t.id === "section:patients")!)).toBe("/?tab=patients&p=2");
  });

  it("replace keeps sibling tabs (no LRU eviction of the rest of the strip)", () => {
    const tabs = [
      tab("section", "patients", 1),
      tab("section", "compliance", 2),
      tab("section", "revenue", 3),
      tab("section", "operations", 4),
      tab("section", "reference-tools", 5),
      tab("patient", "P-001", 6),
    ];
    const next = applyWorkspaceSync(tabs, "patient:P-001", { kind: "patient", refId: "P-002" }, 7);
    expect(next.tabs).toHaveLength(6);
    expect(next.tabs.some((t) => t.id === "section:patients")).toBe(true);
    expect(next.tabs.some((t) => t.id === "patient:P-001")).toBe(false);
    expect(next.activeTabId).toBe("patient:P-002");
  });
});

describe("applyWorkspaceClose", () => {
  it("closing an inactive tab needs no navigation", () => {
    const tabs = [tab("section", "patients", 1), tab("patient", "P-001", 2)];
    const next = applyWorkspaceClose(tabs, "patient:P-001", "section:patients");
    expect(next.navigateTo).toBeNull();
    expect(next.activeTabId).toBe("patient:P-001");
    expect(next.tabs).toHaveLength(1);
  });

  it("closing the active tab activates the most-recently-used remainder", () => {
    const tabs = [
      tab("section", "patients", 1),
      tab("patient", "P-001", 3),
      tab("patient", "P-002", 2),
    ];
    const next = applyWorkspaceClose(tabs, "patient:P-001", "patient:P-001");
    expect(next.activeTabId).toBe("patient:P-002");
    expect(next.navigateTo).toBe("/patient/P-002");
  });

  it("closing the last tab returns to the patients home", () => {
    const next = applyWorkspaceClose([tab("section", "patients", 1)], "section:patients", "section:patients");
    expect(next.tabs).toHaveLength(0);
    expect(next.activeTabId).toBeNull();
    expect(next.navigateTo).toBe("/?tab=patients");
  });
});

describe("ensureWorkspaceTab", () => {
  it("opens without activating and keeps every existing tab", () => {
    const tabs = [
      tab("section", "patients", 1),
      tab("patient", "A", 2),
      tab("patient", "B", 3),
      tab("patient", "C", 4),
      tab("patient", "D", 5),
      tab("patient", "E", 6),
    ];
    const next = ensureWorkspaceTab(tabs, "patient:E", { kind: "patient", refId: "F" }, 7);
    expect(next.tabId).toBe("patient:F");
    expect(next.tabs).toHaveLength(7);
    expect(next.tabs.some((t) => t.id === "section:patients")).toBe(true);
    expect(next.tabs.some((t) => t.id === "patient:E")).toBe(true);
  });
});

describe("workspaceStore split", () => {
  it("openSplit sets pane B without changing the active tab", () => {
    const store = createWorkspaceStore({ tabs: [], activeTabId: null });
    store.getState().syncFromRoute({ kind: "patient", refId: "P-001" });
    store.getState().openSplit({ kind: "patient", refId: "P-002" });
    expect(store.getState().activeTabId).toBe("patient:P-001");
    expect(store.getState().paneBTabId).toBe("patient:P-002");
    expect(store.getState().tabs).toHaveLength(2);
  });

  it("closing pane B's tab clears the split", () => {
    const store = createWorkspaceStore({ tabs: [], activeTabId: null });
    store.getState().syncFromRoute({ kind: "patient", refId: "P-001" });
    store.getState().openSplit({ kind: "patient", refId: "P-002" });
    store.getState().closeTab("patient:P-002");
    expect(store.getState().paneBTabId).toBeNull();
  });

  it("activating pane B's tab moves it to pane A and clears the split", () => {
    const store = createWorkspaceStore({ tabs: [], activeTabId: null });
    store.getState().syncFromRoute({ kind: "patient", refId: "P-001" });
    store.getState().openSplit({ kind: "patient", refId: "P-002" });
    store.getState().syncFromRoute({ kind: "patient", refId: "P-002" });
    expect(store.getState().activeTabId).toBe("patient:P-002");
    expect(store.getState().paneBTabId).toBeNull();
    expect(store.getState().tabs).toHaveLength(2);
  });
});

describe("workspaceStore", () => {
  it("syncs and closes through the store api", () => {
    const store = createWorkspaceStore({ tabs: [], activeTabId: null });
    store.getState().syncFromRoute({ kind: "section", refId: "patients" });
    store.getState().syncFromRoute({ kind: "patient", refId: "P-001" });
    expect(store.getState().tabs).toHaveLength(1);
    expect(store.getState().activeTabId).toBe("patient:P-001");

    const navigateTo = store.getState().closeTab("patient:P-001");
    expect(navigateTo).toBe("/?tab=patients");
    expect(store.getState().activeTabId).toBeNull();
  });

  it("openBackground adds a tab without changing the active view", () => {
    const store = createWorkspaceStore({ tabs: [], activeTabId: null });
    store.getState().syncFromRoute({ kind: "section", refId: "patients" });
    store.getState().openBackground({ kind: "patient", refId: "P-001" });
    store.getState().openBackground({ kind: "patient", refId: "P-002" });
    expect(store.getState().activeTabId).toBe("section:patients");
    expect(store.getState().tabs).toHaveLength(3);
    expect(store.getState().tabs.map((tab) => tab.id)).toEqual([
      "section:patients",
      "patient:P-001",
      "patient:P-002",
    ]);

    store.getState().openBackground({ kind: "patient", refId: "P-001" });
    expect(store.getState().tabs).toHaveLength(3);
    expect(store.getState().activeTabId).toBe("section:patients");
  });
});
