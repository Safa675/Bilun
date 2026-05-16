import { describe, expect, it } from "vitest";

import { shouldEnterSutWorkspace, SUT_WORKSPACE_STORAGE_KEY } from "./sutHomeShell";

describe("sutHomeShell helpers", () => {
  it("prefers an explicit tab query or persisted flag for entering the workspace", () => {
    expect(shouldEnterSutWorkspace("analytics", null)).toBe(true);
    expect(shouldEnterSutWorkspace(null, "1")).toBe(true);
    expect(shouldEnterSutWorkspace(undefined, "0")).toBe(false);
    expect(shouldEnterSutWorkspace(null, null)).toBe(false);
  });

  it("uses the expected storage key", () => {
    expect(SUT_WORKSPACE_STORAGE_KEY).toBe("ilay-sut-workspace-entered");
  });
});
