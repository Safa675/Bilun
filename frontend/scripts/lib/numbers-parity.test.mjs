import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  compareRuns,
  compareSnapshots,
  describeItem,
  foldLabel,
  foldText,
  hiddenAmounts,
  hiddenMarkers,
  normaliseLines,
  reducedMarkers,
  SCHEMA,
  tokenise,
  verdict,
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

describe("honesty markers: vocabulary and Turkish case folding", () => {
  const kinds = (lines) => Object.keys(tokenise(lines).markers).sort();

  it("folds Turkish dotted and dotless i, so CSS-uppercased text still matches", () => {
    expect(foldText("KISMİ KESİN")).toBe("kismi kesin");
    expect(foldText("Kısmi kesin")).toBe("kismi kesin");
    expect(tokenise(["Kısmi kesin"]).markers).toEqual({ partial: 1 });
    expect(tokenise(["KISMİ KESİN"]).markers).toEqual({ partial: 1 });
    expect(tokenise(["KULLANILAMIYOR"]).markers).toEqual({ unavailable: 1 });
    expect(tokenise(["Kullanılamayan Hastalar"]).markers).toEqual({ unavailable: 1 });
    expect(tokenise(["HESAPLANAMAZ"]).markers).toEqual({ cannotCompute: 1 });
    expect(tokenise(["PARTIAL EXACT"]).markers).toEqual({ partial: 1 });
  });

  it("knows the not-evaluated and missing-input wording in EN and TR", () => {
    expect(kinds(["Not evaluated — missing inputs (claim_type)"])).toEqual(["missingInputs", "notEvaluated"]);
    expect(kinds(["Değerlendirilmedi — eksik girdiler (claim_type)"])).toEqual(["missingInputs", "notEvaluated"]);
    expect(kinds(["DEĞERLENDİRİLMEDİ — EKSİK GİRDİLER"])).toEqual(["missingInputs", "notEvaluated"]);
    expect(kinds(["Structural checks: 23 evaluations · 0 findings · 2 missing inputs"])).toEqual(["missingInputs"]);
    expect(kinds(["Yapısal kontroller: 4 değerlendirme · 1 eksik girdi"])).toEqual(["missingInputs"]);
  });

  it("knows the unverified-amount and partial-total wording", () => {
    expect(kinds(["Amount unverified"])).toEqual(["amountUnverified"]);
    expect(kinds(["Tutar doğrulanmadı"])).toEqual(["amountUnverified"]);
    expect(kinds(["TUTAR DOĞRULANMADI"])).toEqual(["amountUnverified"]);
    expect(kinds(["PARTIAL RULE-CALCULATED TOTAL"])).toEqual(["partial"]);
    expect(kinds(["Partial-exact recovery review: exact category-level savings"])).toEqual(["partial"]);
    expect(kinds(["Kısmi kural hesaplı toplam"])).toEqual(["partial"]);
  });

  it("does not turn ordinary prose into markers", () => {
    expect(kinds(["Billed (at risk)", "Eligible", "Waiver grounds: EK-1A · Acil · Koruyucu."])).toEqual([]);
  });
});

describe("honesty markers: the uncertainty wording the UI really shows (strings read from messages/)", () => {
  const messagesDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../src/messages");
  /** Every string value of `key` in messages/<locale>/<file>.ts (one entry per occurrence). */
  function messageValues(locale, file, key) {
    const source = fs.readFileSync(path.join(messagesDir, locale, `${file}.ts`), "utf8");
    const re = new RegExp(`(?:"${key}"|\\b${key})\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"`, "g");
    return [...source.matchAll(re)].map((m) => m[1].replace(/\\"/g, '"'));
  }
  const markersOf = (text) => Object.keys(tokenise([text]).markers);

  // [file, key, marker kinds each locale's text must carry]
  const expectations = [
    ["billing", "riskNotice", ["unverified"]], // Reimbursement condition could not be verified - MEDULA rejection risk
    ["billing", "corpusNoncoverage", ["cannotCompute"]], // The encoded rule corpus cannot evaluate this drug
    ["billing", "corpusNoncoverageDetail", ["manualReview", "notInferred"]], // manual SUT review is required and no financial value is inferred
    ["billing", "indication_mismatch", ["mismatch"]], // No diagnosis-drug match found
    ["billing", "missing_board_report", ["unverified"]],
    ["billing", "inpatient_supply_required", ["unverified"]],
    ["billing", "needs_dose_verification", ["unverified"]],
    ["billing", "report_duration_mismatch", ["mismatch"]],
    ["billing", "ambiguous_route", ["mismatch"]],
    ["billing", "sourceLocator", ["unverified"]],
    ["billing", "sourceUnverified", ["unverified"]],
    ["billing", "procedure_line_charge_not_cent_exact", ["notExact"]],
    ["optimizer", "incompleteFindings", ["unverified"]], // compliance cannot be confirmed
    ["optimizer", "partialResults", ["incompleteList"]], // More findings are available
  ];

  for (const locale of ["en", "tr"]) {
    for (const [file, key, kinds] of expectations) {
      it(`${locale} ${file}.${key} is counted as ${kinds.join(" + ")}`, () => {
        const values = messageValues(locale, file, key);
        expect(values.length, `${key} not found in messages/${locale}/${file}.ts`).toBeGreaterThan(0);
        for (const value of values) for (const kind of kinds) expect(markersOf(value), value).toContain(kind);
      });
    }
    it(`${locale} price lines that are estimates are counted as estimated`, () => {
      const estimates = [...messageValues(locale, "billing", "scopeFootnote")].filter((text) => (locale === "en" ? /estimated/i : /tahmin/i).test(text));
      expect(estimates.length).toBeGreaterThanOrEqual(2); // procedure add-ons and missing materials
      for (const text of estimates) expect(markersOf(text), text).toContain("estimated");
    });
  }

  it("also reads the uppercase and dotless-i renderings of the new Turkish wording", () => {
    expect(markersOf("GERİ ÖDEME KOŞULU DOĞRULANAMADI — MEDULA REDDİ RİSKİ")).toContain("unverified");
    expect(markersOf("KODLANMIŞ KURAL DERLEMİ BU İLACI DEĞERLENDİREMİYOR")).toContain("cannotCompute");
    expect(markersOf("TAHMİNİ KURUM ÖDEMESİ ARTIŞI")).toContain("estimated");
    expect(markersOf("TANI–İLAÇ EŞLEŞMESİ BULUNAMADI")).toContain("mismatch");
  });

  it("does not count ordinary labels and amounts", () => {
    expect(markersOf("Total billed")).toEqual([]);
    expect(markersOf("Doküman")).toEqual([]);
    expect(markersOf("Patient ID Age Sex Recoverable Priority Actions Top action")).toEqual([]);
  });

  it("fails a collapse that hides an uncertainty line the old vocabulary could not see (the review's repro)", () => {
    const line = "Reimbursement condition could not be verified — MEDULA rejection risk";
    const page = ["Drug indication", line, "The encoded rule corpus cannot evaluate this drug", "A14551"];
    const key = "en/1440x900/patient-0029/default";
    const state = (visible) => ({ schema: SCHEMA, identity: "public", expanded: tokenise(page), visible: tokenise(visible) });
    const report = compareRuns({ [key]: state(page) }, { [key]: state(page.filter((l) => l !== line)) });
    expect(report.ok).toBe(false);
    expect(report.failures.map((f) => [f.problem, f.value])).toEqual([["marker_hidden_in_default_view", "unverified"]]);
    const evaluate = compareRuns({ [key]: state(page) }, { [key]: state(page.filter((l) => !/cannot evaluate/.test(l))) });
    expect(evaluate.failures.map((f) => [f.problem, f.value])).toEqual([["marker_hidden_in_default_view", "cannotCompute"]]);
  });
});

describe("placeholders and labelled amounts", () => {
  it("counts lone dash lines only, not dashes inside prose", () => {
    expect(tokenise(["Billed (at risk)", "—", "Risk — review required", "–"]).placeholders).toEqual({ dash: 2 });
  });

  it("ties a standalone amount to the label above it", () => {
    const t = tokenise(["TOTAL BILLED", "66,524.22 TRY", "EXPECTED PAYABLE", "35,739.89 TRY", "BILLS", "5"]);
    expect(t.labelled).toEqual({
      "EXPECTED PAYABLE": { "35739.89": 1 },
      "TOTAL BILLED": { "66524.22": 1 },
    });
  });

  it("does not tie amounts inside table rows or prose, and reads TR amounts the same way", () => {
    expect(tokenise(["Drug A 5 TRY", "Drug B 6 TRY", "paket (9000.00 ₺)"]).labelled).toEqual({});
    expect(tokenise(["TOPLAM FATURALANAN", "₺66.524,22"]).labelled).toEqual({ "TOPLAM FATURALANAN": { "66524.22": 1 } });
  });

  it("does not use a line that is itself an amount, a number or a very long text as the label", () => {
    expect(tokenise(["12 TRY", "13 TRY"]).labelled).toEqual({});
    expect(tokenise(["5", "13 TRY"]).labelled).toEqual({});
    expect(tokenise(["x".repeat(81), "13 TRY"]).labelled).toEqual({});
  });
});

describe("a missing amount must not turn into a zero amount", () => {
  const key = "en/1440x900/patient-0017/default";
  const lines = ["Billed (at risk)", "—", "Paid so far", "0.00 TRY", "Other", "0.00 TRY", "Risk — review required"];
  const state = (l, visibleLines = l) => ({ schema: SCHEMA, identity: "public", expanded: tokenise(l), visible: tokenise(visibleLines) });
  const baseline = { [key]: state(lines) };
  const zeroed = lines.map((l, i) => (i === 1 ? "0.00 TRY" : l));

  it("fails (in the default mode) when the zero-amount count rises and the placeholder is gone", () => {
    const report = compareRuns(baseline, { [key]: state(zeroed) });
    expect(report.ok).toBe(false);
    expect(report.failures.map((f) => f.problem).sort()).toEqual(["placeholder_removed", "zero_amount_added"]);
    expect(report.failures.find((f) => f.problem === "zero_amount_added")).toMatchObject({ before: 2, after: 3 });
  });

  it("fails when only the placeholder is hidden", () => {
    const hidden = lines.filter((_, i) => i !== 1);
    expect(compareRuns(baseline, { [key]: state(hidden) }).failures.map((f) => f.problem)).toEqual(["placeholder_removed"]);
  });

  it("keeps a plain repeat of a non-zero amount a warning and a drop of a zero amount a warning", () => {
    const nonZero = { [key]: state(["TOTAL", "5.00 TRY", "OTHER", "5.00 TRY"]) };
    const merged = { [key]: state(["TOTAL", "5.00 TRY"]) };
    expect(compareRuns(nonZero, merged).ok).toBe(true);
    expect(compareRuns(nonZero, merged).warnings.map((w) => w.problem)).toEqual(["multiplicity_changed", "label_not_in_candidate"]);
    const fewerZeros = lines.filter((_, i) => i !== 5 && i !== 4);
    const report = compareRuns(baseline, { [key]: state(fewerZeros) });
    expect(report.failures).toEqual([]);
    // "Other 0.00 TRY" was removed together with its label: the amount count drops and the label is reported as gone
    expect(report.warnings.map((w) => w.problem)).toEqual(["multiplicity_changed", "label_not_in_candidate"]);
  });

  it("lets a reasoned allow entry waive each failure once, and reports unused ones", () => {
    const allow = {
      added: [
        { key, kind: "zeroAmounts", value: "total", reason: "summary row shows the paid amount twice" },
        { key, kind: "placeholders", value: "dash", reason: "dash line replaced by Amount unverified" },
        { key, kind: "zeroAmounts", value: "total", reason: "stale" },
      ],
    };
    const report = compareRuns(baseline, { [key]: state(zeroed) }, { allow });
    expect(report.ok).toBe(true);
    expect(report.unusedAllow).toHaveLength(1);
  });
});

describe("amounts must stay under their label", () => {
  const key = "en/1440x900/patient-0003/default";
  const state = (l) => ({ schema: SCHEMA, identity: "public", expanded: tokenise(l), visible: tokenise(l) });
  const base = ["TOTAL RECOVERABLE (CLAIM-BACKED)", "29,039.29 TRY", "EXPECTED PAYABLE", "35,739.89 TRY", "BILLS", "5"];

  it("fails when two amounts swap labels although the multiset of amounts is unchanged", () => {
    const swapped = ["TOTAL RECOVERABLE (CLAIM-BACKED)", "35,739.89 TRY", "EXPECTED PAYABLE", "29,039.29 TRY", "BILLS", "5"];
    expect(tokenise(base).money).toEqual(tokenise(swapped).money);
    const report = compareRuns({ [key]: state(base) }, { [key]: state(swapped) });
    expect(report.ok).toBe(false);
    expect(report.failures.map((f) => f.problem)).toEqual(["label_amount_changed", "label_amount_changed"]);
  });

  it("accepts a moved block and a block repeated under the same label", () => {
    const moved = ["BILLS", "5", "EXPECTED PAYABLE", "35,739.89 TRY", "TOTAL RECOVERABLE (CLAIM-BACKED)", "29,039.29 TRY"];
    const movedReport = compareRuns({ [key]: state(base) }, { [key]: state(moved) });
    expect(movedReport.ok).toBe(true);
    expect(movedReport.warnings).toEqual([]);
    const repeated = [...base, "EXPECTED PAYABLE", "35,739.89 TRY"];
    expect(compareRuns({ [key]: state(base) }, { [key]: state(repeated) }).failures).toEqual([]);
  });

  it("still fails a swap when the labels were only re-cased (Phase 5 turns forced uppercase off)", () => {
    const recased = ["Total recoverable (claim-backed)", "35,739.89 TRY", "Expected payable", "29,039.29 TRY", "Bills", "5"];
    const report = compareRuns({ [key]: state(base) }, { [key]: state(recased) });
    expect(report.ok).toBe(false);
    expect(report.failures.map((f) => [f.problem, f.value])).toEqual([
      ["label_amount_changed", "expected payable"],
      ["label_amount_changed", "total recoverable (claim-backed)"],
    ]);
    // Turkish dotted and dotless i: CSS uppercases "kurtarılabilir" to "KURTARILABİLİR" and "fiyat" to "FİYAT"
    const tr = (l) => ({ schema: SCHEMA, identity: "public", expanded: tokenise(l), visible: tokenise(l) });
    const upper = ["TOPLAM KURTARILABİLİR", "₺29.039,29", "FİYAT FARKI", "₺35.739,89"];
    const lower = ["Toplam kurtarılabilir", "₺35.739,89", "Fiyat farkı", "₺29.039,29"];
    expect(compareRuns({ [key]: tr(upper) }, { [key]: tr(lower) }).failures.map((f) => f.problem)).toEqual(["label_amount_changed", "label_amount_changed"]);
    expect(compareRuns({ [key]: tr(upper) }, { [key]: tr(["Toplam kurtarılabilir", "₺29.039,29", "Fiyat farkı", "₺35.739,89"]) }).ok).toBe(true);
    expect(foldLabel("TOPLAM  KURTARILABİLİR ")).toBe("toplam kurtarilabilir");
  });

  it("warns for a renamed label instead of skipping it silently, and the verdict says so", () => {
    const renamed = ["Recoverable (claim-backed)", "35,739.89 TRY", "EXPECTED PAYABLE", "29,039.29 TRY", "BILLS", "5"];
    const report = compareRuns({ [key]: state(base) }, { [key]: state(renamed) });
    // the swap is hidden behind the rename, so the tool cannot fail it: it must at least say that one label was not checked
    expect(report.failures.map((f) => f.problem)).toEqual(["label_amount_changed"]);
    expect(report.warnings.map((w) => [w.problem, w.value, w.before])).toEqual([["label_not_in_candidate", "total recoverable (claim-backed)", ["29039.29"]]]);
    const onlyRename = ["Recoverable (claim-backed)", "29,039.29 TRY", "EXPECTED PAYABLE", "35,739.89 TRY", "BILLS", "5"];
    const renameReport = compareRuns({ [key]: state(base) }, { [key]: state(onlyRename) });
    expect(renameReport.ok).toBe(true);
    expect(renameReport.warnings.map((w) => w.problem)).toEqual(["label_not_in_candidate"]);
    expect(verdict(renameReport).line).toMatch(/^PARITY OK WITH 1 WARNING:.*not proof that no number changed/);
    expect(describeItem(renameReport.warnings[0])).toBe("en/1440x900/patient-0003/default  label_not_in_candidate  labelled total recoverable (claim-backed) ([29039.29] -> -)");
  });

  it("fails a renamed label with strictLabels unless an allow entry names it", () => {
    const onlyRename = ["Recoverable (claim-backed)", "29,039.29 TRY", "EXPECTED PAYABLE", "35,739.89 TRY", "BILLS", "5"];
    const strict = compareRuns({ [key]: state(base) }, { [key]: state(onlyRename) }, { strictLabels: true });
    expect(strict.ok).toBe(false);
    expect(strict.failures.map((f) => [f.problem, f.value])).toEqual([["label_not_in_candidate", "total recoverable (claim-backed)"]]);
    expect(strict.warnings).toEqual([]);
    const allow = { added: [{ key, kind: "labelled", value: "TOTAL RECOVERABLE (CLAIM-BACKED)", reason: "renamed to Recoverable (claim-backed), amount checked by hand" }] };
    const waived = compareRuns({ [key]: state(base) }, { [key]: state(onlyRename) }, { strictLabels: true, allow });
    expect(waived.ok).toBe(true);
    expect(waived.unusedAllow).toEqual([]);
    expect(verdict(waived).line).toBe("PARITY OK: no number changed");
  });

  it("matches an allow entry written with the label as displayed", () => {
    const swapped = ["Total recoverable (claim-backed)", "35,739.89 TRY", "Expected payable", "29,039.29 TRY", "Bills", "5"];
    const allow = { added: ["TOTAL RECOVERABLE (CLAIM-BACKED)", "EXPECTED PAYABLE"].map((value) => ({ key, kind: "labelled", value, reason: "tiles reordered by design" })) };
    const report = compareRuns({ [key]: state(base) }, { [key]: state(swapped) }, { allow });
    expect(report.ok).toBe(true);
    expect(report.unusedAllow).toEqual([]);
  });

  it("can be waived per label with a reason", () => {
    const swapped = ["TOTAL RECOVERABLE (CLAIM-BACKED)", "35,739.89 TRY", "EXPECTED PAYABLE", "29,039.29 TRY", "BILLS", "5"];
    const allow = {
      added: ["TOTAL RECOVERABLE (CLAIM-BACKED)", "EXPECTED PAYABLE"].map((value) => ({ key, kind: "labelled", value, reason: "tiles reordered by design" })),
    };
    expect(compareRuns({ [key]: state(base) }, { [key]: state(swapped) }, { allow }).ok).toBe(true);
  });
});

describe("default-view honesty wording is compared by lines, not by kind", () => {
  const key = "en/1440x900/patient-0003/default";
  const state = (expanded, visible) => ({ schema: SCHEMA, identity: "public", expanded: tokenise(expanded), visible: tokenise(visible) });
  const all = ["Partial exact", "Partial exact", "Not evaluated — missing inputs (a)", "Not evaluated — missing inputs (b)", "Not evaluated — missing inputs (c)"];
  const baseline = { [key]: state(all, all) };

  it("fails when one of two partial lines leaves the default view, and when two of three not-evaluated lines do", () => {
    const oneLess = { [key]: state(all, all.filter((l, i) => i !== 1)) };
    const report = compareRuns(baseline, oneLess);
    expect(report.failures.map((f) => [f.problem, f.value, f.before, f.after])).toEqual([["marker_reduced_in_default_view", "partial", 2, 1]]);
    const twoLess = { [key]: state(all, all.filter((l, i) => i !== 3 && i !== 4)) };
    const second = compareRuns(baseline, twoLess);
    expect(second.failures.map((f) => [f.problem, f.value, f.before, f.after])).toEqual([
      ["marker_reduced_in_default_view", "missingInputs", 3, 1],
      ["marker_reduced_in_default_view", "notEvaluated", 3, 1],
    ]);
    expect(reducedMarkers(baseline[key].visible, twoLess[key].visible)).toHaveLength(2);
  });

  it("fails with the old problem name when a kind disappears entirely, and can be waived for a reason", () => {
    const none = { [key]: state(all, ["Something else"]) };
    expect(compareRuns(baseline, none).failures.map((f) => f.problem)).toContain("marker_hidden_in_default_view");
    expect(hiddenMarkers(baseline[key].visible, none[key].visible).sort()).toEqual(["missingInputs", "notEvaluated", "partial"]);
    const allow = {
      removed: ["partial", "missingInputs", "notEvaluated"].map((value) => ({ key, kind: "markers", value, reason: "collapsed into a header line" })),
    };
    expect(compareRuns(baseline, none, { allow }).ok).toBe(true);
  });

  it("warns, but does not fail, when wording leaves the whole page", () => {
    const fewer = { [key]: state(all.slice(0, 4), all.slice(0, 4)) };
    const visibleFewer = compareRuns(baseline, fewer);
    expect(visibleFewer.failures.map((f) => f.problem)).toContain("marker_reduced_in_default_view");
    const expandedOnly = compareRuns({ [key]: state(all, []) }, { [key]: state(all.slice(0, 4), []) });
    expect(expandedOnly.ok).toBe(true);
    expect(expandedOnly.warnings.map((w) => [w.problem, w.value, w.before, w.after])).toEqual([
      ["marker_lines_removed_from_page", "missingInputs", 3, 2],
      ["marker_lines_removed_from_page", "notEvaluated", 3, 2],
    ]);
  });

  it("warns when an amount leaves the default view but is still on the page", () => {
    const money = { [key]: state(["TOTAL BILLED", "66,524.22 TRY"], ["TOTAL BILLED", "66,524.22 TRY"]) };
    const collapsed = { [key]: state(["TOTAL BILLED", "66,524.22 TRY"], ["TOTAL BILLED"]) };
    expect(hiddenAmounts(money[key].visible, collapsed[key].visible)).toEqual(["66524.22"]);
    const report = compareRuns(money, collapsed);
    expect(report.ok).toBe(true);
    expect(report.warnings.map((w) => w.problem)).toEqual(["default_view_amount_hidden"]);
  });
});

describe("schema and verdict", () => {
  const state = (schema) => ({ schema, identity: "public", expanded: tokenise(["5 TRY"]), visible: tokenise(["5 TRY"]) });

  it("refuses to compare runs recorded with different schemas", () => {
    const report = compareRuns({ a: state("bilun-numbers-parity/1") }, { a: state(SCHEMA) });
    expect(report.failures).toEqual([{ key: "a", problem: "schema_differs", before: "bilun-numbers-parity/1", after: SCHEMA }]);
  });

  it("says 'no number changed' only when there is nothing left to review", () => {
    expect(verdict({ ok: true, failures: [], warnings: [], unusedAllow: [] })).toEqual({ exitCode: 0, line: "PARITY OK: no number changed" });
    const warned = verdict({ ok: true, failures: [], warnings: [{}], unusedAllow: [] });
    expect(warned.exitCode).toBe(0);
    expect(warned.line).toMatch(/^PARITY OK WITH 1 WARNING:/);
    expect(warned.line).toMatch(/not proof that no number changed/);
    expect(verdict({ ok: false, failures: [{}], warnings: [], unusedAllow: [] })).toEqual({ exitCode: 1, line: "PARITY FAILED" });
  });

  it("describes items with their before and after", () => {
    expect(describeItem({ key: "k", problem: "zero_amount_added", kind: "zeroAmounts", value: "total", before: 2, after: 3 })).toBe("k  zero_amount_added  zeroAmounts total (2 -> 3)");
    expect(describeItem({ key: "k", problem: "state_new_in_candidate" })).toBe("k  state_new_in_candidate");
    expect(describeItem({ key: "k", problem: "label_amount_changed", kind: "labelled", value: "L", before: ["1"], after: ["2"] })).toBe("k  label_amount_changed  labelled L ([1] -> [2])");
  });
});
