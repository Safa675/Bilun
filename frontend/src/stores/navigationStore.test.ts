import { describe, expect, it } from "vitest";

import { createNavigationStore } from "./navigationStore";

describe("createNavigationStore", () => {
  it("starts with the expected shell defaults", () => {
    const store = createNavigationStore();

    expect(store.getState()).toMatchObject({
      showHowItWorks: false,
      showAdmin: false,
      aiDockPosition: "center",
    });
  });

  it("updates shell flags through its actions", () => {
    const store = createNavigationStore();

    store.getState().setShowHowItWorks(true);
    store.getState().setShowAdmin(true);
    store.getState().setAiDockPosition("right");

    expect(store.getState()).toMatchObject({
      showHowItWorks: true,
      showAdmin: true,
      aiDockPosition: "right",
    });
  });
});
