import { describe, expect, it } from "vitest";

import { createUIStateStore } from "./uiStateStore";

describe("createUIStateStore", () => {
  it("stores health status separately from chat sessions", () => {
    const store = createUIStateStore();

    store.getState().setHealthStatus({
      status: "ready",
      patients: 12,
      build_id: "build-42",
    });

    expect(store.getState().healthStatus).toEqual({
      status: "ready",
      patients: 12,
      build_id: "build-42",
    });
    expect(store.getState().sutChatSessions).toEqual({});
  });

  it("stores and clears chat sessions by key", () => {
    const store = createUIStateStore();

    store.getState().setSutChatSession("patient:P-001", {
      messages: [{ role: "user", content: "hello" }],
      autoText: "analysis",
      autoFiredKey: "cohort::Patients",
      briefedContextKeys: ["cohort::Patients"],
    });

    expect(store.getState().sutChatSessions["patient:P-001"]).toEqual({
      messages: [{ role: "user", content: "hello" }],
      autoText: "analysis",
      autoFiredKey: "cohort::Patients",
      briefedContextKeys: ["cohort::Patients"],
    });

    store.getState().clearSutChatSession("patient:P-001");
    expect(store.getState().sutChatSessions["patient:P-001"]).toBeUndefined();
  });
});
