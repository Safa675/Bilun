// Pure helpers for the numbers-parity mode of capture-screens.mjs.
// No browser, no file system, no clock: the same text always gives the same
// output, so a PR can prove "no number changed" by comparing two runs.

export const SCHEMA = "bilun-numbers-parity/1";

// EN: "29,039.29 TRY" (fmtTRY/fmtTRY2 in lib/i18n/formatters.ts) and backend
// prose such as "9000.00 TRY". The sign is "-" or the real minus sign.
const MONEY_EN = /(?<![\w.,])([-−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?TRY\b/g;
// TR: "₺29.039,29" (same formatters).
const MONEY_TR = /₺\s?([-−]?)(\d{1,3}(?:\.\d{3})+|\d+)(,\d+)?/g;
// TR backend prose keeps the English number and moves the symbol: "9000.00 ₺".
const MONEY_TR_POSTFIX = /(?<![\w.,])([-−]?)(\d+)(\.\d+)?\s?₺/g;

// Dates and times are masked: they are not "counts", and Phase 3 changes how
// some of them are shown. SUT section numbers such as 3.1.12 are NOT dates.
const DATE_PATTERNS = [
  /\b[A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}\b/g, // en: Oct 6, 2026
  /\b\d{1,2} [A-Za-zÇĞİÖŞÜçğıöşü]{3,9}\.? \d{4}\b/g, // tr: 6 Eki 2026
  /\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b/g, // ISO date (+ time)
  /\b\d{1,2}\.\d{1,2}\.\d{4}(?:,? \d{1,2}:\d{2}(?::\d{2})?)?\b/g, // tr numeric: 06.10.2026 15:45
  /\b\d{1,2}\/\d{1,2}\/\d{2,4}(?:,? \d{1,2}:\d{2}(?::\d{2})?(?: ?[AP]M)?)?\b/gi, // en numeric: 10/6/26, 3:45 PM
  /\b\d{1,2}:\d{2}(?::\d{2})?(?: ?[AP]M)?\b/gi, // bare time
];

const EDGE_PUNCTUATION = /^[()[\]{}:;,"'“”‘’·•|/\\]+|[()[\]{}:;,"'“”‘’·•|/\\]+$/g;

// Honesty markers: wording that says "not exact / not available". It must stay
// visible when a section is collapsed. Informational vocabulary, per locale.
const MARKER_PATTERNS = {
  partial: /partial exact|kısmi kesin/i,
  unavailable: /\bunavailable\b|kullanılamaz|kullanılamıyor/i,
  cannotCompute: /cannot (?:be )?comput|hesaplanamaz|hesaplanamıyor/i,
};
// Lines of the (stubbed) chat panel are not part of the billing UI.
const MARKER_IGNORE = /temporarily unavailable|Unable to reach the LLM/i;

/** innerText -> trimmed, whitespace-collapsed, non-empty lines (\s also covers NBSP and narrow NBSP). */
export function normaliseLines(raw) {
  return String(raw)
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

function bump(map, key) {
  map[key] = (map[key] ?? 0) + 1;
}

function sortedObject(map) {
  return Object.fromEntries(Object.entries(map).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
}

const sign = (value) => (value ? "-" : "");

/**
 * Multiset summary of one rendered state.
 *   money     canonical decimal string -> occurrences   {"29039.29": 2}
 *   counts    numeric word as displayed -> occurrences   {"50": 3}
 *   percents  numeric word incl. "%" as displayed -> occurrences
 *   markers   honesty-wording kind -> number of lines
 * Only money is canonicalised, so the EN and TR money maps of one state are
 * equal. Counts, percents and markers stay in the displayed locale form and
 * are only compared within one locale.
 */
export function tokenise(lines) {
  const money = {};
  const counts = {};
  const percents = {};
  const markers = {};
  for (const original of lines) {
    let line = original;
    line = line.replace(MONEY_EN, (_m, s, int, dec) => {
      bump(money, `${sign(s)}${int.replace(/,/g, "")}${dec ?? ""}`);
      return " ";
    });
    line = line.replace(MONEY_TR, (_m, s, int, dec) => {
      bump(money, `${sign(s)}${int.replace(/\./g, "")}${dec ? dec.replace(",", ".") : ""}`);
      return " ";
    });
    line = line.replace(MONEY_TR_POSTFIX, (_m, s, int, dec) => {
      bump(money, `${sign(s)}${int}${dec ?? ""}`);
      return " ";
    });
    for (const pattern of DATE_PATTERNS) line = line.replace(pattern, " ");
    for (const word of line.split(/\s+/)) {
      const w = word.replace(EDGE_PUNCTUATION, "").replace(/−/g, "-");
      if (/^[-+]?\d+(?:[.,]\d+)*%$/.test(w)) bump(percents, w);
      else if (/^[-+]?\d+(?:[.,]\d+)*$/.test(w)) bump(counts, w);
    }
    if (!MARKER_IGNORE.test(original)) {
      for (const [kind, pattern] of Object.entries(MARKER_PATTERNS)) {
        if (pattern.test(original)) bump(markers, kind);
      }
    }
  }
  return {
    money: sortedObject(money),
    counts: sortedObject(counts),
    percents: sortedObject(percents),
    markers: sortedObject(markers),
  };
}

const VALUE_KINDS = ["money", "counts", "percents"];

/**
 * Compare two tokenised snapshots.
 *   missing       a value of the baseline that is gone            -> failure
 *   added         a value that was not in the baseline            -> failure
 *   multiplicity  same value, different number of occurrences     -> warning
 *                 (a restructured page may repeat or merge a figure)
 *                 or a failure with { strictMultiplicity: true }
 */
export function compareSnapshots(before, after, { strictMultiplicity = false } = {}) {
  const diff = { missing: [], added: [], multiplicity: [] };
  for (const kind of VALUE_KINDS) {
    const a = before?.[kind] ?? {};
    const b = after?.[kind] ?? {};
    for (const value of Object.keys(a)) {
      if (!(value in b)) diff.missing.push({ kind, value, before: a[value] });
      else if (a[value] !== b[value]) diff.multiplicity.push({ kind, value, before: a[value], after: b[value] });
    }
    for (const value of Object.keys(b)) {
      if (!(value in a)) diff.added.push({ kind, value, after: b[value] });
    }
  }
  diff.ok = diff.missing.length === 0 && diff.added.length === 0 && (!strictMultiplicity || diff.multiplicity.length === 0);
  return diff;
}

/** Marker kinds that were visible in the baseline default view and are not any more. */
export function hiddenMarkers(baselineVisible, candidateVisible) {
  const before = baselineVisible?.markers ?? {};
  const after = candidateVisible?.markers ?? {};
  return Object.keys(before).filter((kind) => before[kind] > 0 && !(after[kind] > 0));
}

/**
 * Compare two runs. `baseline` and `candidate` map a state key
 * ("en/1440x900/patient-0003/default") to the parsed numbers JSON of that state.
 * `allow` is { added: [{key, kind, value, reason}], removed: [...] }: explicit,
 * reasoned exceptions (new UI copy such as "Top 3 actions"). Unused entries are
 * reported so stale exceptions do not accumulate.
 */
export function compareRuns(baseline, candidate, { strictMultiplicity = false, allow = {} } = {}) {
  const failures = [];
  const warnings = [];
  const allowed = { added: [...(allow.added ?? [])], removed: [...(allow.removed ?? [])] };
  const take = (list, key, item) => {
    const index = list.findIndex((entry) => entry.key === key && entry.kind === item.kind && entry.value === item.value);
    if (index < 0) return false;
    list.splice(index, 1);
    return true;
  };
  for (const key of Object.keys(baseline).sort()) {
    const before = baseline[key];
    const after = candidate[key];
    if (!after) {
      failures.push({ key, problem: "state_missing_in_candidate" });
      continue;
    }
    if (before.identity !== after.identity) {
      failures.push({ key, problem: "identity_differs", before: before.identity, after: after.identity });
    }
    const diff = compareSnapshots(before.expanded, after.expanded, { strictMultiplicity });
    for (const item of diff.missing) if (!take(allowed.removed, key, item)) failures.push({ key, problem: "value_missing", ...item });
    for (const item of diff.added) if (!take(allowed.added, key, item)) failures.push({ key, problem: "value_added", ...item });
    for (const item of diff.multiplicity) {
      (strictMultiplicity ? failures : warnings).push({ key, problem: "multiplicity_changed", ...item });
    }
    for (const kind of hiddenMarkers(before.visible, after.visible)) {
      failures.push({ key, problem: "marker_hidden_in_default_view", kind });
    }
  }
  for (const key of Object.keys(candidate).sort()) {
    if (!baseline[key]) warnings.push({ key, problem: "state_new_in_candidate" });
  }
  const unusedAllow = [
    ...allowed.added.map((entry) => ({ list: "added", ...entry })),
    ...allowed.removed.map((entry) => ({ list: "removed", ...entry })),
  ];
  return { ok: failures.length === 0, failures, warnings, unusedAllow };
}
