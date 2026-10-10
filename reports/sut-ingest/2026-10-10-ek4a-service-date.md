# EK-4A by service date (2026-10-10)

**Outcome:** runtime readers now take the EK-4A drug list that applied on the claim's service date. Before this work they read one snapshot, `data/gazette/curated/ek4a_drugs.parquet`. That snapshot is the list in force from 2026-05-23 to 2026-06-28 (see `2026-10-05-ek4a-ingest-review.md`). The deferral recorded there is resolved.

## Pull requests

| PR | Step |
|---|---|
| #207 | The scheduled SUT Monitor only opens issues: one per new SUT package, EK-4A announcement or billing notice (`scripts/sut/sgk_watch.py`). |
| #208 | A list with marker-dated rows is admitted as a snapshot only with an explicit `--as-of`. The wall clock no longer promotes it. |
| #209 | `scripts/sut/catalogs/ek4a_timeline.py`: version windows, and the missing list for 2026-06-29 to 2026-08-28. |
| #219 | `scripts/sut/catalogs/ek4a_history.py`: per-drug spans and version windows (`ek4a_history.parquet`, `ek4a_windows.parquet`). |
| #220 | `src/bilun/domain/materials/ek4a_as_of.py`: `ek4a_as_of(service_date)`. |
| #221 | `drugs.py`, EK-4D and `/api/drugs` read through `ek4a_as_of`. A guard test forbids readers of the snapshot. |
| #222 | `scripts/sut/catalogs/ek4a_announcements.py`: the weekly announcements 2026/34-39 and the extraordinary decision of 2026-09-25. |
| this PR | The history reaches back to the list published on 2022-08-25. |

## How it works

1. **Timeline.**
   - A list's footer `RG-dd/mm/yyyy` is the date from which it applies.
   - A replaced list is kept as `MÜLGA … (Yür. X)`, and X is the day it stopped applying.
   - Each version therefore runs from its RG date until the next version's RG date.
   - Before 2025 the lists sit in `raw/annex=EK-4/` as `EK-4-A`. They are read from `OLDEST_LIST` (2022-08-25) on.
   - Result: 25 versions and one gap, 2025-03-25 to 2025-04-25. The list for that gap is in no package SGK still ships.
2. **History.**
   - Footer clauses date the markers:
     - `(*)` in an entry, activation or passivation cell writes the clause date into that cell. Before 2025, `(*)` could also mark a name.
     - A name marker (`**`, `***`, `****`) makes the row's new values apply from the clause date.
   - Identical consecutive spans are joined.
   - Entry, activation and passivation cells stay as text.
3. **Announcements.**
   - `data/gazette/ek4a_announcements.json` pins each announcement:
     - its number, publication and effective dates;
     - the sentence in the PDF that gives the effective date;
     - the SHA-256 of both files under `raw data/ek4a-duyuru/`;
     - `folded_into_list`, the consolidated list that already includes it.
   - A change lasts until that list. A list that does not include it gets the change applied again from the list's own start.
   - The 2026-10-02 list includes 2026/34-37 but neither the extraordinary decision (effective 2026-09-28) nor 2026/38 (effective 2026-10-02).
4. **Reader.** `ek4a_as_of(date)` returns:
   - `coverage`: `covered`, `before_history` (dates before 2022-08-25, served by the oldest list), `gap` (no drugs) or `unavailable`;
   - each drug's `state` on that date: `not_yet_listed`, `passive` (the latest event is a passivation; a passivation wins a same-day tie), `active` or `undated`;
   - each drug's history `status`.

   Callers must not treat a row as fact unless its status is `ok`.

## Rows that are not facts

| Status | Rows | Cause |
|---|---:|---|
| `unrecognized_marker` | 33 | A star the footer does not define. 27 of these are single-star names in the 2024-05-09 list, whose footer defines `(*)` for entry dates only. |
| `duplicate_kamu_no` | 10 | One kamu_no on two drugs; A19661 (KINERET and BIOSHINE) is one example. |
| `unknown_predecessor` | 3 | The oldest list's name markers: the values before the marker date are unknown. |

## Keeping it current

- **New SUT package.**
  1. Convert it.
  2. The timeline picks it up.
  3. Compare the pending announcements' rows with the new list.
  4. Set `folded_into_list` for every announcement the new list includes.
- **New weekly announcement.**
  1. The SUT Monitor opens an issue (or run `python3 scripts/sut/sgk_watch.py --dry-run`).
  2. Save the PDF and xlsx under `raw data/ek4a-duyuru/<year>-<number>/`.
  3. Add a manifest entry, with the effective date taken from the PDF.
  4. Rebuild.

  A new sheet name, header or note wording stops the build until it is added to `ek4a_announcements.py`.
- **Rebuild:**

  ```bash
  python scripts/sut/build_curated_catalogs.py --annex EK-4A --overwrite
  ```

  This exits 1 by design: the snapshot spec refuses the marker-dated 2026-10-02 list without `--as-of`. The history and windows are still written.

## Known limits

- Lists published before 2022-08-25 are not read. Their layouts and footers change several times and their boundaries overlap, and no claim date needs them.
- A list-marker date earlier than its list's publication is applied from the publication date.
- The SUT Monitor workflow is disabled, because GitHub-hosted runners refuse jobs for this account (a billing or spending-limit issue).
- The synthetic data generator still reads the snapshot catalog. Switching it would regenerate the demo cohort.
