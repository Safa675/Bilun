# Showcase story proofs (synthetic demo v3, P2 draft)

Scripts behind `plans/data/2026-10-15-showcase-stories-draft.md`. They build each of the 8 showcase bills twice, clean and with its one injected fault, as in-memory claim objects, then run the engine's rules on both.

- `stories.py`: the 8 stories (patients, dates, lines). Corrected on 2026-10-16 after the review `reports/synthetic-data/2026-10-16-v3-drafts-review.md`.
- `harness.py`: builds the claim objects and runs the rules. It prices every EK-2B/EK-2C line from the catalog row in force on its date and every EK-3/F-1 material from the curated list. It names every drug from the EK-4A row in force, which must have an active ingredient in the drug crosswalk. It fails if not exactly one row matches.
- `prove.py`: for each story, checks that the target rule fires on the faulty bill and stays silent on the clean one, and records every other finding on the clean bill (`noise_in_clean`). It ends with a summary and exits 1 unless every target fires and every clean bill carries 0 TL.
- `render.py`: the bill tables (`results/S*_tables.md`).
- `checks.py`: the first draft's side checks, kept as history; its last block reads a scratch folder that no longer exists.
- `results/`: the output of the last run (2026-10-16). Engine code at `257d1e89` (`main`; `src/` unchanged), with the EK-3/F-1 curated list rebuilt on this branch so the bone cement AP3220 exists.

They read only the synthetic catalogs and the engine. Run them from the repo root with the project's virtualenv: `.venv/bin/python reports/synthetic-data/2026-10-15-showcase-proofs/prove.py`, then `render.py`.

**Golden clean and faulty bills (P2, P3).** `export_clean_lines.py` builds both the clean (`STORIES[sid]("clean")`) and faulty (`STORIES[sid]("faulty")`) variants of each story (it does not run the engine) and writes their line identities to `tests/fixtures/pathways/golden/S1.json` … `S8.json` and `tests/fixtures/pathways/golden_faulty/S1.json` … `S8.json` (`format_version` 1): codes, dates, quantities, specialties, material links, flag values and drug units, with a `billed_ratio` instead of any price, amount, name or id. The care pathways in `data/synthetic/pathways/` must reproduce the clean files line for line, and the P3 fault mutations (plus S1's itemized sibling pathway) must reproduce the faulty files line for line. `--write` (the default) rewrites both directories; `--check` compares a fresh export with the committed files in both directories and exits 1 on any difference or missing file. `tests/unit/synthetic/test_pathways_golden.py` runs `--check` in a subprocess (`test_the_golden_files_equal_a_fresh_export_of_the_stories`), so a golden that differs from `stories.py`, or a pathway and its golden changed together, fails the test run; the same file checks that both sets of golden files are well-formed and differ per story.

**Status on 2026-10-16.** Every target fault fires and every clean bill carries 0 TL.
- The first run (2026-10-15, engine at `1c22ee9c`) recorded 13 kinds of noise on clean bills (N1–N13 in the draft). PRs #272–#278, #283–#285 and #288 closed all of them except N7.
- N7 is still open: an R-code principal diagnosis is blocked as an error. It shows on S7 as one 0 TL row.
