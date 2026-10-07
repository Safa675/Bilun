// Pure helpers for the numbers-parity mode of capture-screens.mjs.
// No browser, no file system, no clock: the same text always gives the same
// output, so a PR can prove "no number changed" by comparing two runs.
//
// What a passing compare does and does not prove (read before trusting it):
//   - every money amount, count and percent of the EXPANDED page is present with
//     the same value (multiplicity differences are warnings, see below);
//   - zero amounts did not become more numerous and lone "-" placeholders did
//     not disappear, so a missing amount cannot silently turn into "0.00 TRY";
//   - a standalone amount still sits under the same label, compared without
//     case (a swap of two amounts between two labels fails, also when the labels
//     were re-cased); amounts inside table rows or prose are not tied to a label,
//     and a label that is RENAMED is only a warning ("label_not_in_candidate"):
//     its amounts are then not checked against a label, so a person must look;
//   - honesty wording (partial, unavailable, not evaluated, missing inputs,
//     amount unverified, cannot compute, unverified, estimated, manual review,
//     no value inferred, mismatch, not exact, more findings available) did not
//     lose a line in the default view. The vocabulary is a list of words taken
//     from messages/en and messages/tr (numbers-parity.test.mjs reads the real
//     strings), not a judgement of meaning: a line worded differently is not
//     protected until its words are added here.
// It does NOT judge layout, wording quality or amounts that were never
// captured (states not in the baseline). Screenshots stay the evidence for those.

export const SCHEMA = "bilun-numbers-parity/3";

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

/**
 * Case folding that survives CSS "text-transform: uppercase" in Turkish.
 * innerText returns the uppercased text, and JS regex /i does not fold the
 * Turkish dotted/dotless i ("KISMİ KESİN" would not match /kısmi kesin/i).
 * So: İ and ı become plain i first, then ordinary lower-casing. Every marker
 * pattern below is written against folded text: no "ı" and no "İ" in them.
 */
export function foldText(text) {
  return String(text).normalize("NFC").replace(/[İı]/g, "i").toLowerCase();
}

/** Key of a label for matching: folded case, one space. "TOTAL BILLED" and "Total billed" are the same label. */
export function foldLabel(text) {
  return foldText(text).replace(/\s+/g, " ").trim();
}

// Honesty markers: wording that says "not exact / not available / not computed".
// It must stay visible when a section is collapsed. Informational vocabulary,
// per locale (EN and TR), taken from messages/en and messages/tr.
const MARKER_PATTERNS = {
  partial: /\bpartial\b|\bkismi\b/,
  unavailable: /\bunavailable\b|\bkullanilam/,
  cannotCompute: /cannot (?:be )?(?:comput|evaluat)|\bhesaplanam|değerlendirem/,
  notEvaluated: /not evaluated|değerlendirilmedi|değerlendirilemedi/,
  missingInputs: /missing (?:exact )?inputs?|eksik (?:kesin )?girdi|required inputs? missing/,
  amountUnverified: /amount unverified|tutar doğrulanmadi/,
  // "could not be verified", "verification is required", "No verified source" and their Turkish twins
  unverified:
    /could not be verified|(?<!amount )\bunverified\b|\bnot verified\b|no verified source|cannot be (?:confirmed|verified)|verification (?:is )?required|requires (?:review|verification)|doğrulanama|(?<!tutar )doğrulanmad|doğrulanmamiş|doğrulanmal|doğrulamasi gerekli|doğrulanmiş kaynak yok|incelenmeli/,
  // a figure that is an estimate, not a computed amount ("is estimated from the EK-3 list price ceiling")
  estimated: /\bestimat(?:e|es|ed|ion)\b|tahmin/,
  // the engine hands the decision to a person ("manual SUT review is required")
  manualReview: /\bmanual(?:ly)?\b|\bmanuel/,
  // "no financial value is inferred": the line says why no amount is shown
  notInferred: /\binferred\b|çikarilmad/,
  // a condition check that did not match or could not pick a route
  mismatch: /no diagnosis[–-]drug match|does not match|eşleşmesi bulunamad|uyuşmuyor|\bambiguous\b|belirsiz/,
  notExact: /\bnot exact|exact to the cent|kesin değil/,
  // the list on screen is a page of a longer list
  incompleteList: /more findings are available|daha fazla bulgu var/,
};
// Lines of the (stubbed) chat panel are not part of the billing UI.
const MARKER_IGNORE = /temporarily unavailable|unable to reach the llm/;

// A lone dash on its own line is how the UI renders a missing value (null
// money, null date). Dashes inside prose or table rows cannot be told apart.
const PLACEHOLDER_LINE = /^[—–-]$/;

// A label for a standalone amount: a short line with at least one letter.
const LABEL_LINE = /\p{L}/u;
const LABEL_MAX_LENGTH = 80;

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
 *   money        canonical decimal string -> occurrences   {"29039.29": 2}
 *   counts       numeric word as displayed -> occurrences   {"50": 3}
 *   percents     numeric word incl. "%" as displayed -> occurrences
 *   markers      honesty-wording kind -> number of lines
 *   placeholders lone-dash lines -> occurrences             {"dash": 2}
 *   labelled     label line -> {amount -> occurrences} for amounts that stand
 *                alone on the line right under a label (a Stat tile)
 * Only money is canonicalised, so the EN and TR money maps of one state are
 * equal. Counts, percents, markers and labels stay in the displayed locale
 * form and are only compared within one locale.
 */
export function tokenise(lines) {
  const money = {};
  const counts = {};
  const percents = {};
  const markers = {};
  const placeholders = {};
  const labelled = {};
  let previous = null; // { text, hadMoney } of the line above
  for (const original of lines) {
    let line = original;
    const found = [];
    line = line.replace(MONEY_EN, (_m, s, int, dec) => {
      found.push(`${sign(s)}${int.replace(/,/g, "")}${dec ?? ""}`);
      return " ";
    });
    line = line.replace(MONEY_TR, (_m, s, int, dec) => {
      found.push(`${sign(s)}${int.replace(/\./g, "")}${dec ? dec.replace(",", ".") : ""}`);
      return " ";
    });
    line = line.replace(MONEY_TR_POSTFIX, (_m, s, int, dec) => {
      found.push(`${sign(s)}${int}${dec ?? ""}`);
      return " ";
    });
    for (const key of found) bump(money, key);
    if (found.length === 1 && line.trim() === "" && previous && !previous.hadMoney) {
      if (previous.text.length <= LABEL_MAX_LENGTH && LABEL_LINE.test(previous.text)) {
        labelled[previous.text] ??= {};
        bump(labelled[previous.text], found[0]);
      }
    }
    for (const pattern of DATE_PATTERNS) line = line.replace(pattern, " ");
    for (const word of line.split(/\s+/)) {
      const w = word.replace(EDGE_PUNCTUATION, "").replace(/−/g, "-");
      if (/^[-+]?\d+(?:[.,]\d+)*%$/.test(w)) bump(percents, w);
      else if (/^[-+]?\d+(?:[.,]\d+)*$/.test(w)) bump(counts, w);
    }
    const folded = foldText(original);
    if (!MARKER_IGNORE.test(folded)) {
      for (const [kind, pattern] of Object.entries(MARKER_PATTERNS)) {
        if (pattern.test(folded)) bump(markers, kind);
      }
    }
    if (PLACEHOLDER_LINE.test(original)) bump(placeholders, "dash");
    previous = { text: original, hadMoney: found.length > 0 };
  }
  return {
    money: sortedObject(money),
    counts: sortedObject(counts),
    percents: sortedObject(percents),
    markers: sortedObject(markers),
    placeholders: sortedObject(placeholders),
    labelled: Object.fromEntries(
      Object.entries(labelled)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([label, values]) => [label, sortedObject(values)]),
    ),
  };
}

const VALUE_KINDS = ["money", "counts", "percents"];

/** { label -> { amount -> n } } with labels folded; labels that differ only in case or spacing are merged. */
function foldLabels(labelled) {
  const folded = {};
  for (const [label, values] of Object.entries(labelled ?? {})) {
    const key = foldLabel(label);
    folded[key] ??= {};
    for (const [amount, n] of Object.entries(values)) folded[key][amount] = (folded[key][amount] ?? 0) + n;
  }
  return folded;
}

const isZeroAmount = (value) => Number(value) === 0;
const zeroTotal = (snapshot) =>
  Object.entries(snapshot?.money ?? {}).reduce((sum, [value, n]) => (isZeroAmount(value) ? sum + n : sum), 0);

/**
 * Compare two tokenised snapshots (the expanded view of one state).
 *   missing       a value of the baseline that is gone            -> failure
 *   added         a value that was not in the baseline            -> failure
 *   zeroAmount    more zero amounts than before (a missing amount turned into
 *                 "0.00 TRY", or a zero amount was repeated)      -> failure
 *   placeholder   fewer lone "-" placeholder lines than before    -> failure
 *   labelChanged  a label (compared without case) that exists in both runs
 *                 now sits above other amounts (swapped, re-attached) -> failure
 *   labelUnmatched  a baseline label that holds amounts has no label of the
 *                 same text in the candidate (renamed or gone): its amounts
 *                 are not checked against a label                  -> warning
 *   multiplicity  same value, different number of occurrences     -> warning
 *                 (a restructured page may repeat or merge a figure)
 *                 or a failure with { strictMultiplicity: true }
 *   markersReduced  honesty wording lost lines on the page        -> warning
 */
export function compareSnapshots(before, after, { strictMultiplicity = false } = {}) {
  const diff = { missing: [], added: [], multiplicity: [], zeroAmount: [], placeholder: [], labelChanged: [], labelUnmatched: [], markersReduced: [] };
  let zeroRiseOnExistingValue = false;
  for (const kind of VALUE_KINDS) {
    const a = before?.[kind] ?? {};
    const b = after?.[kind] ?? {};
    for (const value of Object.keys(a)) {
      if (!(value in b)) diff.missing.push({ kind, value, before: a[value] });
      else if (a[value] !== b[value]) {
        if (kind === "money" && isZeroAmount(value) && b[value] > a[value]) zeroRiseOnExistingValue = true;
        else diff.multiplicity.push({ kind, value, before: a[value], after: b[value] });
      }
    }
    for (const value of Object.keys(b)) {
      if (!(value in a)) diff.added.push({ kind, value, after: b[value] });
    }
  }
  if (zeroRiseOnExistingValue) {
    diff.zeroAmount.push({ kind: "zeroAmounts", value: "total", before: zeroTotal(before), after: zeroTotal(after) });
  }
  const placeholdersBefore = before?.placeholders ?? {};
  const placeholdersAfter = after?.placeholders ?? {};
  for (const value of Object.keys(placeholdersBefore)) {
    const now = placeholdersAfter[value] ?? 0;
    if (now < placeholdersBefore[value]) diff.placeholder.push({ kind: "placeholders", value, before: placeholdersBefore[value], after: now });
  }
  const labelsBefore = foldLabels(before?.labelled);
  const labelsAfter = foldLabels(after?.labelled);
  for (const label of Object.keys(labelsBefore)) {
    if (!(label in labelsAfter)) {
      diff.labelUnmatched.push({ kind: "labelled", value: label, before: Object.keys(labelsBefore[label]).sort() });
      continue;
    }
    const was = Object.keys(labelsBefore[label]).sort();
    const now = Object.keys(labelsAfter[label]).sort();
    if (was.join("|") !== now.join("|")) diff.labelChanged.push({ kind: "labelled", value: label, before: was, after: now });
  }
  const markersBefore = before?.markers ?? {};
  const markersAfter = after?.markers ?? {};
  for (const kind of Object.keys(markersBefore)) {
    const now = markersAfter[kind] ?? 0;
    if (now < markersBefore[kind]) diff.markersReduced.push({ kind: "markers", value: kind, before: markersBefore[kind], after: now });
  }
  diff.ok =
    diff.missing.length === 0 &&
    diff.added.length === 0 &&
    diff.zeroAmount.length === 0 &&
    diff.placeholder.length === 0 &&
    diff.labelChanged.length === 0 &&
    (!strictMultiplicity || diff.multiplicity.length === 0);
  return diff;
}

/**
 * Marker kinds that lost lines in the default view (what a user sees before
 * expanding anything). { kind, before, after, hidden }: `hidden` is true when
 * the kind went from visible to not visible at all. Counting lines, not kinds:
 * collapsing two of three "Not evaluated" lines is reported.
 */
export function reducedMarkers(baselineVisible, candidateVisible) {
  const before = baselineVisible?.markers ?? {};
  const after = candidateVisible?.markers ?? {};
  return Object.keys(before)
    .filter((kind) => before[kind] > 0 && (after[kind] ?? 0) < before[kind])
    .map((kind) => ({ kind, before: before[kind], after: after[kind] ?? 0, hidden: !(after[kind] > 0) }));
}

/** Marker kinds that were visible in the baseline default view and are not visible at all any more. */
export function hiddenMarkers(baselineVisible, candidateVisible) {
  return reducedMarkers(baselineVisible, candidateVisible)
    .filter((item) => item.hidden)
    .map((item) => item.kind);
}

/** Amounts shown in the baseline default view that are not shown in the candidate default view. */
export function hiddenAmounts(baselineVisible, candidateVisible) {
  const before = baselineVisible?.money ?? {};
  const after = candidateVisible?.money ?? {};
  return Object.keys(before).filter((value) => !(value in after));
}

/**
 * Compare two runs. `baseline` and `candidate` map a state key
 * ("en/1440x900/patient-0003/default") to the parsed numbers JSON of that state.
 * `allow` is { added: [{key, kind, value, reason}], removed: [...] }: explicit,
 * reasoned exceptions (new UI copy such as "Top 3 actions"). An entry waives the
 * failure with the same key, kind and value; `kind` is money / counts /
 * percents for values, "zeroAmounts" (value "total"), "placeholders" (value
 * "dash"), "labelled" (value: the label, any case) or "markers" (value: the marker kind,
 * for a reduction in the default view). Unused entries are reported so stale
 * exceptions do not accumulate.
 */
export function compareRuns(baseline, candidate, { strictMultiplicity = false, allow = {} } = {}) {
  const failures = [];
  const warnings = [];
  const allowed = { added: [...(allow.added ?? [])], removed: [...(allow.removed ?? [])] };
  const take = (list, key, item) => {
    const sameValue = (entry) => (item.kind === "labelled" ? foldLabel(entry.value) === item.value : entry.value === item.value);
    const index = list.findIndex((entry) => entry.key === key && entry.kind === item.kind && sameValue(entry));
    if (index < 0) return false;
    list.splice(index, 1);
    return true;
  };
  const takeEither = (key, item) => take(allowed.added, key, item) || take(allowed.removed, key, item);
  for (const key of Object.keys(baseline).sort()) {
    const before = baseline[key];
    const after = candidate[key];
    if (!after) {
      failures.push({ key, problem: "state_missing_in_candidate" });
      continue;
    }
    if (before.schema !== after.schema) {
      failures.push({ key, problem: "schema_differs", before: before.schema, after: after.schema });
      continue;
    }
    if (before.identity !== after.identity) {
      failures.push({ key, problem: "identity_differs", before: before.identity, after: after.identity });
    }
    const diff = compareSnapshots(before.expanded, after.expanded, { strictMultiplicity });
    for (const item of diff.missing) if (!take(allowed.removed, key, item)) failures.push({ key, problem: "value_missing", ...item });
    for (const item of diff.added) if (!take(allowed.added, key, item)) failures.push({ key, problem: "value_added", ...item });
    for (const item of diff.zeroAmount) if (!takeEither(key, item)) failures.push({ key, problem: "zero_amount_added", ...item });
    for (const item of diff.placeholder) if (!takeEither(key, item)) failures.push({ key, problem: "placeholder_removed", ...item });
    for (const item of diff.labelChanged) if (!takeEither(key, item)) failures.push({ key, problem: "label_amount_changed", ...item });
    for (const item of diff.multiplicity) {
      (strictMultiplicity ? failures : warnings).push({ key, problem: "multiplicity_changed", ...item });
    }
    for (const item of diff.labelUnmatched) warnings.push({ key, problem: "label_not_in_candidate", ...item });
    for (const item of diff.markersReduced) warnings.push({ key, problem: "marker_lines_removed_from_page", ...item });
    for (const item of reducedMarkers(before.visible, after.visible)) {
      const entry = { kind: "markers", value: item.kind, before: item.before, after: item.after };
      if (!takeEither(key, entry)) {
        failures.push({ key, problem: item.hidden ? "marker_hidden_in_default_view" : "marker_reduced_in_default_view", ...entry });
      }
    }
    for (const value of hiddenAmounts(before.visible, after.visible)) {
      if (value in (after.expanded?.money ?? {})) warnings.push({ key, problem: "default_view_amount_hidden", kind: "money", value });
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

const show = (value) => (Array.isArray(value) ? `[${value.join(", ")}]` : String(value));

/** One report line for a failure or warning item (pure, used by the CLI). */
export function describeItem(item) {
  const detail = item.before !== undefined || item.after !== undefined ? ` (${show(item.before ?? "-")} -> ${show(item.after ?? "-")})` : "";
  return `${item.key}  ${item.problem}  ${item.kind ?? ""} ${item.value ?? ""}${detail}`.replace(/\s+\(/, " (").trimEnd();
}

/**
 * The last line of a compare and its exit code. "no number changed" is only
 * claimed when there is nothing left to review: a warning means a value,
 * a wording line or a default-view amount moved and a person must look.
 */
export function verdict(report) {
  if (!report.ok) return { exitCode: 1, line: "PARITY FAILED" };
  if (report.warnings.length) {
    return {
      exitCode: 0,
      line: `PARITY OK WITH ${report.warnings.length} WARNING${report.warnings.length === 1 ? "" : "S"}: no value was added or lost, but something moved. Review every warning above; this is not proof that no number changed.`,
    };
  }
  return { exitCode: 0, line: "PARITY OK: no number changed" };
}
