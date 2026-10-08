import { afterEach, describe, expect, it, vi } from "vitest";

import { createNavigationStore } from "./navigationStore";

describe("createNavigationStore", () => {
  it("starts with the expected shell defaults", () => {
    const store = createNavigationStore();

    expect(store.getState()).toMatchObject({
      showHowItWorks: false,
      showAdmin: false,
      showReportProblem: false,
      aiDockPosition: "collapsed",
    });
  });

  it("updates shell flags through its actions", () => {
    const store = createNavigationStore();

    store.getState().setShowHowItWorks(true);
    store.getState().setShowAdmin(true);
    store.getState().setShowReportProblem(true);
    store.getState().setAiDockPosition("right");

    expect(store.getState()).toMatchObject({
      showHowItWorks: true,
      showAdmin: true,
      showReportProblem: true,
      aiDockPosition: "right",
    });
  });

  describe("dock persistence", () => {
    afterEach(() => vi.unstubAllGlobals());

    it("remembers a dock the user chose, but not a change forced by the layout", () => {
      const writes: Array<[string, string]> = [];
      vi.stubGlobal("window", {
        localStorage: { getItem: () => null, setItem: (key: string, value: string) => writes.push([key, value]) },
      });
      const store = createNavigationStore();

      store.getState().setAiDockPosition("right");
      store.setState({ aiDockPosition: "center" }); // split view turns the right column off
      store.getState().setAiDockPosition("collapsed");

      expect(writes).toEqual([
        ["bilun:chat-dock", "right"],
        ["bilun:chat-dock", "collapsed"],
      ]);
      expect(store.getState().aiDockPosition).toBe("collapsed");
    });
  });
});
