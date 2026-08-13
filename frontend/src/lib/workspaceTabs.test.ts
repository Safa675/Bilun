import { describe, expect, it } from "vitest";
import { createWorkspaceStore } from "@/stores/workspaceStore";
import {
  applyWorkspaceClose,
  applyWorkspaceSync,
  deriveWorkspaceView,
  WORKSPACE_MAX_TABS,
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
  it("opens a new tab and activates it", () => {
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

  it("re-activates an existing tab with a fresh timestamp", () => {
    const tabs = [tab("section", "patients", 10), tab("patient", "P-001", 20)];
    const next = applyWorkspaceSync(tabs, "patient:P-001", { kind: "section", refId: "patients" }, 30);
    expect(next.activeTabId).toBe("section:patients");
    expect(next.tabs.find((t) => t.id === "section:patients")?.lastActivatedAt).toBe(30);
  });

  it("remembers each tab's query so list state survives tab switches", () => {
    const opened = applyWorkspaceSync([], null, { kind: "section", refId: "patients", query: "tab=patients&p=2" }, 10);
    const switched = applyWorkspaceSync(opened.tabs, "section:patients", { kind: "patient", refId: "P-001" }, 20);
    const back = applyWorkspaceSync(switched.tabs, "patient:P-001", { kind: "section", refId: "patients", query: "tab=patients&p=2" }, 30);
    expect(workspaceTabHref(back.tabs.find((t) => t.id === "section:patients")!)).toBe("/?tab=patients&p=2");
  });

  it("evicts the least-recently-used tab at the cap, never the new one", () => {
    const tabs = [
      tab("section", "patients", 1),
      tab("section", "compliance", 2),
      tab("section", "revenue", 3),
      tab("section", "operations", 4),
      tab("section", "reference-tools", 5),
      tab("patient", "P-001", 6),
    ];
    const next = applyWorkspaceSync(tabs, "patient:P-001", { kind: "patient", refId: "P-002" }, 7);
    expect(next.tabs).toHaveLength(WORKSPACE_MAX_TABS);
    expect(next.tabs.some((t) => t.id === "section:patients")).toBe(false);
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

describe("workspaceStore", () => {
  it("syncs and closes through the store api", () => {
    const store = createWorkspaceStore({ tabs: [], activeTabId: null });
    store.getState().syncFromRoute({ kind: "section", refId: "patients" });
    store.getState().syncFromRoute({ kind: "patient", refId: "P-001" });
    expect(store.getState().tabs).toHaveLength(2);
    expect(store.getState().activeTabId).toBe("patient:P-001");

    const navigateTo = store.getState().closeTab("patient:P-001");
    expect(navigateTo).toBe("/?tab=patients");
    expect(store.getState().activeTabId).toBe("section:patients");
  });
});
