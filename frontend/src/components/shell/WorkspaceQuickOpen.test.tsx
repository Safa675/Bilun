import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import WorkspaceQuickOpen from "./WorkspaceQuickOpen";
import { createWorkspaceStore } from "@/stores/workspaceStore";
import { searchSutPatients } from "@/lib/api/sut";

// Quick open is the only patient search left on the patient page, so "finds a patient by id and opens it" is pinned here.
const nav = vi.hoisted(() => ({ push: vi.fn(), pathname: "/patient/SENTETIK-HASTA-0003" }));
const holder = vi.hoisted(() => ({ store: undefined as unknown }));
const listeners = vi.hoisted(() => ({ keydown: [] as Array<(event: unknown) => void> }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push }), usePathname: () => nav.pathname }));
vi.mock("@/lib/i18n/useTranslations", () => ({ useT: () => (key: string) => key }));
vi.mock("@/stores/workspaceContext", () => ({ useWorkspaceStoreApi: () => holder.store }));
vi.mock("@/components/shell/PatientTabLink", () => ({
  PatientTabContextMenu: () => null,
  useOpenPatientBackground: () => vi.fn(),
}));
vi.mock("@/lib/api/sut", () => ({ searchSutPatients: vi.fn() }));

const renderers: ReactTestRenderer[] = [];

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("window", {
    setTimeout,
    clearTimeout,
    addEventListener: (type: string, handler: (event: unknown) => void) => {
      if (type === "keydown") listeners.keydown.push(handler);
    },
    removeEventListener: (type: string, handler: (event: unknown) => void) => {
      if (type === "keydown") listeners.keydown = listeners.keydown.filter((entry) => entry !== handler);
    },
  });
  listeners.keydown = [];
  nav.push.mockReset();
  vi.mocked(searchSutPatients).mockReset().mockResolvedValue({
    results: [{ patient_id: "SENTETIK-HASTA-0017", age: 68, sex: "E" }],
    total_matched: 1,
  } as Awaited<ReturnType<typeof searchSutPatients>>);
  holder.store = createWorkspaceStore({ tabs: [], activeTabId: null, paneBTabId: null });
});

afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => { renderer.unmount(); });
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function open() {
  let renderer: ReactTestRenderer;
  await act(async () => { renderer = create(<WorkspaceQuickOpen />); });
  renderers.push(renderer!);
  return renderer!;
}

it("Ctrl+K opens the palette, a typed id is searched, and Enter opens that patient", async () => {
  const renderer = await open();
  expect(renderer.root.findAllByProps({ "data-quick-open": true })).toHaveLength(0);

  await act(async () => {
    for (const handler of listeners.keydown) handler({ ctrlKey: true, metaKey: false, key: "k", preventDefault: vi.fn() });
  });
  const input = renderer.root.findByProps({ "data-quick-open-input": true });

  await act(async () => { input.props.onChange({ target: { value: " 0017 " } }); });
  await act(async () => { vi.advanceTimersByTime(200); });
  expect(searchSutPatients).toHaveBeenCalledWith("0017", 8, expect.anything());
  expect(renderer.root.findAllByProps({ "data-quick-open-result": "SENTETIK-HASTA-0017" }).length).toBeGreaterThan(0);

  await act(async () => { input.props.onKeyDown({ key: "Enter", metaKey: false, ctrlKey: false, preventDefault: vi.fn() }); });
  expect(nav.push).toHaveBeenCalledWith("/patient/SENTETIK-HASTA-0017");
});

it("searches nothing for an empty query and is off on the login page", async () => {
  const renderer = await open();
  await act(async () => { (holder.store as ReturnType<typeof createWorkspaceStore>).getState().setQuickOpen(true); });
  const input = renderer.root.findByProps({ "data-quick-open-input": true });
  await act(async () => { input.props.onChange({ target: { value: "   " } }); });
  await act(async () => { vi.advanceTimersByTime(500); });
  expect(searchSutPatients).not.toHaveBeenCalled();

  nav.pathname = "/login";
  await act(async () => { renderer.update(<WorkspaceQuickOpen />); });
  expect((holder.store as ReturnType<typeof createWorkspaceStore>).getState().quickOpen).toBe(false);
  nav.pathname = "/patient/SENTETIK-HASTA-0003";
});
