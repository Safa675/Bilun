import { describe, expect, it } from "vitest";
import {
  compareRuns,
  compareSnapshots,
  hiddenMarkers,
  normaliseLines,
  tokenise,
} from "./numbers-parity.mjs";

describe("normaliseLines", () => {
  it("collapses whitespace, NBSP, narrow NBSP and blank lines", () => {
    const nbsp = String.fromCharCode(0xa0);
    const narrow = String.fromCharCode(0x202f);
    expect(normaliseLines(`  a${nbsp} b ${narrow}c\n\n\t d\t\n`)).toEqual(["a b c", "d"]);
  });
});

describe("tokenise money", () => {
  it("canonicalises EN amounts", () => {
    const t = tokenise(["Total 29,039.29 TRY", "9000.00 TRY", "1,234 TRY", "-1,250.50 TRY", "0.00 TRY"]);
    expect(t.money).toEqual({ "-1250.50": 1, "0.00": 1, "1234": 1, "29039.29": 1, "9000.00": 1 });
  });

  it("canonicalises TR amounts, including the backend postfix form", () => {
    const t = tokenise(["₺29.039,29", "₺1.234", "₺-1.250,50", "paket (9000.00 ₺)", "₺0,00"]);
    expect(t.money).toEqual({ "-1250.50": 1, "0.00": 1, "1234": 1, "29039.29": 1, "9000.00": 1 });
  });

  it("gives EN and TR renderings of one number the same key", () => {
    expect(tokenise(["29,039.29 TRY"]).money).toEqual(tokenise(["₺29.039,29"]).money);
  });

  it("does not read a plain number as money", () => {
    expect(tokenise(["50 of 50 patients"]).money).toEqual({});
  });
});

describe("tokenise counts, percents, dates, markers", () => {
  it("counts numeric words and keeps percents apart", () => {
    const t = tokenise(["50 of 50 patients", "Actions 14", "Rate 60.0%", "(3)", "SENTETIK-HASTA-0003", "§3.1.1(11)"]);
    expect(t.counts).toEqual({ "14": 1, "3": 1, "50": 2 });
    expect(t.percents).toEqual({ "60.0%": 1 });
  });

  it("masks dates and times", () => {
    const t = tokenise(["Oct 6, 2026", "6 Eki 2026", "06.10.2026 15:45", "10/6/26, 3:45 PM", "2023-02-19", "12:30"]);
    expect(t.counts).toEqual({});
  });

  it("counts honesty markers per line and ignores the chat stub text", () => {
    const t = tokenise(["Partial exact", "Totals unavailable until inputs are exact", "Chat is temporarily unavailable. Please try later."]);
    expect(t.markers).toEqual({ partial: 1, unavailable: 1 });
  });

  it("is deterministic and independent of line order", () => {
    const a = tokenise(["9,000.00 TRY 2 10", "1,650.00 TRY 1 2"]);
    const b = tokenise(["1,650.00 TRY 1 2", "9,000.00 TRY 2 10"]);
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
    expect(Object.keys(a.money)).toEqual(["1650.00", "9000.00"]);
  });

  it("does not mistake SUT section numbers for dates", () => {
    // "§3.1.1(11)" is an identifier (not a count); the bare "3.1.12" is kept as a number word.
    expect(tokenise(["§3.1.1(11) and 3.1.12"]).counts).toEqual({ "3.1.12": 1 });
  });
});

describe("compareSnapshots", () => {
  const base = tokenise(["29,039.29 TRY", "29,039.29 TRY", "26 actions"]);
  it("passes identical snapshots", () => {
    expect(compareSnapshots(base, tokenise(["29,039.29 TRY", "29,039.29 TRY", "26 actions"])).ok).toBe(true);
  });
  it("fails when a value changes", () => {
    const diff = compareSnapshots(base, tokenise(["29,039.30 TRY", "29,039.30 TRY", "26 actions"]));
    expect(diff.ok).toBe(false);
    expect(diff.missing).toEqual([{ kind: "money", value: "29039.29", before: 2 }]);
    expect(diff.added).toEqual([{ kind: "money", value: "29039.30", after: 2 }]);
  });
  it("treats a repeated or merged figure as a warning unless strict", () => {
    const after = tokenise(["29,039.29 TRY", "26 actions"]);
    expect(compareSnapshots(base, after).ok).toBe(true);
    expect(compareSnapshots(base, after).multiplicity).toHaveLength(1);
    expect(compareSnapshots(base, after, { strictMultiplicity: true }).ok).toBe(false);
  });
});

describe("compareRuns", () => {
  const state = (lines, visibleLines = lines) => ({
    identity: "public",
    expanded: tokenise(lines),
    visible: tokenise(visibleLines),
  });
  const baseline = { "en/patient-0003/default": state(["29,039.29 TRY", "Partial exact", "26 actions"]) };

  it("accepts an unchanged run", () => {
    expect(compareRuns(baseline, structuredClone(baseline)).ok).toBe(true);
  });
  it("fails on a missing state and on an invented amount", () => {
    expect(compareRuns(baseline, {}).failures[0].problem).toBe("state_missing_in_candidate");
    const changed = { "en/patient-0003/default": state(["29,039.29 TRY", "1.00 TRY", "Partial exact", "26 actions"]) };
    expect(compareRuns(baseline, changed).failures).toEqual([
      { key: "en/patient-0003/default", problem: "value_added", kind: "money", value: "1.00", after: 1 },
    ]);
  });
  it("accepts a reasoned exception once and reports stale ones", () => {
    const changed = { "en/patient-0003/default": state(["29,039.29 TRY", "Partial exact", "26 actions", "Top 3 actions"]) };
    const allow = {
      added: [
        { key: "en/patient-0003/default", kind: "counts", value: "3", reason: "new heading" },
        { key: "en/patient-0003/default", kind: "counts", value: "99", reason: "stale" },
      ],
    };
    const result = compareRuns(baseline, changed, { allow });
    expect(result.ok).toBe(true);
    expect(result.unusedAllow).toHaveLength(1);
  });
  it("fails when a partial/unavailable marker is hidden by collapsing", () => {
    const collapsed = { "en/patient-0003/default": state(["29,039.29 TRY", "Partial exact", "26 actions"], ["29,039.29 TRY", "26 actions"]) };
    expect(hiddenMarkers(baseline["en/patient-0003/default"].visible, collapsed["en/patient-0003/default"].visible)).toEqual(["partial"]);
    expect(compareRuns(baseline, collapsed).failures.map((f) => f.problem)).toEqual(["marker_hidden_in_default_view"]);
  });
  it("refuses to compare different identities", () => {
    const other = { "en/patient-0003/default": { ...structuredClone(baseline["en/patient-0003/default"]), identity: "dev" } };
    expect(compareRuns(baseline, other).failures.map((f) => f.problem)).toContain("identity_differs");
  });
});
