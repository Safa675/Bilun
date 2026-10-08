import { act } from "react";
import { create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { NavigationProvider, useAiDockPosition } from "./navigationContext";

// The saved chat dock is applied after hydration: the first render must equal the server's (the default dock), then the
// saved choice replaces it before paint, without writing it back.
const storage = vi.hoisted(() => ({ value: null as string | null, writes: [] as Array<[string, string]> }));
const seen: string[] = [];
const renderers: ReactTestRenderer[] = [];

function DockProbe() {
  seen.push(useAiDockPosition());
  return null;
}

async function mount() {
  let renderer: ReactTestRenderer;
  await act(async () => {
    renderer = create(<NavigationProvider><DockProbe /></NavigationProvider>);
  });
  renderers.push(renderer!);
  return renderer!;
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  storage.value = null;
  storage.writes = [];
  seen.length = 0;
  vi.stubGlobal("window", {
    localStorage: {
      getItem: () => storage.value,
      setItem: (key: string, value: string) => storage.writes.push([key, value]),
    },
  });
});

afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => { renderer.unmount(); });
  vi.unstubAllGlobals();
});

it.each(["right", "center", "collapsed"] as const)("applies a saved %s dock after the first render and does not write it back", async (saved) => {
  storage.value = saved;
  await mount();
  expect(seen[0]).toBe("collapsed"); // the server's tree
  expect(seen.at(-1)).toBe(saved);
  expect(storage.writes).toEqual([]);
});

it.each([null, "left", "garbage", ""])("keeps the collapsed default for a missing or unknown saved value (%j)", async (saved) => {
  storage.value = saved;
  await mount();
  expect(new Set(seen)).toEqual(new Set(["collapsed"]));
  expect(storage.writes).toEqual([]);
});

it("still renders the default when the browser blocks storage", async () => {
  vi.stubGlobal("window", { localStorage: { getItem: () => { throw new Error("blocked"); } } });
  await mount();
  expect(new Set(seen)).toEqual(new Set(["collapsed"]));
});
