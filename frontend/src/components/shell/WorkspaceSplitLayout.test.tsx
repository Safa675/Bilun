import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { StoreApi } from "zustand";
import WorkspaceSplitLayout from "./WorkspaceSplitLayout";
import { createNavigationStore } from "@/stores/navigationStore";
import type { NavigationStore } from "@/stores/storeInterfaces";

// A split view turns the right chat column off, but that is a layout rule: it must not overwrite the dock the user saved.
const holder = vi.hoisted(() => ({
  nav: undefined as unknown,
  paneB: null as null | { id: string; kind: "patient"; refId: string },
}));
const writes: Array<[string, string]> = [];
const renderers: ReactTestRenderer[] = [];

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/i18n/useTranslations", () => ({ useT: () => (key: string) => key }));
vi.mock("@/app/patient/[id]/page", () => ({ SutPatientPageContent: () => null }));
vi.mock("@/stores/index", async () => {
  const { useStore } = await import("zustand");
  return {
    useAiDockPosition: () =>
      useStore(holder.nav as StoreApi<NavigationStore>, (state) => state.aiDockPosition),
    useNavigationStoreApi: () => holder.nav,
    useWorkspacePaneB: () => holder.paneB,
    useWorkspaceStoreApi: () => ({ getState: () => ({ tabs: [], activeTabId: null }) }),
  };
});

function navStore() {
  return holder.nav as StoreApi<NavigationStore>;
}

async function mount() {
  let renderer: ReactTestRenderer;
  await act(async () => {
    renderer = create(<WorkspaceSplitLayout><div>routed view</div></WorkspaceSplitLayout>);
  });
  renderers.push(renderer!);
  return renderer!;
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  writes.length = 0;
  vi.stubGlobal("window", {
    localStorage: { getItem: () => "right", setItem: (key: string, value: string) => writes.push([key, value]) },
  });
  holder.nav = createNavigationStore();
  holder.paneB = null;
});

afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => { renderer.unmount(); });
  vi.unstubAllGlobals();
});

it("turns a right dock into the centre card while a split view is open, without saving that change", async () => {
  navStore().setState({ aiDockPosition: "right" }); // as restored from the saved choice
  holder.paneB = { id: "patient:B", kind: "patient", refId: "SENTETIK-HASTA-0017" };
  await mount();
  expect(navStore().getState().aiDockPosition).toBe("center");
  expect(writes).toEqual([]); // the saved dock stays "right" for the next visit without a split view
});

it("leaves the collapsed bar and the centre card alone while a split view is open", async () => {
  holder.paneB = { id: "patient:B", kind: "patient", refId: "SENTETIK-HASTA-0017" };
  for (const dock of ["collapsed", "center"] as const) {
    navStore().setState({ aiDockPosition: dock });
    await mount();
    expect(navStore().getState().aiDockPosition).toBe(dock);
  }
  expect(writes).toEqual([]);
});

it("keeps a right dock when no split view is open", async () => {
  navStore().setState({ aiDockPosition: "right" });
  await mount();
  expect(navStore().getState().aiDockPosition).toBe("right");
  expect(writes).toEqual([]);
});
