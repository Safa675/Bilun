import {
  buildSutHomeHref,
  buildSutPatientHref,
  parseSutHomeTab,
  type SutHomeTab,
} from "@/lib/constants";

/** Workspace-shell tab model: pure helpers (store + tests build on these). */

export type WorkspaceTabKind = "section" | "patient";

export interface WorkspaceTab {
  id: string;
  kind: WorkspaceTabKind;
  refId: string;
  /** Last seen query string while this tab was the active view (restores list state). */
  query?: string;
  lastActivatedAt: number;
}

export interface WorkspaceView {
  kind: WorkspaceTabKind;
  refId: string;
  query?: string;
}

export const WORKSPACE_STORAGE_KEY = "bilun:workspace-tabs";
/** Preferred tab width (`max-w-52` / 13rem). Tabs do not grow past this. */
export const WORKSPACE_TAB_MAX_PX = 208;
/** Floor width (`min-w-[4.5rem]`). Further tabs scroll instead of shrinking. */
export const WORKSPACE_TAB_MIN_PX = 72;

export function workspaceTabId(kind: WorkspaceTabKind, refId: string): string {
  return `${kind}:${refId}`;
}

/** Map the current route to the workspace view it represents (null = no tab). */
export function deriveWorkspaceView(
  pathname: string | null,
  homeTabParam: string | null,
): WorkspaceView | null {
  if (!pathname) return null;
  if (pathname === "/") {
    return { kind: "section", refId: parseSutHomeTab(homeTabParam) };
  }
  const match = pathname.match(/^\/patient\/([^/]+)$/);
  if (match) {
    return { kind: "patient", refId: decodeURIComponent(match[1]) };
  }
  return null;
}

export function workspaceTabHref(
  tab: Pick<WorkspaceTab, "kind" | "refId" | "query">,
): string {
  if (tab.kind === "section") {
    return tab.query ? `/?${tab.query}` : buildSutHomeHref(tab.refId as SutHomeTab);
  }
  return tab.query
    ? `/patient/${encodeURIComponent(tab.refId)}?${tab.query}`
    : buildSutPatientHref(tab.refId);
}

/**
 * Navigate this strip tab like Chrome: if the dest already exists, switch to
 * it; otherwise replace the active tab in-place. Extra tabs are only added
 * via background open (Ctrl / middle / “Open in new tab”).
 */
export function applyWorkspaceSync(
  tabs: WorkspaceTab[],
  activeTabId: string | null,
  view: WorkspaceView,
  now: number,
): { tabs: WorkspaceTab[]; activeTabId: string } {
  const id = workspaceTabId(view.kind, view.refId);
  const existing = tabs.find((tab) => tab.id === id);
  if (existing) {
    // Already active: leave timestamps untouched, only track query drift.
    if (activeTabId === id) {
      if ((existing.query ?? "") === (view.query ?? "")) {
        return { tabs, activeTabId: id };
      }
      return {
        tabs: tabs.map((tab) =>
          tab.id === id ? { ...tab, query: view.query } : tab,
        ),
        activeTabId: id,
      };
    }
    return {
      tabs: tabs.map((tab) =>
        tab.id === id
          ? { ...tab, lastActivatedAt: now, query: view.query }
          : tab,
      ),
      activeTabId: id,
    };
  }
  const nextTab: WorkspaceTab = {
    id,
    kind: view.kind,
    refId: view.refId,
    query: view.query,
    lastActivatedAt: now,
  };
  const activeIndex = activeTabId
    ? tabs.findIndex((tab) => tab.id === activeTabId)
    : -1;
  if (activeIndex >= 0) {
    const nextTabs = tabs.slice();
    nextTabs[activeIndex] = nextTab;
    return { tabs: nextTabs, activeTabId: id };
  }
  return { tabs: [...tabs, nextTab], activeTabId: id };
}

/** Open the view's tab WITHOUT activating it (used for split pane B). */
export function ensureWorkspaceTab(
  tabs: WorkspaceTab[],
  activeTabId: string | null,
  view: WorkspaceView,
  now: number,
): { tabs: WorkspaceTab[]; tabId: string } {
  void activeTabId;
  const id = workspaceTabId(view.kind, view.refId);
  if (tabs.some((tab) => tab.id === id)) return { tabs, tabId: id };
  return {
    tabs: [
      ...tabs,
      { id, kind: view.kind, refId: view.refId, query: view.query, lastActivatedAt: now },
    ],
    tabId: id,
  };
}

/**
 * Remove a tab. When the active tab closes, the most-recently-used remaining
 * tab becomes active. Returns the href the caller should navigate to (null =
 * no navigation needed).
 */
export function applyWorkspaceClose(
  tabs: WorkspaceTab[],
  activeTabId: string | null,
  closeId: string,
): { tabs: WorkspaceTab[]; activeTabId: string | null; navigateTo: string | null } {
  const remaining = tabs.filter((tab) => tab.id !== closeId);
  if (activeTabId !== closeId) {
    return { tabs: remaining, activeTabId, navigateTo: null };
  }
  const nextActive = [...remaining].sort(
    (a, b) => b.lastActivatedAt - a.lastActivatedAt,
  )[0];
  if (!nextActive) {
    return {
      tabs: remaining,
      activeTabId: null,
      navigateTo: buildSutHomeHref("patients"),
    };
  }
  return {
    tabs: remaining,
    activeTabId: nextActive.id,
    navigateTo: workspaceTabHref(nextActive),
  };
}

export interface WorkspaceSessionState {
  tabs: WorkspaceTab[];
  activeTabId: string | null;
  /** Split view: the patient tab rendered in pane B (store-only, not in URL). */
  paneBTabId: string | null;
}

/** Stored navigation is not a permission grant; discard inaccessible developer views. */
export function accessibleWorkspaceSession(
  session: WorkspaceSessionState | null,
  developer: boolean,
): WorkspaceSessionState {
  if (!session) return { tabs: [], activeTabId: null, paneBTabId: null };
  if (developer) return session;
  const tabs = session.tabs.filter((tab) => tab.kind !== "section" || tab.refId !== "rule-database").map((tab) => {
    const query = new URLSearchParams(tab.query);
    query.delete("admin");
    if (query.get("tab") === "rule-database") query.delete("tab");
    return { ...tab, query: query.toString() || undefined };
  });
  const present = (id: string | null) => tabs.some((tab) => tab.id === id) ? id : null;
  return { tabs, activeTabId: present(session.activeTabId), paneBTabId: present(session.paneBTabId) };
}

export function readWorkspaceSession(): WorkspaceSessionState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<WorkspaceSessionState>;
    if (!Array.isArray(parsed.tabs)) return null;
    const tabs: WorkspaceTab[] = [];
    for (const entry of parsed.tabs) {
      if (
        entry &&
        typeof entry.id === "string" &&
        (entry.kind === "section" || entry.kind === "patient") &&
        typeof entry.refId === "string" &&
        typeof entry.lastActivatedAt === "number"
      ) {
        tabs.push({
          id: entry.id,
          kind: entry.kind,
          refId: entry.refId,
          query: typeof entry.query === "string" ? entry.query : undefined,
          lastActivatedAt: entry.lastActivatedAt,
        });
      }
    }
    const activeTabId =
      typeof parsed.activeTabId === "string" &&
      tabs.some((tab) => tab.id === parsed.activeTabId)
        ? parsed.activeTabId
        : null;
    const paneBTabId =
      typeof parsed.paneBTabId === "string" &&
      tabs.some((tab) => tab.id === parsed.paneBTabId && tab.kind === "patient")
        ? parsed.paneBTabId
        : null;
    return { tabs, activeTabId, paneBTabId };
  } catch {
    return null;
  }
}

export function writeWorkspaceSession(state: WorkspaceSessionState): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore quota / private-mode failures.
  }
}
