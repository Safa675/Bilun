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

export const WORKSPACE_MAX_TABS = 6;
/** Inline tabs rendered before the overflow dropdown. */
export const WORKSPACE_INLINE_TABS = 5;
export const WORKSPACE_STORAGE_KEY = "bilun:workspace-tabs";

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

/** Open/activate the view's tab, enforcing the cap with LRU eviction. */
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
  let next = [
    ...tabs,
    { id, kind: view.kind, refId: view.refId, query: view.query, lastActivatedAt: now },
  ];
  if (next.length > WORKSPACE_MAX_TABS) {
    const lru = [...next]
      .filter((tab) => tab.id !== id)
      .sort((a, b) => a.lastActivatedAt - b.lastActivatedAt)[0];
    next = next.filter((tab) => tab.id !== lru.id);
  }
  return { tabs: next, activeTabId: id };
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
    return { tabs: tabs.slice(0, WORKSPACE_MAX_TABS), activeTabId };
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
