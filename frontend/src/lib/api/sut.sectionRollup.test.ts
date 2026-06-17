import { describe, expect, it } from "vitest";

import { sectionRollupRowKey } from "./sut";

describe("sectionRollupRowKey", () => {
  it("combines section_id and section_title for unique keys", () => {
    const a = sectionRollupRowKey({
      section_id: "1",
      section_title: "First title",
    });
    const b = sectionRollupRowKey({
      section_id: "1",
      section_title: "Second title",
    });

    expect(a).not.toBe(b);
    expect(a).toBe("1::First title");
    expect(b).toBe("1::Second title");
  });

  it("handles null fields", () => {
    expect(
      sectionRollupRowKey({ section_id: null, section_title: null }),
    ).toBe("unknown::");
  });
});
