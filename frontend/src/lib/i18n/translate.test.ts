import { describe, expect, it } from "vitest";

import { translate } from "@/lib/i18n/translate";
import enMessages from "@/messages/en/index";

describe("i18n translate", () => {
  it("resolves nested keys", () => {
    expect(translate(enMessages, "shell.appTopBar.howItWorks")).toBe("How it works");
  });

  it("interpolates params", () => {
    expect(
      translate(enMessages, "cohort.filterBar.matchedCount", { matched: 3, total: 10 }),
    ).toBe("3 of 10 patients");
  });
});
