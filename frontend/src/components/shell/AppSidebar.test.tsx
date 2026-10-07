import { act, type ReactNode } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AppSidebar from "./AppSidebar";

// First paint of the sidebar: the saved right dock keeps it a 64px rail from the start, because the provider applies the
// saved dock to the store only in a later layout effect. The width variable that shifts the page is set in the same pass.
const saved = vi.hoisted(() => ({ dock: null as string | null, sidebar: null as string | null }));
const widthWrites: string[] = [];
const renderers: ReactTestRenderer[] = [];
let phone = false;

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams("tab=patients"),
}));
vi.mock("next/link", () => ({ default: ({ children }: { children: ReactNode }) => <span>{children}</span> }));
vi.mock("@/components/sut/SyntheticDemoProvenance", () => ({ SyntheticDemoChip: () => null }));
vi.mock("@/components/shell/LocaleSwitcher", () => ({ default: () => null }));
vi.mock("@/components/shell/RoleSwitcher", () => ({ default: () => null }));
vi.mock("@/components/shell/RoleProvider", () => ({ useSessionIdentity: () => ({ authenticated: false }), useUserRole: () => "billing" }));
vi.mock("@/lib/configContext", () => ({ useConfig: () => ({}) }));
vi.mock("@/lib/i18n/useTranslations", () => ({ useT: () => (key: string) => key }));
vi.mock("@/lib/api/sut", () => ({ getMedulaRejectionIngestStatus: vi.fn(async () => ({ ingest_available: false })) }));
vi.mock("@/lib/api/auth", () => ({ endSession: vi.fn() }));
vi.mock("@/lib/authBrowser", () => ({ announceSessionChange: vi.fn(), clearProtectedBrowserState: vi.fn() }));
vi.mock("@/stores/index", () => ({
  useNavigationStoreApi: () => ({ subscribe: () => () => undefined }),
  useSetShowHowItWorks: () => vi.fn(),
  useSetShowReportProblem: () => vi.fn(),
}));

async function mount() {
  let renderer: ReactTestRenderer;
  await act(async () => { renderer = create(<AppSidebar />); });
  renderers.push(renderer!);
  const aside = renderer!.root.findByType("aside");
  return { renderer: renderer!, aside, width: aside.props.style.width, collapsed: aside.props["data-collapsed"] };
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  saved.dock = null;
  saved.sidebar = null;
  phone = false;
  widthWrites.length = 0;
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => (key === "bilun:chat-dock" ? saved.dock : key === "bilun:sidebar-collapsed" ? saved.sidebar : null),
      setItem: vi.fn(),
    },
    matchMedia: () => ({ matches: phone, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    setInterval: () => 1,
    clearInterval: () => undefined,
  });
  vi.stubGlobal("document", {
    documentElement: {
      style: {
        setProperty: (name: string, value: string) => {
          if (name === "--shell-sidebar-width") widthWrites.push(value);
        },
      },
    },
  });
});

afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => { renderer.unmount(); });
  vi.unstubAllGlobals();
});

describe("AppSidebar first width", () => {
  it("opens phone navigation without reserving a rail or changing the saved desktop choice", async () => {
    phone = true;
    saved.dock = "right";
    saved.sidebar = "1";
    const { renderer, aside } = await mount();
    expect(aside.props.hidden).toBe(true);
    expect(widthWrites.every(width => width === "0px")).toBe(true);
    const trigger = renderer.root.findAllByType("button").find(button => button.props["aria-controls"] === "phone-navigation")!;
    await act(async () => trigger.props.onClick());
    expect(aside.props.hidden).toBe(false);
    expect(aside.props["aria-modal"]).toBe(true);
    expect(aside.props["data-mobile-open"]).toBe("true");
    const backdrop = renderer.root.findByProps({ "data-phone-sidebar-backdrop": true });
    await act(async () => backdrop.props.onClick());
    expect(aside.props.hidden).toBe(true);
    expect(window.localStorage.setItem).toHaveBeenCalledWith("bilun:sidebar-collapsed", "1");
    expect(window.localStorage.setItem).not.toHaveBeenCalledWith("bilun:sidebar-collapsed", "0");
  });

  it("renders the existing full-resolution wordmark at a readable size", async () => {
    const { aside } = await mount();
    const logo = aside.findByType("img");
    expect(logo.props.src).toBe("/brand/full.png");
    expect(logo.props.width).toBe(75);
    expect(logo.props.height).toBe(40);
    expect(logo.props.style.height).toBe(40);
  });

  it("keeps the larger crest inside the existing collapsed rail", async () => {
    saved.sidebar = "1";
    const { aside, width } = await mount();
    const logo = aside.findByType("img");
    expect(width).toBe(64);
    expect(logo.props.src).toBe("/brand/nameless.png");
    expect(logo.props.width).toBe(27);
    expect(logo.props.height).toBe(32);
    expect(logo.props.className).toContain("h-8 w-auto");
  });

  it("is the 64px rail from the first paint when the saved chat dock is right", async () => {
    saved.dock = "right";
    const sidebar = await mount();
    expect(sidebar.width).toBe(64);
    expect(sidebar.collapsed).toBe("true");
    expect(widthWrites.at(-1)).toBe("64px");
  });

  it("stays 220px for the collapsed bar, the centre card and a first visit", async () => {
    for (const dock of [null, "collapsed", "center", "garbage"]) {
      saved.dock = dock;
      const sidebar = await mount();
      expect(sidebar.width).toBe(220);
      expect(sidebar.collapsed).toBe("false");
      expect(widthWrites.at(-1)).toBe("220px");
    }
  });

  it("keeps the user's own collapsed choice whatever the dock is", async () => {
    saved.sidebar = "1";
    saved.dock = "center";
    const sidebar = await mount();
    expect(sidebar.width).toBe(64);
    expect(widthWrites.at(-1)).toBe("64px");
  });
});
