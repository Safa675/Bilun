import { describe, expect, it } from "vitest";

import {
  buildSutChatContextKey,
  formatSutChatContextPrompt,
  visibleChatMessages,
} from "./sutChatSession";

describe("sutChatSession", () => {
  it("builds stable context keys for cohort and patient views", () => {
    expect(buildSutChatContextKey(null, "Patients")).toBe("cohort::Patients::en");
    expect(buildSutChatContextKey("P-001", "SUT Patient Workspace")).toBe(
      "P-001::SUT Patient Workspace::en",
    );
  });

  it("formats context prompts with scope labels", () => {
    expect(formatSutChatContextPrompt("Compliance", null, "Summarize alerts.")).toBe(
      "[Compliance]\n\nSummarize alerts.",
    );
    expect(
      formatSutChatContextPrompt(
        "SUT Patient Workspace",
        "P-001",
        "Summarize patient state.",
      ),
    ).toBe("[Patient P-001 · SUT Patient Workspace]\n\nSummarize patient state.");
  });

  it("detects and hides auto-briefing user prompts from the visible thread", () => {
    const briefingUser = {
      role: "user" as const,
      content: formatSutChatContextPrompt("Patients", null, "Summarize the cohort."),
    };
    const followUpUser = { role: "user" as const, content: "What about patient P-001?" };
    const assistant = { role: "assistant" as const, content: "Cohort summary..." };

    expect(visibleChatMessages([briefingUser, assistant])).toEqual([assistant]);
    expect(visibleChatMessages([briefingUser, assistant, followUpUser])).toEqual([
      assistant,
      followUpUser,
    ]);
  });
});
