import { afterEach, describe, expect, it, vi } from "vitest";
import { motionScrollBehavior, prefersReducedMotion, runBillCrossfade } from "./motion";

afterEach(() => vi.unstubAllGlobals());

function motionPreference(initial = false) {
  const preference = {
    matches: initial,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal("window", { matchMedia: () => preference });
  return preference;
}

function pane() {
  return { style: { viewTransitionName: "" } } as HTMLElement;
}

function deferredTransition() {
  let finish!: () => void;
  const finished = new Promise<void>((resolve) => { finish = resolve; });
  return { finished, finish, skipTransition: vi.fn() };
}

async function settle() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

describe("interaction motion", () => {
  it("is safe without a browser and keeps scrolling native", () => {
    vi.stubGlobal("window", undefined);
    vi.stubGlobal("document", undefined);
    const update = vi.fn();
    expect(prefersReducedMotion()).toBe(false);
    expect(motionScrollBehavior()).toBe("smooth");
    runBillCrossfade(null, update);
    expect(update).toHaveBeenCalledOnce();
  });

  it("reads the current reduced-motion preference for every scroll", () => {
    const preference = motionPreference();
    expect(motionScrollBehavior()).toBe("smooth");
    preference.matches = true;
    expect(motionScrollBehavior()).toBe("auto");
  });

  it("does not start a bill transition under reduced motion", () => {
    motionPreference(true);
    const startViewTransition = vi.fn();
    vi.stubGlobal("document", { startViewTransition });
    const root = pane();
    const update = vi.fn();
    runBillCrossfade(root, update);
    expect(update).toHaveBeenCalledOnce();
    expect(startViewTransition).not.toHaveBeenCalled();
    expect(root.style.viewTransitionName).toBe("");
  });

  it("updates instantly when native ViewTransition is unavailable", () => {
    motionPreference();
    vi.stubGlobal("document", {});
    const update = vi.fn();
    runBillCrossfade(pane(), update);
    expect(update).toHaveBeenCalledOnce();
  });

  it("names only the owning pane and restores its prior name after settling", async () => {
    const preference = motionPreference();
    const transition = deferredTransition();
    vi.stubGlobal("document", {
      startViewTransition: (update: () => void) => { update(); return transition; },
    });
    const root = pane();
    root.style.viewTransitionName = "previous";
    const sibling = pane();
    const update = vi.fn();
    runBillCrossfade(root, update);
    expect(update).toHaveBeenCalledOnce();
    expect(root.style.viewTransitionName).toMatch(/^bilun-bill-/);
    expect(sibling.style.viewTransitionName).toBe("");
    transition.finish();
    await settle();
    expect(root.style.viewTransitionName).toBe("previous");
    expect(preference.removeEventListener).toHaveBeenCalledOnce();
  });

  it("cancels an active transition if reduced motion is enabled", async () => {
    const preference = motionPreference();
    const transition = deferredTransition();
    vi.stubGlobal("document", {
      startViewTransition: (update: () => void) => { update(); return transition; },
    });
    runBillCrossfade(pane(), vi.fn());
    preference.matches = true;
    preference.addEventListener.mock.calls[0][1]();
    expect(transition.skipTransition).toHaveBeenCalledOnce();
    transition.finish();
    await settle();
  });

  it("drops a superseded update and does not restore an old pane name", async () => {
    motionPreference();
    const callbacks: (() => void)[] = [];
    const transitions = [deferredTransition(), deferredTransition()];
    vi.stubGlobal("document", {
      startViewTransition: (update: () => void) => {
        callbacks.push(update);
        return transitions[callbacks.length - 1];
      },
    });
    const root = pane();
    const oldUpdate = vi.fn();
    const latestUpdate = vi.fn();
    runBillCrossfade(root, oldUpdate);
    runBillCrossfade(root, latestUpdate);
    const latestName = root.style.viewTransitionName;
    callbacks[0]();
    callbacks[1]();
    expect(oldUpdate).not.toHaveBeenCalled();
    expect(latestUpdate).toHaveBeenCalledOnce();
    expect(transitions[0].skipTransition).toHaveBeenCalledOnce();
    transitions[0].finish();
    await settle();
    expect(root.style.viewTransitionName).toBe(latestName);
    transitions[1].finish();
    await settle();
    expect(root.style.viewTransitionName).toBe("");
  });

  it("falls back once if starting the native transition throws", () => {
    motionPreference();
    vi.stubGlobal("document", {
      startViewTransition: () => { throw new Error("unsupported state"); },
    });
    const root = pane();
    const update = vi.fn();
    runBillCrossfade(root, update);
    expect(update).toHaveBeenCalledOnce();
    expect(root.style.viewTransitionName).toBe("");
  });

  it("drops a queued bill selection when the pane's patient changes", async () => {
    motionPreference();
    let callback!: () => void;
    const transition = deferredTransition();
    vi.stubGlobal("document", {
      startViewTransition: (update: () => void) => { callback = update; return transition; },
    });
    const root = { style: { viewTransitionName: "" }, dataset: { patientId: "old" } } as unknown as HTMLElement;
    const update = vi.fn();
    runBillCrossfade(root, update);
    root.dataset.patientId = "new";
    callback();
    expect(update).not.toHaveBeenCalled();
    transition.finish();
    await settle();
    expect(root.style.viewTransitionName).toBe("");
  });

  it.each(["reduced", "instant"])("keeps the latest selection when %s motion bypasses a queued transition", async (mode) => {
    const preference = motionPreference();
    let callback!: () => void;
    const transition = deferredTransition();
    vi.stubGlobal("document", {
      startViewTransition: (update: () => void) => { callback = update; return transition; },
    });
    const root = pane();
    root.style.viewTransitionName = "previous";
    const selections: string[] = [];
    runBillCrossfade(root, () => selections.push("A"));
    if (mode === "reduced") {
      preference.matches = true;
      preference.addEventListener.mock.calls[0][1]();
    }
    runBillCrossfade(root, () => selections.push("B"), mode !== "instant");
    callback();
    try {
      expect(selections).toEqual(["B"]);
      expect(root.style.viewTransitionName).toBe("previous");
    } finally {
      transition.finish();
      await settle();
    }
  });
});
