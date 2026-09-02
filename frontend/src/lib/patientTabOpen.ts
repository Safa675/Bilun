import {
  workspaceTabId,
  type WorkspaceTab,
  type WorkspaceView,
} from "@/lib/workspaceTabs";

/** Ctrl/Cmd-click or middle mouse — open a strip tab without leaving this view. */
export function isBackgroundTabPointer(event: {
  metaKey: boolean;
  ctrlKey: boolean;
  button: number;
}): boolean {
  return event.metaKey || event.ctrlKey || event.button === 1;
}

/** Map a patient profile href (including claim/section query) to a workspace view. */
export function patientViewFromHref(href: string, patientId: string): WorkspaceView {
  try {
    const url = new URL(href, "http://local.invalid");
    const query = url.searchParams.toString();
    return { kind: "patient", refId: patientId, query: query || undefined };
  } catch {
    return { kind: "patient", refId: patientId };
  }
}

/** Already-open dest → switch to it. Missing dest → add a background tab. */
export function backgroundOpenKind(
  tabs: readonly Pick<WorkspaceTab, "id">[],
  view: WorkspaceView,
): "switch" | "add" {
  const id = workspaceTabId(view.kind, view.refId);
  return tabs.some((tab) => tab.id === id) ? "switch" : "add";
}
