import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SutHome from "./page";
import SutInlineAIPanel from "@/components/chat/SutInlineAIPanel";
import type { SutChatDockPosition } from "@/stores/storeInterfaces";

// The home page frames its content by the chat dock: only the right dock (a fixed column) uses the full width, so the
// collapsed bar (the default) and the centre card keep the centred max-w-7xl frame. The split view switches the right
// dock off for the panel (allowRightDock) while collapse and open stay.
const state = vi.hoisted(() => ({ dock: "collapsed" as SutChatDockPosition, split: false }));
const navigation = vi.hoisted(() => ({ query: "tab=patients" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(navigation.query),
}));
vi.mock("next/dynamic", () => ({ default: () => () => null }));
vi.mock("@/lib/i18n", () => ({ useT: () => (key: string) => key }));
vi.mock("@/components/chat/SutInlineAIPanel", () => ({ default: () => null }));
vi.mock("@/components/admin/SutHealthPanel", () => ({ default: () => null }));
vi.mock("@/components/admin/useHealthPolling", () => ({ useHealthPolling: vi.fn() }));
vi.mock("@/components/modals/SutHowItWorksModal", () => ({ default: () => null }));
vi.mock("@/components/feedback/ReportProblemModal", () => ({ default: () => null }));
vi.mock("@/components/skeletons/SutSkeletons", () => ({
  SutAnalyticsShellSkeleton: () => null,
  SutOptimizerShellSkeleton: () => null,
}));
vi.mock("@/components/shell/RoleProvider", () => ({ useSessionIdentity: () => null }));
vi.mock("@/lib/auth", () => ({ canUseDeveloper: () => false, requestsDeveloper: () => false }));
vi.mock("@/stores/index", () => ({
  useAiDockPosition: () => state.dock,
  useSetAiDockPosition: () => vi.fn(),
  useWorkspacePaneBTabId: () => (state.split ? "patient:B" : null),
  useHealthStatus: () => null,
  useSetHealthStatus: () => vi.fn(),
  useSetShowAdmin: () => vi.fn(),
  useShowAdmin: () => false,
  useSetShowHowItWorks: () => vi.fn(),
  useShowHowItWorks: () => false,
  useSetShowReportProblem: () => vi.fn(),
  useShowReportProblem: () => false,
  useSetSutChatSession: () => vi.fn(),
  useSutChatSession: () => ({ messages: [], autoText: "" }),
}));

const renderers: ReactTestRenderer[] = [];

async function mount() {
  let renderer: ReactTestRenderer;
  await act(async () => { renderer = create(<SutHome />); });
  renderers.push(renderer!);
  return renderer!;
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  state.dock = "collapsed";
  state.split = false;
  navigation.query = "tab=patients";
});

afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => { renderer.unmount(); });
  vi.unstubAllGlobals();
});

describe("home page frame", () => {
  it.each([
    ["collapsed", "mx-auto max-w-7xl space-y-6"],
    ["center", "mx-auto max-w-7xl space-y-6"],
    ["right", "w-full space-y-6"],
  ] as const)("frames the page for the %s chat dock as '%s'", async (dock, expectedClass) => {
    state.dock = dock;
    const renderer = await mount();
    const frames = renderer.root.findAll(node => node.type === "section" && String(node.props.className).includes("space-y-6"));
    expect(frames).toHaveLength(1);
    expect(frames[0].props.className).toBe(expectedClass);
  });

  it("passes the dock to the one chat panel and keeps the right dock only while no split view is open", async () => {
    state.dock = "center";
    const single = await mount();
    expect(single.root.findByType(SutInlineAIPanel).props).toMatchObject({ dock: "center", allowRightDock: true });
    expect(typeof single.root.findByType(SutInlineAIPanel).props.onDockChange).toBe("function");

    state.split = true;
    const split = await mount();
    expect(split.root.findByType(SutInlineAIPanel).props).toMatchObject({ dock: "center", allowRightDock: false });
  });
});
